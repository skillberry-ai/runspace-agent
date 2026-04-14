"""In-container entry point for runspace_agent.

Reads a JSON config from the path specified by the ``RUNSPACE_CONFIG``
environment variable, creates a :class:`FilesystemAgent` via the agent
factory, runs it, and prints the :class:`AgentResult` as JSON to stdout.

Usage inside a container::

    RUNSPACE_CONFIG=/workspace/config.json python -m runspace_agent.entrypoint
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from runspace_agent.agents import Workspace, create_default_agent
from runspace_agent.sandbox import build_hooks_config


def main() -> None:
    config_path = os.environ.get("RUNSPACE_CONFIG")
    if not config_path:
        print(
            json.dumps({"success": False, "error": "RUNSPACE_CONFIG not set"}),
            flush=True,
        )
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    session_id = config.get("session_id", "unknown")
    cwd = Path(config["cwd"])
    editable_dir = Path(config["editable_dir"])
    context_dir = Path(config["context_dir"])

    # Build sandbox hooks for the container workspace
    hooks = build_hooks_config(cwd)

    # Create the agent via the generic factory
    agent = create_default_agent(
        settings=config.get("settings"),
        max_turns=config.get("max_turns", 300),
        mcp_servers=config.get("mcp_servers"),
    )

    workspace = Workspace(
        editable_dir=editable_dir,
        context_dir=context_dir,
        prompt=config["prompt"],
        skills_dir=cwd / agent.skills_folder_name if (cwd / agent.skills_folder_name).is_dir() else None,
        cwd=cwd,
        hooks=hooks,
    )

    # Run the agent
    result = asyncio.run(agent.run(workspace))

    # Persist the conversation trajectory for the UI and API
    if result.conversation:
        conv_path = cwd.parent / "conversation.json"
        conv_path.write_text(
            json.dumps(result.conversation, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Output result as JSON (last line of stdout)
    result_dict = asdict(result)
    # Raw messages are not JSON-serializable; drop them (conversation field
    # already holds the serialized form and is saved to disk above).
    result_dict.pop("messages", None)
    print(json.dumps(result_dict), flush=True)


if __name__ == "__main__":
    main()
