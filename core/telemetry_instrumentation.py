"""Spans and metrics aligned with the shared AHEAD Agent Overview dashboard."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry.trace import Status, StatusCode

from core.telemetry import get_meter, get_tracer

T = TypeVar("T")

_tracer = get_tracer("core.telemetry_instrumentation")
_meter = get_meter("core.telemetry_instrumentation")

_llm_calls = None
_llm_latency = None
_llm_tokens = None
_tool_calls = None


def _ensure_tool_and_llm_metrics() -> tuple[Any, Any, Any, Any]:
    global _llm_calls, _llm_latency, _llm_tokens, _tool_calls
    if _llm_calls is None:
        _llm_calls = _meter.create_counter(
            "llm.calls.total",
            description="Total LLM invocations",
        )
        _llm_latency = _meter.create_histogram(
            "llm.latency_ms",
            description="LLM call latency in milliseconds",
            unit="ms",
        )
        _llm_tokens = _meter.create_histogram(
            "llm.tokens.total",
            description="Total tokens per LLM call",
        )
        _tool_calls = _meter.create_counter(
            "tool.calls.total",
            description="Total tool invocations",
        )
    return _llm_calls, _llm_latency, _llm_tokens, _tool_calls


def langchain_usage_tokens(response: Any) -> tuple[int | None, int | None, int | None]:
    """Best-effort token counts from LangChain AIMessage."""
    prompt_t: int | None = None
    completion_t: int | None = None
    total_t: int | None = None

    um = getattr(response, "usage_metadata", None)
    if isinstance(um, dict):
        prompt_t = um.get("input_tokens") or um.get("prompt_tokens")
        completion_t = um.get("output_tokens") or um.get("completion_tokens")
        total_t = um.get("total_tokens")

    rm = getattr(response, "response_metadata", None) or {}
    if isinstance(rm, dict):
        tu = rm.get("token_usage")
        if isinstance(tu, dict):
            prompt_t = prompt_t if prompt_t is not None else tu.get("prompt_tokens")
            completion_t = completion_t if completion_t is not None else tu.get("completion_tokens")
            total_t = total_t if total_t is not None else tu.get("total_tokens")

    if total_t is None and prompt_t is not None and completion_t is not None:
        total_t = prompt_t + completion_t
    return prompt_t, completion_t, total_t


def trace_llm_langchain(model_name: str, temperature: float, fn: Callable[[], T]) -> T:
    """Run a LangChain sync call inside an ``llm.invoke`` span with dashboard metrics."""
    llm_calls, llm_latency, llm_tokens, _ = _ensure_tool_and_llm_metrics()
    with _tracer.start_as_current_span(
        "llm.invoke",
        attributes={"llm.model": model_name, "llm.temperature": temperature},
    ) as span:
        llm_calls.add(1, {"llm.model": model_name})
        t0 = time.perf_counter()
        try:
            response = fn()
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        elapsed_ms = (time.perf_counter() - t0) * 1000
        llm_latency.record(elapsed_ms, {"llm.model": model_name})

        pt, ct, tot = langchain_usage_tokens(response)
        if pt is not None:
            span.set_attribute("llm.prompt_tokens", pt)
        if ct is not None:
            span.set_attribute("llm.completion_tokens", ct)
        if tot is not None:
            span.set_attribute("llm.total_tokens", tot)
            llm_tokens.record(tot, {"llm.model": model_name})
        span.set_attribute("llm.latency_ms", round(elapsed_ms, 1))
        return response


def trace_tool(name: str, fn: Callable[[], T]) -> T:
    """Run ``fn`` inside ``tool.<name>`` span and increment ``tool.calls.total``."""
    _, _, _, tool_calls = _ensure_tool_and_llm_metrics()
    with _tracer.start_as_current_span(
        f"tool.{name}",
        attributes={"tool.name": name},
    ) as span:
        tool_calls.add(1, {"tool.name": name})
        try:
            result = fn()
            span.set_attribute("tool.result_length", len(str(result)))
            return result
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
