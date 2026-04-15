"""Convert server request dicts into ClaudeCodeOptions objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from claude_code_sdk import ClaudeCodeOptions

    from runspace_agent.server.models import RunRequest


def build_options_from_request(req: RunRequest) -> ClaudeCodeOptions:
    """Build a :class:`ClaudeCodeOptions` from the JSON-serializable server request."""
    from claude_code_sdk import ClaudeCodeOptions

    kwargs: dict[str, Any] = {}

    if req.agent_settings:
        env_vars = {k: str(v) for k, v in req.agent_settings.get("env", {}).items()}
        if env_vars:
            kwargs["env"] = env_vars

        model = req.agent_settings.get("model")
        if model:
            kwargs["model"] = model

        permissions = req.agent_settings.get("permissions", {})
        if permissions.get("allow"):
            kwargs["allowed_tools"] = list(permissions["allow"])

    kwargs["max_turns"] = req.agent_max_turns

    if req.mcp_servers:
        kwargs["mcp_servers"] = req.mcp_servers

    return ClaudeCodeOptions(**kwargs)
