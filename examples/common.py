"""Shared helpers for runspace_agent examples.

For building Claude Code env vars, import ``build_claude_env`` (and ``ClaudeModel``)
from ``runspace_agent.agents.claude_code``.
"""

from __future__ import annotations


def print_result(result) -> None:
    """Print a RunspaceResult summary to stdout."""
    print(f"Success:  {result.success}")
    print(f"Session:  {result.session_id}")
    print(f"Duration: {result.duration_seconds}s")
    print(f"Tokens:   {result.agent_result.total_tokens}")
    if result.agent_result.error:
        print(f"Error:    {result.agent_result.error}")
    print(f"Output:   {result.output_dir}")
