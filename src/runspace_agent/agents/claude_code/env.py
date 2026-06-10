"""Helper for building Claude Code environment variables from the current shell.

This is a convenience for the examples and manual tests in this repo — it reads
your real ``os.environ`` to assemble the env dict passed to Claude Code. Library
users typically don't need it: they call ``POST /run`` and pass their own
credentials explicitly via ``agent_settings.env`` (or ``ClaudeCodeOptions.env``).
"""

from __future__ import annotations

import os
from enum import StrEnum


class ClaudeModel(StrEnum):
    OPUS_4_8 = "claude-opus-4-8"
    SONNET_4_6 = "claude-sonnet-4-6"
    HAIKU_4_5 = "claude-haiku-4-5"


def build_claude_env(model: ClaudeModel | None = None) -> dict[str, str]:
    """Build Claude Code env vars from the current environment.

    Reads credentials/config from ``os.environ`` (with a couple of common
    fallbacks). Callers typically drop empty values before use, e.g.
    ``{k: v for k, v in build_claude_env().items() if v}``.
    """
    model_id = (
        model.value if model else os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
    )
    return {
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "")
        or os.environ.get("CLAUDE_CODE_LITELLM_BASE_URL", "")
        or os.environ.get("IBM_THIRD_PARTY_API_BASE", ""),
        "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        or os.environ.get("IBM_THIRD_PARTY_API_KEY", ""),
        "ANTHROPIC_MODEL": model_id,
        "CLAUDE_CODE_SUBAGENT_MODEL": model_id,
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1",
        "opusPlanEnabled": "true",
    }
