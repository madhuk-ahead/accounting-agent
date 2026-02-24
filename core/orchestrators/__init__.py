"""Orchestrator abstraction. Default implementation: Strands (see strands_orchestrator)."""

from .base import AgentOrchestrator, OrchestratorResult
from .factory import get_orchestrator

__all__ = ["AgentOrchestrator", "OrchestratorResult", "get_orchestrator"]
