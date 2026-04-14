"""runspace_agent — Sandboxed execution environment for AI agents.

Provides a simple interface for running AI agents that operate on
filesystem directories: an **editable** directory (the agent's output)
and a **read-only context** directory (traces, domain knowledge, etc.).

Quick start::

    from runspace_agent import RunspaceSession, run_agent

    result = await run_agent(RunspaceSession(
        editable_dir=Path("./my_skill"),
        context_dir=Path("./context"),
        prompt="Improve the skill based on the traces.",
    ))
"""

from runspace_agent.agents.base import AgentResult, FilesystemAgent, Workspace
from runspace_agent.core import RunspaceResult, RunspaceSession, run_agent
from runspace_agent.skills import Skill

__all__ = [
    "AgentResult",
    "FilesystemAgent",
    "RunspaceResult",
    "RunspaceSession",
    "Skill",
    "Workspace",
    "run_agent",
]
