"""LangGraph-based AP Invoice Triage + Coding Copilot orchestrator."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable

from core.config import Settings, get_settings
from core.state import APInvoiceState
from .base import AgentOrchestrator, OrchestratorResult

graph = None
try:
    from core.orchestrators.ap_graph import graph
except ImportError:
    pass


class APInvoiceOrchestrator(AgentOrchestrator):
    """24/7 Agentic AP Assistant: Extract -> 3-Way Match -> GL Coding -> Artifact Generation."""

    def __init__(self, settings: Settings | None = None, session_id: str | None = None):
        self.settings = settings or get_settings()
        self._session_id = session_id or ""
        self._graph = graph

    def run_turn(
        self,
        task_input: str,
        conversation_history: list[dict[str, str]],
        session_id: str,
        on_stream_message: Callable[[str, str], None] | None = None,
        **kwargs: Any,
    ) -> OrchestratorResult:
        """Run one AP triage turn. Expects task_input or form_data with file_path or invoice_data."""
        self._session_id = session_id or self._session_id
        form_data = kwargs.get("form_data") or {}
        user_text = (kwargs.get("user_text") or task_input or "").strip()

        # Handle user modification requests (e.g., "change GL code to 6100")
        last_display = form_data.get("last_display_data")
        last_file = form_data.get("last_file_content")
        if last_display and user_text:
            override_result = _apply_user_override(user_text, last_display, last_file)
            if override_result:
                return override_result

        if self._graph is None:
            msg = "AP Invoice graph not loaded (pip install langgraph langchain-openai langchain-core)."
            if on_stream_message:
                on_stream_message(msg, "status")
            return OrchestratorResult(content=msg, raw=None)

        # Build initial state from form_data or task_input
        file_path = form_data.get("file_path") or "invoices/INV-2026-001.txt"
        invoice_hint = form_data.get("invoice_data") or {}
        invoice_file_base64 = form_data.get("invoice_file_base64")
        invoice_file_type = form_data.get("invoice_file_type")
        invoice_pages_base64 = form_data.get("invoice_pages_base64")

        invoice_data = dict(invoice_hint) if invoice_hint else {}
        if "_source" not in invoice_data:
            invoice_data["_source"] = file_path
        if invoice_pages_base64 and isinstance(invoice_pages_base64, list) and len(invoice_pages_base64) > 0:
            invoice_data["_image_pages_base64"] = invoice_pages_base64
        elif invoice_file_base64:
            invoice_data["_image_base64"] = invoice_file_base64
        if invoice_file_type:
            invoice_data["_image_media_type"] = invoice_file_type

        initial_state: APInvoiceState = {
            "invoice_data": invoice_data,
            "flags": [],
            "audit_log": [],
        }

        try:
            result = asyncio.run(self._run_graph(initial_state, on_stream_message))
            return result
        except Exception as e:
            return OrchestratorResult(content=f"Error: {e}", raw=None)

    async def _run_graph(
        self,
        initial_state: APInvoiceState,
        on_stream_message: Callable[[str, str], None] | None,
    ) -> dict:
        """Invoke the compiled graph and format the response."""
        if on_stream_message:
            on_stream_message("Running AP triage workflow...", "status")

        # Rebuild graph with session_id for finalize_packet
        from core.orchestrators.ap_graph import build_workflow
        g = build_workflow(session_id=self._session_id).compile()

        final_state = await g.ainvoke(initial_state)

        reasoning_stages = _get_reasoning_stages(final_state)
        content = _format_response(final_state)
        raw_export = _format_raw_erp_export(final_state)
        display_data = _get_display_data(final_state)
        confirmation_prompt = "Does everything look good? Any changes needed?"

        if on_stream_message:
            on_stream_message(content, "status")

        return OrchestratorResult(
            content=content,
            raw=final_state,
            file_content=raw_export,
            display_data=display_data,
            reasoning_stages=reasoning_stages,
            confirmation_prompt=confirmation_prompt,
        )

    def reset(self) -> None:
        pass


def _apply_user_override(
    user_text: str,
    last_display_data: dict,
    last_file_content: str | None,
) -> OrchestratorResult | None:
    """Parse user modification requests and apply overrides. Returns OrchestratorResult if applied, else None."""
    text_lower = user_text.lower()
    # Match: "change GL code to 6100", "use account 6100", "GL 6100", "change account to 6100"
    gl_match = re.search(
        r"(?:gl(?:\s*code)?|account(?:\s*code)?)\s*(?:to|as|=)?\s*(\d{4,6})",
        user_text,
        re.IGNORECASE,
    )
    if gl_match:
        new_code = gl_match.group(1)
        display = dict(last_display_data)
        coding = display.get("coding_and_routing") or {}
        coding = dict(coding)
        coding["account_code"] = new_code
        coding["rationale"] = (
            (coding.get("rationale") or "")
            + f" [User override: GL code changed to {new_code}]"
        )
        display["coding_and_routing"] = coding

        # Update raw export (file_content) if available
        new_file_content = last_file_content
        if last_file_content:
            try:
                raw = json.loads(last_file_content)
                gl_raw = raw.get("gl_coding") or {}
                gl_raw = dict(gl_raw)
                gl_raw["account_code"] = new_code
                raw["gl_coding"] = gl_raw
                from core.tools import ap_invoice_tools
                new_file_content = ap_invoice_tools._json_dumps_safe(raw, indent=2)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        return OrchestratorResult(
            content=f"Updated GL code to {new_code}.",
            raw=None,
            file_content=new_file_content,
            display_data=_to_json_safe(display),
            reasoning_stages=None,
            confirmation_prompt="Anything else to change?",
        )

    # Cost center override: "change cost center to X", "use cost center MKT-200"
    cc_match = re.search(
        r"cost\s*center\s*(?:to|as|=)?\s*([A-Za-z0-9\-]+)",
        text_lower,
        re.IGNORECASE,
    )
    if cc_match:
        new_cc = cc_match.group(1).strip()
        display = dict(last_display_data)
        coding = display.get("coding_and_routing") or {}
        coding = dict(coding)
        coding["cost_center"] = new_cc
        coding["rationale"] = (
            (coding.get("rationale") or "")
            + f" [User override: cost center changed to {new_cc}]"
        )
        display["coding_and_routing"] = coding

        new_file_content = last_file_content
        if last_file_content:
            try:
                raw = json.loads(last_file_content)
                gl_raw = raw.get("gl_coding") or {}
                gl_raw = dict(gl_raw)
                gl_raw["cost_center"] = new_cc
                raw["gl_coding"] = gl_raw
                from core.tools import ap_invoice_tools
                new_file_content = ap_invoice_tools._json_dumps_safe(raw, indent=2)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        return OrchestratorResult(
            content=f"Updated cost center to {new_cc}.",
            raw=None,
            file_content=new_file_content,
            display_data=_to_json_safe(display),
            reasoning_stages=None,
            confirmation_prompt="Anything else to change?",
        )

    return None


def _format_response(state: dict) -> str:
    """Format a human-readable summary of the triage result."""
    gl = state.get("gl_coding") or {}
    invoice = state.get("invoice_data") or {}
    po_match = state.get("po_match_results") or {}
    flags = state.get("flags", [])
    artifacts = state.get("output_artifacts", [])
    audit = state.get("audit_log", [])

    po = po_match.get("po_details") or {}
    receipt = po_match.get("receipt_details") or {}
    recon = po_match.get("reconciliation") or {}

    lines = [
        "## AP Invoice Triage Result",
        "",
        f"**Vendor:** {invoice.get('vendor_name', 'N/A')}",
        f"**Invoice #:** {invoice.get('invoice_no', 'N/A')} | **Total:** ${invoice.get('amount', invoice.get('total', 'N/A'))}",
        f"**Dates:** {invoice.get('invoice_date', invoice.get('date', 'N/A'))} | Due: {invoice.get('due_date', 'N/A')}",
        f"**Payment terms:** {invoice.get('payment_terms', 'N/A')}",
        f"**Line items:** {len(invoice.get('line_items', []))}",
        f"**Flags:** " + (", ".join(flags) if flags else "None"),
        "",
        "### 3-Way Validation & Reconciliation",
        f"- **PO found:** {po_match.get('po_found', False)} | **2-way match:** {po_match.get('two_way_match', False)} | **3-way match:** {po_match.get('three_way_match', False)}",
        f"- **PO:** {po.get('po_id', 'N/A')} | Amount: ${po.get('amount', 'N/A')}",
        f"- **Receipt:** {receipt.get('receipt_id', 'N/A')} | Received: {receipt.get('received', False)} ({receipt.get('received_date', 'N/A')})",
        f"- **Reconciliation:** {recon.get('match_summary', 'N/A')} (Invoice ${recon.get('invoice_amount', recon.get('invoice_subtotal', '-'))} vs PO ${recon.get('po_amount', '-')})",
        "",
        "### GL Coding & Routing",
        f"- **Account:** {gl.get('account_code', 'N/A')} | **Cost Center:** {gl.get('cost_center', 'N/A')} | **Entity:** {gl.get('entity', 'N/A')}",
        f"- **Approval path:** {gl.get('approval_path', 'N/A')}",
        f"- **Next actions:** {', '.join(gl.get('next_actions', []))}",
        f"- **Rationale:** {gl.get('rationale', 'N/A')}",
        "",
        "### Audit Trail",
    ]
    for entry in audit[-5:]:
        lines.append(f"- [{entry.get('node', '')}] {entry.get('decision', '')}")

    if artifacts:
        lines.extend(["", "### Output Artifacts", *[f"- {a}" for a in artifacts]])

    return "\n".join(lines)


def _get_reasoning_stages(state: dict) -> list[dict]:
    """Build human-readable reasoning stages from audit_log for chat display."""
    audit = state.get("audit_log", [])
    stage_labels = {
        "ingest": ("Extracting key fields from invoice", "Using LLM/vision to parse vendor, dates, amounts, line items."),
        "validate_and_match": ("Fetching PO & Receipt from DynamoDB", "Querying Vendors, PurchaseOrders, Receipts tables for 3-way match."),
        "assign_coding": ("Assigning GL coding from policy", "Applying policy rules for account, cost center, approval path."),
        "finalize_packet": ("Generating ERP export packet", "Building ERP-ready JSON for export."),
        "handle_exceptions": ("Routing for manual review", "Flags detected; prepared for exception handling."),
    }
    stages: list[dict] = []
    for i, entry in enumerate(audit):
        node = entry.get("node", "")
        decision = entry.get("decision", "")
        label, detail = stage_labels.get(node, (node.replace("_", " ").title(), ""))
        if node == "validate_and_match":
            stages.append({
                "step": len(stages) + 1,
                "label": "Fetching PO & Receipt from DynamoDB/S3",
                "detail": "Querying Vendors, PurchaseOrders, Receipts tables.",
            })
            stages.append({
                "step": len(stages) + 1,
                "label": "Validating 3-way match",
                "detail": f"Invoice ↔ PO ↔ Receipt: {decision}",
            })
        else:
            stages.append({
                "step": len(stages) + 1,
                "label": label,
                "detail": detail or decision,
            })
    return stages


def _format_raw_erp_export(state: dict) -> str | None:
    """Return raw ERP export JSON for download."""
    from core.tools import ap_invoice_tools
    raw = ap_invoice_tools.generate_raw_erp_export(state)
    return ap_invoice_tools._json_dumps_safe(raw, indent=2)


def _to_json_safe(val: Any) -> Any:
    """Convert Decimals and other non-JSON types for frontend."""
    from decimal import Decimal
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, list):
        return [_to_json_safe(v) for v in val]
    if isinstance(val, dict):
        return {k: _to_json_safe(v) for k, v in val.items()}
    return val


def _get_display_data(state: dict) -> dict | None:
    """Return structured display data for right panel: extracted fields, PO match, receipt match, coding & rationale."""
    invoice = state.get("invoice_data") or {}
    po_match = state.get("po_match_results") or {}
    gl = state.get("gl_coding") or {}
    po = po_match.get("po_details") or {}
    receipt = po_match.get("receipt_details") or {}

    data = {
        "extracted_invoice": {
            "vendor_name": invoice.get("vendor_name"),
            "invoice_no": invoice.get("invoice_no"),
            "invoice_date": invoice.get("invoice_date", invoice.get("date")),
            "due_date": invoice.get("due_date"),
            "amount": invoice.get("amount", invoice.get("total")),
            "line_items": invoice.get("line_items", []),
            "currency": invoice.get("currency", "USD"),
        },
        "po_match": {
            "found": bool(po_match.get("po_found", False)),
            "po_id": po.get("po_id"),
            "po_amount": po.get("amount"),
            "two_way_match": po_match.get("two_way_match", False),
            "three_way_match": po_match.get("three_way_match", False),
        },
        "receipt_match": {
            "receipt_id": receipt.get("receipt_id"),
            "received": bool(receipt.get("received", False)),
            "received_date": receipt.get("received_date"),
        },
        "coding_and_routing": {
            "account_code": gl.get("account_code"),
            "cost_center": gl.get("cost_center"),
            "entity": gl.get("entity"),
            "approval_path": gl.get("approval_path"),
            "next_actions": gl.get("next_actions", []),
            "rationale": gl.get("rationale"),
        },
        "flags": state.get("flags", []),
    }
    return _to_json_safe(data)
