"""Factory for the configured orchestrator (Strands)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import Settings

if TYPE_CHECKING:
    from .base import AgentOrchestrator

def get_orchestrator(settings: Settings | None = None, session_id: str | None = None) -> "AgentOrchestrator":
    """Return the configured orchestrator instance."""
    from core.config import get_settings
    from .strands_orchestrator import StrandsOrchestrator
    s = settings or get_settings()
    return StrandsOrchestrator(settings=s, session_id=session_id)
