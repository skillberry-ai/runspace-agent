"""Shared helpers for runspace_agent examples."""

from __future__ import annotations

import os
from enum import Enum


class ClaudeModel(str, Enum):
    OPUS_4_7 = "claude-opus-4-7"
    SONNET_4_6 = "claude-sonnet-4-6"
    HAIKU_4_5 = "claude-haiku-4-5"


def build_env(model: ClaudeModel | None = None) -> dict[str, str]:
    """Build environment variables for the Claude Code process.

    This is just an example — you can pass any env vars that enable
    claude-code-sdk to authenticate and configure the model.
    """
    model_id = (
        model.value if model else os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
    )
    return {
        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "")
        or os.environ.get("CLAUDE_CODE_LITELLM_BASE_URL", "")
        or os.environ.get("IBM_THIRD_PARTY_API_BASE", ""),
        "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        or os.environ.get("IBM_THIRD_PARTY_API_KEY", ""),
        "ANTHROPIC_MODEL": model_id,
        # "ANTHROPIC_SMALL_FAST_MODEL": os.environ.get("ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku-4-5"),
        # "ANTHROPIC_DEFAULT_OPUS_MODEL": os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL", "claude-opus-4-7"),
        # "ANTHROPIC_DEFAULT_SONNET_MODEL": os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-6"),
        # "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5"),
        "CLAUDE_CODE_SUBAGENT_MODEL": model_id,
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
        "opusPlanEnabled": "true",
    }


def print_result(result) -> None:
    """Print a RunspaceResult summary to stdout."""
    print(f"Success:  {result.success}")
    print(f"Session:  {result.session_id}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Tokens:   {result.agent_result.total_tokens}")
    if result.agent_result.error:
        print(f"Error:    {result.agent_result.error}")
    print(f"Output:   {result.output_dir}")
