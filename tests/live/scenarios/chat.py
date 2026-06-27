"""Chat Completion test scenarios."""

from __future__ import annotations

from ..client import http_post
from . import ScenarioResult


def test_chat_simple(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Simple non-streaming ChatCompletion."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "say hello in one word"}],
    }
    resp = http_post(
        f"{api_base}/v1/chat/completions", headers, body, timeout=timeout
    )
    if resp.ok:
        usage = resp.json.get("usage", {})
        content = resp.json.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ScenarioResult(
            name=f"Chat Simple ({model})",
            passed=True,
            detail=f"content={content!r}, tokens={usage.get('total_tokens', '?')}",
        )
    return ScenarioResult(
        name=f"Chat Simple ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or resp.body[:200]}",
    )


def test_chat_multi_turn(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Multi-turn ChatCompletion with assistant history."""
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": "my name is Alice"},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "what is my name?"},
        ],
    }
    resp = http_post(
        f"{api_base}/v1/chat/completions", headers, body, timeout=timeout
    )
    if resp.ok:
        content = resp.json.get("choices", [{}])[0].get("message", {}).get("content", "")
        remembered = "alice" in content.lower()
        return ScenarioResult(
            name=f"Multi-turn ({model})",
            passed=remembered,
            detail=f"content={content!r}",
            warn=not remembered,
        )
    return ScenarioResult(
        name=f"Multi-turn ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or resp.body[:200]}",
    )


def test_chat_reasoning_replay(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Multi-turn with reasoning_content in assistant message (DeepSeek)."""
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": "what is 2+2"},
            {
                "role": "assistant",
                "content": "4",
                "reasoning_content": "Simple arithmetic: 2+2=4",
            },
            {"role": "user", "content": "what is that plus 1"},
        ],
    }
    resp = http_post(
        f"{api_base}/v1/chat/completions", headers, body, timeout=timeout
    )
    if resp.ok:
        content = resp.json.get("choices", [{}])[0].get("message", {}).get("content", "")
        return ScenarioResult(
            name=f"Reasoning Replay ({model})",
            passed=True,
            detail=f"content={content!r}",
        )
    return ScenarioResult(
        name=f"Reasoning Replay ({model})",
        passed=False,
        detail=f"HTTP {resp.status}: {resp.error or resp.body[:200]}",
    )
