"""Prompt construction for runspace agent sessions."""

from __future__ import annotations

from pathlib import Path


def build_prompt(
    editable_dir: Path,
    context_dir: Path,
    user_prompt: str,
    editable_description: str = "",
    context_description: str = "",
) -> str:
    """Assemble the full agent prompt from components.

    Combines directory descriptions with the user's task prompt into a
    structured instruction that any :class:`FilesystemAgent` can follow.

    Parameters:
        editable_dir: Path to the editable directory (as seen by the agent).
        context_dir: Path to the context directory (as seen by the agent).
        user_prompt: The user's task-specific instructions.
        editable_description: Optional description of editable dir contents.
        context_description: Optional description of context dir contents.
    """
    editable_desc = editable_description or (
        "This directory contains files you should read and modify."
    )
    context_desc = context_description or (
        "This directory contains read-only reference material."
    )

    return f"""\
You have access to two directories:

1. **EDITABLE DIRECTORY**: `{editable_dir}`
   {editable_desc}

2. **CONTEXT DIRECTORY**: `{context_dir}`
   {context_desc}
   Common contents include: execution traces/trajectories, domain knowledge,
   performance history, and reward signals.

## Rules

- Focus your modifications on the editable directory.
- The context directory is for reference — read it but do not modify it.
  Changes to context files will not be preserved.
- You are running as an autonomous service with no human in the loop.
  No one is available to answer questions or provide clarification.
  When you encounter ambiguity, make a reasonable decision and move forward —
  asking a question will block this process indefinitely with no one to respond.
- After making changes, you MUST verify they work as intended. Run the code,
  execute tests, or otherwise validate that your modifications produce the
  expected behavior. Do not assume correctness — confirm it.

## Your Task

{user_prompt}

## Final Step — Session Summary

After completing all modifications, create a file called `summary.md` in the
current working directory (NOT inside editable/ or context/).

This summary will be displayed to users in the session dashboard UI, so write
it for a human audience — clear, concise, and well-structured.

Include:

1. **Objective**: What you were asked to do (1-2 sentences).
2. **Changes Made**: A bulleted list of every file you modified or created,
   with a brief description of each change.
3. **Verification & Testing**: Describe how you verified that your changes work
   correctly. Include: what tests or commands you ran, their output/results,
   and whether all checks passed. If any test failed, explain what went wrong
   and how you addressed it.
4. **Key Decisions**: Any non-obvious decisions or trade-offs you made and why.
5. **Recurrent Issues Found**: Any repeatable problems, failure patterns, or limitations you observed that could reappear in future runs, including where they occur and how they were handled in this session.

Write in Markdown format. Be thorough but concise.
"""
