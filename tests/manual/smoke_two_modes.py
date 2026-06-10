#!/usr/bin/env python3
"""Manual smoke test: fire one local + one container run, confirm both show up.

Not collected by pytest (no ``test_*`` name) — it needs a live server and spends
real tokens. Run it by hand:

    python tests/manual/smoke_two_modes.py

Assumes ``runspace-srv`` is already running on http://localhost:6767.

Auth: the agent needs credentials in its env to reach the model. This reads them
from your shell (base URL + auth token, or an API key) and forwards them via
``agent_settings.env`` — the same pattern the examples use. Container mode is a
clean room, so without this the container run fails with a non-zero exit.
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
    root = Path(tempfile.mkdtemp(prefix="smoke_"))
    editable = root / "editable"
    context = root / "context"
    editable.mkdir()
    context.mkdir()
    (editable / "notes.txt").write_text("start\n")
    (context / "README.md").write_text("Reference material.\n")
    return str(editable), str(context)


def _fire(mode: str, env: dict[str, str]) -> str:
    editable, context = _make_dirs()
    info = _post(
        "/run",
        {
            "name": f"smoke-{mode}",
            "editable_dir": editable,
            "context_dir": context,
            "prompt": "Append the line 'done' to notes.txt. Nothing else.",
            "mode": mode,
            "agent_settings": {"env": env},
        },
    )
    print(f"  {mode:9s} -> session {info['session_id']} ({info['status']})")
    return info["session_id"]


def main() -> None:
    env = build_env()
    if not env.get("ANTHROPIC_AUTH_TOKEN") and not env.get("ANTHROPIC_API_KEY"):
        print(
            "WARNING: no ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY in your env — "
            "runs will likely fail to authenticate.\n"
        )

    print("Firing one run per mode...")
    ids = {mode: _fire(mode, env) for mode in ("local", "container")}

    print("\nPolling /sessions until both leave 'running' (max 180s)...")
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        sessions = {s["session_id"]: s for s in _get("/sessions")}
        statuses = {m: sessions.get(sid, {}).get("status", "missing") for m, sid in ids.items()}
        print("  " + ", ".join(f"{m}={st}" for m, st in statuses.items()))
        if all(st in ("completed", "failed") for st in statuses.values()):
            break
        time.sleep(3)

    print("\nFinal check — both sessions present in /sessions (the UI's data source):")
    sessions = {s["session_id"]: s for s in _get("/sessions")}
    ok = True
    for mode, sid in ids.items():
        s = sessions.get(sid)
        if s is None:
            print(f"  MISSING: {mode} ({sid})")
            ok = False
        else:
            print(f"  OK: {mode} -> {s['status']}  (name={s.get('name')!r})")
    print(f"\n{'PASS' if ok else 'FAIL'} — open {BASE}/ui to see them in the UI.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Could not reach {BASE} — is `runspace-srv` running? ({exc})"
        ) from exc
