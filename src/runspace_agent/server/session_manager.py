"""Session lifecycle management.

Tracks active and completed sessions, runs background cleanup of stale
sessions (default: 8 hours idle).
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runspace_agent.server.models import SessionStatus


class SessionRecord:
    """In-memory record of a session."""

    def __init__(self, session_id: str, workspace_dir: Path | None = None) -> None:
        self.session_id = session_id
        self.status = SessionStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.last_accessed = datetime.now(timezone.utc)
        self.workspace_dir = workspace_dir
        self.started_at: float | None = None  # time.monotonic() when run began
        self.duration_seconds: float | None = None
        self.total_tokens: int = 0
        self.duration_ms: int = 0
        self.error: str | None = None
        self.output_zip_path: Path | None = None
        self.task: asyncio.Task[Any] | None = None

    def touch(self) -> None:
        self.last_accessed = datetime.now(timezone.utc)


class SessionManager:
    """Manages session lifecycle with auto-cleanup.

    Parameters:
        cleanup_interval_seconds: How often the cleanup task runs (default 28800 = 8h).
        session_ttl_seconds: Sessions idle longer than this are cleaned up (default 28800 = 8h).
    """

    def __init__(
        self,
        cleanup_interval_seconds: int = 28800,
        session_ttl_seconds: int = 28800,
    ) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._cleanup_interval = cleanup_interval_seconds
        self._session_ttl = session_ttl_seconds
        self._cleanup_task: asyncio.Task[Any] | None = None

    def start_cleanup_loop(self) -> None:
        """Start the background cleanup coroutine."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self._cleanup_interval)
            self._cleanup_stale()

    def _cleanup_stale(self) -> None:
        now = datetime.now(timezone.utc)
        stale_ids = []
        for sid, record in self._sessions.items():
            elapsed = (now - record.last_accessed).total_seconds()
            if elapsed > self._session_ttl and record.status in (
                SessionStatus.COMPLETED,
                SessionStatus.FAILED,
            ):
                stale_ids.append(sid)

        for sid in stale_ids:
            self.remove_session(sid)

    def register(self, session_id: str, workspace_dir: Path | None = None) -> SessionRecord:
        record = SessionRecord(session_id, workspace_dir)
        self._sessions[session_id] = record
        return record

    def get(self, session_id: str) -> SessionRecord | None:
        record = self._sessions.get(session_id)
        if record:
            record.touch()
        return record

    def list_sessions(self, include_orphaned: bool = True) -> list[SessionRecord]:
        """Return all known sessions.

        When *include_orphaned* is True (the default), the temp directory is
        scanned for ``runspace_*`` workspace folders that are not tracked
        in-memory (e.g. from a previous server process).  These are returned
        as synthetic ``COMPLETED`` records so the UI always shows them.
        """
        records = list(self._sessions.values())
        if not include_orphaned:
            return records

        known_ids = {r.session_id for r in records}
        # Skip orphan scanning entirely if any session is still running —
        # its workspace exists on disk but isn't registered under its real
        # session_id yet, so the scanner would wrongly mark it COMPLETED.
        has_active = any(
            r.status in (SessionStatus.RUNNING, SessionStatus.PENDING)
            for r in records
        )
        if has_active:
            return records
        temp_base = Path(tempfile.gettempdir())
        for entry in temp_base.iterdir():
            if entry.is_dir() and entry.name.startswith("runspace_"):
                sid = entry.name[len("runspace_"):]
                if sid and sid not in known_ids:
                    rec = SessionRecord(sid, workspace_dir=entry)
                    rec.status = SessionStatus.COMPLETED
                    rec.created_at = datetime.fromtimestamp(
                        entry.stat().st_ctime, tz=timezone.utc,
                    )
                    rec.last_accessed = datetime.fromtimestamp(
                        entry.stat().st_mtime, tz=timezone.utc,
                    )
                    # Try to recover metadata from conversation.json
                    conv = entry / "conversation.json"
                    if conv.is_file():
                        try:
                            import json
                            data = json.loads(conv.read_text(encoding="utf-8"))
                            rec.duration_ms = data.get("duration_ms", 0)
                            rec.total_tokens = data.get("total_tokens", 0)
                            if rec.duration_ms:
                                rec.duration_seconds = round(rec.duration_ms / 1000, 2)
                        except Exception:
                            pass
                    records.append(rec)
        return records

    def remove_session(self, session_id: str) -> bool:
        record = self._sessions.pop(session_id, None)
        if record:
            # Cancel running task
            if record.task and not record.task.done():
                record.task.cancel()
            # Clean up workspace directory
            if record.workspace_dir and record.workspace_dir.exists():
                shutil.rmtree(record.workspace_dir, ignore_errors=True)

        # Also clean up orphaned workspace on disk (not tracked in-memory)
        workspace = Path(tempfile.gettempdir()) / f"runspace_{session_id}"
        if workspace.is_dir():
            shutil.rmtree(workspace, ignore_errors=True)
            return True

        return record is not None

    def get_workspace_for_session(self, session_id: str) -> Path | None:
        """Return the workspace directory path for a session."""
        temp_base = Path(tempfile.gettempdir())
        workspace = temp_base / f"runspace_{session_id}"
        if workspace.is_dir():
            return workspace
        record = self.get(session_id)
        if record and record.workspace_dir and record.workspace_dir.is_dir():
            return record.workspace_dir
        return None
