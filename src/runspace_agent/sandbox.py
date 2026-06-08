"""Sandbox enforcement via PreToolUse hooks.

Provides hook functions and settings that restrict the agent to operating
only within its session directory.  Files outside the session boundary are
denied.

Works cross-platform (Windows, macOS, Linux) by using :mod:`pathlib` for
all path operations.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_DOTDOT_RE = re.compile(r"(?:^|[/\\])\.\.(?:[/\\]|$)")


def _resolve(p: str) -> Path:
    """Resolve a string to an absolute, normalized Path."""
    return Path(p).resolve()


def _is_inside(p: str, session_dir: Path) -> bool:
    """Return True if *p* resolves to a location inside *session_dir*."""
    try:
        resolved = _resolve(p)
        session = session_dir.resolve()
        # Use is_relative_to (Python 3.9+) for cross-platform safety
        return resolved == session or resolved.is_relative_to(session)
    except (ValueError, OSError):
        return False


def make_sandbox_hook(session_dir: Path):
    """Return an async hook callable that denies access outside *session_dir*.

    The returned function has the signature expected by the Claude Code SDK's
    ``hooks`` parameter::

        async def hook(
            tool_input: dict[str, Any],
            tool_name: str | None,
            ctx: HookContext,
        ) -> HookJSONOutput

    It returns a block decision when a tool call references a path outside
    the session directory, or an empty dict to allow the call.
    """
    session = session_dir.resolve()

    async def _sandbox_hook(
        tool_input: dict[str, Any],
        tool_name: str | None,
        ctx: Any,
    ) -> dict[str, Any]:
        reason = _check_tool(tool_name or "", tool_input, session)
        if reason:
            return {
                "decision": "block",
                "systemMessage": reason,
            }
        return {}

    return _sandbox_hook


def _check_tool(tool_name: str, tool_input: dict[str, Any], session: Path) -> str | None:
    """Return a denial reason if the tool call escapes *session*, else None."""
    if tool_name in ("Write", "Edit", "Read"):
        file_path = tool_input.get("file_path", "")
        if file_path and not _is_inside(file_path, session):
            return f"Access denied: {file_path} is outside the session directory"

    elif tool_name in ("Glob", "Grep"):
        path = tool_input.get("path", "")
        if path and not _is_inside(path, session):
            return f"Access denied: {path} is outside the session directory"

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        reason = _check_bash_command(command, session)
        if reason:
            return reason

    return None


def _check_bash_command(command: str, session: Path) -> str | None:
    """Best-effort check that a bash command doesn't escape the session."""
    for token in command.split():
        cleaned = token.strip("'\"")
        if _DOTDOT_RE.search(cleaned) or cleaned == "..":
            return "Access denied: command contains path traversal (..)"
        if Path(cleaned).is_absolute() and not _is_inside(cleaned, session):
            return f"Access denied: command references path outside session: {cleaned}"
    return None


def build_hooks_config(session_dir: Path) -> dict[str, list[Any]]:
    """Build a hooks dict for agent sandbox enforcement.

    Returns a dict like::

        {
            "PreToolUse": [{"matcher": "...", "hook_fn": <callable>}]
        }

    This is an intermediate representation.  Each agent implementation
    converts it into its own SDK-specific hook objects (e.g.
    ``HookMatcher`` for Claude Code) or uses the ``hook_fn`` directly.

    No SDK dependency — pure Python.
    """
    hook_fn = make_sandbox_hook(session_dir)
    return {
        "PreToolUse": [
            {
                "matcher": "Write|Edit|Read|Glob|Grep|Bash",
                "hook_fn": hook_fn,
            }
        ]
    }
