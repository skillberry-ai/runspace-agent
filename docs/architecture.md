# Architecture

`runspace_agent` runs an AI agent against a sandboxed view of two directories —
an **editable** directory the agent modifies and a **read-only context**
directory it reads from — either locally or inside a Docker container.

This document maps the modules and the path a single run takes through them.

## High-level flow

```
client (Python API or HTTP)
        │
        ▼
RunspaceSession ──► run_agent()           core.py
        │
        ├─ mode="local"     ──► run_local()        local.py
        └─ mode="container" ──► run_container()     container.py
                                     │
                                     ▼
                              entrypoint.py (inside the container)
        │
        ▼
   FilesystemAgent.run(workspace)         agents/base.py (protocol)
        │
        ▼
   AgentResult  ──►  RunspaceResult
```

## Modules

### Core orchestration

- **`core.py`** — the public entry point. `RunspaceSession` is the pydantic
  model describing a run (editable dir, context dir, prompt, agent, mode,
  skills). `run_agent()` resolves the agent, builds the prompt, and dispatches
  to local or container execution, returning a `RunspaceResult`.
- **`prompt.py`** — constructs the full agent prompt from the directory
  descriptions and the user prompt, and defines the summary sections the agent
  can emit.
- **`skills.py`** — `prepare_skills()` copies user-provided and bundled default
  skills into the agent's skills folder inside the workspace.

### Execution backends

- **`local.py`** — `run_local()` builds the workspace on the host, installs the
  sandbox hooks, runs the agent in-process, and syncs results back.
- **`container.py`** — `run_container()` runs the agent inside the
  `runspace-agent:latest` Docker image with hardened settings
  (`--cap-drop ALL`, `no-new-privileges`, memory/CPU limits). Each run gets a
  fresh, auto-removed container.
- **`entrypoint.py`** — the process that runs *inside* the container: it reads
  the serialized config, rebuilds the workspace and sandbox hooks, and invokes
  the agent.
- **`sandbox.py`** — PreToolUse hooks that confine the agent to the session
  directory. In local mode this is the isolation boundary; in container mode it
  is defense-in-depth on top of Docker.

### Agents

- **`agents/base.py`** — defines the `FilesystemAgent` protocol plus the
  `Workspace` (the sandboxed view handed to the agent) and `AgentResult` (what
  it returns) dataclasses. Any class with a `skills_folder_name`, a
  `default_skills_dir`, and an async `run(workspace)` method is a valid agent —
  no inheritance required.
- **`agents/__init__.py`** — the agent registry. Maps an `agent_type` string
  (e.g. `"claude-code"`) to its module so the server, container, and entrypoint
  can resolve agents uniformly.
- **`agents/claude_code/`** — the built-in `ClaudeCodeAgent`, which drives
  Claude Code headlessly via the Claude Agent SDK. It enforces security-critical
  options (permission mode, cwd, system prompt, hooks) and forwards the rest.

### Server

- **`server/app.py`** — the FastAPI application: endpoints to start runs, list
  and inspect sessions, browse workspace files, fetch diffs and conversation
  trajectories, and serve the React UI.
- **`server/session_manager.py`** — tracks session records and status, and
  handles TTL-based cleanup of stale sessions.
- **`server/models.py`** — request/response pydantic models and the
  `SessionStatus` enum.

### CLI

- **`cli.py`** — the `runspace-srv` entry point. Starts the server (local
  execution by default; `--docker` runs the Docker pre-flight and enables
  container mode).

## Adding a new agent backend

Implement the `FilesystemAgent` protocol and register it. The full step-by-step
recipe lives in the `FilesystemAgent` docstring in
[../src/runspace_agent/agents/base.py](../src/runspace_agent/agents/base.py).
Because every layer resolves agents through the registry, no changes are needed
outside `agents/`.
