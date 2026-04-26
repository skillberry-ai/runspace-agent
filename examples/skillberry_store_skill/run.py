"""Example: Run skillberry-store skill optimization using runspace_agent.

All modes require: ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN env vars.

Three modes are available (ordered by recommendation):

Attention: Runs about 11 minutes,
to expereince the library the skill_improvement example is faster to run.

  1. server
     Sends a request to the runspace_agent HTTP server, which runs the agent
     inside a Docker container. The most production-like and secure option.
     Prerequisites:
         uv pip install -e ".[all]"
         Docker running + runspace-agent:latest image built
         Start the server FIRST in a separate terminal:
             runspace-srv
     Run:
         uv run python examples/skillberry_store_skill/run.py server

  2. library-container
     Calls the Python library directly (no server), but still runs the agent
     inside a Docker container. The original editable/ directory is never modified.
     Prerequisites:
         uv pip install -e ".[claude,container]"
         Docker running + runspace-agent:latest image built
     Run:
         uv run python examples/skillberry_store_skill/run.py library-container

  3. library-local
     Calls the Python library directly, runs on your machine with no Docker.
     Fastest for development but least isolated — the agent modifies editable/.
     Prerequisites:
         uv pip install -e ".[claude]"
     Run:
         uv run python examples/skillberry_store_skill/run.py library-local
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from common import build_env, print_result
from prompt import build_prompt

from runspace_agent.prompt import SummarySection

EXAMPLE_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

EDITABLE_DIR = EXAMPLE_DIR / "editable" / "primitive-skill"
CONTEXT_DIR = EXAMPLE_DIR / "context"
EDITABLE_DESCRIPTION = "Anthropic skill for airline customer service (tau-bench)"
CONTEXT_DESCRIPTION = (
    "Tau-bench traces, evaluation criteria, and task definitions. "
    "Common contents include: execution traces/trajectories, domain knowledge, "
    "performance history, and reward signals."
)
EXTRA_SUMMARY_SECTIONS = [
    SummarySection(
        title="Recurrent Issues Found",
        content="Any repeatable problems, failure patterns, or limitations you "
        "observed that could reappear in future runs, including where they "
        "occur and how they were handled in this session.",
    ),
    SummarySection(
        title="Expected Production Behavior",
        content="Describe how the agent is expected to behave now in production as "
        "a result of your changes — specifically how it will avoid the "
        "issues identified in the traces.",
    ),
]
PREINSTALLED_SKILLS = ["skill-creator"]

# Load tasks and build prompt — pass the task IDs you want to optimize for
TASKS_FILE = CONTEXT_DIR / "tasks.json"
ALL_TASKS = json.loads(TASKS_FILE.read_text(encoding="utf-8"))
TARGET_TASK_IDS = {"9"}  # change this to target different tasks
TARGET_TASKS = [t for t in ALL_TASKS if t["id"] in TARGET_TASK_IDS]
PROMPT = build_prompt(TARGET_TASKS)


# ---------------------------------------------------------------------------
# Option 1: server (HTTP API + Docker) — recommended
#
# Start the server first in a separate terminal:
#     runspace-srv
# Then run this script:
#     uv run python examples/skillberry_store_skill/run.py server
# ---------------------------------------------------------------------------


def run_server() -> None:
    """Send a request to the runspace_agent HTTP server and poll for results."""
    import httpx

    server_url = os.environ.get("RUNSPACE_SERVER_URL", "http://localhost:6767")

    request_body = {
        "name": "skillberry-store-optimization",
        "editable_dir": str(EDITABLE_DIR),
        "context_dir": str(CONTEXT_DIR),
        "prompt": PROMPT,
        "editable_description": EDITABLE_DESCRIPTION,
        "context_description": CONTEXT_DESCRIPTION,
        "extra_summary_sections": EXTRA_SUMMARY_SECTIONS,
        "preinstalled_skills": PREINSTALLED_SKILLS,
        "agent_type": "claude-code",
        "mode": "container",
        "output_zip": False,
        "agent_settings": {"env": {k: v for k, v in build_env().items() if v}},
        "agent_max_turns": 50,
    }

    print(f"Sending request to {server_url}/run ...")
    resp = httpx.post(f"{server_url}/run", json=request_body, timeout=60)
    resp.raise_for_status()
    session = resp.json()
    session_id = session["session_id"]
    print(f"Session created: {session_id}")
    print()

    # Poll until done
    created_at = session["created_at"]
    print("Waiting for agent to finish...")
    while True:
        time.sleep(5)
        resp = httpx.get(f"{server_url}/sessions/{session_id}", timeout=10)
        if resp.status_code == 404:
            all_sessions = httpx.get(f"{server_url}/sessions", timeout=10).json()
            for s in all_sessions:
                if s["created_at"] == created_at and s["session_id"] != "pending":
                    session_id = s["session_id"]
                    break
            resp = httpx.get(f"{server_url}/sessions/{session_id}", timeout=10)

        data = resp.json()
        status = data["status"]
        print(
            f"  [{status}] tokens={data.get('total_tokens', 0)} "
            f"duration={data.get('duration_seconds', '?')}s"
        )
        if status in ("completed", "failed"):
            break

    print()
    if status == "completed":
        print("SUCCESS! The agent optimized the skill.")
        print(f"Browse session in UI: {server_url}/ui/sessions/{session_id}")
    else:
        print(f"FAILED: {data.get('error', 'unknown error')}")


# ---------------------------------------------------------------------------
# Option 2: library-container (Python library + Docker, no server needed)
# ---------------------------------------------------------------------------


async def run_library_container() -> None:
    """Run the agent in a Docker container — editable/ is never modified."""
    from claude_code_sdk import ClaudeCodeOptions

    from runspace_agent import RunspaceSession, run_agent
    from runspace_agent.agents.claude_code import ClaudeCodeAgent

    options = ClaudeCodeOptions(env=build_env(), max_turns=50)
    agent = ClaudeCodeAgent(options=options)

    session = RunspaceSession(
        editable_dir=EDITABLE_DIR,
        context_dir=CONTEXT_DIR,
        prompt=PROMPT,
        editable_description=EDITABLE_DESCRIPTION,
        context_description=CONTEXT_DESCRIPTION,
        extra_summary_sections=EXTRA_SUMMARY_SECTIONS,
        agent=agent,
        preinstalled_skills=PREINSTALLED_SKILLS,
        mode="container",
        output_zip=True,
        container_image="runspace-agent:latest",
        container_memory="4g",
        container_cpus=2,
    )

    print("Running agent in container mode (via library)...")
    result = await run_agent(session)
    print_result(result)

    if result.output_zip_path:
        print(f"Output zip: {result.output_zip_path}")


# ---------------------------------------------------------------------------
# Option 3: library-local (Python library, no Docker — least isolated)
# ---------------------------------------------------------------------------


async def run_library_local() -> None:
    """Run the agent locally — modifies editable/ directly."""
    from claude_code_sdk import ClaudeCodeOptions

    from runspace_agent import RunspaceSession, run_agent
    from runspace_agent.agents.claude_code import ClaudeCodeAgent

    options = ClaudeCodeOptions(env=build_env(), max_turns=50)
    agent = ClaudeCodeAgent(options=options)

    session = RunspaceSession(
        editable_dir=EDITABLE_DIR,
        context_dir=CONTEXT_DIR,
        prompt=PROMPT,
        editable_description=EDITABLE_DESCRIPTION,
        context_description=CONTEXT_DESCRIPTION,
        extra_summary_sections=EXTRA_SUMMARY_SECTIONS,
        agent=agent,
        preinstalled_skills=PREINSTALLED_SKILLS,
        mode="local",
    )

    print("Running agent in local mode (via library)...")
    result = await run_agent(session)
    print_result(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

MODES = {
    "server": run_server,
    "library-container": lambda: asyncio.run(run_library_container()),
    "library-local": lambda: asyncio.run(run_library_local()),
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in MODES:
        print("Usage: python run.py <mode>")
        print()
        print("Modes:")
        print(
            "  server             HTTP API + Docker (recommended, start server first)"
        )
        print("  library-container  Python library + Docker (no server needed)")
        print(
            "  library-local      Python library, no Docker (modifies editable/ directly)"
        )
        sys.exit(1)

    MODES[sys.argv[1]]()


if __name__ == "__main__":
    main()
