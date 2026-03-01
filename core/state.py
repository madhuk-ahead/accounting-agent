"""State schema for AP Invoice Triage + Coding Copilot LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class APInvoiceState(TypedDict, total=False):
    """State passed through the AP triage workflow nodes.
    
    All fields are optional to support incremental updates across nodes.
    """

    # --- Input ---
    invoice_data: dict[str, Any]
    """Extracted invoice fields: vendor_id, vendor_name, invoice_no, amount, 
    line_items, po_reference, date, etc."""

    # --- 3-Way Match (Invoice / PO / Receipt) ---
    po_match_results: dict[str, Any]
    """Match results: po_found, amount_match, line_items_match, receipt_status,
    po_details, receipt_details."""

    # --- Exception flags ---
    flags: list[str]
    """List of exception codes, e.g. 'PO_MISMATCH', 'AMOUNT_MISMATCH',
    'DUPLICATE_INVOICE', 'MISSING_RECEIPT', 'NO_PO'."""

    # --- GL Coding (evidence-first) ---
    gl_coding: dict[str, Any]
    """GL coding: account_code, cost_center, department, rationale.
    rationale MUST cite policy_snippets for audit trail."""

    # --- Output artifacts ---
    output_artifacts: list[str]
    """Paths to generated files: ERP JSON, approval email drafts, etc.
    e.g. ['outputs/erp_packet_123.json', 'outputs/email_draft_123.txt']"""

    # --- Supporting context ---
    policy_snippets: list[str]
    """Relevant policy excerpts used for GL coding rationale."""

    # --- Audit log ---
    audit_log: list[dict[str, Any]]
    """Auditable log entries: node, decision, timestamp, evidence."""
