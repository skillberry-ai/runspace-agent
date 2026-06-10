"""Host-side locations for session workspaces.

All session workspaces live under a single parent directory in the system temp
location::

    {temp}/runspace/
        {session_id}/
            agent_workspace/   <- editable/ + context/ + skills
            editable_original/ <- pre-run snapshot (for diff)
            ...

Keeping every session under one ``runspace/`` folder (rather than scattering
``runspace_<id>`` folders directly in temp) keeps the temp dir tidy and makes
the orphan scan a single ``iterdir`` of one directory.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

WORKSPACES_DIRNAME = "runspace"

# Session-level metadata file written at the workspace root. It records how the
# session ran (e.g. its execution mode) so the orphan scan can recover that info
# for sessions left over from a previous server process.
SESSION_META_FILE = "session_meta.json"


def workspaces_root() -> Path:
    """Return the parent directory that holds every session workspace."""
    return Path(tempfile.gettempdir()) / WORKSPACES_DIRNAME


def session_workspace(session_id: str) -> Path:
    """Return the workspace directory for a single session."""
    return workspaces_root() / session_id


def write_session_meta(
    workspace_root: Path, *, mode: str, container_mode: str | None = None
) -> None:
    """Persist session metadata (execution mode) at the workspace root."""
    meta: dict[str, str] = {"mode": mode}
    if container_mode:
        meta["container_mode"] = container_mode
    try:
        (workspace_root / SESSION_META_FILE).write_text(
            json.dumps(meta), encoding="utf-8"
        )
    except OSError:
        pass  # best-effort; the live record still carries the mode


def read_session_meta(workspace_root: Path) -> dict[str, str]:
    """Read session metadata from a workspace root, or ``{}`` if unavailable."""
    try:
        data = json.loads((workspace_root / SESSION_META_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}
