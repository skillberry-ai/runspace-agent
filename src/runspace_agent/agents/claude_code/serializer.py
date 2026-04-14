"""Serialize claude_code_sdk messages to JSON-serializable dicts.

Converts the SDK's dataclass message types into plain dicts with ``type``
discriminators so they can be persisted as ``conversation.json`` and
rendered in the session dashboard UI.

Uses ``type(obj).__name__`` checks rather than direct imports so the
module works even when the SDK isn't installed (serialization is only
called after a successful agent run, which already proved the SDK is
available).
"""

from __future__ import annotations

from typing import Any


def serialize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Convert a list of SDK message objects to JSON-serializable dicts."""
    return [_serialize_message(m) for m in messages]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _serialize_message(msg: Any) -> dict[str, Any]:
    name = type(msg).__name__

    if name == "AssistantMessage":
        d: dict[str, Any] = {
            "type": "assistant",
            "content": [_serialize_block(b) for b in (msg.content or [])],
        }
        if getattr(msg, "model", None):
            d["model"] = msg.model
        if getattr(msg, "parent_tool_use_id", None):
            d["parent_tool_use_id"] = msg.parent_tool_use_id
        return d

    if name == "UserMessage":
        content = msg.content
        if isinstance(content, str):
            serialized_content: Any = content
        elif isinstance(content, list):
            serialized_content = [_serialize_block(b) for b in content]
        else:
            serialized_content = str(content)
        d = {"type": "user", "content": serialized_content}
        if getattr(msg, "parent_tool_use_id", None):
            d["parent_tool_use_id"] = msg.parent_tool_use_id
        return d

    if name == "SystemMessage":
        return {
            "type": "system",
            "subtype": getattr(msg, "subtype", ""),
            "data": getattr(msg, "data", {}),
        }

    if name == "ResultMessage":
        return {
            "type": "result",
            "subtype": getattr(msg, "subtype", ""),
            "duration_ms": getattr(msg, "duration_ms", 0),
            "duration_api_ms": getattr(msg, "duration_api_ms", 0),
            "is_error": getattr(msg, "is_error", False),
            "num_turns": getattr(msg, "num_turns", 0),
            "session_id": getattr(msg, "session_id", ""),
            "total_cost_usd": getattr(msg, "total_cost_usd", None),
            "usage": getattr(msg, "usage", None),
            "result": getattr(msg, "result", None),
        }

    # Unknown message type — best-effort
    return {"type": name, "data": str(msg)}


def _serialize_block(block: Any) -> dict[str, Any]:
    name = type(block).__name__

    if name == "TextBlock":
        return {"type": "text", "text": block.text}

    if name == "ToolUseBlock":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }

    if name == "ToolResultBlock":
        d: dict[str, Any] = {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
        }
        if block.content is not None:
            d["content"] = block.content
        if block.is_error is not None:
            d["is_error"] = block.is_error
        return d

    if name == "ThinkingBlock":
        return {"type": "thinking", "thinking": block.thinking}

    # Unknown block type
    return {"type": name, "data": str(block)}
