"""Tests for runspace_agent.workspaces."""

import tempfile
from pathlib import Path

from runspace_agent.workspaces import (
    DATA_DIR_ENV,
    HOME_DIRNAME,
    SESSIONS_DIRNAME,
    read_session_meta,
    session_workspace,
    workspaces_root,
    write_session_meta,
)


def test_workspaces_root_defaults_to_temp(monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    assert workspaces_root() == (
        Path(tempfile.gettempdir()) / HOME_DIRNAME / SESSIONS_DIRNAME
    )


def test_workspaces_root_honors_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    # The override dir directly contains sessions/ (no extra "runspace" segment).
    assert workspaces_root() == tmp_path / SESSIONS_DIRNAME
    assert session_workspace("abc123") == tmp_path / SESSIONS_DIRNAME / "abc123"


def test_session_workspace_is_under_root(monkeypatch, tmp_path):
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    assert session_workspace("sid").parent == workspaces_root()


def test_session_meta_round_trip(tmp_path):
    write_session_meta(tmp_path, mode="container")
    assert read_session_meta(tmp_path) == {"mode": "container"}


def test_session_meta_local(tmp_path):
    write_session_meta(tmp_path, mode="local")
    assert read_session_meta(tmp_path) == {"mode": "local"}


def test_read_session_meta_missing_returns_empty(tmp_path):
    assert read_session_meta(tmp_path) == {}
