"""Strands-based AP orchestrator (alternative to LangGraph).

Uses Strands Agent with tools when ORCHESTRATOR_TYPE=strands.
Requires strands-ahead package (or strands-agents) and Lambda layer when deployed.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Callable

from core.config import Settings, get_settings
from .base import AgentOrchestrator, OrchestratorResult

_STRANDS_AVAILABLE = False
try:
    from strands import Agent, tool
    from strands.models.openai import OpenAIModel
    _STRANDS_AVAILABLE = True
except ImportError:
    pass


def _create_ap_tools(settings: Settings) -> list:
    """Create Strands tools for AP workflow."""
    if not _STRANDS_AVAILABLE:
        return []

    from core.tools.ap_invoice_tools import extract_invoice

    @tool(description="Extract invoice fields from a document path or image. Use file_path for S3 key like invoices/INV-001.pdf, or image_base64 for uploaded images.")
    def extract_invoice_tool(
        file_path: str = "",
        image_base64: str | None = None,
        image_media_type: str | None = None,
    ) -> str:
        import json
        result = extract_invoice(
            file_path=file_path or "",
            image_base64=image_base64,
            image_media_type=image_media_type,
        )
        return json.dumps(result, default=str)

    return [extract_invoice_tool]


class StrandsOrchestrator(AgentOrchestrator):
    """Strands-based AP assistant. Use when ORCHESTRATOR_TYPE=strands."""

    def __init__(self, settings: Settings | None = None, session_id: str | None = None):
        self.settings = settings or get_settings()
        self._session_id = session_id or ""
        self._agent = None

    def _build_agent(self) -> Any:
        if not _STRANDS_AVAILABLE:
            return None
        api_key = self.settings.openai_api_key
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        model = OpenAIModel(model_id=self.settings.openai_model or "gpt-4o")
        tools = _create_ap_tools(self.settings)
        return Agent(model=model, tools=tools)

    def run_turn(
        self,
        task_input: str,
        conversation_history: list[dict[str, str]],
        session_id: str,
        on_stream_message: Callable[[str, str], None] | None = None,
        **kwargs: Any,
    ) -> OrchestratorResult:
        """Run one turn using Strands Agent."""
        self._session_id = session_id or self._session_id
        user_text = (kwargs.get("user_text") or task_input or "").strip()

        if not _STRANDS_AVAILABLE:
            return OrchestratorResult(
                content="Strands orchestrator requires the strands-ahead package. "
                "Install it or set ORCHESTRATOR_TYPE=langraph to use the LangGraph orchestrator."
            )

        agent = self._build_agent()
        if agent is None:
            return OrchestratorResult(
                content="Failed to build Strands agent. Check OPENAI_API_KEY and ORCHESTRATOR_TYPE=langraph as fallback."
            )

        prompt = user_text
        if conversation_history:
            hist = "\n".join(
                f"{m.get('role', 'user').upper()}: {m.get('content', '')}"
                for m in conversation_history[-6:]
            )
            prompt = f"{hist}\n\nUSER: {user_text}"

        try:
            result = asyncio.run(self._run_agent(agent, prompt, on_stream_message))
            return OrchestratorResult(content=result or "I had nothing to say.")
        except Exception as e:
            return OrchestratorResult(
                content=f"Error running Strands agent: {e}. Try ORCHESTRATOR_TYPE=langraph for the LangGraph orchestrator."
            )

    async def _run_agent(
        self,
        agent: Any,
        prompt: str,
        on_stream_message: Callable[[str, str], None] | None,
    ) -> str:
        collected: list[str] = []
        async for event in agent.stream_async(prompt):
            if "data" in event:
                chunk = event["data"]
                collected.append(chunk)
                if on_stream_message:
                    on_stream_message("stream", chunk)
            if "result" in event:
                res = event["result"]
                # AgentResult: use __str__ which extracts text from message.content
                if res:
                    return str(res) if str(res).strip() else "".join(collected)
        return "".join(collected)
