"""Agent abstractions and implementations for runspace_agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from runspace_agent.agents.base import AgentResult, FilesystemAgent, Workspace

if TYPE_CHECKING:
    from claude_code_sdk import ClaudeCodeOptions

__all__ = [
    "AgentResult",
    "FilesystemAgent",
    "Workspace",
    "create_default_agent",
]


def create_default_agent(
    options: ClaudeCodeOptions | None = None,
) -> FilesystemAgent:
    """Create the default agent (currently :class:`ClaudeCodeAgent`).

    This is the single place outside ``agents/claude_code/`` that is
    allowed to know about the concrete default implementation.
    """
    from runspace_agent.agents.claude_code import ClaudeCodeAgent

    return ClaudeCodeAgent(options=options)
