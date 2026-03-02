"""Factory for AP Invoice Triage orchestrator.

ORCHESTRATOR_TYPE: langraph (default) or strands only.
- langraph: LangGraph-based AP Invoice workflow (ap_invoice_orchestrator)
- strands: Strands Agent with AP tools (strands_orchestrator)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import Settings

if TYPE_CHECKING:
    from .base import AgentOrchestrator


def get_orchestrator(settings: Settings | None = None, session_id: str | None = None) -> "AgentOrchestrator":
    """Return orchestrator based on ORCHESTRATOR_TYPE (langraph or strands). Default: langraph."""
    from core.config import get_settings

    s = settings or get_settings()
    orch_type = (s.orchestrator_type or "langraph").lower()
    if orch_type not in ("langraph", "strands"):
        orch_type = "langraph"

    if orch_type == "strands":
        from .strands_orchestrator import StrandsOrchestrator
        return StrandsOrchestrator(settings=s, session_id=session_id)

    from .ap_invoice_orchestrator import APInvoiceOrchestrator
    return APInvoiceOrchestrator(settings=s, session_id=session_id)
