"""Prompt construction for runspace agent sessions."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class SummarySection(BaseModel):
    """A single section in the agent's session summary."""

    title: str
    content: str

    def to_markdown(self, index: int) -> str:
        return f"{index}. **{self.title}**: {self.content}"


def build_prompt(
    editable_dir: Path,
    context_dir: Path,
    user_prompt: str,
    editable_description: str = "",
    context_description: str = "",
    extra_summary_sections: list[SummarySection] | None = None,
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
        extra_summary_sections: Optional additional :class:`SummarySection`
            entries appended to the session summary.
    """
    editable_desc = editable_description or (
        "This directory contains files you should read and modify."
    )
    context_desc = context_description or ("This directory contains read-only reference material.")

    summary_sections: list[SummarySection] = [
        SummarySection(
            title="Objective",
            content="What you were asked to do (1-2 sentences).",
        ),
        SummarySection(
            title="Changes Made",
            content="A bulleted list of every file you modified or created, "
            "with a brief description of each change.",
        ),
        SummarySection(
            title="Verification & Testing",
            content="Describe how you verified that your changes work correctly. "
            "Include: what tests or commands you ran, their output/results, "
            "and whether all checks passed. If any test failed, explain what "
            "went wrong and how you addressed it.",
        ),
        SummarySection(
            title="Key Decisions",
            content="Any non-obvious decisions or trade-offs you made and why.",
        ),
        SummarySection(
            title="Issues Found",
            content="If you encountered any repeatable problems, failure patterns, "
            "or limitations that could reappear in future runs, describe "
            "where they occur and how they were handled in this session. "
            "If none were found, you may omit this section.",
        ),
    ]

    if extra_summary_sections:
        summary_sections.extend(extra_summary_sections)

    numbered_sections = "\n".join(s.to_markdown(i) for i, s in enumerate(summary_sections, 1))

    return f"""\
You have access to two directories:

1. **EDITABLE DIRECTORY**: `{editable_dir}`
   {editable_desc}

2. **CONTEXT DIRECTORY**: `{context_dir}`
   {context_desc}

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

{numbered_sections}

Write in Markdown format. Be thorough but concise.
"""
