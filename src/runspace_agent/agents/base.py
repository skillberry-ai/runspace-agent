"""Base types for the FilesystemAgent abstraction.

Defines the Protocol that any agent implementation must satisfy,
plus the Workspace and AgentResult types used across all backends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass
class Workspace:
    """The sandboxed view that any FilesystemAgent receives.

    Attributes:
        editable_dir: Directory the agent should focus on modifying.
        context_dir: Directory with read-only reference material
            (traces, domain knowledge, performance history, etc.).
        prompt: Fully constructed prompt including directory descriptions.
        skills_dir: Path to the agent-specific skills directory, if loaded.
        cwd: Session root directory (the agent's working directory).
    """

    editable_dir: Path
    context_dir: Path
    prompt: str
    skills_dir: Path | None
    cwd: Path
    hooks: dict[str, list[Any]] | None = None


@dataclass
class AgentResult:
    """Result returned by a FilesystemAgent after execution.

    Attributes:
        success: Whether the agent completed without errors.
        messages: Raw messages from the agent execution (SDK-specific).
        conversation: Serialized conversation as a list of JSON-ready dicts.
            Each agent implementation is responsible for populating this
            from its SDK-specific message types.
        total_tokens: Approximate total tokens consumed.
        duration_ms: Wall-clock execution time in milliseconds.
        error: Error message if the agent failed, None otherwise.
    """

    success: bool
    messages: list[Any] = field(default_factory=list)
    conversation: list[dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    duration_ms: int = 0
    error: str | None = None


@runtime_checkable
class FilesystemAgent(Protocol):
    """Protocol for agents that operate on filesystem directories.

    Any class with a ``skills_folder_name`` attribute and an async ``run``
    method matching this signature satisfies the protocol.  This enables
    pluggable agent backends (Claude Code, OpenCode, custom, ...) without
    requiring inheritance.

    Attributes:
        skills_folder_name: Relative path from ``cwd`` where this agent
            expects skills to be placed.  For example ``".claude/skills"``
            for Claude Code or ``".opencode/skills"`` for OpenCode.
            Used to determine where to copy user-provided skills and default skills.
        default_skills_dir: Absolute path to the directory containing the
            agent's bundled/preinstalled skills on disk.  Each subdirectory
            is a separate skill.  ``None`` means the agent ships no default
            skills.
    """

    skills_folder_name: str
    default_skills_dir: Path | None

    async def run(self, workspace: Workspace) -> AgentResult:
        """Execute the agent inside the given workspace.

        The agent should read from ``workspace.context_dir``, modify files
        in ``workspace.editable_dir``, and follow the instructions in
        ``workspace.prompt``.
        """
        ...
