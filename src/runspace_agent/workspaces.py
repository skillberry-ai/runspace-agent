"""Host-side locations for session workspaces.

Everything lives under a single **runspace home** directory, with session
workspaces grouped under a ``sessions/`` subfolder::

    {home}/
        sessions/
            {session_id}/
                agent_workspace/   <- editable/ + context/ + skills
                editable_original/ <- pre-run snapshot (for diff)
                ...

The home is the ``RUNSPACE_DATA_DIR`` environment variable when set — so that
directory directly contains ``sessions/`` (and leaves room for other runspace
data later). When unset, the home defaults to ``{system-temp}/runspace`` so the
shared temp dir stays namespaced and tidy.

Grouping sessions under one ``sessions/`` folder makes the orphan scan a single
``iterdir`` of one directory.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Default home namespace inside the system temp dir (used when RUNSPACE_DATA_DIR
# is not set), and the subfolder that holds per-session workspaces.
HOME_DIRNAME = "runspace"
SESSIONS_DIRNAME = "sessions"

# Optional override for the runspace home. When set, this directory directly
# contains ``sessions/``, letting users point all managed data at a known,
# persistent location (e.g. ``~/.runspace`` or ``/var/lib/runspace``).
DATA_DIR_ENV = "RUNSPACE_DATA_DIR"

# Session-level metadata file written at the workspace root. It records how the
# session ran (e.g. its execution mode) so the orphan scan can recover that info
# for sessions left over from a previous server process.
SESSION_META_FILE = "session_meta.json"


def runspace_home() -> Path:
    """Return the runspace home directory (holds ``sessions/`` and friends)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / HOME_DIRNAME


def workspaces_root() -> Path:
    """Return the parent directory that holds every session workspace."""
    return runspace_home() / SESSIONS_DIRNAME


def session_workspace(session_id: str) -> Path:
    """Return the workspace directory for a single session."""
    return workspaces_root() / session_id


def write_session_meta(workspace_root: Path, *, mode: str) -> None:
    """Persist session metadata (execution mode) at the workspace root."""
    meta: dict[str, str] = {"mode": mode}
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
