"""ClaudeCodeAgent -- FilesystemAgent implementation using the Claude Agent SDK.

Requires the optional ``claude-code-sdk`` dependency::

    uv pip install runspace-agent[claude]
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from runspace_agent.agents.base import AgentResult, Workspace
from runspace_agent.agents.claude_code.defaults import (
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_MAX_TURNS,
    DEFAULT_SYSTEM_PROMPT,
)


class ClaudeCodeAgent:
    """Run a Claude Code agent inside a :class:`Workspace`.

    This is the built-in :class:`~runspace_agent.agents.base.FilesystemAgent`
    implementation backed by the Claude Agent SDK.

    Parameters:
        settings: Full Claude Code settings dict (env, permissions, model,
            plugins, ...).  Follows the ``settings.json`` schema.  The
            ``settings["env"]`` entries are injected as environment variables
            when launching the SDK.
        max_turns: Maximum number of agentic turns before the agent is
            stopped.
        mcp_servers: Optional MCP server configurations passed through to
            ``ClaudeCodeOptions.mcpServers``.
    """

    skills_folder_name: str = ".claude/skills"

    # Repo-root-relative path to bundled skills.  Computed once at module load.
    _DEFAULT_SKILLS_DIR: Path = (
        Path(__file__).resolve().parent.parent.parent.parent.parent / ".claude" / "skills"
    )

    def __init__(
        self,
        settings: dict[str, Any] | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        mcp_servers: dict[str, Any] | None = None,
    ) -> None:
        self.settings = settings or {}
        self.max_turns = max_turns
        self.mcp_servers = mcp_servers
        self.default_skills_dir: Path | None = self._DEFAULT_SKILLS_DIR

    async def run(self, workspace: Workspace) -> AgentResult:
        """Execute the Claude Code agent inside *workspace*."""
        query, ClaudeCodeOptions = self._import_sdk()
        return await self._run_agent(query, ClaudeCodeOptions, workspace)

    async def _run_agent(
        self,
        query: Any,
        ClaudeCodeOptions: Any,
        workspace: Workspace,
    ) -> AgentResult:
        """Build SDK options and iterate the agent loop."""
        # Pass env vars directly to the SDK (no os.environ manipulation)
        env_vars = {k: str(v) for k, v in self.settings.get("env", {}).items()}

        options_kwargs: dict[str, Any] = {
            "allowed_tools": list(DEFAULT_ALLOWED_TOOLS),
            "permission_mode": "bypassPermissions",
            "cwd": str(workspace.cwd),
            "max_turns": self.max_turns,
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "env": env_vars,
        }

        if self.mcp_servers:
            options_kwargs["mcp_servers"] = self.mcp_servers

        # Merge model from settings if provided
        model = self.settings.get("model")
        if model:
            options_kwargs["model"] = model

        # Merge permission allow-list from settings if provided
        permissions = self.settings.get("permissions", {})
        if permissions.get("allow"):
            options_kwargs["allowed_tools"].extend(permissions["allow"])

        # Convert sandbox hooks to SDK HookMatcher objects
        if workspace.hooks:
            options_kwargs["hooks"] = self._build_sdk_hooks(workspace.hooks)

        options = ClaudeCodeOptions(**options_kwargs)

        messages: list[Any] = []
        total_tokens = 0
        start_ms = int(time.time() * 1000)

        async for message in query(
            prompt=workspace.prompt,
            options=options,
        ):
            messages.append(message)

            # Extract token usage from the ResultMessage (always last).
            # ResultMessage.usage is a dict, not an object.
            if type(message).__name__ == "ResultMessage":
                usage = getattr(message, "usage", None)
                if isinstance(usage, dict):
                    total_tokens += usage.get("input_tokens", 0)
                    total_tokens += usage.get("output_tokens", 0)

        from runspace_agent.agents.claude_code.serializer import serialize_messages

        duration_ms = int(time.time() * 1000) - start_ms
        return AgentResult(
            success=True,
            messages=messages,
            conversation=serialize_messages(messages),
            total_tokens=total_tokens,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _build_sdk_hooks(hooks: dict[str, list[Any]]) -> dict[str, list[Any]]:
        """Convert intermediate hooks format to SDK HookMatcher objects."""
        from claude_code_sdk.types import HookMatcher

        sdk_hooks: dict[str, list[Any]] = {}
        for event_name, matchers in hooks.items():
            sdk_hooks[event_name] = [
                HookMatcher(
                    matcher=m["matcher"],
                    hooks=[m["hook_fn"]],
                )
                for m in matchers
            ]
        return sdk_hooks

    @staticmethod
    def _import_sdk() -> tuple[Any, Any]:
        """Lazily import the Claude Agent SDK.

        Raises :class:`ImportError` with a helpful message when the
        optional dependency is missing.
        """
        try:
            from claude_code_sdk import ClaudeCodeOptions, query
        except ImportError:
            raise ImportError(
                "ClaudeCodeAgent requires the 'claude-code-sdk' package. "
                "Install it with:  uv pip install claude-code-sdk"
            ) from None
        return query, ClaudeCodeOptions
