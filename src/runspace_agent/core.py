"""Core orchestration for runspace_agent.

Defines :class:`RunspaceSession` (configuration), :class:`RunspaceResult`
(output), and :func:`run_agent` (the top-level entry point).
"""

from __future__ import annotations

import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from runspace_agent.agents.base import AgentResult, FilesystemAgent
from runspace_agent.skills import Skill


class RunspaceSession(BaseModel):
    """Configuration for a single agent execution session.

    At minimum you must provide ``editable_dir``, ``context_dir``, and
    ``prompt``.  Everything else has sensible defaults.

    Attributes:
        editable_dir: Directory the agent will modify.
        context_dir: Read-only context directory (traces, domain knowledge, ...).
        prompt: Task-specific instructions for the agent.
        editable_description: Optional description of what editable_dir contains.
        context_description: Optional description of what context_dir contains.
        agent: A :class:`FilesystemAgent` instance.  When ``None``,
            a default agent is created via :func:`~runspace_agent.agents.create_default_agent`.
        agent_options: A :class:`~claude_code_sdk.ClaudeCodeOptions` instance
            passed to the default agent when ``agent`` is ``None``.
        skills_dir: Optional directory of custom skills to load into the workspace.
        preinstalled_skills: Which preinstalled skills to include.
            ``None`` (default) includes all.  An explicit list filters
            by name (e.g. ``["mcp-builder"]``).  ``[]`` skips all.
        mode: Execution mode — ``"local"`` or ``"container"``.
        output_zip: Whether to zip the editable directory after the agent runs.
        container_image: Docker image for container mode.
        container_memory: Memory limit for the container.
        container_cpus: CPU limit for the container.
        container_mode: ``"ephemeral"`` (new container per run) or
            ``"persistent"`` (long-running container, docker exec per job).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    editable_dir: Path
    context_dir: Path
    prompt: str
    editable_description: str = ""
    context_description: str = ""
    agent: Any = None  # FilesystemAgent instance
    agent_options: Any = None  # ClaudeCodeOptions instance
    skills_dir: Path | None = None
    preinstalled_skills: list[str] | None = None
    mode: Literal["local", "container"] = "local"
    output_zip: bool = False
    # Container settings
    container_image: str = "runspace-agent:latest"
    container_memory: str = "4g"
    container_cpus: int = 2
    container_mode: Literal["ephemeral", "persistent"] = "ephemeral"


@dataclass
class RunspaceResult:
    """Result of an agent execution session.

    Attributes:
        success: Whether the agent completed successfully.
        session_id: Unique identifier for this session.
        output_dir: Path to the editable directory after the agent ran.
        output_zip_path: Path to the zipped output, if ``output_zip`` was True.
        agent_result: Detailed result from the agent execution.
        duration_seconds: Total wall-clock time for the session.
    """

    success: bool
    session_id: str
    output_dir: Path
    output_zip_path: Path | None
    agent_result: AgentResult
    duration_seconds: float


def _resolve_agent(session: RunspaceSession) -> FilesystemAgent:
    """Return the session's agent, or create a default via the agent factory."""
    if session.agent is not None:
        return session.agent  # type: ignore[return-value]
    from runspace_agent.agents import create_default_agent

    return create_default_agent(options=session.agent_options)


async def run_agent(
    session: RunspaceSession,
    session_id: str | None = None,
) -> RunspaceResult:
    """Execute an agent session.

    This is the main entry point for the library.  It validates inputs,
    prepares the workspace, runs the agent, and returns the result.

    Parameters:
        session: A :class:`RunspaceSession` describing what to run.
        session_id: Optional pre-generated session ID.  When called from
            the server, the API layer passes its own ID so that the
            in-memory record and the on-disk workspace share the same
            identifier.  When ``None`` a random ID is generated.

    Returns:
        A :class:`RunspaceResult` with the outcome.
    """
    start = time.monotonic()
    if session_id is None:
        session_id = uuid.uuid4().hex[:12]

    # Validate directories
    if not session.editable_dir.is_dir():
        return RunspaceResult(
            success=False,
            session_id=session_id,
            output_dir=session.editable_dir,
            output_zip_path=None,
            agent_result=AgentResult(
                success=False,
                error=f"editable_dir does not exist: {session.editable_dir}",
            ),
            duration_seconds=0.0,
        )
    if not session.context_dir.is_dir():
        return RunspaceResult(
            success=False,
            session_id=session_id,
            output_dir=session.editable_dir,
            output_zip_path=None,
            agent_result=AgentResult(
                success=False,
                error=f"context_dir does not exist: {session.context_dir}",
            ),
            duration_seconds=0.0,
        )

    agent = _resolve_agent(session)

    # Dispatch to execution backend
    if session.mode == "local":
        from runspace_agent.local import run_local

        agent_result = await run_local(session, agent, session_id)
    elif session.mode == "container":
        from runspace_agent.container import run_container

        agent_result = await run_container(session, agent, session_id)
    else:
        agent_result = AgentResult(
            success=False,
            error=f"Unknown mode: {session.mode}",
        )

    # Optionally zip the output
    output_zip_path: Path | None = None
    if session.output_zip and agent_result.success:
        zip_path = session.editable_dir.parent / f"{session.editable_dir.name}.zip"
        shutil.make_archive(
            str(zip_path.with_suffix("")),  # base name without .zip
            "zip",
            root_dir=str(session.editable_dir.parent),
            base_dir=session.editable_dir.name,
        )
        output_zip_path = zip_path

    duration = time.monotonic() - start
    return RunspaceResult(
        success=agent_result.success,
        session_id=session_id,
        output_dir=session.editable_dir,
        output_zip_path=output_zip_path,
        agent_result=agent_result,
        duration_seconds=round(duration, 2),
    )
