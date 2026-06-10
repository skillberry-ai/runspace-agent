"""Skill loading and workspace preparation.

Handles discovery of bundled default skills (skill-creator, mcp-builder)
and copying them into the agent's workspace alongside user-provided skills.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    """A named skill directory.

    Attributes:
        name: Human-readable skill name (used as the directory name).
        path: Absolute path to the skill directory on disk.
    """

    name: str
    path: Path


def get_default_skills(skills_dir: Path) -> list[Skill]:
    """Discover skills inside the given directory.

    Returns a :class:`Skill` for each subdirectory inside *skills_dir*.
    Returns an empty list if the directory does not exist.
    """
    if not skills_dir.is_dir():
        return []
    skills: list[Skill] = []
    for child in sorted(skills_dir.iterdir()):
        if child.is_dir():
            skills.append(Skill(name=child.name, path=child))
    return skills


def parse_skill_frontmatter(skill_dir: Path) -> dict[str, str]:
    """Parse YAML frontmatter from a skill's SKILL.md file.

    Returns a dict with ``name`` and ``description`` keys.
    Falls back to the directory name if parsing fails.
    """
    skill_md = skill_dir / "SKILL.md"
    result: dict[str, str] = {"name": skill_dir.name, "description": ""}
    if not skill_md.is_file():
        return result
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return result

    # Extract YAML frontmatter between --- delimiters
    if not text.startswith("---"):
        return result
    end = text.find("---", 3)
    if end == -1:
        return result
    frontmatter = text[3:end]
    for line in frontmatter.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "name":
                result["name"] = value
            elif key == "description":
                result["description"] = value
    return result


def prepare_skills(
    skills_dir: Path | None,
    default_skills_dir: Path | None,
    workspace_root: Path,
    folder_name: str,
    preinstalled_skills: list[str] | None = None,
) -> Path | None:
    """Copy skills into the workspace for the agent to discover.

    Parameters:
        skills_dir: Optional user-provided directory containing custom
            skills.  Each subdirectory is treated as a separate skill.
        default_skills_dir: Optional path to the agent's bundled default
            skills.  ``None`` to skip defaults entirely.
        workspace_root: The session workspace directory.
        folder_name: Agent-specific skills folder name relative to
            *workspace_root* (e.g. ``".claude/skills"``).
        preinstalled_skills: Which preinstalled skills to include.
            Preinstalled skills are **opt-in**: ``None`` (default) or an
            empty list includes none.  Pass an explicit list of names to
            include only those (e.g. ``["mcp-builder"]``).

    Returns:
        The created skills directory path, or ``None`` if no skills
        were loaded.
    """
    if not skills_dir and not default_skills_dir:
        return None

    # Preinstalled skills are opt-in: only included when explicitly named.
    # None (default) or an empty list means "no preinstalled skills".
    if not preinstalled_skills:
        default_skills_dir = None

    if not skills_dir and not default_skills_dir:
        return None

    target = workspace_root / folder_name
    target.mkdir(parents=True, exist_ok=True)

    # Copy the selected preinstalled skills first
    if default_skills_dir:
        for skill in get_default_skills(default_skills_dir):
            if not preinstalled_skills or skill.name not in preinstalled_skills:
                continue
            dest = target / skill.name
            if not dest.exists():
                shutil.copytree(skill.path, dest)

    # Copy user-provided skills (may override defaults)
    if skills_dir and skills_dir.is_dir():
        for child in skills_dir.iterdir():
            if child.is_dir():
                dest = target / child.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(child, dest)

    return target
