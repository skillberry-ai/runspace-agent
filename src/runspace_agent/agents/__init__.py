"""Agent abstractions and implementations for runspace_agent."""

from __future__ import annotations

from typing import Any

from runspace_agent.agents.base import AgentResult, FilesystemAgent, Workspace

__all__ = [
    "AgentResult",
    "FilesystemAgent",
    "Workspace",
    "create_default_agent",
]


def create_default_agent(
    settings: dict[str, Any] | None = None,
    max_turns: int | None = None,
    mcp_servers: dict[str, Any] | None = None,
) -> FilesystemAgent:
    """Create the default agent (currently :class:`ClaudeCodeAgent`).

    This is the single place outside ``agents/claude_code/`` that is
    allowed to know about the concrete default implementation.
    """
    from runspace_agent.agents.claude_code import ClaudeCodeAgent

    kwargs: dict[str, Any] = {}
    if settings is not None:
        kwargs["settings"] = settings
    if max_turns is not None:
        kwargs["max_turns"] = max_turns
    if mcp_servers is not None:
        kwargs["mcp_servers"] = mcp_servers
    return ClaudeCodeAgent(**kwargs)
