"""
AP Invoice Triage + Coding Copilot – LangGraph workflow.

Nodes: ingest -> validate_and_match -> assign_coding -> [handle_exceptions | finalize_packet]
Exported as `graph = workflow.compile()` for LangGraph Studio visualization.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from core.state import APInvoiceState
from core.tools import ap_invoice_tools
from core.config import get_settings

# Optional LangGraph imports
StateGraph = None
try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Node: ingest
# ---------------------------------------------------------------------------

def ingest_node(state: APInvoiceState) -> dict:
    """Ingest invoice: extract fields via LLM or mock (text or image)."""
    inv = state.get("invoice_data") or {}
    file_path = inv.get("_source") or "invoices/INV-2026-001.txt"
    image_base64 = inv.get("_image_base64")
    image_media_type = inv.get("_image_media_type")
    image_pages_base64 = inv.get("_image_pages_base64")
    extracted = ap_invoice_tools.extract_invoice(
        file_path=file_path,
        image_base64=image_base64,
        image_media_type=image_media_type,
        image_pages_base64=image_pages_base64,
    )
    if "error" in extracted:
        return {
            "invoice_data": extracted,
            "flags": list(state.get("flags", [])) + ["EXTRACTION_ERROR"],
            "audit_log": list(state.get("audit_log", [])) + [{
                "node": "ingest",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "decision": "extraction_failed",
                "evidence": extracted,
            }],
        }
    return {
        "invoice_data": extracted,
        "audit_log": list(state.get("audit_log", [])) + [{
            "node": "ingest",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "decision": "extracted",
            "evidence": {"invoice_no": extracted.get("invoice_no"), "amount": extracted.get("amount")},
        }],
    }


# ---------------------------------------------------------------------------
# Node: validate_and_match
# ---------------------------------------------------------------------------

def validate_and_match_node(state: APInvoiceState) -> dict:
    """3-way match: Invoice / PO / Receipt. Check duplicates. Populate flags."""
    invoice = state.get("invoice_data") or {}
    vendor_id = invoice.get("vendor_id", "vendor:techsupply")
    po_ref = invoice.get("po_reference") or invoice.get("invoice_no", "").replace("INV-", "PO-")
    invoice_no = invoice.get("invoice_no", "")
    invoice_amount = invoice.get("amount") or invoice.get("total") or 0

    flags: list[str] = list(state.get("flags", []))

    # 1. Check duplicates
    dup_result = ap_invoice_tools.check_duplicates(invoice_no, vendor_id)
    if dup_result.get("duplicate"):
        flags.append("DUPLICATE_INVOICE")

    # 2. Query ERP (Vendors, POs, Receipts)
    erp = ap_invoice_tools.query_mock_erp(vendor_id, po_ref)
    vendor = erp.get("vendor") or {}
    po = erp.get("po") or {}
    receipt = erp.get("receipt") or {}

    po_found = bool(po)
    # No PO → no meaningful receipt match; ignore any mock/fallback receipt data
    if not po_found:
        receipt = {}
    po_amount = po.get("amount") or 0
    amount_match = abs(float(invoice_amount) - float(po_amount)) < 0.01 if po_found else False
    line_items_match = True  # Simplified for demo
    receipt_received = receipt.get("received", False) if receipt else False

    # 2-way match: Invoice vs PO (amount, line items) – compute before flags
    invoice_subtotal = invoice.get("subtotal") or invoice_amount
    two_way_amount_ok = abs(float(invoice_subtotal or 0) - float(po_amount)) < 0.01 if po_found else False

    if not po_found:
        flags.append("NO_PO")
    elif not two_way_amount_ok:
        flags.append("AMOUNT_MISMATCH")
    elif not line_items_match:
        flags.append("PO_MISMATCH")
    if not receipt_received and po_found:
        flags.append("MISSING_RECEIPT")
    two_way_match = po_found and (amount_match or two_way_amount_ok) and line_items_match
    # 3-way match: Invoice + PO + Receipt
    three_way_match = two_way_match and receipt_received

    po_match_results = {
        "po_found": po_found,
        "amount_match": amount_match,
        "two_way_amount_match": two_way_amount_ok,
        "line_items_match": line_items_match,
        "receipt_status": "received" if receipt_received else "pending",
        "two_way_match": two_way_match,
        "three_way_match": three_way_match,
        "po_details": po,
        "receipt_details": receipt,
        "vendor_details": vendor,
        "reconciliation": {
            "invoice_amount": float(invoice_amount or 0),
            "invoice_subtotal": float(invoice_subtotal or 0),
            "po_amount": float(po_amount or 0),
            "match_summary": "3-way match OK" if three_way_match else ("2-way match OK" if two_way_match else "Match failed"),
        },
    }

    return {
        "po_match_results": po_match_results,
        "flags": flags,
        "audit_log": list(state.get("audit_log", [])) + [{
            "node": "validate_and_match",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "decision": "3_way_match",
            "evidence": {"flags": flags, "three_way_match": three_way_match, "po_details": po, "receipt_details": receipt},
        }],
    }


# ---------------------------------------------------------------------------
# Node: assign_coding (Evidence-First: rationale MUST cite policy_snippets)
# ---------------------------------------------------------------------------

def _load_policy_snippets() -> list[str]:
    """Load policy snippets from S3 policies/ or return defaults."""
    settings = get_settings()
    bucket = getattr(settings, "s3_ap_bucket", None) or os.getenv("S3_AP_BUCKET", "")
    if bucket:
        try:
            import boto3
            client = boto3.client("s3", region_name=settings.aws_region or "us-east-1")
            resp = client.get_object(Bucket=bucket, Key="policies/gl_coding_policy.md")
            content = resp["Body"].read().decode("utf-8", errors="replace")
            return [content[:2000]]  # First 2k chars
        except Exception:
            pass
    return [
        "Policy 4.1: IT equipment and software under $5k → GL 6105, cost center IT-100.",
        "Policy 4.2: Vendor TechSupply Inc. is pre-approved IT provider; default GL 6105.",
        "Policy 4.3: Amounts over $10k require additional approval; under $5k auto-code.",
    ]


def assign_coding_node(state: APInvoiceState) -> dict:
    """Assign GL coding with evidence-first rationale citing policy_snippets."""
    invoice = state.get("invoice_data") or {}
    po_match = state.get("po_match_results") or {}
    vendor = po_match.get("vendor_details") or {}
    flags = state.get("flags", [])

    policy_snippets = state.get("policy_snippets") or _load_policy_snippets()

    # Use vendor defaults when available
    account_code = vendor.get("default_gl_code") or "6105"
    cost_center = vendor.get("default_cost_center") or "IT-100"
    department = "IT"
    amount = float(invoice.get("amount") or invoice.get("total") or 0)
    vendor_name = invoice.get("vendor_name") or "vendor"

    # Build rationale citing policy
    rationale_parts = [
        f"Coded to GL {account_code} because the vendor is an IT provider",
        f"and the amount (${amount}) is under the $5k threshold per Policy 4.1.",
        f"Vendor {vendor_name} uses default GL {account_code} per Policy 4.2.",
    ]
    rationale = " ".join(rationale_parts)

    # Coding & routing: entity, approval path, next actions
    entity = vendor.get("entity") or "Corp"
    if amount <= 5000:
        approval_path = "Auto-approve (under $5k per Policy 4.1)"
        next_actions = ["Submit for payment", "Route to AP for processing"]
    elif amount <= 10000:
        approval_path = "Manager approval required ($5k–$10k per Policy 4.3)"
        next_actions = ["Route to manager for approval", "Hold until approved"]
    else:
        approval_path = "VP approval required (over $10k per Policy 4.3)"
        next_actions = ["Escalate to VP", "Hold until approved"]

    gl_coding = {
        "account_code": account_code,
        "cost_center": cost_center,
        "department": department,
        "entity": entity,
        "approval_path": approval_path,
        "next_actions": next_actions,
        "rationale": rationale,
    }

    return {
        "gl_coding": gl_coding,
        "policy_snippets": policy_snippets,
        "audit_log": list(state.get("audit_log", [])) + [{
            "node": "assign_coding",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "decision": "gl_assigned",
            "evidence": {"gl_coding": gl_coding, "policy_cited": "4.1, 4.2"},
        }],
    }


# ---------------------------------------------------------------------------
# Node: handle_exceptions
# ---------------------------------------------------------------------------

def handle_exceptions_node(state: APInvoiceState) -> dict:
    """Handle PO mismatch, duplicate, or other flags. Log and prepare for manual review."""
    flags = state.get("flags", [])
    return {
        "audit_log": list(state.get("audit_log", [])) + [{
            "node": "handle_exceptions",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "decision": "routed_to_exception_handler",
            "evidence": {"flags": flags},
        }],
        "output_artifacts": list(state.get("output_artifacts", [])),
    }


# ---------------------------------------------------------------------------
# Node: finalize_packet
# ---------------------------------------------------------------------------

def finalize_packet_node(state: APInvoiceState, session_id: str = "") -> dict:
    """Generate ERP-ready JSON and other artifacts."""
    result = ap_invoice_tools.generate_accounting_packet(dict(state), session_id=session_id)
    paths = result.get("output_paths", [])
    return {
        "output_artifacts": list(state.get("output_artifacts", [])) + paths,
        "audit_log": list(state.get("audit_log", [])) + [{
            "node": "finalize_packet",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "decision": "packet_generated",
            "evidence": {"paths": paths},
        }],
    }


# ---------------------------------------------------------------------------
# Routing: assign_coding -> handle_exceptions | finalize_packet
# ---------------------------------------------------------------------------

def route_after_coding(state: APInvoiceState) -> Literal["handle_exceptions", "finalize_packet"]:
    """If PO mismatch or duplicate, route to handle_exceptions; else finalize_packet."""
    flags = state.get("flags", [])
    exception_flags = {"PO_MISMATCH", "AMOUNT_MISMATCH", "DUPLICATE_INVOICE", "NO_PO", "MISSING_RECEIPT"}
    if any(f in exception_flags for f in flags):
        return "handle_exceptions"
    return "finalize_packet"


# ---------------------------------------------------------------------------
# Build workflow and export graph
# ---------------------------------------------------------------------------

def build_workflow(session_id: str = ""):
    """Build the AP Invoice Triage StateGraph. Call .compile() for graph."""
    if StateGraph is None:
        raise ImportError("langgraph not available (pip install langgraph langchain-openai langchain-core)")

    workflow = StateGraph(APInvoiceState)

    workflow.add_node("ingest", ingest_node)
    workflow.add_node("validate_and_match", validate_and_match_node)
    workflow.add_node("assign_coding", assign_coding_node)
    workflow.add_node("handle_exceptions", handle_exceptions_node)
    workflow.add_node(
        "finalize_packet",
        lambda s: finalize_packet_node(s, session_id=session_id),
    )

    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "validate_and_match")
    workflow.add_edge("validate_and_match", "assign_coding")
    workflow.add_conditional_edges("assign_coding", route_after_coding)
    workflow.add_edge("handle_exceptions", END)
    workflow.add_edge("finalize_packet", END)

    return workflow


# Export for LangGraph Studio: graph = workflow.compile()
try:
    if StateGraph is not None:
        graph = build_workflow().compile()
    else:
        graph = None
except Exception:
    graph = None  # LangGraph not installed
