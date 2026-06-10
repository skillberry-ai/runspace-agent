"""Shared test fixtures for runspace_agent."""

from __future__ import annotations

from pathlib import Path

import pytest

from runspace_agent.agents.base import AgentResult, Workspace


class MockFilesystemAgent:
    """A mock agent that writes a marker file to prove it ran."""

    skills_folder_name: str = ".mock/skills"
    default_skills_dir: Path | None = None
    npx_agent_name: str | None = None

    async def run(self, workspace: Workspace) -> AgentResult:
        marker = workspace.editable_dir / "agent_was_here.txt"
        marker.write_text("done", encoding="utf-8")
        return AgentResult(success=True, messages=["mock ran"], total_tokens=42, duration_ms=100)


class FailingAgent:
    """A mock agent that always fails."""

    skills_folder_name: str = ".mock/skills"
    default_skills_dir: Path | None = None
    npx_agent_name: str | None = None

    async def run(self, workspace: Workspace) -> AgentResult:
        return AgentResult(success=False, error="intentional failure")


@pytest.fixture
def tmp_editable(tmp_path: Path) -> Path:
    """Create a temporary editable directory with a sample file."""
    d = tmp_path / "editable"
    d.mkdir()
    (d / "SKILL.md").write_text("# My Skill\nOriginal content", encoding="utf-8")
    (d / "scripts").mkdir()
    (d / "scripts" / "run.py").write_text("print('hello')", encoding="utf-8")
    return d


@pytest.fixture
def tmp_context(tmp_path: Path) -> Path:
    """Create a temporary context directory with sample traces."""
    d = tmp_path / "context"
    d.mkdir()
    traces = d / "traces"
    traces.mkdir()
    (traces / "trace_001.json").write_text('{"reward": 0.8, "success": true}', encoding="utf-8")
    (traces / "trace_002.json").write_text('{"reward": 0.3, "success": false}', encoding="utf-8")
    domain = d / "domain_knowledge"
    domain.mkdir()
    (domain / "policy.md").write_text("# Domain Policy\nBe helpful.", encoding="utf-8")
    return d


@pytest.fixture
def mock_agent() -> MockFilesystemAgent:
    return MockFilesystemAgent()


@pytest.fixture
def failing_agent() -> FailingAgent:
    return FailingAgent()
