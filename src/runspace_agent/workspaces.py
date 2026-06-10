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

import tempfile
from pathlib import Path

WORKSPACES_DIRNAME = "runspace"


def workspaces_root() -> Path:
    """Return the parent directory that holds every session workspace."""
    return Path(tempfile.gettempdir()) / WORKSPACES_DIRNAME


def session_workspace(session_id: str) -> Path:
    """Return the workspace directory for a single session."""
    return workspaces_root() / session_id
