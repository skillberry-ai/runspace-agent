"""FastAPI server for runspace_agent.

Provides HTTP endpoints for creating sessions, checking status,
browsing files, and downloading results.

Start with::

    uv run uvicorn runspace_agent.server.app:app --host 0.0.0.0 --port 6767

For development (auto-reload on code changes)::

    uv run uvicorn runspace_agent.server.app:app --host 0.0.0.0 --port 6767 --reload
"""

from __future__ import annotations

import asyncio
import difflib
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from runspace_agent.core import RunspaceSession, run_agent
from runspace_agent.server.models import (
    FileEntry,
    RenameRequest,
    RunRequest,
    SessionDetail,
    SessionInfo,
    SessionStatus,
    SkillInfo,
)
from runspace_agent.server.session_manager import SessionManager

app = FastAPI(title="Runspace Agent", version="0.1.0")
_ttl = int(os.environ.get("RUNSPACE_SESSION_TTL", "0")) or None
manager = SessionManager(
    **({"session_ttl_seconds": _ttl, "cleanup_interval_seconds": _ttl} if _ttl else {})
)

# Serve built React frontend
_STATIC_DIR = Path(__file__).parent / "static"
if (_STATIC_DIR / "assets").is_dir():
    app.mount(
        "/ui/assets",
        StaticFiles(directory=_STATIC_DIR / "assets"),
        name="frontend-assets",
    )


@app.on_event("startup")
async def startup() -> None:
    manager.start_cleanup_loop()


# ---------- Session endpoints ----------


@app.post("/run", response_model=SessionInfo)
async def create_run(req: RunRequest) -> SessionInfo:
    """Create a new session and start the agent in the background."""
    from runspace_agent.server._options import build_options_from_request

    agent_options = build_options_from_request(req)

    session = RunspaceSession(
        editable_dir=Path(req.editable_dir),
        context_dir=Path(req.context_dir),
        prompt=req.prompt,
        editable_description=req.editable_description,
        context_description=req.context_description,
        agent_options=agent_options,
        skills_dir=Path(req.skills_dir) if req.skills_dir else None,
        preinstalled_skills=req.preinstalled_skills,
        mode=req.mode,  # type: ignore[arg-type]
        output_zip=req.output_zip,
        container_image=req.container_image,
        container_memory=req.container_memory,
        container_cpus=req.container_cpus,
        container_mode=req.container_mode,  # type: ignore[arg-type]
    )

    # Generate a stable session ID upfront so the UI only ever sees one entry.
    preliminary_id = uuid.uuid4().hex[:12]
    record = manager.register(preliminary_id, name=req.name)

    # Set workspace_dir eagerly so the orphan scanner skips this directory
    # while the agent is still running.
    record.workspace_dir = Path(tempfile.gettempdir()) / f"runspace_{preliminary_id}"

    async def _run() -> None:
        record.status = SessionStatus.RUNNING
        t0 = time.monotonic()
        record.started_at = t0
        try:
            result = await run_agent(session, session_id=preliminary_id)
        except Exception as exc:
            record.status = SessionStatus.FAILED
            record.error = f"{type(exc).__name__}: {exc}"
            record.duration_seconds = round(time.monotonic() - t0, 2)
            raise

        record.status = (
            SessionStatus.COMPLETED if result.success else SessionStatus.FAILED
        )
        record.duration_seconds = result.duration_seconds
        record.total_tokens = result.agent_result.total_tokens
        record.duration_ms = result.agent_result.duration_ms
        record.error = result.agent_result.error
        if result.output_zip_path:
            record.output_zip_path = result.output_zip_path
        record.workspace_dir = manager.get_workspace_for_session(preliminary_id)

    task = asyncio.create_task(_run())
    record.task = task

    return SessionInfo(
        session_id=record.session_id,
        name=record.name,
        status=record.status,
        created_at=record.created_at.isoformat(),
        last_accessed=record.last_accessed.isoformat(),
    )


def _effective_duration(r: Any) -> float | None:
    """Return final duration, or elapsed time if the session is still running."""
    if r.duration_seconds is not None:
        return r.duration_seconds
    if getattr(r, "started_at", None) is not None:
        return round(time.monotonic() - r.started_at, 2)
    return None


@app.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(status: SessionStatus | None = None) -> list[SessionInfo]:
    """List all sessions, most recently created first.

    Optionally filter by *status* (e.g. ``?status=completed``).
    """
    records = manager.list_sessions()
    if status is not None:
        records = [r for r in records if r.status == status]
    records.sort(key=lambda r: r.created_at, reverse=True)
    return [
        SessionInfo(
            session_id=r.session_id,
            name=getattr(r, "name", None),
            status=r.status,
            created_at=r.created_at.isoformat(),
            last_accessed=r.last_accessed.isoformat(),
            workspace_dir=str(r.workspace_dir) if r.workspace_dir else None,
            duration_seconds=_effective_duration(r),
            error=r.error,
        )
        for r in records
    ]


@app.delete("/sessions")
async def delete_all_sessions() -> dict[str, Any]:
    """Delete every session and its workspace."""
    count = manager.remove_all_sessions()
    return {"status": "deleted", "count": count}


@app.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str) -> SessionDetail:
    """Get session details."""
    record = manager.get(session_id)
    workspace = manager.get_workspace_for_session(session_id)

    if record:
        detail = SessionDetail(
            session_id=record.session_id,
            name=record.name,
            status=record.status,
            created_at=record.created_at.isoformat(),
            last_accessed=record.last_accessed.isoformat(),
            workspace_dir=str(record.workspace_dir) if record.workspace_dir else None,
            duration_seconds=_effective_duration(record),
            error=record.error,
            total_tokens=record.total_tokens,
            duration_ms=record.duration_ms,
            output_zip_path=str(record.output_zip_path)
            if record.output_zip_path
            else None,
        )
    elif workspace:
        # Session not in manager but workspace exists on disk (e.g. after server restart)
        from datetime import datetime

        st = workspace.stat()
        elapsed = st.st_mtime - st.st_ctime
        detail = SessionDetail(
            session_id=session_id,
            status=SessionStatus.COMPLETED,
            created_at=datetime.fromtimestamp(st.st_ctime).isoformat(),
            last_accessed=datetime.fromtimestamp(st.st_mtime).isoformat(),
            workspace_dir=str(workspace),
            duration_seconds=round(elapsed, 2) if elapsed > 0 else None,
        )
    else:
        raise HTTPException(404, f"Session {session_id} not found")

    # Populate availability flags for conversation and summary
    if workspace:
        detail.has_conversation = (workspace / "conversation.json").is_file()
        detail.has_summary = (workspace / "agent_workspace" / "summary.md").is_file()
    return detail


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a session and its workspace."""
    if not manager.remove_session(session_id):
        raise HTTPException(404, f"Session {session_id} not found")
    return {"status": "deleted", "session_id": session_id}


@app.patch("/sessions/{session_id}", response_model=SessionInfo)
async def rename_session(session_id: str, req: RenameRequest) -> SessionInfo:
    """Rename a session."""
    if not manager.rename(session_id, req.name):
        raise HTTPException(404, f"Session {session_id} not found")
    record = manager.get(session_id)
    assert record is not None
    return SessionInfo(
        session_id=record.session_id,
        name=record.name,
        status=record.status,
        created_at=record.created_at.isoformat(),
        last_accessed=record.last_accessed.isoformat(),
        workspace_dir=str(record.workspace_dir) if record.workspace_dir else None,
        duration_seconds=_effective_duration(record),
        error=record.error,
    )


# ---------- Skills ----------


_BUNDLED_SKILLS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "skills"
)


@app.get("/skills", response_model=list[SkillInfo])
async def list_skills() -> list[SkillInfo]:
    """List preinstalled/bundled skills shipped with the package."""
    from runspace_agent.skills import get_default_skills, parse_skill_frontmatter

    if not _BUNDLED_SKILLS_DIR.is_dir():
        return []
    skills = get_default_skills(_BUNDLED_SKILLS_DIR)
    return [SkillInfo(**parse_skill_frontmatter(s.path)) for s in skills]


# ---------- File browsing ----------


@app.get("/sessions/{session_id}/files")
async def list_session_files(session_id: str) -> list[FileEntry]:
    """List files in the session workspace root."""
    workspace = manager.get_workspace_for_session(session_id)
    if not workspace:
        raise HTTPException(404, f"Workspace for session {session_id} not found")
    return _list_dir(workspace, workspace)


@app.get("/sessions/{session_id}/files/{path:path}")
async def get_session_file(session_id: str, path: str) -> Any:
    """Browse or download a file/directory in the session workspace."""
    workspace = manager.get_workspace_for_session(session_id)
    if not workspace:
        raise HTTPException(404, f"Workspace for session {session_id} not found")

    target = (workspace / path).resolve()

    # Security: ensure target is inside workspace
    try:
        target.relative_to(workspace.resolve())
    except ValueError:
        raise HTTPException(403, "Access denied: path escapes session workspace")

    if not target.exists():
        raise HTTPException(404, f"Path not found: {path}")

    if target.is_dir():
        return JSONResponse([e.model_dump() for e in _list_dir(target, workspace)])

    # Return file content
    return FileResponse(target, filename=target.name)


@app.get("/sessions/{session_id}/editable.zip")
async def download_result(session_id: str) -> FileResponse:
    """Download the editable directory as a zip file."""
    workspace = manager.get_workspace_for_session(session_id)
    if not workspace:
        raise HTTPException(404, f"Workspace for session {session_id} not found")

    editable = workspace / "agent_workspace" / "editable"
    if not editable.is_dir():
        raise HTTPException(404, "No editable directory found in session workspace")

    # Create zip — include session name in filename when available
    record = manager.get(session_id)
    if record and record.name:
        safe_name = (
            record.name.replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace(":", "_")
        )
        filename = f"editable_{safe_name}_{session_id}.zip"
    else:
        filename = f"editable_{session_id}.zip"
    zip_base = Path(tempfile.gettempdir()) / f"runspace_editable_{session_id}"
    zip_path = shutil.make_archive(str(zip_base), "zip", str(editable))
    return FileResponse(zip_path, filename=filename)


# ---------- Diff ----------


@app.get("/sessions/{session_id}/diff")
async def get_session_diff(session_id: str) -> JSONResponse:
    """Return unified diffs for all changed files in editable/."""
    workspace = manager.get_workspace_for_session(session_id)
    if not workspace:
        raise HTTPException(404, f"Workspace for session {session_id} not found")

    original = workspace / "editable_original"
    modified = workspace / "agent_workspace" / "editable"

    if not original.is_dir():
        raise HTTPException(
            404, "No original snapshot found (session may predate diff support)"
        )
    if not modified.is_dir():
        raise HTTPException(404, "No editable directory found")

    diffs = _compute_diffs(original, modified)
    return JSONResponse(diffs)


@app.get("/sessions/{session_id}/diff/{path:path}")
async def get_file_diff(session_id: str, path: str) -> JSONResponse:
    """Return unified diff for a single file."""
    workspace = manager.get_workspace_for_session(session_id)
    if not workspace:
        raise HTTPException(404, f"Workspace for session {session_id} not found")

    original_file = workspace / "editable_original" / path
    modified_file = workspace / "agent_workspace" / "editable" / path

    # Security check
    try:
        original_file.resolve().relative_to((workspace / "editable_original").resolve())
    except ValueError:
        raise HTTPException(403, "Access denied: path escapes session workspace")

    original_lines = _read_file_lines(original_file)
    modified_lines = _read_file_lines(modified_file)

    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )

    return JSONResponse(
        {
            "path": path,
            "diff": "\n".join(diff_lines),
            "has_changes": len(diff_lines) > 0,
            "original_exists": original_file.is_file(),
            "modified_exists": modified_file.is_file(),
        }
    )


# ---------- Conversation & Summary ----------


@app.get("/sessions/{session_id}/conversation")
async def get_conversation(session_id: str) -> JSONResponse:
    """Return the serialized agent conversation trajectory."""
    workspace = manager.get_workspace_for_session(session_id)
    if not workspace:
        raise HTTPException(404, f"Workspace for session {session_id} not found")

    conv_path = workspace / "conversation.json"
    if not conv_path.is_file():
        raise HTTPException(
            404, "Conversation not found (session may still be running)"
        )

    import json as _json

    data = _json.loads(conv_path.read_text(encoding="utf-8"))
    return JSONResponse(data)


@app.get("/sessions/{session_id}/summary")
async def get_summary(session_id: str) -> JSONResponse:
    """Return the agent-generated session summary."""
    workspace = manager.get_workspace_for_session(session_id)
    if not workspace:
        raise HTTPException(404, f"Workspace for session {session_id} not found")

    summary_path = workspace / "agent_workspace" / "summary.md"
    if not summary_path.is_file():
        raise HTTPException(404, "Summary not found (agent may not have generated one)")

    content = summary_path.read_text(encoding="utf-8")
    return JSONResponse({"content": content})


# ---------- UI (React SPA) ----------


@app.get("/ui/{path:path}", response_model=None)
@app.get("/ui", response_model=None)
async def serve_spa(path: str = ""):
    """Serve the React SPA for all /ui routes.

    Static files (favicon, etc.) in the build output are served directly;
    everything else returns index.html for client-side routing.
    """
    # Serve static files from the build output (e.g. favicon.svg)
    if path and not path.startswith("assets"):
        static_file = _STATIC_DIR / path
        if static_file.is_file():
            try:
                static_file.resolve().relative_to(_STATIC_DIR.resolve())
                return FileResponse(static_file)
            except ValueError:
                pass  # path escape attempt, fall through to SPA

    index = _STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    # Fallback when frontend hasn't been built yet
    return HTMLResponse(
        "<h1>Frontend not built</h1>"
        "<p>Run: <code>cd frontend && npm install && npm run build</code></p>",
        status_code=200,
    )


# ---------- Helpers ----------


def _list_dir(directory: Path, workspace_root: Path) -> list[FileEntry]:
    """List immediate children of *directory*.

    Paths are returned relative to *workspace_root* so they can be used
    directly in ``/sessions/{id}/files/{path}`` API calls.
    Skips cache and generated directories that clutter the UI.
    """
    resolved_root = workspace_root.resolve()
    entries: list[FileEntry] = []
    for child in sorted(directory.iterdir()):
        if child.name in _DIFF_IGNORE_DIRS or child.name.endswith(".egg-info"):
            continue
        try:
            rel = child.resolve().relative_to(resolved_root)
        except ValueError:
            rel = Path(child.name)
        entries.append(
            FileEntry(
                name=child.name,
                path=str(rel).replace("\\", "/"),
                is_dir=child.is_dir(),
                size=child.stat().st_size if child.is_file() else 0,
            )
        )
    return entries


def _read_file_lines(path: Path) -> list[str]:
    """Read a file as a list of lines, returning [] if it doesn't exist."""
    if not path.is_file():
        return []
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return ["(binary or unreadable file)"]


_DIFF_IGNORE_DIRS = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    ".tox",
    ".nox",
    ".eggs",
    "*.egg-info",
    ".cache",
}


def _should_skip(rel_path: str) -> bool:
    """Return True if *rel_path* falls inside an ignored directory."""
    parts = rel_path.split("/")
    return any(p in _DIFF_IGNORE_DIRS or p.endswith(".egg-info") for p in parts)


def _compute_diffs(original_dir: Path, modified_dir: Path) -> list[dict[str, Any]]:
    """Compute unified diffs for all files that changed between two directories."""
    diffs: list[dict[str, Any]] = []

    # Collect all file paths from both directories, skipping caches/generated dirs
    orig_files: set[str] = set()
    mod_files: set[str] = set()
    if original_dir.is_dir():
        for f in original_dir.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(original_dir)).replace("\\", "/")
                if not _should_skip(rel):
                    orig_files.add(rel)
    if modified_dir.is_dir():
        for f in modified_dir.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(modified_dir)).replace("\\", "/")
                if not _should_skip(rel):
                    mod_files.add(rel)

    all_paths = sorted(orig_files | mod_files)

    for rel_path in all_paths:
        orig_lines = _read_file_lines(original_dir / rel_path)
        mod_lines = _read_file_lines(modified_dir / rel_path)

        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                mod_lines,
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
                lineterm="",
            )
        )

        if diff_lines:
            added = sum(
                1 for l in diff_lines if l.startswith("+") and not l.startswith("+++")
            )
            removed = sum(
                1 for l in diff_lines if l.startswith("-") and not l.startswith("---")
            )
            status = (
                "added"
                if rel_path not in orig_files
                else ("deleted" if rel_path not in mod_files else "modified")
            )
            diffs.append(
                {
                    "path": rel_path,
                    "status": status,
                    "diff": "\n".join(diff_lines),
                    "additions": added,
                    "deletions": removed,
                }
            )

    return diffs
