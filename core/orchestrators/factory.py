"""Factory for the Press Release orchestrator (LangGraph-based)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import Settings

if TYPE_CHECKING:
    from .base import AgentOrchestrator


def get_orchestrator(settings: Settings | None = None, session_id: str | None = None) -> "AgentOrchestrator":
    """Return the Press Release orchestrator (LangGraph with DynamoDB and S3 tools)."""
    from core.config import get_settings
    from .press_release_orchestrator import PressReleaseOrchestrator
    s = settings or get_settings()
    return PressReleaseOrchestrator(settings=s, session_id=session_id)
