"""Tests for FilesystemAgent protocol conformance."""

from __future__ import annotations

from runspace_agent.agents.base import FilesystemAgent


def test_mock_agent_satisfies_protocol(mock_agent) -> None:
    """MockFilesystemAgent satisfies the FilesystemAgent protocol."""
    assert isinstance(mock_agent, FilesystemAgent)
    assert hasattr(mock_agent, "skills_folder_name")
    assert hasattr(mock_agent, "run")


def test_failing_agent_satisfies_protocol(failing_agent) -> None:
    """FailingAgent satisfies the FilesystemAgent protocol."""
    assert isinstance(failing_agent, FilesystemAgent)
