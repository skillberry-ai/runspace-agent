# runspace_agent

Sandboxed execution environment for AI agents operating on filesystem directories.

Given an **editable directory** (the agent's workspace), a **read-only context directory**
(traces, domain knowledge, etc.), and a **prompt**, `runspace_agent` runs an AI agent
that modifies the editable directory — either locally or inside a Docker container for
full isolation.

## Requirements

- **Python 3.11+**
- [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 18+** (only for frontend development)

## Install

```bash
# Create venv with Python 3.11
uv venv --python 3.11

# Core library only
uv pip install -e .

# With Claude Code agent support
uv pip install -e ".[claude]"

# With Docker container support
uv pip install -e ".[container]"

# With FastAPI server + UI
uv pip install -e ".[server]"

# Everything
uv pip install -e ".[all]"

# Dev dependencies
uv pip install -e ".[dev]"
```

## Quick Start

### Server + Web UI

The fastest way to get started is with the built-in server:

```bash
uv pip install -e ".[all]"
runspace-server
```

This will:
1. Verify Docker is installed and running
2. Build the `runspace-agent:latest` image if it doesn't exist
3. Start the API server + React UI on port 6767

Open **http://localhost:6767/ui** in your browser.

```bash
# Custom port
runspace-server --port 9000

# Disable auto-reload (reload is on by default)
runspace-server --no-reload

# Custom session TTL (default: 8 hours)
runspace-server --session-ttl 24
```

### Python API

```python
import asyncio
from pathlib import Path
from runspace_agent import RunspaceSession, run_agent
from runspace_agent.agents.claude_code import ClaudeCodeAgent

agent = ClaudeCodeAgent(
    settings={
        "env": {
            "ANTHROPIC_BASE_URL": "https://your-api-proxy.example.com",
            "ANTHROPIC_AUTH_TOKEN": "sk-...",
            "ANTHROPIC_MODEL": "claude-opus-4-6",
        },
    },
)

session = RunspaceSession(
    editable_dir=Path("./my_project"),
    context_dir=Path("./context"),
    prompt="Improve the code based on the traces in the context directory.",
    agent=agent,
)

result = asyncio.run(run_agent(session))
print(f"Success: {result.success}, Session: {result.session_id}")
```

## Concepts

### FilesystemAgent Protocol

Any agent that implements the `FilesystemAgent` protocol can be used:

```python
from runspace_agent.agents.base import FilesystemAgent, Workspace, AgentResult

class MyCustomAgent:
    skills_folder_name = ".my_agent/skills"
    default_skills_dir = Path("./my_bundled_skills")  # or None

    async def run(self, workspace: Workspace) -> AgentResult:
        # Read from workspace.context_dir
        # Modify files in workspace.editable_dir
        # Follow workspace.prompt
        return AgentResult(success=True)
```

### Built-in: ClaudeCodeAgent

Uses the Claude Agent SDK to run Claude Code headlessly with:
- `permission_mode="bypassPermissions"` — fully autonomous
- All tools enabled (Read, Write, Edit, Bash, Glob, Grep, Skill, WebSearch, WebFetch, Agent, LSP)
- No AskHumanQuestion — the agent works without human interaction
- Full settings support (custom API URL, auth token, model, plugins)

### Skills

Skills are agent-specific tool extensions. Each `FilesystemAgent` declares a
`skills_folder_name` (e.g. `.claude/skills` for Claude Code) and the library
copies skills into the workspace.

Each agent declares its own `default_skills_dir` — the directory containing its
bundled preinstalled skills. The `ClaudeCodeAgent` ships with:
- **skill-creator** — Create, modify, improve, and evaluate skills
- **mcp-builder** — Build MCP servers in Python (FastMCP) or Node/TypeScript

By default all preinstalled skills are included. Control which ones via `preinstalled_skills`:
```python
# Include all preinstalled skills (default)
session = RunspaceSession(..., preinstalled_skills=None)

# Include only specific ones
session = RunspaceSession(..., preinstalled_skills=["mcp-builder"])

# Skip all preinstalled skills
session = RunspaceSession(..., preinstalled_skills=[])
```

Provide your own with `skills_dir=Path(...)` — custom skills override preinstalled
ones with the same name.

Use `GET /skills` to list all preinstalled skills via the API.

### Sandbox

In **local mode**, PreToolUse hooks restrict the agent to the session directory —
it cannot read or write files outside the workspace.

In **container mode**, Docker provides true isolation:
- `--cap-drop ALL` — no Linux capabilities
- `--security-opt no-new-privileges` — no privilege escalation
- Memory and CPU limits
- Per-session workspace directories

### Execution Modes

| Mode | When to use |
|------|-------------|
| `mode="local"` | Development, debugging, fast iteration |
| `mode="container"` + `container_mode="ephemeral"` | Production, full isolation per run |
| `mode="container"` + `container_mode="persistent"` | Development with containers, faster startup |

## Server

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run` | Start a new agent session |
| `GET` | `/sessions` | List all sessions with status |
| `GET` | `/sessions/{id}` | Session details (tokens, duration, status) |
| `DELETE` | `/sessions/{id}` | Delete session and cleanup workspace |
| `GET` | `/sessions/{id}/files` | Browse workspace file tree (JSON) |
| `GET` | `/sessions/{id}/files/{path}` | View/download a specific file |
| `GET` | `/sessions/{id}/editable.zip` | Download editable dir as zip |
| `GET` | `/sessions/{id}/diff` | Unified diffs for all changed files |
| `GET` | `/sessions/{id}/diff/{path}` | Diff for a single file |
| `GET` | `/sessions/{id}/conversation` | Agent conversation trajectory (JSON) |
| `GET` | `/sessions/{id}/summary` | Agent-generated session summary |
| `GET` | `/skills` | List preinstalled/bundled skills |
| `GET` | `/ui` | Web UI (React SPA) |

Sessions auto-cleanup after 8 hours of inactivity (configurable with `--session-ttl`).

### Manual Start (Advanced)

If you prefer to manage Docker separately:

```bash
uv pip install -e ".[server]"
uv run uvicorn runspace_agent.server.app:app --host 0.0.0.0 --port 6767

# Development (auto-reload)
uv run uvicorn runspace_agent.server.app:app --host 0.0.0.0 --port 6767 --reload
```

## Frontend Development

The web UI is a React + TypeScript + Tailwind CSS app built with Vite.

```bash
cd frontend
npm install
```

There are two ways to work with the UI:

| | Vite dev server (`npm run dev`) | Production build (`npm run build`) |
|---|---|---|
| **URL** | http://localhost:5173/ui | http://localhost:6767/ui |
| **Hot reload** | Yes — changes appear instantly | No — must rebuild manually |
| **API** | Proxied to `localhost:6767` | Served by FastAPI directly |
| **Use when** | Developing the frontend | Testing the final build / production |

### Recommended workflow

1. Start the backend: `runspace-server`
2. Start the Vite dev server: `cd frontend && npm run dev`
3. Open **http://localhost:5173/ui** — edits to frontend code update automatically
4. When done, run `npm run build` to update the production UI at `localhost:6767/ui`

> **Note:** The UI at `localhost:6767/ui` is a static build baked into the Python package.
> It does **not** auto-update when you edit frontend source files — you must run
> `npm run build` to rebuild it.

## Docker

Build the image (required for container mode):

```bash
docker build -t runspace-agent:latest .
```

Containers auto-remove after each run. All output (conversation, diffs, files) is
persisted on the host via the volume mount — the container is just a throwaway
execution environment.

To clean up any leftover stopped containers:

```bash
docker container prune
```

## Tests

```bash
uv pip install -e ".[dev]"
uv run pytest tests/
```

## Skillberry Integration

See [docs/skillberry_integration.md](docs/skillberry_integration.md) for how to
use this library to replace stages 1-3 of the skillberry-skill-maker pipeline.
