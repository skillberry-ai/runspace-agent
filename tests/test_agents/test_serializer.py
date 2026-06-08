"""Tests for the Claude Code message serializer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runspace_agent.agents.claude_code.serializer import serialize_messages


# Mock SDK types — mimic the dataclass structure used by claude_code_sdk
@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResultBlock:
    tool_use_id: str
    content: str | None = None
    is_error: bool | None = None


@dataclass
class ThinkingBlock:
    thinking: str
    signature: str = ""


@dataclass
class AssistantMessage:
    content: list[Any]
    model: str = "claude-opus-4-8"
    parent_tool_use_id: str | None = None


@dataclass
class UserMessage:
    content: str | list[Any]
    parent_tool_use_id: str | None = None


@dataclass
class SystemMessage:
    subtype: str
    data: dict[str, Any]


@dataclass
class ResultMessage:
    subtype: str
    duration_ms: int
    duration_api_ms: int
    is_error: bool
    num_turns: int
    session_id: str
    total_cost_usd: float | None = None
    usage: dict[str, Any] | None = None
    result: str | None = None


def test_serialize_assistant_with_text() -> None:
    msgs = [AssistantMessage(content=[TextBlock(text="Hello world")])]
    result = serialize_messages(msgs)
    assert len(result) == 1
    assert result[0]["type"] == "assistant"
    assert result[0]["model"] == "claude-opus-4-8"
    assert result[0]["content"] == [{"type": "text", "text": "Hello world"}]


def test_serialize_assistant_with_tool_use() -> None:
    msgs = [
        AssistantMessage(
            content=[
                ToolUseBlock(id="tu_1", name="Read", input={"file_path": "/tmp/test.py"}),
            ]
        )
    ]
    result = serialize_messages(msgs)
    block = result[0]["content"][0]
    assert block["type"] == "tool_use"
    assert block["name"] == "Read"
    assert block["input"] == {"file_path": "/tmp/test.py"}


def test_serialize_user_with_tool_result() -> None:
    msgs = [
        UserMessage(
            content=[
                ToolResultBlock(tool_use_id="tu_1", content="file contents here", is_error=False),
            ]
        )
    ]
    result = serialize_messages(msgs)
    assert result[0]["type"] == "user"
    block = result[0]["content"][0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "tu_1"
    assert block["content"] == "file contents here"
    assert block["is_error"] is False


def test_serialize_user_with_string_content() -> None:
    msgs = [UserMessage(content="plain text prompt")]
    result = serialize_messages(msgs)
    assert result[0]["content"] == "plain text prompt"


def test_serialize_system_message() -> None:
    msgs = [SystemMessage(subtype="init", data={"version": "1.0"})]
    result = serialize_messages(msgs)
    assert result[0]["type"] == "system"
    assert result[0]["subtype"] == "init"
    assert result[0]["data"] == {"version": "1.0"}


def test_serialize_result_message() -> None:
    msgs = [
        ResultMessage(
            subtype="success",
            duration_ms=5000,
            duration_api_ms=4500,
            is_error=False,
            num_turns=10,
            session_id="abc123",
            total_cost_usd=0.15,
            usage={"input_tokens": 1000, "output_tokens": 500},
            result="Done.",
        )
    ]
    result = serialize_messages(msgs)
    r = result[0]
    assert r["type"] == "result"
    assert r["duration_ms"] == 5000
    assert r["is_error"] is False
    assert r["num_turns"] == 10
    assert r["total_cost_usd"] == 0.15
    assert r["usage"]["input_tokens"] == 1000
    assert r["result"] == "Done."


def test_serialize_thinking_block() -> None:
    msgs = [
        AssistantMessage(
            content=[
                ThinkingBlock(thinking="Let me analyze this...", signature="sig123"),
            ]
        )
    ]
    result = serialize_messages(msgs)
    block = result[0]["content"][0]
    assert block["type"] == "thinking"
    assert block["thinking"] == "Let me analyze this..."
    # Signature should NOT be in the output
    assert "signature" not in block


def test_serialize_full_conversation() -> None:
    """Test a realistic multi-turn conversation."""
    msgs = [
        SystemMessage(subtype="init", data={"version": "1.0"}),
        AssistantMessage(
            content=[
                TextBlock(text="I'll read the file first."),
                ToolUseBlock(id="tu_1", name="Read", input={"file_path": "test.py"}),
            ]
        ),
        UserMessage(
            content=[
                ToolResultBlock(tool_use_id="tu_1", content="print('hello')"),
            ]
        ),
        AssistantMessage(content=[TextBlock(text="The file contains a print statement.")]),
        ResultMessage(
            subtype="success",
            duration_ms=3000,
            duration_api_ms=2800,
            is_error=False,
            num_turns=2,
            session_id="s123",
        ),
    ]
    result = serialize_messages(msgs)
    assert len(result) == 5
    assert [m["type"] for m in result] == [
        "system",
        "assistant",
        "user",
        "assistant",
        "result",
    ]


def test_serialize_empty_list() -> None:
    assert serialize_messages([]) == []
