"""Claude Messages format test scenarios.

Tests the /v1/messages endpoint - for providers with NATIVE_FORMATS
including claude_messages, this goes direct without conversion.
"""

from __future__ import annotations

import json

from ..client import http_post, http_post_stream
from ..config import config
from . import ScenarioResult


def test_claude_messages_simple(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Non-streaming Claude Messages via /v1/messages."""
    body = {
        "model": model,
        "max_tokens": 200,
        "messages": [{"role": "user", "content": "say hello in one word"}],
    }
    claude_headers = dict(headers)
    claude_headers["anthropic-version"] = "2023-06-01"

    resp = http_post(
        f"{api_base}/v1/messages", claude_headers, body, timeout=timeout
    )
    if resp.ok:
        data = resp.json
        content_blocks = data.get("content", [])
        text = " ".join(
            c.get("text", "") for c in content_blocks if c.get("type") == "text"
        )
        model_out = data.get("model", "?")
        usage = data.get("usage", {})
        return ScenarioResult(
            name=f"Claude Messages ({model})",
            passed=True,
            detail=f"model={model_out}, text={text!r}, tokens={usage.get('output_tokens', '?')}",
        )

    body_snippet = resp.body[:300] if resp.body else ""
    return ScenarioResult(
        name=f"Claude Messages ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or body_snippet}",
    )


def test_claude_messages_tool(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Claude Messages with tool calling."""
    body = {
        "model": model,
        "max_tokens": 300,
        "messages": [
            {
                "role": "user",
                "content": "What's the weather in Beijing? Use the tool provided.",
            }
        ],
        "tools": [
            {
                "name": "get_weather",
                "description": "Get current weather for a city",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"}
                    },
                    "required": ["city"],
                },
            }
        ],
        "tool_choice": {"type": "any"},
    }
    claude_headers = dict(headers)
    claude_headers["anthropic-version"] = "2023-06-01"

    resp = http_post(
        f"{api_base}/v1/messages", claude_headers, body, timeout=timeout
    )
    if resp.ok:
        data = resp.json
        content_blocks = data.get("content", [])
        has_tool_use = any(c.get("type") == "tool_use" for c in content_blocks)
        stop_reason = data.get("stop_reason", "")
        return ScenarioResult(
            name=f"Claude Messages Tool ({model})",
            passed=has_tool_use,
            detail=f"stop_reason={stop_reason}, has_tool_use={has_tool_use}",
            warn=not has_tool_use,
        )

    body_snippet = resp.body[:300] if resp.body else ""
    return ScenarioResult(
        name=f"Claude Messages Tool ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or body_snippet}",
    )


def test_claude_messages_multi_turn(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Multi-turn Claude Messages (Claude Code pattern)."""
    body = {
        "model": model,
        "max_tokens": 200,
        "messages": [
            {"role": "user", "content": "My name is Bob"},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hi Bob! How can I help?"}],
            },
            {"role": "user", "content": "What is my name?"},
        ],
    }
    claude_headers = dict(headers)
    claude_headers["anthropic-version"] = "2023-06-01"

    resp = http_post(
        f"{api_base}/v1/messages", claude_headers, body, timeout=timeout
    )
    if resp.ok:
        data = resp.json
        content_blocks = data.get("content", [])
        text = " ".join(
            c.get("text", "") for c in content_blocks if c.get("type") == "text"
        )
        remembered = "bob" in text.lower()
        return ScenarioResult(
            name=f"Claude Messages Multi-turn ({model})",
            passed=remembered,
            detail=f"text={text!r}",
            warn=not remembered,
        )

    body_snippet = resp.body[:300] if resp.body else ""
    return ScenarioResult(
        name=f"Claude Messages Multi-turn ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or body_snippet}",
    )
