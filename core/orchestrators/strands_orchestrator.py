"""Strands-AHEAD orchestrator with one tool: recall_weather_record (DynamoDB knowledge table)."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from contextlib import contextmanager
from io import StringIO
from typing import Any, Callable

# Import strands (Strands-AHEAD via Lambda layer at /opt/python)
# Use importlib like secunit so layer is resolved consistently in Lambda
Agent = None  # type: ignore
tool = None  # type: ignore

try:
    strands_module = importlib.import_module("strands")
    Agent = getattr(strands_module, "Agent", None)
    tool = getattr(strands_module, "tool", None)
    # Always log where Strands came from so we can confirm layer in CloudWatch
    _src = getattr(strands_module, "__file__", "unknown")
    print(f"[STRANDS_ORCH] Strands loaded from: {_src}", file=sys.stderr)
except Exception as e:
    print(f"[STRANDS_ORCH] Strands import failed (will use fallback): {e}", file=sys.stderr)
    if os.getenv("DEBUG_LAYERS", "false").lower() == "true":
        print(f"[DEBUG] sys.path: {sys.path}", file=sys.stderr)
        layer_path = "/opt/python"
        if os.path.exists(layer_path):
            print(f"[DEBUG] Layer path exists: {layer_path}", file=sys.stderr)
            print(f"[DEBUG] Strands in layer: {os.path.exists(f'{layer_path}/strands')}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

from core.config import Settings, get_settings
from .base import AgentOrchestrator, OrchestratorResult

# System prompt: weather-obsessed, campy; when user asks to recall the weather record, use the tool
AGENT_SYSTEM_PROMPT = """You are a cheerful but annoyingly weather-obsessed assistant. You love talking about the weather, especially dramatic weather events.

When the user asks you to "recall the weather record", "get the weather record", "recall the weather", "fetch the Chicago weather", or similar, you MUST use the recall_weather_record tool and then share that content with them in your own campy, dramatic style.

For any other message, be helpful but steer the conversation back to weather whenever you can. Be a little campy and dramatic. Mention cold fronts, polar vortices, or "what's it like outside" often. Have fun with it."""


@contextmanager
def _suppress_stdout():
    if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
        yield
        return
    old = sys.stdout
    sys.stdout = StringIO()
    try:
        yield
    finally:
        sys.stdout = old


def _create_recall_tool(settings: Settings):
    """Create the single Strands tool: recall from knowledge table."""
    if tool is None:
        return []

    table_name = settings.dynamodb_knowledge_table or os.getenv("DYNAMODB_KNOWLEDGE_TABLE", "")
    region = settings.aws_region or os.getenv("AWS_REGION", "us-east-1")

    @tool(
        description="Recall the stored weather record (Chicago polar vortex). Use this when the user asks to recall, fetch, or get the weather record.",
        context=False,
    )
    def recall_weather_record() -> dict[str, Any]:
        """Fetch the single weather record from the knowledge table."""
        try:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=region)
            table = dynamodb.Table(table_name)
            resp = table.get_item(Key={"id": "polar-vortex-chicago"})
            item = resp.get("Item") or {}
            return {
                "title": item.get("title", "Weather Record"),
                "content": item.get("content", "No weather record found. Run scripts/seed_knowledge.py after deploy."),
                "id": item.get("id", "polar-vortex-chicago"),
            }
        except Exception as e:
            return {"error": str(e), "content": "Failed to load weather record."}

    return [recall_weather_record]


class StrandsOrchestrator(AgentOrchestrator):
    """Strands-AHEAD orchestrator with one tool (recall_weather_record) and weather-focused prompt."""

    def __init__(self, settings: Settings | None = None, session_id: str | None = None):
        self.settings = settings or get_settings()
        self._session_id = session_id
        self._agent = None
        self._stream_callback: Callable[[str, str], None] | None = None
        self._current_session_id = session_id
        self._strands_available = Agent is not None and tool is not None

    def _build_agent(self) -> Any:
        """Build Strands Agent with recall tool and system prompt."""
        if Agent is None:
            raise ImportError("strands package not available (install strands-agents or use Lambda layer)")
        tools = _create_recall_tool(self.settings)
        if not tools:
            raise RuntimeError("No tools created (strands.tool not available)")
        model_config = None
        try:
            from strands.models.openai import OpenAIModel
            if self.settings.openai_api_key:
                os.environ["OPENAI_API_KEY"] = self.settings.openai_api_key
            model_config = OpenAIModel(model_id=self.settings.openai_model)
        except (ImportError, AttributeError):
            model_config = f"openai/{self.settings.openai_model}"
        return Agent(
            model=model_config,
            tools=tools,
            system_prompt=AGENT_SYSTEM_PROMPT,
        )

    def _extract_text_from_event(self, event: Any) -> str:
        if hasattr(event, "message"):
            msg = event.message
            if isinstance(msg, dict) and "content" in msg:
                c = msg["content"]
                if isinstance(c, list):
                    return " ".join(
                        str(x.get("text", x)) if isinstance(x, dict) else str(x)
                        for x in c
                    )
                if isinstance(c, str):
                    return c
            if isinstance(msg, str):
                return msg
        if hasattr(event, "final_text") and event.final_text:
            return str(event.final_text) if isinstance(event.final_text, str) else ""
        if hasattr(event, "text") and event.text:
            return str(event.text)
        if isinstance(event, dict):
            if "data" in event:
                data = event["data"]
                if isinstance(data, str):
                    return data
                if isinstance(data, dict) and "text" in data:
                    return str(data["text"])
            if "text" in event and isinstance(event["text"], str):
                return event["text"]
            if "message" in event and isinstance(event["message"], str):
                return event["message"]
            if "content" in event:
                content = event["content"]
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            return str(item["text"])
                        if isinstance(item, str):
                            return item
            if event.get("role") == "assistant" and "content" in event:
                content = event["content"]
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            return str(item["text"])
                        if isinstance(item, str):
                            return item
        return ""

    async def _run_async_turn(
        self,
        prompt: str,
        on_stream_message: Callable[[str, str], None] | None,
    ) -> str:
        final_text = ""
        collected_events: list[Any] = []
        if self._agent is None:
            self._agent = self._build_agent()
        with _suppress_stdout():
            try:
                async for event in self._agent.stream_async(prompt):
                    collected_events.append(event)
                    if isinstance(event, dict):
                        event_type = event.get("type") or event.get("event_type")
                        if on_stream_message and event_type in ("status", "thinking", "tool_call"):
                            content = event.get("content") or event.get("message")
                            if content and isinstance(content, str):
                                on_stream_message(content, "status")
                    extracted = self._extract_text_from_event(event)
                    if extracted:
                        if isinstance(event, dict) and "data" in event and isinstance(event.get("data"), str):
                            final_text += extracted
                        elif isinstance(event, dict) and event.get("complete", False):
                            final_text = extracted
                        elif len(extracted) > len(final_text):
                            final_text = extracted
            except Exception as exc:
                return f"Error during streaming: {exc}"
        if not final_text and collected_events:
            for ev in reversed(collected_events):
                extracted = self._extract_text_from_event(ev)
                if extracted:
                    final_text = extracted
                    break
        return final_text or "I couldn't generate a response. Try asking me to recall the weather record!"

    def run_turn(
        self,
        task_input: str,
        conversation_history: list[dict[str, str]],
        session_id: str,
        on_stream_message: Callable[[str, str], None] | None = None,
        **kwargs: Any,
    ) -> OrchestratorResult:
        self._stream_callback = on_stream_message
        self._current_session_id = session_id
        if not self._strands_available:
            if on_stream_message:
                on_stream_message("Strands not loaded (use Lambda layer or install strands-agents).", "status")
            return OrchestratorResult(
                content="I'm your weather-obsessed agent! Ask me to *recall the weather record* for the Chicago polar vortex report. (Strands SDK not available in this environment.)",
                raw=None,
            )
        user_message = task_input or ""
        if not user_message and conversation_history:
            for m in reversed(conversation_history):
                if m.get("role") == "user" and m.get("content"):
                    user_message = m["content"] if isinstance(m["content"], str) else str(m.get("content", ""))
                    break
        if not user_message:
            user_message = "Hello!"
        try:
            final_text = asyncio.run(self._run_async_turn(user_message, on_stream_message))
            return OrchestratorResult(content=final_text, raw=None)
        except Exception as e:
            return OrchestratorResult(content=f"Error: {e}", raw=None)

    def reset(self) -> None:
        self._agent = None
        self._stream_callback = None
