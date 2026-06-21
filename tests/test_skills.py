"""Tests for runspace_agent.skills."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from runspace_agent.skills import install_remote_skills, prepare_skills


def test_prepare_skills_with_user_dir(tmp_path: Path) -> None:
    """prepare_skills copies user skills into the workspace."""
    # Create user skills
    user_skills = tmp_path / "my_skills"
    user_skills.mkdir()
    skill_a = user_skills / "skill_a"
    skill_a.mkdir()
    (skill_a / "SKILL.md").write_text("# Skill A", encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = prepare_skills(
        skills_dir=user_skills,
        workspace_root=workspace,
        folder_name=".claude/skills",
    )

    assert result is not None
    assert (result / "skill_a" / "SKILL.md").read_text() == "# Skill A"


def test_prepare_skills_no_skills_dir(tmp_path: Path) -> None:
    """prepare_skills returns None when no skills_dir is provided."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = prepare_skills(
        skills_dir=None,
        workspace_root=workspace,
        folder_name=".claude/skills",
    )

    assert result is None


def test_prepare_skills_missing_dir(tmp_path: Path) -> None:
    """prepare_skills returns None when skills_dir does not exist."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = prepare_skills(
        skills_dir=tmp_path / "nonexistent",
        workspace_root=workspace,
        folder_name=".claude/skills",
    )

    assert result is None


def test_prepare_skills_replaces_existing(tmp_path: Path) -> None:
    """A re-copied skill replaces any existing copy in the target."""
    user_skills = tmp_path / "skills"
    skill = user_skills / "my_skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("new content", encoding="utf-8")

    workspace = tmp_path / "ws"
    workspace.mkdir()
    # Pre-seed a stale copy in the target.
    stale = workspace / ".claude" / "skills" / "my_skill"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("stale", encoding="utf-8")
    (stale / "old.txt").write_text("leftover", encoding="utf-8")

    result = prepare_skills(
        skills_dir=user_skills,
        workspace_root=workspace,
        folder_name=".claude/skills",
    )

    assert result is not None
    assert (result / "my_skill" / "SKILL.md").read_text() == "new content"
    # The stale extra file is gone after replacement.
    assert not (result / "my_skill" / "old.txt").exists()


def test_prepare_skills_creates_folder_structure(tmp_path: Path) -> None:
    """prepare_skills creates nested folder structure."""
    user_skills = tmp_path / "skills"
    user_skills.mkdir()
    s = user_skills / "my_skill"
    s.mkdir()
    (s / "SKILL.md").write_text("test", encoding="utf-8")

    workspace = tmp_path / "ws"
    workspace.mkdir()

    result = prepare_skills(
        skills_dir=user_skills,
        workspace_root=workspace,
        folder_name=".opencode/skills",
    )

    assert result is not None
    assert result == workspace / ".opencode" / "skills"
    assert (result / "my_skill" / "SKILL.md").exists()


def test_install_remote_skills_noop_when_empty(tmp_path: Path) -> None:
    """No sources is a no-op that returns None."""
    assert (
        install_remote_skills(
            remote_skills=None,
            agent_workspace=tmp_path,
            npx_agent_name="claude",
            folder_name=".claude/skills",
        )
        is None
    )
    assert (
        install_remote_skills(
            remote_skills=[],
            agent_workspace=tmp_path,
            npx_agent_name="claude",
            folder_name=".claude/skills",
        )
        is None
    )


def test_install_remote_skills_requires_npx_agent_name(tmp_path: Path) -> None:
    """An agent without an npx_agent_name cannot install remote skills."""
    with pytest.raises(RuntimeError, match="npx_agent_name"):
        install_remote_skills(
            remote_skills=["owner/repo"],
            agent_workspace=tmp_path,
            npx_agent_name=None,
            folder_name=".claude/skills",
        )


def test_install_remote_skills_requires_npx(tmp_path: Path, monkeypatch) -> None:
    """A missing npx on PATH raises a clear error."""
    monkeypatch.setattr("runspace_agent.skills.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="npx"):
        install_remote_skills(
            remote_skills=["owner/repo"],
            agent_workspace=tmp_path,
            npx_agent_name="claude",
            folder_name=".claude/skills",
        )


def test_install_remote_skills_builds_command(tmp_path: Path, monkeypatch) -> None:
    """Each source is installed with the expected npx argv and cwd."""
    monkeypatch.setattr("runspace_agent.skills.shutil.which", lambda _: "/usr/bin/npx")

    calls: list[dict] = []

    def fake_run(cmd, cwd, capture_output, text):  # noqa: ANN001
        calls.append({"cmd": cmd, "cwd": cwd})
        # Simulate the CLI creating the skills folder.
        (tmp_path / ".claude" / "skills" / "demo").mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("runspace_agent.skills.subprocess.run", fake_run)

    result = install_remote_skills(
        remote_skills=["owner/repo", "vercel-labs/agent-skills"],
        agent_workspace=tmp_path,
        npx_agent_name="claude",
        folder_name=".claude/skills",
    )

    assert result == tmp_path / ".claude" / "skills"
    assert len(calls) == 2
    cmd = calls[0]["cmd"]
    assert cmd[:5] == ["npx", "-y", "skills@latest", "add", "owner/repo"]
    assert "-a" in cmd and cmd[cmd.index("-a") + 1] == "claude"
    assert "--copy" in cmd
    assert calls[0]["cwd"] == str(tmp_path)


def test_install_remote_skills_raises_on_failure(tmp_path: Path, monkeypatch) -> None:
    """A non-zero npx exit fails the run, naming the source."""
    monkeypatch.setattr("runspace_agent.skills.shutil.which", lambda _: "/usr/bin/npx")

    def fake_run(cmd, cwd, capture_output, text):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

    monkeypatch.setattr("runspace_agent.skills.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="bad/repo"):
        install_remote_skills(
            remote_skills=["bad/repo"],
            agent_workspace=tmp_path,
            npx_agent_name="claude",
            folder_name=".claude/skills",
        )


def test_install_remote_skills_cleans_scaffolding(tmp_path: Path, monkeypatch) -> None:
    """node_modules and lockfiles left by the CLI are removed afterwards."""
    monkeypatch.setattr("runspace_agent.skills.shutil.which", lambda _: "/usr/bin/npx")

    def fake_run(cmd, cwd, capture_output, text):  # noqa: ANN001
        (tmp_path / ".claude" / "skills" / "demo").mkdir(parents=True, exist_ok=True)
        (tmp_path / "node_modules").mkdir(exist_ok=True)
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (tmp_path / "skills-lock.json").write_text("{}", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("runspace_agent.skills.subprocess.run", fake_run)

    install_remote_skills(
        remote_skills=["owner/repo"],
        agent_workspace=tmp_path,
        npx_agent_name="claude",
        folder_name=".claude/skills",
    )

    assert not (tmp_path / "node_modules").exists()
    assert not (tmp_path / "package.json").exists()
    assert not (tmp_path / "skills-lock.json").exists()
    assert (tmp_path / ".claude" / "skills" / "demo").exists()
