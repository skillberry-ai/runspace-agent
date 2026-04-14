"""Example: Send a skill improvement request to the runspace_agent server.

Runs in container mode so the original example files are never modified
and the example can be rerun repeatedly.

Prerequisites:
    1. Server running: uv run uvicorn runspace_agent.server.app:app --port 6767
    2. Docker running with the runspace-agent image built
    3. claude-code-sdk installed: uv pip install runspace-agent[claude]
    4. Set env vars: ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN (or IBM_THIRD_PARTY_API_KEY)

Usage:
    uv run python examples/skill_improvement/run_example.py

Expected Changes (what the agent should fix)
=============================================

The editable/ directory contains intentionally broken files. After a
successful run, the diff tab in the UI should show changes similar to:

**scripts/analyze.py** — 4 bugs to fix:

  1. Encoding: ``open(filepath, encoding="ascii")`` → ``encoding="utf-8"``
     (trace_002 crash: UnicodeDecodeError on German umlauts)

  2. Missing values: Remove the row-dropping logic that filters out rows
     with any blank field. Instead, compute stats per-column on non-empty
     values and report ``missing`` count per column.
     (trace_003: 15 of 50 rows silently dropped)

  3. Median: Add ``from statistics import median`` and include ``median``
     in numeric column output.
     (trace_004: median missing from numeric results)

  4. String stats: Replace the bare ``{"type": "string", "count": N}``
     with unique count, most frequent value, and its frequency using
     ``collections.Counter``.
     (trace_004: string columns only showed count)

**SKILL.md** — 3 incorrect instructions to fix:

  1. "Assume the file uses **ASCII** encoding"  → UTF-8
  2. "Skip rows with any missing values"         → handle per-column
  3. "cast to string and skip — just report count" → provide string stats
  4. "Only ASCII files are supported" / "Rows with missing values are
     dropped entirely" / "String columns just show a count" notes removed
"""

import os
import time
from pathlib import Path

import httpx

SERVER_URL = "http://localhost:6767"

# Resolve paths relative to this script
EXAMPLE_DIR = Path(__file__).parent
EDITABLE_DIR = str(EXAMPLE_DIR / "editable")
CONTEXT_DIR = str(EXAMPLE_DIR / "context")

PROMPT = """\
You are a skill improvement specialist. Your job is to analyze execution traces
and fix the issues found in the skill.

## Context Directory Layout

- `context/traces/` — Contains 4 execution traces (JSON files). Each has:
  - `success` (bool), `reward` (0.0-1.0), `summary`, `messages`, `evaluation_notes`
  - READ ALL OF THEM carefully.
- `context/domain_knowledge/policy.md` — The data handling requirements.

## Editable Directory Layout

- `editable/SKILL.md` — The skill instructions (has incorrect guidance).
- `editable/scripts/analyze.py` — The analysis script (has several bugs).

## Your Task

1. Read ALL trace files in `context/traces/` to understand what's failing.
2. Read `context/domain_knowledge/policy.md` to understand the requirements.
3. Read the current `editable/SKILL.md` and `editable/scripts/analyze.py`.
4. Fix the bugs in `analyze.py`:
   - ASCII encoding should be UTF-8
   - Missing values should be handled per-column, not by dropping rows
   - Add median calculation for numeric columns
   - Add proper string column statistics (unique count, most frequent)
5. Update `SKILL.md` to correct the wrong instructions:
   - Remove "assume ASCII encoding" — should say UTF-8
   - Remove "skip rows with missing values" — should say handle per-column
   - Remove "cast to string and skip" for mixed types — should say provide string stats
6. Make sure the script works correctly after your changes.
"""

REQUEST_BODY = {
    "editable_dir": EDITABLE_DIR,
    "context_dir": CONTEXT_DIR,
    "prompt": PROMPT,
    "editable_description": "An Anthropic skill for CSV analysis (SKILL.md + scripts/analyze.py). Has bugs to fix.",
    "context_description": "Execution traces showing failures + domain knowledge with data handling policy.",
    "preinstalled_skills": ["skill-creator"],  # only include the skill-creator preinstalled skill
    "mode": "container",  # no local! it will overwrite the local files then cant run the example again..
    "output_zip": False,
    # Reads from env vars: ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN (or aliases)
    "agent_settings": {
        "env": {
            k: v
            for k, v in {
                "ANTHROPIC_BASE_URL": os.environ.get("CLAUDE_CODE_LITELLM_BASE_URL")
                or os.environ.get("ANTHROPIC_BASE_URL", ""),
                "ANTHROPIC_AUTH_TOKEN": os.environ.get("IBM_THIRD_PARTY_API_KEY")
                or os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
                "ANTHROPIC_MODEL": os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6"),
                "ANTHROPIC_SMALL_FAST_MODEL": os.environ.get(
                    "ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku-4-5"
                ),
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5",
                "CLAUDE_CODE_SUBAGENT_MODEL": "claude-opus-4-6",
                "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
            }.items()
            if v
        }
    },
    "agent_max_turns": 50,
}


def main() -> None:
    print(f"Sending request to {SERVER_URL}/run ...")
    print(f"  Editable: {EDITABLE_DIR}")
    print(f"  Context:  {CONTEXT_DIR}")
    print()

    # 60 since it takes time for the container to spin up and run the agent
    resp = httpx.post(f"{SERVER_URL}/run", json=REQUEST_BODY, timeout=60)
    resp.raise_for_status()
    session = resp.json()
    session_id = session["session_id"]
    print(f"Session created: {session_id}")
    print(f"  Status: {session['status']}")
    print()

    # Poll until done
    created_at = session["created_at"]
    print("Waiting for agent to finish...")
    while True:
        time.sleep(5)
        resp = httpx.get(f"{SERVER_URL}/sessions/{session_id}", timeout=10)
        if resp.status_code == 404:
            # Session ID changes from "pending" to the real ID after task starts.
            # Find OUR session by matching the creation timestamp.
            all_sessions = httpx.get(f"{SERVER_URL}/sessions", timeout=10).json()
            for s in all_sessions:
                if s["created_at"] == created_at and s["session_id"] != "pending":
                    session_id = s["session_id"]
                    break
            resp = httpx.get(f"{SERVER_URL}/sessions/{session_id}", timeout=10)

        data = resp.json()
        status = data["status"]
        print(
            f"  [{status}] tokens={data.get('total_tokens', 0)} duration={data.get('duration_seconds', '?')}s"
        )

        if status in ("completed", "failed"):
            break

    print()
    if status == "completed":
        print("SUCCESS! The agent fixed the skill.")
        print()
        print(f"Browse session in UI:  {SERVER_URL}/ui/sessions/{session_id}")
        print("  - Files, diff, conversation, and summary all available in the UI")
        print()
        # Download result files via the API (original editable/ is NOT modified):
        # print(f"Download editable:     {SERVER_URL}/sessions/{session_id}/editable.zip")
        # print(f"View summary:          {SERVER_URL}/sessions/{session_id}/summary")
        # print(f"View conversation:     {SERVER_URL}/sessions/{session_id}/conversation")
    else:
        print(f"FAILED: {data.get('error', 'unknown error')}")


if __name__ == "__main__":
    main()
