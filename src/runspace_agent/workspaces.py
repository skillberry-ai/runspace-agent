"""Host-side locations for session workspaces.

All session workspaces live under a single parent directory::

    {base}/runspace/
        {session_id}/
            agent_workspace/   <- editable/ + context/ + skills
            editable_original/ <- pre-run snapshot (for diff)
            ...

By default ``{base}`` is the system temp directory. Set the ``RUNSPACE_DATA_DIR``
environment variable to put the ``runspace/`` folder somewhere stable and
discoverable instead (e.g. ``~/.runspace`` or ``/var/lib/runspace``) so every
session's managed data is easy to find.

Keeping every session under one ``runspace/`` folder (rather than scattering
``runspace_<id>`` folders directly in the base) keeps things tidy and makes the
orphan scan a single ``iterdir`` of one directory.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

WORKSPACES_DIRNAME = "runspace"

# Optional override for the parent of the ``runspace/`` folder. When set, it
# replaces the system temp dir as the base, letting users point all managed
# session data at a known, persistent location.
DATA_DIR_ENV = "RUNSPACE_DATA_DIR"


def _base_dir() -> Path:
    """Return the parent directory of the ``runspace/`` folder."""
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else Path(tempfile.gettempdir())

# Session-level metadata file written at the workspace root. It records how the
# session ran (e.g. its execution mode) so the orphan scan can recover that info
# for sessions left over from a previous server process.
SESSION_META_FILE = "session_meta.json"


def workspaces_root() -> Path:
    """Return the parent directory that holds every session workspace."""
    return _base_dir() / WORKSPACES_DIRNAME


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
