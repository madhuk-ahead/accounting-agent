"""Factory for AP Invoice Triage orchestrator (LangGraph-based)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import Settings

if TYPE_CHECKING:
    from .base import AgentOrchestrator


def get_orchestrator(settings: Settings | None = None, session_id: str | None = None) -> "AgentOrchestrator":
    """Return AP Invoice orchestrator. ORCHESTRATOR_TYPE: langraph or ap (default: ap)."""
    from core.config import get_settings
    from .ap_invoice_orchestrator import APInvoiceOrchestrator
    s = settings or get_settings()
    return APInvoiceOrchestrator(settings=s, session_id=session_id)
