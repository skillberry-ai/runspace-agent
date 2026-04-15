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
```

Activate the virtual environment:
- On Linux/macOS:
  ```bash
  source .venv/bin/activate
  ```
- On Windows:
  ```powershell
    .venv\Scripts\activate
    ```

Select the installation option based on your needs:

```bash
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
runspace-srv
```

This will:
1. Verify Docker is installed and running
2. Build the `runspace-agent:latest` image if it doesn't exist
3. Start the API server + React UI on port 6767

Open in your browser:
- **http://localhost:6767/ui** — Web UI (React SPA)
- **http://localhost:6767/docs** — Swagger interactive API docs
- **http://localhost:6767/redoc** — ReDoc API docs

```bash
# Custom port
runspace-srv --port 9000

# Enable auto-reload on code changes (off by default)
runspace-srv --watch

# Custom session TTL (default: 8 hours)
runspace-srv --session-ttl 24
```

### Python API

Configure the agent using `ClaudeCodeOptions` from the Claude Code SDK:

```python
import asyncio
from pathlib import Path
from claude_code_sdk import ClaudeCodeOptions
from runspace_agent import RunspaceSession, run_agent
from runspace_agent.agents.claude_code import ClaudeCodeAgent

options = ClaudeCodeOptions(
    env={
        "ANTHROPIC_BASE_URL": "https://your-api-proxy.example.com",
        "ANTHROPIC_AUTH_TOKEN": "sk-...",
        "ANTHROPIC_MODEL": "claude-opus-4-6",
    },
    max_turns=50,
    # Any ClaudeCodeOptions field is supported — model, mcp_servers,
    # allowed_tools, disallowed_tools, append_system_prompt, etc.
)
agent = ClaudeCodeAgent(options=options)

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

Uses the Claude Agent SDK to run Claude Code headlessly. Configure it by passing
a `ClaudeCodeOptions` object — every SDK field is supported and automatically
forwarded. The agent **enforces** the following fields for security (your values
are overridden):

| Field | Enforced value | Reason |
|-------|---------------|--------|
| `permission_mode` | `"bypassPermissions"` | Headless container, no human to approve |
| `cwd` | workspace directory | Sandbox boundary |
| `system_prompt` | Headless prompt | Prevents interactive prompts |
| `hooks` | Sandbox hooks | Filesystem isolation enforcement |

If you don't set these, sensible defaults are applied:

| Field | Default |
|-------|---------|
| `allowed_tools` | Read, Write, Edit, Bash, Glob, Grep, Skill, WebSearch, WebFetch, Agent, LSP |
| `max_turns` | 300 |

Everything else is fully configurable: `model`, `env`, `mcp_servers`,
`append_system_prompt`, `allowed_tools`, `disallowed_tools`, `add_dirs`,
`extra_args`, `user`, etc.

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
| `GET` | `/docs` | Swagger interactive API docs |
| `GET` | `/redoc` | ReDoc API docs |

Sessions auto-cleanup after 8 hours of inactivity (configurable with `--session-ttl`).

### Session Lifecycle

Sessions are **single-use by design**. There is no recall or resume within the
same session — each run gets a fresh session with its own context and editable
directory.

To "recall" the agent (e.g., run another improvement iteration), create a **new
session** with the updated editable directory and fresh context. This avoids the
complexity of maintaining conversation history, summarization across runs, and
stale state.

Sessions are automatically cleaned up after the configured TTL (default: 8
hours of inactivity, set via `--session-ttl`). If you want to free disk space
on the host (or container volume) immediately rather than waiting for the
auto-cleanup, delete the session explicitly after downloading the results:

```bash
# 1. Download the improved editable directory
curl -O http://localhost:6767/sessions/{session_id}/editable.zip

# 2. (Optional) Delete the session immediately to free space
#    Otherwise it will be auto-deleted after the session TTL expires
curl -X DELETE http://localhost:6767/sessions/{session_id}

# 3. Next iteration: create a new session with the updated files
curl -X POST http://localhost:6767/run \
  -H "Content-Type: application/json" \
  -d '{"editable_dir": "./updated_skill", "context_dir": "./new_context", "prompt": "..."}'
```

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

1. Start the backend: `runspace-srv`
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

## Examples

Ready-to-run examples live in `examples/`. Each example supports three execution modes:

| Mode | Command suffix | Description |
|------|---------------|-------------|
| `server` | Requires `runspace-srv` running | Sends a request to the HTTP server (recommended) |
| `library-container` | Requires Docker | Calls the Python library directly, runs in Docker |
| `library-local` | No Docker needed | Runs locally, modifies `editable/` in place |

All modes require `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` environment variables.

### Skill Improvement

Fixes bugs in a skill based on execution traces and domain knowledge:

```bash
# Start the server first (in a separate terminal)
runspace-srv

# Then run the example
uv run python examples/skill_improvement/run.py server
```

### Skillberry Store Skill

Optimizes a skillberry-store skill (airline customer service for tau-bench) using traces and evaluation criteria:

```bash
# Start the server first (in a separate terminal)
runspace-srv

# Then run the example
uv run python examples/skillberry_store_skill/run.py server
```

Replace `server` with `library-container` or `library-local` for alternative modes.

## Skillberry Integration

See [docs/skillberry_integration.md](docs/skillberry_integration.md) for how to
use this library to replace stages 1-3 of the skillberry-skill-maker pipeline.
