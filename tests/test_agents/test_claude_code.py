"""Tests for ClaudeCodeAgent (mocked SDK)."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from runspace_agent.agents.base import FilesystemAgent, Workspace
from runspace_agent.agents.claude_code.agent import ClaudeCodeAgent
from runspace_agent.agents.claude_code.defaults import (
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_DISALLOWED_TOOLS,
    DEFAULT_MAX_TURNS,
    DEFAULT_SYSTEM_PROMPT,
)


# ---------------------------------------------------------------------------
# Lightweight stand-in for ClaudeCodeOptions so tests don't need the real SDK
# ---------------------------------------------------------------------------
@dataclass
class _FakeClaudeCodeOptions:
    allowed_tools: list[str] = dataclasses.field(default_factory=list)
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    mcp_servers: dict = dataclasses.field(default_factory=dict)
    permission_mode: str | None = None
    max_turns: int | None = None
    model: str | None = None
    cwd: str | None = None
    env: dict[str, str] = dataclasses.field(default_factory=dict)
    hooks: dict | None = None
    disallowed_tools: list[str] = dataclasses.field(default_factory=list)
    continue_conversation: bool = False
    resume: str | None = None
    permission_prompt_tool_name: str | None = None
    settings: str | None = None
    add_dirs: list = dataclasses.field(default_factory=list)
    extra_args: dict = dataclasses.field(default_factory=dict)
    user: str | None = None
    include_partial_messages: bool = False


def test_claude_code_agent_satisfies_protocol() -> None:
    agent = ClaudeCodeAgent()
    assert isinstance(agent, FilesystemAgent)
    assert agent.skills_folder_name == ".claude/skills"


def test_default_options() -> None:
    agent = ClaudeCodeAgent()
    assert agent._user_options is None


def test_custom_options() -> None:
    opts = _FakeClaudeCodeOptions(model="claude-opus-4-6", max_turns=50)
    agent = ClaudeCodeAgent(options=opts)
    assert agent._user_options is opts
    assert agent._user_options.model == "claude-opus-4-6"
    assert agent._user_options.max_turns == 50


def test_enforced_fields_override(tmp_path) -> None:
    """User-provided permission_mode, cwd, system_prompt are overridden."""
    opts = _FakeClaudeCodeOptions(
        permission_mode="plan",
        cwd="/user/provided/path",
        system_prompt="user prompt",
        model="claude-sonnet-4-6",
    )
    agent = ClaudeCodeAgent(options=opts)
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )

    effective = agent._build_effective_options(_FakeClaudeCodeOptions, workspace)

    # Enforced fields
    assert effective.permission_mode == "bypassPermissions"
    assert effective.cwd == str(tmp_path)
    assert effective.system_prompt == DEFAULT_SYSTEM_PROMPT

    # User fields preserved
    assert effective.model == "claude-sonnet-4-6"


def test_defaults_applied_when_omitted(tmp_path) -> None:
    """Bare options get default allowed_tools and max_turns."""
    agent = ClaudeCodeAgent(options=_FakeClaudeCodeOptions())
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )

    effective = agent._build_effective_options(_FakeClaudeCodeOptions, workspace)

    assert effective.allowed_tools == list(DEFAULT_ALLOWED_TOOLS)
    assert effective.max_turns == DEFAULT_MAX_TURNS


def test_user_allowed_tools_preserved(tmp_path) -> None:
    """User-provided allowed_tools are NOT replaced by defaults."""
    custom_tools = ["Read", "Write", "CustomTool"]
    opts = _FakeClaudeCodeOptions(allowed_tools=custom_tools)
    agent = ClaudeCodeAgent(options=opts)
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )

    effective = agent._build_effective_options(_FakeClaudeCodeOptions, workspace)

    assert effective.allowed_tools == custom_tools


def test_user_max_turns_preserved(tmp_path) -> None:
    """User-provided max_turns is NOT replaced by default."""
    opts = _FakeClaudeCodeOptions(max_turns=50)
    agent = ClaudeCodeAgent(options=opts)
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )

    effective = agent._build_effective_options(_FakeClaudeCodeOptions, workspace)

    assert effective.max_turns == 50


def test_none_options_uses_defaults(tmp_path) -> None:
    """When no options are passed, a bare default is created."""
    agent = ClaudeCodeAgent()
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )

    effective = agent._build_effective_options(_FakeClaudeCodeOptions, workspace)

    assert effective.permission_mode == "bypassPermissions"
    assert effective.allowed_tools == list(DEFAULT_ALLOWED_TOOLS)
    assert effective.max_turns == DEFAULT_MAX_TURNS


@pytest.mark.asyncio
async def test_run_raises_without_sdk(tmp_path) -> None:
    """ClaudeCodeAgent.run raises ImportError when SDK is not installed."""
    agent = ClaudeCodeAgent()
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )
    with patch.dict("sys.modules", {"claude_code_sdk": None}):
        with pytest.raises(ImportError, match="claude-code-sdk"):
            await agent.run(workspace)


def test_allowed_tools_are_comprehensive() -> None:
    expected = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill",
                "WebSearch", "WebFetch", "Agent", "LSP"}
    assert set(DEFAULT_ALLOWED_TOOLS) == expected


def test_disallowed_tools_always_enforced(tmp_path) -> None:
    """disallowed_tools is enforced even when user provides their own."""
    opts = _FakeClaudeCodeOptions(disallowed_tools=["OnlyThis"])
    agent = ClaudeCodeAgent(options=opts)
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )
    effective = agent._build_effective_options(_FakeClaudeCodeOptions, workspace)
    assert effective.disallowed_tools == list(DEFAULT_DISALLOWED_TOOLS)


def test_disallowed_tools_applied_by_default(tmp_path) -> None:
    """Bare options get the default disallowed_tools."""
    agent = ClaudeCodeAgent()
    workspace = Workspace(
        editable_dir=tmp_path / "editable",
        context_dir=tmp_path / "context",
        prompt="test",
        skills_dir=None,
        cwd=tmp_path,
    )
    effective = agent._build_effective_options(_FakeClaudeCodeOptions, workspace)
    assert "AskUserQuestion" in effective.disallowed_tools
    assert "EnterPlanMode" in effective.disallowed_tools
    assert "Monitor" in effective.disallowed_tools


def test_disallowed_tools_list_is_complete() -> None:
    """Verify the disallowed tools list contains all expected entries."""
    expected = {
        "AskUserQuestion", "EnterPlanMode", "ExitPlanMode",
        "EnterWorktree", "ExitWorktree", "ScheduleWakeup",
        "CronCreate", "CronDelete", "CronList", "Monitor",
    }
    assert set(DEFAULT_DISALLOWED_TOOLS) == expected
