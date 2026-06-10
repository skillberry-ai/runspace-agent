"""Tests for runspace_agent.skills."""

from __future__ import annotations

from pathlib import Path

from runspace_agent.skills import prepare_skills


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
        default_skills_dir=None,
        workspace_root=workspace,
        folder_name=".claude/skills",
    )

    assert result is not None
    assert (result / "skill_a" / "SKILL.md").read_text() == "# Skill A"


def _make_default_skills(tmp_path: Path) -> Path:
    """Create a default-skills dir with two named skills."""
    defaults = tmp_path / "defaults"
    for name in ("skill-creator", "mcp-builder"):
        d = defaults / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}", encoding="utf-8")
    return defaults


def test_preinstalled_skills_excluded_by_default(tmp_path: Path) -> None:
    """Preinstalled skills are opt-in: None includes none."""
    defaults = _make_default_skills(tmp_path)
    workspace = tmp_path / "ws"
    workspace.mkdir()

    result = prepare_skills(
        skills_dir=None,
        default_skills_dir=defaults,
        workspace_root=workspace,
        folder_name=".claude/skills",
        preinstalled_skills=None,
    )

    assert result is None


def test_preinstalled_skills_selected_by_name(tmp_path: Path) -> None:
    """Only explicitly named preinstalled skills are included."""
    defaults = _make_default_skills(tmp_path)
    workspace = tmp_path / "ws"
    workspace.mkdir()

    result = prepare_skills(
        skills_dir=None,
        default_skills_dir=defaults,
        workspace_root=workspace,
        folder_name=".claude/skills",
        preinstalled_skills=["mcp-builder"],
    )

    assert result is not None
    assert (result / "mcp-builder" / "SKILL.md").exists()
    assert not (result / "skill-creator").exists()


def test_prepare_skills_no_skills(tmp_path: Path) -> None:
    """prepare_skills returns None when no skills are provided."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = prepare_skills(
        skills_dir=None,
        default_skills_dir=None,
        workspace_root=workspace,
        folder_name=".claude/skills",
    )

    assert result is None


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
        default_skills_dir=None,
        workspace_root=workspace,
        folder_name=".opencode/skills",
    )

    assert result is not None
    assert result == workspace / ".opencode" / "skills"
    assert (result / "my_skill" / "SKILL.md").exists()
