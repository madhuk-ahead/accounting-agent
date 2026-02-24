"""Agent manager: runs the orchestrator (Strands) for chat turns."""

from __future__ import annotations

from typing import Any, Callable
from dataclasses import dataclass

from core.config import Settings, get_settings


@dataclass
class RunResult:
    """Result from agent run."""
    message: str
    buttons: list[Any]
    conversation_id: str


_agent_manager: "AgentManager | None" = None


def get_agent_manager(settings: Settings | None = None) -> "AgentManager":
    """Return singleton agent manager (used by Lambda chat)."""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager(settings or get_settings())
    else:
        if settings is not None:
            _agent_manager.settings = settings
    return _agent_manager


class AgentManager:
    """Runs the orchestrator for each chat turn. Stub until Step 4 wires Strands."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def run(
        self,
        conversation_id: str,
        user_text: str,
        transcript: str = "",
        host_id: Any = None,
        on_stream_message: Callable[[str, str], None] | None = None,
    ) -> RunResult:
        """Run one turn: user message -> orchestrator -> response. Implemented in Step 4 with Strands."""
        # Stub: will be replaced by Strands orchestrator in Step 4
        from core.orchestrators import get_orchestrator
        orchestrator = get_orchestrator(self.settings, session_id=conversation_id)
        result = orchestrator.run_turn(
            task_input=user_text or transcript,
            conversation_history=self._parse_transcript(transcript),
            session_id=conversation_id,
            on_stream_message=on_stream_message,
        )
        return RunResult(
            message=result.content or "I had nothing to say.",
            buttons=[],
            conversation_id=conversation_id,
        )

    def _parse_transcript(self, transcript: str) -> list[dict[str, str]]:
        """Convert transcript string to list of {role, content} for orchestrator."""
        out: list[dict[str, str]] = []
        for line in (transcript or "").strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.upper().startswith("USER:"):
                out.append({"role": "user", "content": line[5:].strip()})
            elif line.upper().startswith("AGENT:"):
                out.append({"role": "assistant", "content": line[6:].strip()})
            else:
                out.append({"role": "user", "content": line})
        return out
