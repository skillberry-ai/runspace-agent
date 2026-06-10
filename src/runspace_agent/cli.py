"""CLI entry point for ``runspace-srv``.

Starts the FastAPI server. Sessions default to Docker container execution,
running the Docker pre-flight (daemon check + image build) before serving.
Pass ``--no-docker`` to run sessions locally on the host instead.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_PORT = 6767
DEFAULT_HOST = "0.0.0.0"
DEFAULT_SESSION_TTL_HOURS = 8
SECONDS_IN_HOUR = 3600
IMAGE_NAME = "runspace-agent:latest"


def _docker_bin() -> str:
    """Return the path to the docker CLI, or exit with a helpful message."""
    path = shutil.which("docker")
    if not path:
        print(
            "ERROR: 'docker' command not found.\n"
            "Install Docker Desktop (https://www.docker.com/products/docker-desktop/) "
            "and make sure it is on your PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    return path


def _check_docker_running(docker: str) -> None:
    """Verify the Docker daemon is reachable."""
    try:
        subprocess.run(
            [docker, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError:
        print(
            "ERROR: Docker is not running.\n"
            "Please ensure the Docker engine is installed and running, then try again.",
            file=sys.stderr,
        )
        sys.exit(1)


def _ensure_image(docker: str, *, force_rebuild: bool = False) -> None:
    """Build the runspace-agent Docker image if it doesn't exist or rebuild is forced."""
    if not force_rebuild:
        result = subprocess.run(
            [docker, "images", "-q", IMAGE_NAME],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            return  # image exists

    action = "Rebuilding" if force_rebuild else "Building"
    print(f"{action} Docker image '{IMAGE_NAME}'...")

    # Assemble a self-contained build context from the installed package so the
    # build works regardless of how runspace-agent was installed (editable, git,
    # or wheel) and from any working directory.
    build_context = _prepare_build_context()
    try:
        print(f"Building from {build_context} ...")
        subprocess.run(
            [docker, "build", "-t", IMAGE_NAME, str(build_context)],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(
            f"\nERROR: Failed to build Docker image '{IMAGE_NAME}'.\n"
            "Check the output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)
    finally:
        shutil.rmtree(build_context, ignore_errors=True)

    print(f"Image '{IMAGE_NAME}' built successfully.\n")


# Runtime deps to fall back on if package metadata is unavailable (these mirror
# the base dependencies + the [claude] extra in pyproject.toml).
_FALLBACK_REQUIREMENTS = ["pydantic>=2.0", "claude-code-sdk>=0.0.25"]


def _runtime_requirements() -> list[str]:
    """Return the deps the in-container agent needs: base + the ``claude`` extra.

    Read from the installed distribution metadata so the list never drifts from
    pyproject.toml. Entries with no environment marker are base dependencies;
    entries marked ``extra == "claude"`` are the claude extra. Everything else
    (server/container/examples/dev/all extras) is excluded — the container only
    runs ``python -m runspace_agent.entrypoint``.
    """
    try:
        from importlib.metadata import requires

        raw = requires("runspace-agent") or []
    except Exception:
        return list(_FALLBACK_REQUIREMENTS)

    reqs: list[str] = []
    for entry in raw:
        spec, _, marker = entry.partition(";")
        marker = marker.strip()
        if not marker:
            reqs.append(spec.strip())  # base dependency
        elif 'extra == "claude"' in marker or "extra == 'claude'" in marker:
            reqs.append(spec.strip())  # the claude extra
    return reqs or list(_FALLBACK_REQUIREMENTS)


def _prepare_build_context() -> Path:
    """Assemble a temporary Docker build context from the installed package.

    Layout produced (consumed by ``_docker/Dockerfile``):
        <ctx>/Dockerfile        the shipped build recipe
        <ctx>/requirements.txt  base + claude runtime deps
        <ctx>/runspace_agent/   the installed package source tree
    """
    pkg_dir = Path(__file__).resolve().parent  # the installed runspace_agent/ package
    ctx = Path(tempfile.mkdtemp(prefix="runspace-build-"))

    shutil.copytree(
        pkg_dir,
        ctx / "runspace_agent",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy(pkg_dir / "_docker" / "Dockerfile", ctx / "Dockerfile")
    (ctx / "requirements.txt").write_text(
        "\n".join(_runtime_requirements()) + "\n", encoding="utf-8"
    )
    return ctx


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="runspace-srv",
        description=(
            "Start the Runspace Agent server "
            "(container execution by default; --no-docker for local mode)."
        ),
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host to bind to (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Enable auto-reload on code changes (disabled by default)",
    )
    parser.add_argument(
        "--session-ttl",
        type=int,
        default=DEFAULT_SESSION_TTL_HOURS,
        help=f"Session TTL in hours before cleanup (default: {DEFAULT_SESSION_TTL_HOURS})",
    )
    parser.add_argument(
        "--docker",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run sessions in Docker containers (the default) and run the Docker "
            "pre-flight (daemon check + image build) before starting. Pass "
            "--no-docker to run sessions locally on the host instead, with no "
            "Docker dependency."
        ),
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild of the Docker image before starting (implies --docker)",
    )
    args = parser.parse_args()

    # Port is environment-only (no CLI flag): set RUNSPACE_PORT to change it.
    port = int(os.environ.get("RUNSPACE_PORT", DEFAULT_PORT))

    # Propagate session TTL (converted to seconds) to the server via environment variable
    os.environ["RUNSPACE_SESSION_TTL"] = str(args.session_ttl * SECONDS_IN_HOUR)

    # Container mode is the default; --no-docker switches to local. --rebuild
    # implies Docker. This becomes the server's default session mode for any
    # /run request that doesn't specify one explicitly.
    docker_enabled = args.docker or args.rebuild
    os.environ["RUNSPACE_DEFAULT_MODE"] = "container" if docker_enabled else "local"

    # Docker pre-flight (skipped with --no-docker)
    if docker_enabled:
        docker = _docker_bin()
        _check_docker_running(docker)
        _ensure_image(docker, force_rebuild=args.rebuild)

    # Start the server
    display_host = "localhost" if args.host == "0.0.0.0" else args.host
    print(f"Starting Runspace Agent server on http://{display_host}:{port}")
    print(f"  UI:       http://{display_host}:{port}/ui")
    print(f"  API docs: http://{display_host}:{port}/docs")
    print(f"  ReDoc:    http://{display_host}:{port}/redoc\n")

    try:
        import uvicorn
    except ImportError:
        print(
            "ERROR: uvicorn is not installed.\n"
            "Install the server extra:  pip install runspace-agent[server]",
            file=sys.stderr,
        )
        sys.exit(1)

    uvicorn.run(
        "runspace_agent.server.app:app",
        host=args.host,
        port=port,
        reload=args.watch,
    )


if __name__ == "__main__":
    main()
