"""CLI entry point for ``runspace-srv``.

Checks Docker availability, builds the container image if missing,
then starts the FastAPI server.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
            "ERROR: Docker is not running.\nPlease ensure the Docker engine is installed and running, then try again.",
            file=sys.stderr,
        )
        sys.exit(1)


def _ensure_image(docker: str) -> None:
    """Build the runspace-agent Docker image if it doesn't exist."""
    result = subprocess.run(
        [docker, "images", "-q", IMAGE_NAME],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        return  # image exists

    print(f"Docker image '{IMAGE_NAME}' not found. Building...")

    # Find Dockerfile: next to the package root (editable install) or CWD
    dockerfile = _find_dockerfile()
    if not dockerfile:
        print(
            f"ERROR: Cannot find Dockerfile to build '{IMAGE_NAME}'.\n"
            "Either run this command from the runspace-agent repo root,\n"
            "or build the image manually:\n"
            f"  docker build -t {IMAGE_NAME} .",
            file=sys.stderr,
        )
        sys.exit(1)

    build_context = str(dockerfile.parent)
    print(f"Building from {build_context} ...")
    try:
        subprocess.run(
            [docker, "build", "-t", IMAGE_NAME, build_context],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(
            f"\nERROR: Failed to build Docker image '{IMAGE_NAME}'.\n"
            "Check the output above for details.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Image '{IMAGE_NAME}' built successfully.\n")


def _find_dockerfile() -> Path | None:
    """Locate the Dockerfile shipped with the package."""
    # 1. Relative to this file: src/runspace_agent/cli.py -> repo root
    pkg_dir = Path(__file__).resolve().parent  # src/runspace_agent/
    repo_root = pkg_dir.parent.parent  # two levels up
    candidate = repo_root / "Dockerfile"
    if candidate.is_file():
        return candidate

    # 2. Current working directory
    cwd_candidate = Path.cwd() / "Dockerfile"
    if cwd_candidate.is_file():
        return cwd_candidate

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="runspace-srv",
        description="Start the Runspace Agent server (checks Docker first).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
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
    args = parser.parse_args()

    # Propagate session TTL (converted to seconds) to the server via environment variable
    os.environ["RUNSPACE_SESSION_TTL"] = str(args.session_ttl * SECONDS_IN_HOUR)

    # Pre-flight checks
    docker = _docker_bin()
    _check_docker_running(docker)
    _ensure_image(docker)

    # Start the server
    display_host = "localhost" if args.host == "0.0.0.0" else args.host
    print(f"Starting Runspace Agent server on http://{display_host}:{args.port}")
    print(f"  UI:       http://{display_host}:{args.port}/ui")
    print(f"  API docs: http://{display_host}:{args.port}/docs")
    print(f"  ReDoc:    http://{display_host}:{args.port}/redoc\n")

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
        port=args.port,
        reload=args.watch,
    )


if __name__ == "__main__":
    main()
