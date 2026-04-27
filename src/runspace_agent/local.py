"""Local execution backend.

Runs the agent directly on the host machine inside a temporary session
workspace.  A sandbox hook restricts file access to the session directory.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from runspace_agent.agents.base import AgentResult, FilesystemAgent, Workspace
from runspace_agent.prompt import build_prompt
from runspace_agent.sandbox import build_hooks_config
from runspace_agent.skills import prepare_skills

if TYPE_CHECKING:
    from runspace_agent.core import RunspaceSession


async def run_local(
    session: RunspaceSession,
    agent: FilesystemAgent,
    session_id: str,
) -> AgentResult:
    """Run the agent locally in a temporary session workspace.

    The workspace layout is::

        {temp}/runspace_{session_id}/
            editable/          <- copy of session.editable_dir (agent modifies this)
            editable_original/ <- snapshot before agent runs (for diff)
            context/           <- copy of session.context_dir

    After the agent completes, modified files from ``editable/`` are
    copied back to the original ``session.editable_dir``.

    The session workspace is **not** deleted so it can be inspected
    later (the server's session manager handles cleanup).
    """
    # Create session workspace with isolated agent subdirectory.
    # The agent runs inside agent_workspace/ and is sandboxed there,
    # so it cannot touch session-level files like editable_original/.
    temp_base = Path(tempfile.gettempdir())
    workspace_root = temp_base / f"runspace_{session_id}"
    workspace_root.mkdir(parents=True, exist_ok=True)

    agent_workspace = workspace_root / "agent_workspace"
    agent_workspace.mkdir(parents=True, exist_ok=True)

    editable_workspace = agent_workspace / "editable"
    context_workspace = agent_workspace / "context"

    # Copy directories into agent workspace
    shutil.copytree(session.editable_dir, editable_workspace)
    shutil.copytree(session.context_dir, context_workspace)

    # Snapshot the original editable OUTSIDE agent reach (for diff)
    editable_original = workspace_root / "editable_original"
    shutil.copytree(editable_workspace, editable_original)

    # Prepare skills inside agent workspace
    skills_dir = prepare_skills(
        skills_dir=session.skills_dir,
        default_skills_dir=agent.default_skills_dir,
        workspace_root=agent_workspace,
        folder_name=agent.skills_folder_name,
        preinstalled_skills=session.preinstalled_skills,
    )

    # Build sandbox hooks to restrict agent to its workspace only
    hooks = build_hooks_config(agent_workspace)

    # Build the enriched prompt
    prompt = build_prompt(
        editable_dir=editable_workspace,
        context_dir=context_workspace,
        user_prompt=session.prompt,
        editable_description=session.editable_description,
        context_description=session.context_description,
        extra_summary_sections=session.extra_summary_sections,
    )

    prompt_path = workspace_root / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    # Create workspace and run agent
    workspace = Workspace(
        editable_dir=editable_workspace,
        context_dir=context_workspace,
        prompt=prompt,
        skills_dir=skills_dir,
        cwd=agent_workspace,
        hooks=hooks,
    )

    result = await agent.run(workspace)

    # Persist conversation at session root (outside agent reach)
    if result.conversation:
        conv_path = workspace_root / "conversation.json"
        conv_path.write_text(
            json.dumps(result.conversation, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Copy modified editable back to original location
    if result.success and editable_workspace.is_dir():
        _sync_back(editable_workspace, session.editable_dir)

    return result


def _sync_back(source: Path, target: Path) -> None:
    """Overwrite *target* with the contents of *source*.

    Removes the existing target and replaces it entirely.
    """
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
