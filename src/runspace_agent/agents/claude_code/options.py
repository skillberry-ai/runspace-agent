"""Claude Code agent options builder and factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from claude_code_sdk import ClaudeCodeOptions

    from runspace_agent.agents.claude_code.agent import ClaudeCodeAgent


def build_options(
    agent_settings: dict[str, Any] | None = None,
) -> ClaudeCodeOptions:
    """Build a :class:`ClaudeCodeOptions` from a settings dict.

    The dict may contain any of the following keys (all optional):

    - ``env``: dict of environment variables
    - ``model``: Claude model name
    - ``permissions.allow`` / ``permissions.disallow``: tool lists
    - ``max_turns``: maximum conversation turns (default 300)
    - ``mcp_servers``: MCP server configuration
    """
    from claude_code_sdk import ClaudeCodeOptions

    settings = agent_settings or {}
    kwargs: dict[str, Any] = {}

    env_vars = {k: str(v) for k, v in settings.get("env", {}).items()}
    if env_vars:
        kwargs["env"] = env_vars

    model = settings.get("model")
    if model:
        kwargs["model"] = model

    permissions = settings.get("permissions", {})
    if permissions.get("allow"):
        kwargs["allowed_tools"] = list(permissions["allow"])
    if permissions.get("disallow"):
        kwargs["disallowed_tools"] = list(permissions["disallow"])

    kwargs["max_turns"] = settings.get("max_turns", 300)

    mcp_servers = settings.get("mcp_servers")
    if mcp_servers:
        kwargs["mcp_servers"] = mcp_servers

    return ClaudeCodeOptions(**kwargs)


def create(options: Any = None) -> ClaudeCodeAgent:
    """Create a :class:`ClaudeCodeAgent` instance."""
    from runspace_agent.agents.claude_code.agent import ClaudeCodeAgent

    return ClaudeCodeAgent(options=options)
