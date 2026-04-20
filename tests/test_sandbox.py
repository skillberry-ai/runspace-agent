"""Tests for runspace_agent.sandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from runspace_agent.sandbox import _is_inside, make_sandbox_hook


def test_is_inside_accepts_child(tmp_path: Path) -> None:
    child = tmp_path / "editable" / "file.py"
    child.parent.mkdir(parents=True, exist_ok=True)
    child.touch()
    assert _is_inside(str(child), tmp_path)


def test_is_inside_rejects_outside(tmp_path: Path) -> None:
    outside = tmp_path.parent / "other_dir"
    assert not _is_inside(str(outside), tmp_path)


def test_is_inside_accepts_same_dir(tmp_path: Path) -> None:
    assert _is_inside(str(tmp_path), tmp_path)


@pytest.mark.asyncio
async def test_sandbox_hook_allows_inside(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"file_path": str(tmp_path / "editable" / "file.py")},
        "Write",
        None,
    )
    assert result == {}


@pytest.mark.asyncio
async def test_sandbox_hook_blocks_outside(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    outside = str(tmp_path.parent / "secret.txt")
    result = await hook(
        {"file_path": outside},
        "Write",
        None,
    )
    assert result.get("decision") == "block"
    assert "outside the session directory" in result.get("systemMessage", "")


@pytest.mark.asyncio
async def test_sandbox_hook_blocks_bash_outside(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    # Use an absolute path that's outside the session on any platform
    outside = str(tmp_path.parent / "secret.txt")
    result = await hook(
        {"command": f"cat {outside}"},
        "Bash",
        None,
    )
    assert result.get("decision") == "block"


@pytest.mark.asyncio
async def test_sandbox_hook_allows_bash_inside(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"command": f"ls {tmp_path / 'editable'}"},
        "Bash",
        None,
    )
    assert result == {}


@pytest.mark.asyncio
async def test_sandbox_hook_blocks_glob_outside(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"path": str(tmp_path.parent / "other")},
        "Glob",
        None,
    )
    assert result.get("decision") == "block"


@pytest.mark.asyncio
async def test_sandbox_hook_blocks_relative_traversal(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"command": "cat ../editable_original/secret.txt"},
        "Bash",
        None,
    )
    assert result.get("decision") == "block"
    assert "path traversal" in result.get("systemMessage", "")


@pytest.mark.asyncio
async def test_sandbox_hook_blocks_cd_dotdot(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"command": "cd .. && ls"},
        "Bash",
        None,
    )
    assert result.get("decision") == "block"


@pytest.mark.asyncio
async def test_sandbox_hook_blocks_dotdot_in_middle(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"command": "cat editable/../../etc/passwd"},
        "Bash",
        None,
    )
    assert result.get("decision") == "block"


@pytest.mark.asyncio
async def test_sandbox_hook_allows_dots_in_filenames(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"command": f"cat {tmp_path / 'file..name.txt'}"},
        "Bash",
        None,
    )
    assert result == {}


@pytest.mark.asyncio
async def test_sandbox_hook_blocks_quoted_dotdot(tmp_path: Path) -> None:
    hook = make_sandbox_hook(tmp_path)
    result = await hook(
        {"command": 'cat "../secret.txt"'},
        "Bash",
        None,
    )
    assert result.get("decision") == "block"
