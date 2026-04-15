# Skillberry Skill Maker Integration Guide

This guide explains how to use `runspace_agent` to replace stages 1-3 of the
[skillberry-skill-maker](../skillberry-skill-maker-future-integration/) pipeline.

## What It Replaces

The skillberry-skill-maker pipeline has 6 stages:

| Stage | Name | Replaced? |
|-------|------|-----------|
| 0 | Fold Evaluation | **No** — still runs to generate trajectories |
| 1 | Issues Identification | **Yes** — replaced by the agent |
| 2 | Remediation | **Yes** — replaced by the agent |
| 3 | Tool-Making | **Yes** — replaced by the agent |
| 4 | Selection | **Yes** — no longer needed |
| 5 | Skill-Generation | **Yes** — no longer needed |

Instead of five separate LangGraph-based multi-agent stages, a single
`FilesystemAgent` (e.g. Claude Code) reads the traces, identifies issues,
designs remediations, and **directly edits the skill files**. The updated
skill is then imported back into the Skillberry Store as the new version —
no selection or generation stage required.

## Directory Mapping

### Editable Directory

The **editable directory** should be an exported Anthropic skill from the
Skillberry Store. This is a directory following the standard skill format:

```
my-skill/
  SKILL.md              # Skill instructions and guidelines
  scripts/
    run.py              # Executable scripts
    helpers.py
  references/
    schemas.md          # Reference documentation
  assets/               # Static assets
```

The agent will read and modify these files to improve the skill based on
the context it receives.

### Context Directory

The **context directory** should contain read-only reference material.
Common practice is to organize it as:

```
context/
  traces/               # Agent execution trajectories from Stage 0 (Fold Evaluation)
    trace_001.json      # {reward, success, messages, metadata, ...}
    trace_002.json
    ...
  domain_knowledge/     # Domain specifications and policies
    policy.md           # Environment policy, constraints
    available_tools.md  # Tools available to the agent
    general_description.md
  performance_history/  # Historical benchmark results
    eval_results.json   # Previous evaluation metrics
    reward_history.json # Reward signals over time
```

**Traces** are the most important input. Each trace file contains a complete
agent execution trajectory with:
- `messages` — the conversation/action sequence
- `reward_info.reward` — numeric reward (float)
- `success` — boolean task outcome
- `metadata` — task ID, simulation ID, evaluation criteria

The agent analyzes these traces to find failure patterns and improvement
opportunities.

## Example Usage

```python
import asyncio
from pathlib import Path
from runspace_agent import RunspaceSession, run_agent
from runspace_agent.agents.claude_code import ClaudeCodeAgent

agent = ClaudeCodeAgent(
    settings={
        "env": {
            "ANTHROPIC_BASE_URL": "https://your-proxy.example.com",
            "ANTHROPIC_AUTH_TOKEN": "sk-...",
            "ANTHROPIC_MODEL": "claude-opus-4-6",
        },
        "model": "opus[1m]",
    },
    max_turns=300,
)

session = RunspaceSession(
    editable_dir=Path("./exported_skill"),
    context_dir=Path("./context"),
    prompt="""\
You are a skill improvement specialist.

In the context directory you have:
- traces/ — agent execution trajectories showing task performance.
  Each trace has a 'reward' (0.0-1.0) and 'success' (bool).
- domain_knowledge/ — policy documents and environment descriptions.
- performance_history/ — historical benchmark results.

In the editable directory you have an Anthropic skill with:
- SKILL.md — the skill's instructions and guidelines.
- scripts/ — executable Python scripts.
- references/ — reference documentation.

## Skillberry Store Anthropic Skill Format

The editable directory follows the Skillberry Store's Anthropic skill format.
The prompt MUST explain this format to the agent so it understands the
structure and purpose of each component:

- **SKILL.md** — The main skill definition file. Contains the skill's
  system-level instructions, behavioral guidelines, and constraints that
  govern how the agent should act when the skill is active. This is the
  most impactful file to modify.
- **scripts/** — Executable Python scripts that the skill can invoke as
  tools. Each script is a self-contained tool with defined inputs/outputs.
  Modifying these changes the skill's available actions.
- **references/** — Read-only reference documents (schemas, examples,
  domain knowledge) that the skill can consult. These provide grounding
  information but are not executed.
- **assets/** — Static files (images, templates, configs) used by the
  skill at runtime.

The prompt should make the agent aware that this is a **structured skill
package** — not a generic codebase — so changes should respect the format
conventions (e.g., tool definitions in scripts/, instructions in SKILL.md).

### Example Prompt Section

Include something like the following in your prompt:

```
The editable directory is an Anthropic skill exported from the Skillberry
Store. It follows a specific structure:
- SKILL.md: The skill's core instructions and behavioral guidelines.
  This is the primary file to update for improving agent behavior.
- scripts/: Executable tool scripts. Each .py file is a tool the agent
  can call. Modify these to fix tool-related failures.
- references/: Reference documentation the skill consults for context.
  Update these if traces show knowledge gaps.
- assets/: Static assets used at runtime.

When making changes, preserve this structure. Do not reorganize files
or break the skill format conventions.
```

## Example Usage

```python
import asyncio
from pathlib import Path
from runspace_agent import RunspaceSession, run_agent
from runspace_agent.agents.claude_code import ClaudeCodeAgent

agent = ClaudeCodeAgent(
    settings={
        "env": {
            "ANTHROPIC_BASE_URL": "https://your-proxy.example.com",
            "ANTHROPIC_AUTH_TOKEN": "sk-...",
            "ANTHROPIC_MODEL": "claude-opus-4-6",
        },
        "model": "opus[1m]",
    },
    max_turns=300,
)

session = RunspaceSession(
    editable_dir=Path("./exported_skill"),
    context_dir=Path("./context"),
    prompt="""\
You are a skill improvement specialist.

In the context directory you have:
- traces/ — agent execution trajectories showing task performance.
  Each trace has a 'reward' (0.0-1.0) and 'success' (bool).
- domain_knowledge/ — policy documents and environment descriptions.
- performance_history/ — historical benchmark results.

In the editable directory you have an Anthropic skill exported from the
Skillberry Store. It follows a specific format:
- SKILL.md — the skill's core instructions and behavioral guidelines.
  This is the primary file to update for improving agent behavior.
- scripts/ — executable tool scripts the agent can call. Modify these
  to fix tool-related failures.
- references/ — reference documentation the skill consults for context.
  Update these if traces show domain knowledge gaps.
- assets/ — static assets used at runtime.

Preserve the skill format structure when making changes.

Your task:
1. Read ALL traces in context/traces/ to understand current performance.
2. Identify failure patterns (low reward, success=false).
3. Identify what successful traces do differently.
4. Update SKILL.md to address the identified issues.
5. Modify or add scripts/ as needed to fix tool-related problems.
6. Update references/ if domain knowledge gaps are found.

Focus on: task_success, policy_compliance, plan_efficiency.
""",
    editable_description="Anthropic skill directory (Skillberry Store format)",
    context_description="Traces, domain knowledge, and performance history from fold evaluation",
    agent=agent,
    preinstalled_skills=None,  # include all preinstalled skills
    mode="local",
)

result = asyncio.run(run_agent(session))

if result.success:
    print(f"Skill improved! Session: {result.session_id}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Tokens: {result.agent_result.total_tokens}")
else:
    print(f"Failed: {result.agent_result.error}")
```

## Session Lifecycle and Cleanup

Sessions are **single-use by design** — there is no recall or resume within the
same session. Reusing sessions would require complex summarization per run and
add unnecessary state management. Instead, to run another improvement iteration,
create a **new session** with the updated editable directory and fresh context.

Each pipeline run should:

1. Create a new session and upload the current context + editable directory.
2. Run the agent.
3. Download the resulting `editable.zip`.
4. (Optional) Delete the session immediately, or let it auto-cleanup.

Sessions are automatically cleaned up after the configured TTL (default: 8
hours of inactivity, set via `--session-ttl`). If you want to free disk space
immediately rather than waiting for the auto-cleanup, delete the session
explicitly:

```bash
# Download the improved skill
curl -O http://localhost:6767/sessions/{session_id}/editable.zip

# (Optional) Delete the session immediately to free space
# Otherwise it will be auto-deleted after the session TTL expires
curl -X DELETE http://localhost:6767/sessions/{session_id}
```

This ensures every pipeline run gets a clean slate with fresh context and
the latest editable directory, avoiding stale state from previous runs.

## Wiring Back Into the Pipeline

After `run_agent()` completes, the modified editable directory contains the
improved skill. Import it back into the Skillberry Store as the new skill
version — stages 4 (Selection) and 5 (Skill-Generation) are no longer needed.

In the pipeline orchestrator
(`skillberry-skill-maker/src/skillberry_skill_maker/pipeline/orchestrator.py`),
replace the sequential calls to `IssuesIdentificationStage`,
`RemediationStage`, `ToolMakingStage`, `SelectionStage`, and
`SkillGenerationStage` with a single `run_agent()` call, then push the
result back to the store.

## Container Mode

For production use, run the agent in a Docker container for full isolation:

```python
session = RunspaceSession(
    editable_dir=Path("./exported_skill"),
    context_dir=Path("./context"),
    prompt="...",
    agent=agent,
    mode="container",
    container_image="runspace-agent:latest",
    container_memory="8g",
    container_cpus=4,
    container_mode="ephemeral",
)
```

Build the Docker image first:

```bash
docker build -t runspace-agent:latest .
```

## Server Mode

For a managed HTTP API with session tracking and a file browser UI:

```bash
uv pip install runspace-agent[all]

# Production
uv run uvicorn runspace_agent.server.app:app --host 0.0.0.0 --port 6767

# Development (auto-reload on code changes)
uv run uvicorn runspace_agent.server.app:app --host 0.0.0.0 --port 6767 --reload
```

Then use the REST API:

```bash
# Start a session
curl -X POST http://localhost:6767/run \
  -H "Content-Type: application/json" \
  -d '{"editable_dir": "./exported_skill", "context_dir": "./context", "prompt": "..."}'

# Check status
curl http://localhost:6767/sessions/{session_id}

# Browse files
curl http://localhost:6767/sessions/{session_id}/files

# Download result
curl -O http://localhost:6767/sessions/{session_id}/editable.zip
```

Or use the web UI at `http://localhost:6767/ui`.
