"""ClaudeCodeAgent -- FilesystemAgent implementation using the Claude Agent SDK.

Requires the optional ``claude-code-sdk`` dependency::

    uv pip install runspace-agent[claude]
"""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from runspace_agent.agents.base import AgentResult, Workspace
from runspace_agent.agents.claude_code.defaults import (
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_DISALLOWED_TOOLS,
    DEFAULT_MAX_TURNS,
    DEFAULT_SYSTEM_PROMPT,
)

if TYPE_CHECKING:
    from claude_code_sdk import ClaudeCodeOptions


class ClaudeCodeAgent:
    """Run a Claude Code agent inside a :class:`Workspace`.

    This is the built-in :class:`~runspace_agent.agents.base.FilesystemAgent`
    implementation backed by the Claude Agent SDK.

    Users pass a :class:`~claude_code_sdk.ClaudeCodeOptions` object to
    configure the agent.  The agent **enforces** the following fields
    regardless of what the user sets:

    * ``permission_mode`` → ``"bypassPermissions"`` (headless container)
    * ``cwd`` → from the workspace (sandbox boundary)
    * ``system_prompt`` → headless system prompt (no interactive prompts)
    * ``disallowed_tools`` → interactive/scheduling tools disabled for headless
    * ``hooks`` → from the workspace (sandbox enforcement)

    If the user does not set ``allowed_tools`` or ``max_turns``, sensible
    defaults are applied.

    Parameters:
        options: A :class:`~claude_code_sdk.ClaudeCodeOptions` instance.
            When ``None``, a bare default is created at run time.
    """

    skills_folder_name: str = ".claude/skills"

    # The "-a" value for `npx skills add`, used to install per-run remote_skills.
    npx_agent_name: str = "claude"

    # Repo-root-relative path to bundled skills.  Computed once at module load.
    _DEFAULT_SKILLS_DIR: Path = (
        Path(__file__).resolve().parent.parent.parent.parent.parent / ".claude" / "skills"
    )

    def __init__(self, options: ClaudeCodeOptions | None = None) -> None:
        self._user_options = options
        self.default_skills_dir: Path | None = self._DEFAULT_SKILLS_DIR

    async def run(self, workspace: Workspace) -> AgentResult:
        """Execute the Claude Code agent inside *workspace*."""
        query, ClaudeCodeOptions = self._import_sdk()
        options = self._build_effective_options(ClaudeCodeOptions, workspace)
        return await self._run_agent(query, options, workspace)

    def _build_effective_options(
        self,
        ClaudeCodeOptions: type,
        workspace: Workspace,
    ) -> Any:
        """Merge user options with enforced sandbox overrides.

        Priority (highest to lowest):
        1. Enforced fields (always override, non-negotiable)
        2. User-provided fields (from self._user_options)
        3. Sensible defaults (only if user left field at dataclass default)
        """
        base = self._user_options if self._user_options is not None else ClaudeCodeOptions()

        overrides: dict[str, Any] = {}

        # Defaults: fill in only if user did not set them
        if not base.allowed_tools:
            overrides["allowed_tools"] = list(DEFAULT_ALLOWED_TOOLS)

        if base.max_turns is None:
            overrides["max_turns"] = DEFAULT_MAX_TURNS

        # Enforced fields: always override regardless of user input
        overrides["permission_mode"] = "bypassPermissions"
        overrides["cwd"] = str(workspace.cwd)
        overrides["system_prompt"] = DEFAULT_SYSTEM_PROMPT
        overrides["disallowed_tools"] = list(DEFAULT_DISALLOWED_TOOLS)

        if workspace.hooks:
            overrides["hooks"] = self._build_sdk_hooks(workspace.hooks)

        return dataclasses.replace(base, **overrides)

    async def _run_agent(
        self,
        query: Any,
        options: Any,
        workspace: Workspace,
    ) -> AgentResult:
        """Iterate the agent loop with pre-built options."""
        messages: list[Any] = []
        total_tokens = 0
        total_cost_usd: float | None = None
        start_ms = int(time.time() * 1000)

        async for message in query(
            prompt=workspace.prompt,
            options=options,
        ):
            messages.append(message)

            if type(message).__name__ == "ResultMessage":
                usage = getattr(message, "usage", None)
                if isinstance(usage, dict):
                    total_tokens += usage.get("input_tokens", 0)
                    total_tokens += usage.get("output_tokens", 0)
                cost = getattr(message, "total_cost_usd", None)
                if cost is not None:
                    total_cost_usd = cost

        from runspace_agent.agents.claude_code.serializer import serialize_messages

        duration_ms = int(time.time() * 1000) - start_ms
        return AgentResult(
            success=True,
            messages=messages,
            conversation=serialize_messages(messages),
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
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
