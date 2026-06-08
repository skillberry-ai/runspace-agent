"""Agent abstractions and implementations for runspace_agent."""

from __future__ import annotations

import importlib
from typing import Any

from runspace_agent.agents.base import AgentResult, FilesystemAgent, Workspace

__all__ = [
    "AgentResult",
    "FilesystemAgent",
    "Workspace",
    "build_agent_options",
    "create_agent",
    "create_default_agent",
]

_AGENT_REGISTRY: dict[str, str] = {
    "claude-code": "runspace_agent.agents.claude_code",
}


def _get_agent_module(agent_type: str) -> Any:
    module_path = _AGENT_REGISTRY.get(agent_type)
    if module_path is None:
        available = ", ".join(sorted(_AGENT_REGISTRY))
        raise ValueError(f"Unknown agent_type: {agent_type!r}. Available: {available}")
    return importlib.import_module(module_path)


def build_agent_options(
    agent_type: str = "claude-code",
    agent_settings: dict[str, Any] | None = None,
) -> Any:
    """Build agent-specific options from a freeform settings dict.

    Each agent's ``build_options`` receives the full dict and reads
    only the keys it understands.
    """
    mod = _get_agent_module(agent_type)
    return mod.build_options(agent_settings)


def create_agent(
    agent_type: str = "claude-code",
    options: Any = None,
) -> FilesystemAgent:
    """Create an agent instance of the specified type."""
    mod = _get_agent_module(agent_type)
    return mod.create(options)


def create_default_agent(
    options: Any = None,
) -> FilesystemAgent:
    """Create the default agent (currently :class:`ClaudeCodeAgent`).

    Backward-compatible wrapper around :func:`create_agent`.
    """
    return create_agent(agent_type="claude-code", options=options)
