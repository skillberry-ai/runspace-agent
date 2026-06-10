"""Request/response models for the runspace_agent server."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from runspace_agent.prompt import SummarySection


class SessionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunRequest(BaseModel):
    """POST /run request body."""

    name: str | None = None
    editable_dir: str
    context_dir: str
    prompt: str
    editable_description: str = ""
    context_description: str = ""
    skills_dir: str | None = None
    preinstalled_skills: list[str] | None = None
    # None means "use the server's default mode" (set by the runspace-srv CLI:
    # container unless started with --no-docker).
    mode: str | None = None
    output_zip: bool = False
    mcp_servers: dict[str, Any] | None = None
    # Agent selection and settings
    agent_type: str = "claude-code"
    agent_settings: dict[str, Any] | None = None
    agent_max_turns: int = 300
    # Container settings
    container_image: str = "runspace-agent:latest"
    container_memory: str = "4g"
    container_cpus: int = 2
    extra_summary_sections: list[SummarySection] | None = None


class RenameRequest(BaseModel):
    """PATCH /sessions/{session_id} request body."""

    name: str


class SessionInfo(BaseModel):
    """Session metadata."""

    session_id: str
    name: str | None = None
    agent_type: str = ""
    status: SessionStatus
    created_at: str
    last_accessed: str
    workspace_dir: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    # Execution mode this session ran in ("local" or "container").
    mode: str | None = None


class SessionDetail(SessionInfo):
    """Full session details including agent result."""

    total_tokens: int = 0
    total_cost_usd: float | None = None
    duration_ms: int = 0
    output_zip_path: str | None = None
    has_conversation: bool = False
    has_summary: bool = False


class SkillInfo(BaseModel):
    """A preinstalled skill."""

    name: str
    description: str = ""


class FileEntry(BaseModel):
    """A file or directory entry."""

    name: str
    path: str
    is_dir: bool
    size: int = 0
