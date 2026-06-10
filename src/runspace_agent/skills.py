"""Skill loading and workspace preparation.

Handles discovery of bundled default skills (skill-creator, mcp-builder)
and copying them into the agent's workspace alongside user-provided skills.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Scaffolding the `skills` CLI may drop in the workspace root.  We install with
# ``--copy`` (real files, not symlinks), so these are safe to remove afterwards.
_NPX_SCAFFOLDING = ("node_modules", "package.json", "package-lock.json", "skills-lock.json")


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


def install_remote_skills(
    remote_skills: list[str] | None,
    agent_workspace: Path,
    npx_agent_name: str | None,
    folder_name: str,
) -> Path | None:
    """Install remote skills into the agent workspace via ``npx skills add``.

    Each entry of *remote_skills* is a source accepted by the ``skills`` CLI
    (skills.sh): an ``owner/repo`` slug, a GitHub URL, or a repo subpath.  Each
    source is installed at project scope (the CLI default), scoped to the agent
    via *npx_agent_name*, which lands the skills in
    ``agent_workspace / folder_name`` (e.g. ``.claude/skills``).

    Runs in the same environment as the caller, so the host's ``npx`` is used
    for local mode and the container's ``npx`` is used inside the container.

    Parameters:
        remote_skills: Sources to install.  ``None`` or empty is a no-op.
        agent_workspace: The agent's working directory; ``npx skills`` is run
            here so project-scope skills land in ``folder_name`` beneath it.
        npx_agent_name: The ``-a`` value for the CLI (e.g. ``"claude"``).
            ``None`` means the agent has no skills-CLI mapping.
        folder_name: Agent-specific skills folder name relative to
            *agent_workspace* (e.g. ``".claude/skills"``).

    Returns:
        The skills folder path if anything was installed, else ``None``.

    Raises:
        RuntimeError: If the agent has no ``npx_agent_name``, if ``npx`` is not
            available, or if any source fails to install.
    """
    if not remote_skills:
        return None

    if not npx_agent_name:
        raise RuntimeError(
            "remote_skills was provided but this agent has no npx_agent_name, "
            "so it cannot install skills via the `npx skills` CLI."
        )

    if shutil.which("npx") is None:
        raise RuntimeError(
            "remote_skills requires Node.js / `npx` to be available, but `npx` "
            "was not found on PATH. Install Node.js (the container image already "
            "includes it; local mode needs it on the host)."
        )

    agent_workspace.mkdir(parents=True, exist_ok=True)

    for source in remote_skills:
        # `-y` (npx) auto-installs the CLI; `-s *` + `-y` (skills) install all
        # skills from the source non-interactively; `--copy` writes real files.
        cmd = [
            "npx",
            "-y",
            "skills@latest",
            "add",
            source,
            "-a",
            npx_agent_name,
            "-s",
            "*",
            "-y",
            "--copy",
        ]
        proc = subprocess.run(
            cmd,
            cwd=str(agent_workspace),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to install remote skill source {source!r} "
                f"(npx skills exited {proc.returncode}).\n{proc.stderr.strip()}"
            )

    # Remove the scaffolding the CLI leaves behind so the agent's cwd stays
    # tidy; the `--copy`'d skills under folder_name are self-contained.
    for name in _NPX_SCAFFOLDING:
        leftover = agent_workspace / name
        if leftover.is_dir():
            shutil.rmtree(leftover, ignore_errors=True)
        elif leftover.exists():
            leftover.unlink()

    target = agent_workspace / folder_name
    return target if target.is_dir() else None
