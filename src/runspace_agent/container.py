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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from runspace_agent.agents.base import AgentResult, FilesystemAgent
from runspace_agent.prompt import build_prompt
from runspace_agent.skills import prepare_skills
from runspace_agent.workspaces import session_workspace, write_session_meta

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
        result["mcp_servers"] = (
            dict(mcp_servers) if not isinstance(mcp_servers, (str, Path)) else str(mcp_servers)
        )

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
    """Run the agent inside a fresh, auto-removed Docker container.

    All work (file copies, Docker API calls) is blocking I/O, so we run the
    entire function in a thread to avoid freezing the asyncio event loop.
    """
    import asyncio as _aio

    return await _aio.to_thread(_run_container_blocking, session, agent, session_id)


def _run_container_blocking(
    session: RunspaceSession,
    agent: FilesystemAgent,
    session_id: str,
) -> AgentResult:
    """Spin up a new container, run the agent, tear it down."""
    docker = _import_docker()
    client = docker.from_env()

    # Prepare host-side session workspace with isolated agent subdirectory
    workspace_root = session_workspace(session_id)
    workspace_root.mkdir(parents=True, exist_ok=True)
    write_session_meta(workspace_root, mode="container")

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

    prompt_path = workspace_root / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    # Write entrypoint config at workspace root (outside agent reach)
    config_data = {
        "prompt": prompt,
        "session_id": session_id,
        "agent_type": session.agent_type,
        "cwd": "/workspace/agent_workspace",
        "editable_dir": "/workspace/agent_workspace/editable",
        "context_dir": "/workspace/agent_workspace/context",
        # Remote skills are installed inside the container (its own npx),
        # never on the host.
        "remote_skills": session.remote_skills,
        "npx_agent_name": agent.npx_agent_name,
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
