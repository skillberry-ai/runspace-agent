"""Docker container execution backend.

Supports two modes:

* **Ephemeral** — a new container per ``run_agent()`` call.  The container
  is removed after the agent finishes; the session workspace on the host
  persists for inspection.

* **Persistent** — one long-running container.  Each job creates a
  ``/workspace/{session_id}/`` directory inside the container and uses
  ``docker exec`` to run the agent process.  PreToolUse hooks enforce
  per-session isolation.

Requires the optional ``docker`` dependency::

    uv pip install runspace-agent[container]
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from runspace_agent.agents.base import AgentResult, FilesystemAgent
from runspace_agent.prompt import build_prompt
from runspace_agent.skills import prepare_skills

if TYPE_CHECKING:
    from runspace_agent.core import RunspaceSession


def _serialize_agent_options(agent_options: Any) -> dict[str, Any]:
    """Extract JSON-serializable fields from a ClaudeCodeOptions for the container config.

    The entrypoint inside the container reads these and reconstructs a
    ClaudeCodeOptions object.
    """
    if agent_options is None:
        return {}

    result: dict[str, Any] = {}
    settings: dict[str, Any] = {}

    env = getattr(agent_options, "env", None)
    if env:
        settings["env"] = dict(env)

    model = getattr(agent_options, "model", None)
    if model:
        settings["model"] = model

    allowed_tools = getattr(agent_options, "allowed_tools", None)
    if allowed_tools:
        settings.setdefault("permissions", {})["allow"] = list(allowed_tools)

    disallowed_tools = getattr(agent_options, "disallowed_tools", None)
    if disallowed_tools:
        settings.setdefault("permissions", {})["disallow"] = list(disallowed_tools)

    if settings:
        result["settings"] = settings

    max_turns = getattr(agent_options, "max_turns", None)
    if max_turns is not None:
        result["max_turns"] = max_turns

    mcp_servers = getattr(agent_options, "mcp_servers", None)
    if mcp_servers:
        result["mcp_servers"] = dict(mcp_servers) if not isinstance(mcp_servers, (str, Path)) else str(mcp_servers)

    return result


def _import_docker() -> Any:
    try:
        import docker  # type: ignore[import-untyped]
    except ImportError:
        raise ImportError(
            "Container mode requires the 'docker' package. "
            "Install it with:  uv pip install runspace-agent[container]"
        ) from None
    return docker


async def run_container(
    session: RunspaceSession,
    agent: FilesystemAgent,
    session_id: str,
) -> AgentResult:
    """Run the agent inside a Docker container."""
    if session.container_mode == "ephemeral":
        return await _run_ephemeral(session, agent, session_id)
    elif session.container_mode == "persistent":
        return await _run_persistent(session, agent, session_id)
    else:
        return AgentResult(
            success=False,
            error=f"Unknown container_mode: {session.container_mode}",
        )


async def _run_ephemeral(
    session: RunspaceSession,
    agent: FilesystemAgent,
    session_id: str,
) -> AgentResult:
    """Spin up a new container, run the agent, tear it down.

    All work (file copies, Docker API calls) is blocking I/O, so we run
    the entire function in a thread to avoid freezing the asyncio event loop.
    """
    import asyncio as _aio

    return await _aio.to_thread(_run_ephemeral_blocking, session, agent, session_id)


def _run_ephemeral_blocking(
    session: RunspaceSession,
    agent: FilesystemAgent,
    session_id: str,
) -> AgentResult:
    """Synchronous implementation of ephemeral container execution."""
    docker = _import_docker()
    client = docker.from_env()

    # Prepare host-side session workspace with isolated agent subdirectory
    temp_base = Path(tempfile.gettempdir())
    workspace_root = temp_base / f"runspace_{session_id}"
    workspace_root.mkdir(parents=True, exist_ok=True)

    agent_workspace = workspace_root / "agent_workspace"
    agent_workspace.mkdir(parents=True, exist_ok=True)

    editable_workspace = agent_workspace / "editable"
    context_workspace = agent_workspace / "context"
    shutil.copytree(session.editable_dir, editable_workspace)
    shutil.copytree(session.context_dir, context_workspace)

    # Snapshot original editable OUTSIDE agent reach (for diff)
    editable_original = workspace_root / "editable_original"
    shutil.copytree(editable_workspace, editable_original)

    # Prepare skills inside agent workspace
    prepare_skills(
        skills_dir=session.skills_dir,
        default_skills_dir=agent.default_skills_dir,
        workspace_root=agent_workspace,
        folder_name=agent.skills_folder_name,
        preinstalled_skills=session.preinstalled_skills,
    )

    # Build prompt with container-internal paths (agent workspace)
    prompt = build_prompt(
        editable_dir=Path("/workspace/agent_workspace/editable"),
        context_dir=Path("/workspace/agent_workspace/context"),
        user_prompt=session.prompt,
        editable_description=session.editable_description,
        context_description=session.context_description,
        extra_summary_sections=session.extra_summary_sections,
    )

    # Write entrypoint config at workspace root (outside agent reach)
    config_data = {
        "prompt": prompt,
        "session_id": session_id,
        "agent_type": session.agent_type,
        "cwd": "/workspace/agent_workspace",
        "editable_dir": "/workspace/agent_workspace/editable",
        "context_dir": "/workspace/agent_workspace/context",
    }

    # Include agent options in the config for the in-container entrypoint
    config_data.update(_serialize_agent_options(session.agent_options))

    config_path = workspace_root / "config.json"
    config_path.write_text(json.dumps(config_data), encoding="utf-8")

    # Build environment variables from agent options
    env_vars: dict[str, str] = {}
    if session.agent_options is not None:
        opt_env = getattr(session.agent_options, "env", None)
        if opt_env:
            env_vars.update({k: str(v) for k, v in opt_env.items()})
    env_vars["RUNSPACE_CONFIG"] = "/workspace/config.json"

    container = client.containers.run(
        image=session.container_image,
        command=["python", "-m", "runspace_agent.entrypoint"],
        volumes={
            str(workspace_root): {"bind": "/workspace", "mode": "rw"},
        },
        environment=env_vars,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        mem_limit=session.container_memory,
        nano_cpus=int(session.container_cpus * 1e9),
        detach=False,
        stdout=True,
        stderr=True,
        remove=True,  # Auto-remove container after it exits
    )

    # Parse the output
    output = container.decode("utf-8") if isinstance(container, bytes) else str(container)
    result_data = json.loads(output.strip().split("\n")[-1])
    agent_result = AgentResult(
        success=result_data.get("success", False),
        messages=result_data.get("messages", []),
        total_tokens=result_data.get("total_tokens", 0),
        duration_ms=result_data.get("duration_ms", 0),
        error=result_data.get("error"),
    )

    # In container mode, do NOT sync files back to the original directory.
    # The modified files live in the workspace and can be downloaded via the API.
    # This keeps the original editable directory untouched so runs are repeatable.

    return agent_result


async def _run_persistent(
    session: RunspaceSession,
    agent: FilesystemAgent,
    session_id: str,
) -> AgentResult:
    """Run the agent via docker exec in a persistent container.

    The persistent container must already be running. It is expected to
    have the runspace_agent package installed and a ``/workspace/``
    volume mounted.
    """
    docker = _import_docker()
    client = docker.from_env()

    # Find or verify the persistent container
    container_name = f"runspace-persistent-{session.container_image.replace(':', '-')}"
    try:
        container = client.containers.get(container_name)
        if container.status != "running":
            container.start()
    except docker.errors.NotFound:
        # Start a new persistent container
        container = client.containers.run(
            image=session.container_image,
            name=container_name,
            command=["sleep", "infinity"],
            volumes={},  # No host mounts — files are copied in
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            mem_limit=session.container_memory,
            nano_cpus=int(session.container_cpus * 1e9),
            detach=True,
        )

    # Create session directory with agent workspace inside container
    session_path = f"/workspace/{session_id}"
    agent_path = f"{session_path}/agent_workspace"
    container.exec_run(f"mkdir -p {agent_path}/editable {agent_path}/context")

    # Copy directories into agent workspace
    _copy_to_container(container, session.editable_dir, f"{agent_path}/editable")
    _copy_to_container(container, session.context_dir, f"{agent_path}/context")

    # Build prompt with agent workspace paths
    prompt = build_prompt(
        editable_dir=Path(f"{agent_path}/editable"),
        context_dir=Path(f"{agent_path}/context"),
        user_prompt=session.prompt,
        editable_description=session.editable_description,
        context_description=session.context_description,
        extra_summary_sections=session.extra_summary_sections,
    )

    # Write config at session root (outside agent workspace)
    config_data = {
        "prompt": prompt,
        "session_id": session_id,
        "agent_type": session.agent_type,
        "cwd": agent_path,
        "editable_dir": f"{agent_path}/editable",
        "context_dir": f"{agent_path}/context",
    }
    config_data.update(_serialize_agent_options(session.agent_options))

    config_json = json.dumps(config_data)
    container.exec_run(
        f"bash -c 'echo {json.dumps(config_json)} > {session_path}/config.json'"
    )

    # Build environment for exec
    env_vars: list[str] = [f"RUNSPACE_CONFIG={session_path}/config.json"]
    if session.agent_options is not None:
        opt_env = getattr(session.agent_options, "env", None)
        if opt_env:
            for k, v in opt_env.items():
                env_vars.append(f"{k}={v}")

    # Run the agent inside the agent workspace
    exit_code, output = container.exec_run(
        cmd=["python", "-m", "runspace_agent.entrypoint"],
        environment=env_vars,
        workdir=agent_path,
    )

    output_str = output.decode("utf-8") if isinstance(output, bytes) else str(output)
    result_data = json.loads(output_str.strip().split("\n")[-1])
    agent_result = AgentResult(
        success=result_data.get("success", False),
        messages=result_data.get("messages", []),
        total_tokens=result_data.get("total_tokens", 0),
        duration_ms=result_data.get("duration_ms", 0),
        error=result_data.get("error"),
    )

    # In container mode, do NOT sync files back to the original directory.
    # The modified files live in the workspace and can be downloaded via the API.

    return agent_result


def _copy_to_container(container: Any, local_path: Path, container_path: str) -> None:
    """Copy a local directory into a running container using tar."""
    import io
    import tarfile

    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        tar.add(str(local_path), arcname=".")
    stream.seek(0)
    container.put_archive(container_path, stream)


def _copy_from_container(container: Any, container_path: str, local_path: Path) -> None:
    """Copy a directory from a running container to the local filesystem."""
    import io
    import tarfile

    bits, _ = container.get_archive(container_path)
    stream = io.BytesIO()
    for chunk in bits:
        stream.write(chunk)
    stream.seek(0)

    if local_path.exists():
        shutil.rmtree(local_path)
    local_path.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=stream) as tar:
        tar.extractall(path=str(local_path))
