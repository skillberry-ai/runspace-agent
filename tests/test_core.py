"""Tests for runspace_agent.core."""

from __future__ import annotations

from pathlib import Path

import pytest

from runspace_agent.core import RunspaceSession, run_agent


@pytest.mark.asyncio
async def test_run_agent_with_mock(tmp_editable: Path, tmp_context: Path, mock_agent) -> None:
    """run_agent succeeds with a mock agent and syncs editable back."""
    session = RunspaceSession(
        editable_dir=tmp_editable,
        context_dir=tmp_context,
        prompt="Do something useful.",
        agent=mock_agent,
        preinstalled_skills=[],
    )
    result = await run_agent(session)
    assert result.success
    assert result.session_id
    # The mock agent writes a marker file; it should be synced back
    assert (tmp_editable / "agent_was_here.txt").read_text() == "done"


@pytest.mark.asyncio
async def test_run_agent_failing(tmp_editable: Path, tmp_context: Path, failing_agent) -> None:
    """run_agent reports failure when the agent fails."""
    session = RunspaceSession(
        editable_dir=tmp_editable,
        context_dir=tmp_context,
        prompt="This will fail.",
        agent=failing_agent,
        preinstalled_skills=[],
    )
    result = await run_agent(session)
    assert not result.success
    assert result.agent_result.error == "intentional failure"


@pytest.mark.asyncio
async def test_run_agent_missing_editable(tmp_path: Path, tmp_context: Path, mock_agent) -> None:
    """run_agent returns error when editable_dir doesn't exist."""
    session = RunspaceSession(
        editable_dir=tmp_path / "nonexistent",
        context_dir=tmp_context,
        prompt="test",
        agent=mock_agent,
        preinstalled_skills=[],
    )
    result = await run_agent(session)
    assert not result.success
    assert "does not exist" in (result.agent_result.error or "")


@pytest.mark.asyncio
async def test_run_agent_missing_context(tmp_editable: Path, tmp_path: Path, mock_agent) -> None:
    """run_agent returns error when context_dir doesn't exist."""
    session = RunspaceSession(
        editable_dir=tmp_editable,
        context_dir=tmp_path / "nonexistent",
        prompt="test",
        agent=mock_agent,
        preinstalled_skills=[],
    )
    result = await run_agent(session)
    assert not result.success
    assert "does not exist" in (result.agent_result.error or "")


@pytest.mark.asyncio
async def test_run_agent_output_zip(tmp_editable: Path, tmp_context: Path, mock_agent) -> None:
    """run_agent creates a zip when output_zip=True."""
    session = RunspaceSession(
        editable_dir=tmp_editable,
        context_dir=tmp_context,
        prompt="Do something.",
        agent=mock_agent,
        preinstalled_skills=[],
        output_zip=True,
    )
    result = await run_agent(session)
    assert result.success
    assert result.output_zip_path is not None
    assert result.output_zip_path.exists()
