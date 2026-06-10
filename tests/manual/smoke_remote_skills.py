#!/usr/bin/env python3
"""Manual smoke test: fire one run with `remote_skills` and prove the skill
landed in the agent's skills dir.

Not collected by pytest (no ``test_*`` name) — it needs a live server and spends
real tokens. Run it by hand:

    python tests/manual/smoke_remote_skills.py

Assumes ``runspace-srv`` is already running (set ``RUNSPACE_PORT`` to match its
port; defaults to 6767).

What it does:
  1. POST /run with ``remote_skills`` (default: ``vercel-labs/agent-skills``).
  2. Polls /sessions until the run leaves ``running``.
  3. Lists ``agent_workspace/.claude/skills`` via the files API and confirms the
     remote skill(s) were installed.
  4. Prints the session URL so you can open the skills dir in the web UI.

Overrides:
  RUNSPACE_PORT   server port (default 6767)
  REMOTE_SKILLS   comma-separated sources (default "vercel-labs/agent-skills")
  RUN_MODE        "local" (default) or "container"

Auth: the agent needs credentials in its env to reach the model. This reads them
from your shell (base URL + auth token, or an API key) and forwards them via
``agent_settings.env`` — the same pattern the examples use.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from runspace_agent.agents.claude_code import build_claude_env

BASE = f"http://localhost:{os.environ.get('RUNSPACE_PORT', '6767')}"
REMOTE_SKILLS = [
    s.strip()
    for s in os.environ.get("REMOTE_SKILLS", "vercel-labs/agent-skills").split(",")
    if s.strip()
]
MODE = os.environ.get("RUN_MODE", "local")

# Where remote skills land inside the session workspace (relative to its root).
SKILLS_PATH = "agent_workspace/.claude/skills"


def build_env() -> dict[str, str]:
    """Auth env forwarded to the agent (from the current environment)."""
    return {k: v for k, v in build_claude_env().items() if v}


def _post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _get(path: str) -> list | dict:
    with urllib.request.urlopen(BASE + path) as resp:
        return json.loads(resp.read())


def _make_dirs() -> tuple[str, str]:
    """Create a tiny editable + context dir the agent can work in."""
    root = Path(tempfile.mkdtemp(prefix="smoke_skills_"))
    editable = root / "editable"
    context = root / "context"
    editable.mkdir()
    context.mkdir()
    (editable / "notes.txt").write_text("start\n")
    (context / "README.md").write_text("Reference material.\n")
    return str(editable), str(context)


def main() -> None:
    env = build_env()
    if not env.get("ANTHROPIC_AUTH_TOKEN") and not env.get("ANTHROPIC_API_KEY"):
        print(
            "WARNING: no ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY in your env — "
            "the run will likely fail to authenticate (but skills still install "
            "at setup before the agent runs).\n"
        )

    editable, context = _make_dirs()
    print(f"Firing a {MODE} run with remote_skills={REMOTE_SKILLS} ...")
    info = _post(
        "/run",
        {
            "name": "smoke-remote-skills",
            "editable_dir": editable,
            "context_dir": context,
            "prompt": "Append the line 'done' to notes.txt. Nothing else.",
            "mode": MODE,
            "remote_skills": REMOTE_SKILLS,
            "agent_settings": {"env": env},
        },
    )
    sid = info["session_id"]
    print(f"  -> session {sid} ({info['status']})")

    print("\nPolling /sessions until it leaves 'running' (max 240s)...")
    deadline = time.monotonic() + 240
    status = info["status"]
    while time.monotonic() < deadline:
        sessions = {s["session_id"]: s for s in _get("/sessions")}
        status = sessions.get(sid, {}).get("status", "missing")
        print(f"  status={status}")
        if status in ("completed", "failed"):
            break
        time.sleep(3)

    print(f"\nListing {SKILLS_PATH} via the files API ...")
    try:
        entries = _get(f"/sessions/{sid}/files/{SKILLS_PATH}")
    except urllib.error.HTTPError as exc:
        entries = []
        print(f"  (could not list skills dir: HTTP {exc.code})")

    names = [e["name"] for e in entries] if isinstance(entries, list) else []
    if names:
        print(f"  installed skills: {', '.join(sorted(names))}")
    else:
        print("  no skills found in the skills dir")

    ok = bool(names)
    print(f"\n{'PASS' if ok else 'FAIL'} — remote skill(s) "
          f"{'present' if ok else 'MISSING'} in the agent's skills dir.")

    print("\nSee for yourself:")
    print(f"  UI (browse files):  {BASE}/ui/sessions/{sid}")
    print(f"  Skills dir (JSON):   {BASE}/sessions/{sid}/files/{SKILLS_PATH}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Could not reach {BASE} — is `runspace-srv` running? ({exc})"
        ) from exc
