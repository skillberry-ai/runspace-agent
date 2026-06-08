"""Tests for the Docker build-context assembly in runspace_agent.cli.

These exercise the logic that makes `runspace-srv --docker` build the image after
any install (editable, git, wheel) without a repo checkout. No Docker required.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from runspace_agent import cli


def test_runtime_requirements_includes_base_and_claude_only() -> None:
    """Base deps + the claude extra are kept; other extras are excluded."""
    reqs = cli._runtime_requirements()
    joined = " ".join(reqs)

    assert any(r.startswith("pydantic") for r in reqs)
    assert any("claude-code-sdk" in r for r in reqs)

    # No environment markers should survive.
    assert ";" not in joined
    # server / container / examples / dev / all extras must not leak in.
    for excluded in ("fastapi", "uvicorn", "docker>", "mcp>", "pytest"):
        assert excluded not in joined


def test_runtime_requirements_falls_back_when_metadata_missing(monkeypatch) -> None:
    """If distribution metadata is unavailable, fall back to the known deps."""
    import importlib.metadata as md

    def _boom(_name: str):
        raise md.PackageNotFoundError

    monkeypatch.setattr(md, "requires", _boom)
    assert cli._runtime_requirements() == cli._FALLBACK_REQUIREMENTS


def test_prepare_build_context_is_self_contained() -> None:
    """The assembled context has everything the shipped Dockerfile needs."""
    ctx = cli._prepare_build_context()
    try:
        assert (ctx / "Dockerfile").is_file()
        assert (ctx / "requirements.txt").is_file()
        # The package source is copied in and importable from the context.
        assert (ctx / "runspace_agent" / "entrypoint.py").is_file()
        assert (ctx / "runspace_agent" / "cli.py").is_file()

        # requirements.txt carries the runtime deps.
        reqs = (ctx / "requirements.txt").read_text(encoding="utf-8")
        assert "pydantic" in reqs
        assert "claude-code-sdk" in reqs

        # Build noise should not be copied along.
        assert not (ctx / "runspace_agent" / "__pycache__").exists()
    finally:
        shutil.rmtree(ctx, ignore_errors=True)


def test_packaged_dockerfile_ships_with_the_package() -> None:
    """The Dockerfile lives inside the package so it travels in the wheel."""
    pkg_dir = Path(cli.__file__).resolve().parent
    assert (pkg_dir / "_docker" / "Dockerfile").is_file()
