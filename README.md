# runspace_agent

Run AI agents fully autonomously on a filesystem directory — MCP servers and skills
enabled, with zero human approvals or permission prompts — safely isolated in a
hardened Docker container (or locally).

Given an **editable directory** (the agent's workspace), a **read-only context directory**
(traces, domain knowledge, etc.), and a **prompt**, `runspace_agent` runs an AI agent
that modifies the editable directory and then exits.

Because each session runs inside a locked-down container by default, the agent
operates **unattended**: it can use its full toolset — MCP servers, skills, shell,
file edits, web access — without stopping to ask for permission, since the container
boundary (not a human in the loop) is what keeps it safe. The same agent can also run
**locally** with `--no-docker`, where filesystem hooks confine it to the session
workspace.

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

This starts the API server + React UI on port 6767. Sessions run inside a Docker
**container** by default, so starting the server runs a Docker pre-flight (verify
the daemon, build `runspace-agent:latest` if missing). To run sessions **locally**
on the host instead — no Docker required — start with `--no-docker`:

```bash
runspace-srv --no-docker
```

An explicit `mode` in a `POST /run` request always overrides this default; the CLI
flag only sets the default for requests that don't specify one.

Open in your browser:
- **http://localhost:6767/ui** — Web UI (React SPA)
- **http://localhost:6767/docs** — Swagger interactive API docs
- **http://localhost:6767/redoc** — ReDoc API docs

```bash
# Custom port (environment-only; default 6767)
RUNSPACE_PORT=9000 runspace-srv

# Enable auto-reload on code changes (off by default)
runspace-srv --watch

# Custom session TTL (default: 8 hours)
runspace-srv --session-ttl 24
```

See [Configuration](#configuration) for the environment variables the server reads.

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
        "ANTHROPIC_MODEL": "claude-opus-4-8",
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

There are **two ways** to give an agent skills, and you can use either or both:

#### 1. Preinstalled skills (`preinstalled_skills`)

Each agent ships with a set of bundled skills. The `ClaudeCodeAgent` ships with:
- **skill-creator** — Create, modify, improve, and evaluate skills
- **mcp-builder** — Build MCP servers in Python (FastMCP) or Node/TypeScript

Preinstalled skills are **opt-in** — none are included unless you select them
by name. Only the names you list are loaded:
```python
# No preinstalled skills (default)
session = RunspaceSession(...)

# Include only the ones you select
session = RunspaceSession(..., preinstalled_skills=["mcp-builder"])
```

#### 2. Your own skills (`skills_dir`)

Point `skills_dir` at a directory that contains one subdirectory per skill
(each with its own `SKILL.md`):
```
my-skills/
├── my-skill/
│   └── SKILL.md
└── another-skill/
    └── SKILL.md
```
```python
session = RunspaceSession(..., skills_dir=Path("my-skills"))
```

Combine both — select preinstalled skills *and* supply your own directory.
Custom skills override preinstalled ones with the same name:
```python
session = RunspaceSession(
    ...,
    preinstalled_skills=["mcp-builder"],
    skills_dir=Path("my-skills"),
)
```

Use `GET /skills` to list the available preinstalled skills via the API.

### Sandbox

In **local mode**, PreToolUse hooks restrict the agent to the session directory —
it cannot read or write files outside the workspace.

In **container mode**, Docker provides true isolation:
- `--cap-drop ALL` — no Linux capabilities
- `--security-opt no-new-privileges` — no privilege escalation
- Memory and CPU limits
- Per-session workspace directories

> **Running the server on your own machine? Prefer container mode.** It gives the
> agent a hard isolation boundary: it runs *inside* the container and the only
> part of your computer it can touch is the single session workspace directory,
> which is bind-mounted into the container. Nothing else on your PC is visible or
> changeable. Container mode also **does not** write back to your original
> `editable_dir` — it works on a copy in the workspace, so your source files stay
> untouched.
>
> **local mode**, by contrast, runs the agent as a process directly on your host.
> The PreToolUse hooks keep it inside the session directory, but it shares your
> machine and user, and on success it **syncs results back to your original
> `editable_dir`** — i.e. it does change files on your PC. Use local mode for
> trusted, fast iteration; use container mode when you want your machine
> protected from whatever the agent does.

### Execution Modes

| Mode | When to use |
|------|-------------|
| `mode="local"` | Development, debugging, fast iteration |
| `mode="container"` | Production — full isolation, a fresh container per run |

In **container** mode each run gets a brand-new container that is auto-removed
(`--rm`) when it exits. The container is disposable but your data is not: the agent
writes to a host directory bind-mounted at `/workspace`, so the editable output,
diffs, and conversation remain on the host after the container is removed (see
[Sandbox](#sandbox)). Container runs never sync back to your original
`editable_dir` — changes live in the session workspace and are fetched via the API.

### Agent Credentials

Credentials are **agent-specific** — there is no global API-key setting in the
runspace layer. Each `FilesystemAgent` decides what it needs to reach its model and
exposes it through its own configuration, which you supply per session via
`agent_settings` (HTTP API) or the agent's options object (Python API). Whatever you
provide is what the agent process receives in its environment.

**Claude Code agent (built-in).** Authenticate by setting credentials in the agent's
`env`: either an Anthropic API key, or a base URL + auth token for a proxy/gateway.

- **HTTP API** — `agent_settings.env` on `POST /run`:

```jsonc
{
  "editable_dir": "...", "context_dir": "...", "prompt": "...",
  "agent_settings": {
    "env": {
      "ANTHROPIC_API_KEY": "sk-ant-..."
      // — or, for a proxy/gateway —
      // "ANTHROPIC_BASE_URL": "https://your-gateway.example.com",
      // "ANTHROPIC_AUTH_TOKEN": "...",
      // "ANTHROPIC_MODEL": "claude-opus-4-8"
    }
  }
}
```

- **Python API** — `ClaudeCodeOptions(env={...})` (see [Python API](#python-api) above).
- The examples and manual tests build this dict from your shell environment with the
  `build_claude_env()` helper in `runspace_agent.agents.claude_code` (reads
  `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL`).

**Other agents.** A different agent type authenticates however *it* requires — its own
API-key variable, a token file, a config field, etc. Expose those through the same
`agent_settings` (the agent reads them when it builds its options); nothing in the
runspace layer is Anthropic-specific.

> **Container vs local:** a local-mode run may inherit auth from the host
> environment, but a container is a clean room — it only receives what you put in
> `agent_settings.env`. If a container session fails immediately with a non-zero
> exit, missing credentials are the most common cause.

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

### Session Storage

Every session workspace lives under a single parent folder, `{base}/runspace/`,
with one subdirectory per session (its editable copy, pre-run snapshot, context,
conversation, and metadata). These directories are what the UI scans and what the
file/diff/download endpoints read.

By default `{base}` is the system temp directory. Set the optional
**`RUNSPACE_DATA_DIR`** environment variable to relocate the `runspace/` folder
to a stable, discoverable location instead:

```bash
RUNSPACE_DATA_DIR=~/.runspace runspace-srv
# -> workspaces live under ~/.runspace/runspace/<session_id>/
```

This is handy when you want all managed session data in one known place (e.g. to
inspect, back up, or persist it across reboots) rather than scattered in temp.

See [Configuration](#configuration) for all server environment variables.

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

The `runspace-agent:latest` image (required for container mode) is built
automatically the first time you start the server, since the Docker pre-flight
runs by default:

```bash
runspace-srv              # builds the image if missing, then serves
runspace-srv --rebuild    # force a rebuild, then serves
runspace-srv --no-docker  # skip Docker entirely; run sessions locally
```

The build context is assembled from the installed package, so this works the same
whether runspace-agent was installed editable, from git, or from a wheel — no repo
checkout required.

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

## Architecture

For a map of the modules and how a run flows through them, see
[docs/architecture.md](docs/architecture.md).

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the local
setup, how to run the linter and tests, and the conventions we follow.

## License

Licensed under the [Apache License 2.0](LICENSE.txt).
