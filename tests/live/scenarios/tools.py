"""Tool calling test scenarios (Chat Completions format)."""

from __future__ import annotations

from ..client import http_post
from . import ScenarioResult


def test_tool_call_basic(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Basic tool calling with function definition."""
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "What's the weather in Tokyo? Call the get_weather function.",
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "City name",
                            }
                        },
                        "required": ["city"],
                    },
                },
            }
        ],
        "tool_choice": "required",
    }
    resp = http_post(
        f"{api_base}/v1/chat/completions", headers, body, timeout=timeout
    )
    if resp.ok:
        msg = resp.json.get("choices", [{}])[0].get("message", {})
        has_tool_calls = bool(msg.get("tool_calls"))
        finish = msg.get("finish_reason", "")
        return ScenarioResult(
            name=f"Tool Call Basic ({model})",
            passed=has_tool_calls,
            detail=f"finish_reason={finish}, has_tool_calls={has_tool_calls}",
            warn=not has_tool_calls,
        )

    return ScenarioResult(
        name=f"Tool Call Basic ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or resp.body[:200]}",
    )


def test_tool_call_history(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Multi-turn tool calling with history."""
    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "What is the weather in Paris?",
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_paris_1",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"city": "Paris"}',
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "content": '{"temperature": 22, "condition": "sunny"}',
                "tool_call_id": "call_paris_1",
            },
            {
                "role": "assistant",
                "content": "The weather in Paris is sunny at 22°C.",
            },
            {
                "role": "user",
                "content": "What about London? Call the tool again.",
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name"}
                        },
                        "required": ["city"],
                    },
                },
            }
        ],
        "tool_choice": "required",
    }
    resp = http_post(
        f"{api_base}/v1/chat/completions", headers, body, timeout=timeout
    )
    if resp.ok:
        msg = resp.json.get("choices", [{}])[0].get("message", {})
        has_tool_calls = bool(msg.get("tool_calls"))
        finish = msg.get("finish_reason", "")
        return ScenarioResult(
            name=f"Tool Call History ({model})",
            passed=has_tool_calls,
            detail=f"finish_reason={finish}, has_tool_calls={has_tool_calls}",
            warn=not has_tool_calls,
        )

    return ScenarioResult(
        name=f"Tool Call History ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or resp.body[:200]}",
    )
