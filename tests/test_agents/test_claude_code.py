"""Tests for ClaudeCodeAgent (mocked SDK)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from runspace_agent.agents.base import FilesystemAgent, Workspace
from runspace_agent.agents.claude_code.agent import ClaudeCodeAgent
from runspace_agent.agents.claude_code.defaults import DEFAULT_ALLOWED_TOOLS


def test_claude_code_agent_satisfies_protocol() -> None:
    agent = ClaudeCodeAgent()
    assert isinstance(agent, FilesystemAgent)
    assert agent.skills_folder_name == ".claude/skills"


def test_default_settings() -> None:
    agent = ClaudeCodeAgent()
    assert agent.max_turns == 300
    assert agent.settings == {}
    assert agent.mcp_servers is None


def test_custom_settings() -> None:
    settings = {"env": {"ANTHROPIC_MODEL": "claude-opus-4-6"}, "model": "opus[1m]"}
    agent = ClaudeCodeAgent(settings=settings, max_turns=500)
    assert agent.settings == settings
    assert agent.max_turns == 500


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
