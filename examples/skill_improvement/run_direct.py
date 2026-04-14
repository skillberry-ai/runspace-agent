"""Example: Run skill improvement directly via the library (no server needed).

Usage:
    uv run python examples/skill_improvement/run_direct.py

Environment variables (optional, override defaults):
    IBM_THIRD_PARTY_API_KEY   - API auth token
    CLAUDE_CODE_LITELLM_BASE_URL - LiteLLM proxy base URL
    ANTHROPIC_MODEL           - Model to use (default: claude-sonnet-4-6)
"""

import asyncio
import os
from pathlib import Path

from runspace_agent import RunspaceSession, run_agent
from runspace_agent.agents.claude_code import ClaudeCodeAgent

EXAMPLE_DIR = Path(__file__).parent

# Build env from environment variables or defaults.
# Reads from your shell env — set ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN
# (or IBM_THIRD_PARTY_API_KEY / CLAUDE_CODE_LITELLM_BASE_URL as aliases).
_ENV_DEFAULTS = {
    "ANTHROPIC_MODEL": "claude-opus-4-6",
    "ANTHROPIC_SMALL_FAST_MODEL": "claude-haiku-4-5",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5",
    "CLAUDE_CODE_SUBAGENT_MODEL": "claude-opus-4-6",
    "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
}

env: dict[str, str] = {}
base_url = os.environ.get("CLAUDE_CODE_LITELLM_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL", "")
auth_token = os.environ.get("IBM_THIRD_PARTY_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")

if base_url:
    env["ANTHROPIC_BASE_URL"] = base_url
if auth_token:
    env["ANTHROPIC_AUTH_TOKEN"] = auth_token
for k, v in _ENV_DEFAULTS.items():
    env[k] = os.environ.get(k, v)

agent = ClaudeCodeAgent(
    settings={"env": env},
    max_turns=50,
)

session = RunspaceSession(
    editable_dir=EXAMPLE_DIR / "editable",
    context_dir=EXAMPLE_DIR / "context",
    prompt="""\
You are a skill improvement specialist. Analyze the execution traces and fix the skill.

1. Read ALL trace files in context/traces/ — they show what's failing and why.
2. Read context/domain_knowledge/policy.md — the requirements to follow.
3. Fix editable/scripts/analyze.py:
   - Change ASCII encoding to UTF-8
   - Handle missing values per-column (don't drop entire rows)
   - Add median calculation
   - Add string column stats (unique count, most frequent value)
4. Fix editable/SKILL.md to match the corrected behavior.
""",
    editable_description="Anthropic skill with CSV analyzer (has bugs to fix)",
    context_description="Traces showing failures + domain policy requirements",
    agent=agent,
    preinstalled_skills=[],
    mode="local",
)


async def main() -> None:
    print("Running agent...")
    result = await run_agent(session)
    print(f"Success: {result.success}")
    print(f"Session: {result.session_id}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Tokens: {result.agent_result.total_tokens}")
    if result.agent_result.error:
        print(f"Error: {result.agent_result.error}")


asyncio.run(main())
