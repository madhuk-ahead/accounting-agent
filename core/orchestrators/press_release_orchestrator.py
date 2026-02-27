"""LangGraph-based Press Release Drafting Assistant with DynamoDB and S3 tools."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable

from core.config import Settings, get_settings
from core.tools import press_release_tools
from .base import AgentOrchestrator, OrchestratorResult

# Optional LangGraph imports
create_react_agent = None
ChatOpenAI = None
try:
    from langgraph.prebuilt import create_react_agent
    from langchain_openai import ChatOpenAI
except ImportError as e:
    import sys
    print(f"[PRESS_RELEASE_ORCH] LangGraph import failed: {e}", file=sys.stderr)

PRESS_RELEASE_SYSTEM_PROMPT = """You are a Press Release Drafting Assistant. Your job is to help users turn rough drafts and key topics into polished, publication-ready press releases across multiple announcement types.

## Your behavior
- ALWAYS use the internal lookup tools (lookup_company_boilerplate, lookup_product_facts, lookup_quotes, lookup_partner_info, lookup_metrics, fetch_press_kit_document) to ground your draft with real facts. Do NOT invent facts, metrics, or quotes.
- If information is missing from the tools, say so explicitly and suggest what to add to the internal sources.
- Tailor the draft to the user's selected **press release type** and **tone**.
- Structure every press release with: headline (required), subhead (optional), dateline, body, quotes, boilerplate, media contact.

## Press release types – tailor content and emphasis accordingly
- **product_launch**: Focus on product features, differentiators, availability. Use lookup_product_facts heavily. Lead with the product name and value proposition.
- **partnership**: Lead with both companies. Use lookup_partner_info for partner details. Emphasize joint benefits, scope of collaboration, timelines.
- **funding**: Lead with round size and use of funds. Use lookup_metrics for growth, traction. Include investor quotes if available; otherwise CEO quote on company vision.
- **award**: Lead with the award name and recipient. Emphasize significance, criteria, and what it means for the company. Use company boilerplate and quotes.
- **event**: Lead with event name, date, location. Include agenda highlights, speakers, how to attend. Use lookup_metrics or product facts if the event features product demos or milestones.
- **executive_hire**: Lead with the executive's name and title. Include background, rationale for hire, quote from CEO or hiring manager. Use lookup_company_boilerplate and lookup_quotes.

## Press release structure (follow this template)
1. **Headline** – Compelling, newsworthy, concise (type-specific)
2. **Subhead** (optional) – Supporting detail or context
3. **Dateline** – ALWAYS call lookup_dateline() to get the real-time date and location. Use the returned "dateline" value (e.g. "San Francisco, CA - February 26, 2026"). Do NOT use [CITY, STATE - Date] placeholders.
4. **Lead paragraph** – Who, what, when, where, why in 1–2 sentences
5. **Body** – Supporting paragraphs with facts from your lookups (tailored to type)
6. **Quotes** – Use approved quotes from lookup_quotes; attribute correctly
7. **Boilerplate** – Use lookup_company_boilerplate
8. **Media contact** – Standard format: Name, Title, Email, Phone

## Tools
- lookup_dateline: Returns current date and location for the dateline (call this first for every press release)
- lookup_company_boilerplate: Company description and boilerplate
- lookup_product_facts: Product features, differentiators (for product_launch, event)
- lookup_quotes: Approved executive quotes (e.g., CEO, CMO)
- lookup_partner_info: Partner blurbs and facts (for partnership)
- lookup_metrics: Metrics, dates, locations (for funding, milestones)
- fetch_press_kit_document: Long-form docs (company_overview.md, product_one_pager.md, etc.)
- save_press_release: Save the final draft to internal storage (call when you deliver the complete draft)

When the user provides a rough draft and key topics, first fetch relevant internal data for the selected type, then draft the press release. Call save_press_release with the final content before responding.

CRITICAL: Your final response to the user must contain ONLY the formatted press release text. Do NOT include:
- Raw JSON or tool output (e.g. {"id": "quote:ceo", ...})
- Metadata like "key", "success", or file paths
- Descriptions of what you found or which sources you used
Output only the press release itself, using markdown: **Headline**, *Subhead*, and clear structure."""


def _build_task_message(rough_draft: str, key_topics: str, tone: str, press_release_type: str = "product_launch", **constraints) -> str:
    """Build a structured user message from form inputs."""
    from datetime import datetime, timezone
    current_date = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    parts = [
        "Please draft a press release with the following inputs:",
        "",
        "**Press release type:**",
        press_release_type.replace("_", " ").title(),
        "",
        "**Rough draft:**",
        rough_draft or "(none provided)",
        "",
        "**Key topics to include:**",
        key_topics or "(none specified)",
        "",
        "**Tone:**",
        tone or "professional",
        "",
        "**Current date (use for dateline):**",
        current_date,
    ]
    if constraints.get("audience"):
        parts.extend(["", "**Target audience:**", constraints["audience"]])
    if constraints.get("length"):
        parts.extend(["", "**Target length:**", constraints["length"]])
    if constraints.get("cta"):
        parts.extend(["", "**Call to action:**", constraints["cta"]])
    if constraints.get("exclusions"):
        parts.extend(["", "**Exclude:**", constraints["exclusions"]])
    return "\n".join(parts)


def _make_press_release_tools(settings: Settings, session_id: str) -> list:
    """Create tool functions for LangGraph (plain functions with docstrings)."""
    tools = []

    def lookup_dateline() -> dict:
        """Fetch current date and location for the press release dateline. Call this first to get the real-time dateline."""
        return press_release_tools.lookup_dateline()

    def lookup_company(company_id: str = "acme") -> dict:
        """Fetch company boilerplate and description. Use when you need the About Us / company description section."""
        return press_release_tools.lookup_company_boilerplate(company_id)

    def lookup_product(product_id: str = "skyline-2") -> dict:
        """Fetch product facts and differentiators. Use for product launches."""
        return press_release_tools.lookup_product_facts(product_id)

    def lookup_quote(quote_id: str = "ceo") -> dict:
        """Fetch approved executive quote. Use quote_id: ceo, cmo, etc."""
        return press_release_tools.lookup_quotes(quote_id)

    def lookup_partner(partner_id: str = "globex") -> dict:
        """Fetch partner blurb and facts. Use for partnership announcements."""
        return press_release_tools.lookup_partner_info(partner_id)

    def lookup_metric(metrics_id: str = "q1-2026") -> dict:
        """Fetch metrics (growth, dates, etc.). Use for funding or milestone announcements."""
        return press_release_tools.lookup_metrics(metrics_id)

    def fetch_doc(doc_key: str) -> dict:
        """Fetch press-kit document from S3. Keys: docs/press-kit/company_overview.md, docs/press-kit/product_one_pager.md, docs/press-kit/partner_blurb.md, docs/press-kit/metrics_summary.json"""
        return press_release_tools.fetch_press_kit_document(doc_key)

    def save_release(content: str, filename: str = "PressRelease.md") -> dict:
        """Save the generated press release to internal storage. Call this with the final draft content."""
        return press_release_tools.save_press_release(session_id, content, filename)

    tools.extend([
        lookup_dateline, lookup_company, lookup_product, lookup_quote, lookup_partner,
        lookup_metric, fetch_doc, save_release,
    ])
    return tools


def _conversation_to_messages(conversation_history: list[dict[str, str]], task_input: str) -> list:
    """Convert conversation_history + task_input to message list."""
    messages = []
    for m in conversation_history or []:
        role = (m.get("role") or "user").lower()
        content = m.get("content") or ""
        if isinstance(content, list):
            content = str(content)
        if role in ("assistant", "ai"):
            messages.append({"role": "assistant", "content": content})
        else:
            messages.append({"role": "user", "content": content})
    messages.append({"role": "user", "content": task_input or ""})
    return messages


def _get_final_content_from_state(state: dict) -> str:
    """Extract final assistant text from LangGraph state."""
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and getattr(msg, "type", "") == "ai":
            return msg.content if isinstance(msg.content, str) else str(msg.content)
        if isinstance(msg, dict):
            if msg.get("type") == "ai" and msg.get("content"):
                c = msg["content"]
                return c if isinstance(c, str) else str(c)
    return ""


class PressReleaseOrchestrator(AgentOrchestrator):
    """LangGraph-based Press Release Drafting Assistant with DynamoDB and S3 tools."""

    def __init__(self, settings: Settings | None = None, session_id: str | None = None):
        self.settings = settings or get_settings()
        self._session_id = session_id or ""
        self._agent = None
        self._langgraph_available = (
            create_react_agent is not None
            and ChatOpenAI is not None
        )

    def _build_agent(self):
        """Build LangGraph ReAct agent with press-release tools and system prompt."""
        if not self._langgraph_available:
            raise ImportError(
                "langgraph not available (pip install langgraph langchain-openai langchain-core)"
            )
        tools = _make_press_release_tools(self.settings, self._session_id)
        model = ChatOpenAI(
            model=self.settings.openai_model,
            api_key=self.settings.openai_api_key or os.getenv("OPENAI_API_KEY"),
            temperature=0.3,
        )
        return create_react_agent(
            model=model,
            tools=tools,
            prompt=PRESS_RELEASE_SYSTEM_PROMPT,
        )

    async def _run_async_turn(
        self,
        messages: list,
        on_stream_message: Callable[[str, str], None] | None,
    ) -> str:
        if self._agent is None:
            self._agent = self._build_agent()
        inputs = {"messages": messages}
        final_content = ""

        if on_stream_message:
            try:
                async for event in self._agent.astream(inputs, stream_mode="messages"):
                    if isinstance(event, tuple) and len(event) >= 1:
                        chunk = event[0]
                        if hasattr(chunk, "content") and chunk.content:
                            text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                            if text:
                                on_stream_message(text, "status")
                                final_content += text
                        elif isinstance(chunk, str) and chunk:
                            on_stream_message(chunk, "status")
                            final_content += chunk
            except Exception as e:
                return f"Error during streaming: {e}"

        if not final_content:
            try:
                state = await self._agent.ainvoke(inputs)
                final_content = _get_final_content_from_state(state)
            except Exception as e:
                return f"Error: {e}"

        return final_content or "I couldn't generate a response. Please try again with a rough draft and key topics."

    def run_turn(
        self,
        task_input: str,
        conversation_history: list[dict[str, str]],
        session_id: str,
        on_stream_message: Callable[[str, str], None] | None = None,
        **kwargs: Any,
    ) -> OrchestratorResult:
        self._session_id = session_id or self._session_id
        # Rebuild agent with session_id for save_press_release
        self._agent = None

        if not self._langgraph_available:
            if on_stream_message:
                on_stream_message(
                    "LangGraph not loaded (pip install langgraph langchain-openai langchain-core).",
                    "status",
                )
            return OrchestratorResult(
                content="Press Release Assistant unavailable. Install langgraph, langchain-openai, and langchain-core.",
                raw=None,
            )

        # Support structured form payload
        form_data = kwargs.get("form_data") or {}
        if form_data:
            task_input = _build_task_message(
                rough_draft=form_data.get("rough_draft", ""),
                key_topics=form_data.get("key_topics", ""),
                tone=form_data.get("tone", "professional"),
                press_release_type=form_data.get("press_release_type", "product_launch"),
                audience=form_data.get("audience"),
                length=form_data.get("length"),
                cta=form_data.get("cta"),
                exclusions=form_data.get("exclusions"),
            )
            # If there was also free-form text, append it
            if kwargs.get("user_text"):
                task_input += "\n\n**Additional instructions:**\n" + kwargs["user_text"]

        messages = _conversation_to_messages(conversation_history, task_input or "Hello. Please draft a press release.")
        try:
            final_text = asyncio.run(self._run_async_turn(messages, on_stream_message))
            return OrchestratorResult(content=final_text, raw=None, file_content=final_text)
        except Exception as e:
            return OrchestratorResult(content=f"Error: {e}", raw=None)

    def reset(self) -> None:
        self._agent = None
