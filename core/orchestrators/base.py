"""Base orchestrator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class OrchestratorResult:
    """Result from a single orchestrator turn."""
    content: str
    raw: Any = None


class AgentOrchestrator(ABC):
    """Abstract agent orchestrator (e.g. Strands)."""

    @abstractmethod
    def run_turn(
        self,
        task_input: str,
        conversation_history: list[dict[str, str]],
        session_id: str,
        on_stream_message: Callable[[str, str], None] | None = None,
        **kwargs: Any,
    ) -> OrchestratorResult:
        """Run one turn and return response content."""
        ...

    def reset(self) -> None:
        """Reset conversation state."""
        pass
