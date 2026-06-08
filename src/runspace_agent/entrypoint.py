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

from runspace_agent.agents import Workspace, build_agent_options, create_agent
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

    cwd = Path(config["cwd"])
    editable_dir = Path(config["editable_dir"])
    context_dir = Path(config["context_dir"])

    # Build sandbox hooks for the container workspace
    hooks = build_hooks_config(cwd)

    # Create the agent via the registry
    agent_type = config.get("agent_type", "claude-code")
    settings = dict(config.get("settings") or {})
    if "max_turns" in config:
        settings.setdefault("max_turns", config["max_turns"])
    if config.get("mcp_servers"):
        settings.setdefault("mcp_servers", config["mcp_servers"])

    options = build_agent_options(agent_type=agent_type, agent_settings=settings)
    agent = create_agent(agent_type=agent_type, options=options)

    workspace = Workspace(
        editable_dir=editable_dir,
        context_dir=context_dir,
        prompt=config["prompt"],
        skills_dir=cwd / agent.skills_folder_name
        if (cwd / agent.skills_folder_name).is_dir()
        else None,
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
