"""Tests for runspace_agent.local."""

from __future__ import annotations

from pathlib import Path

import pytest

from runspace_agent.core import RunspaceSession, run_agent


@pytest.mark.asyncio
async def test_local_workspace_setup(tmp_editable: Path, tmp_context: Path, mock_agent) -> None:
    """Local mode creates workspace and syncs back correctly."""
    original_content = (tmp_editable / "SKILL.md").read_text()

    session = RunspaceSession(
        editable_dir=tmp_editable,
        context_dir=tmp_context,
        prompt="Modify the skill.",
        agent=mock_agent,
        preinstalled_skills=[],
        mode="local",
    )
    result = await run_agent(session)
    assert result.success
    # Original file should still exist
    assert (tmp_editable / "SKILL.md").read_text() == original_content
    # Mock agent's marker should be synced back
    assert (tmp_editable / "agent_was_here.txt").exists()


@pytest.mark.asyncio
async def test_local_preserves_context(tmp_editable: Path, tmp_context: Path, mock_agent) -> None:
    """Local mode does not modify the original context directory."""
    original_traces = list(tmp_context.rglob("*"))

    session = RunspaceSession(
        editable_dir=tmp_editable,
        context_dir=tmp_context,
        prompt="Read the traces.",
        agent=mock_agent,
        preinstalled_skills=[],
        mode="local",
    )
    result = await run_agent(session)
    assert result.success

    # Context dir should be unchanged
    current_traces = list(tmp_context.rglob("*"))
    assert len(current_traces) == len(original_traces)
