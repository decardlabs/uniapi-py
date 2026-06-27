"""Streaming test scenarios."""

from __future__ import annotations

from ..client import http_post_stream
from . import ScenarioResult


def test_stream_chat(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Streaming ChatCompletion."""
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "say hi in three words"}],
        "stream": True,
    }
    chunks = 0
    last_error = None
    for status, line, err in http_post_stream(
        f"{api_base}/v1/chat/completions", headers, body, timeout=timeout
    ):
        if err:
            last_error = err
        if line and line.startswith("data:"):
            chunks += 1

    if last_error:
        return ScenarioResult(
            name=f"Stream Chat ({model})",
            passed=False,
            detail=f"error: {last_error}",
        )
    if chunks == 0:
        return ScenarioResult(
            name=f"Stream Chat ({model})",
            passed=False,
            detail="no chunks received",
        )
    return ScenarioResult(
        name=f"Stream Chat ({model})",
        passed=True,
        detail=f"{chunks} chunks",
    )


def test_stream_claude_messages(
    model: str, headers: dict, api_base: str, timeout: int
) -> ScenarioResult:
    """Streaming Claude Messages via /v1/messages."""
    body = {
        "model": model,
        "max_tokens": 100,
        "stream": True,
        "messages": [{"role": "user", "content": "what is 3+3"}],
    }
    claude_headers = dict(headers)
    claude_headers["anthropic-version"] = "2023-06-01"

    events = 0
    last_error = None
    for status, line, err in http_post_stream(
        f"{api_base}/v1/messages", claude_headers, body, timeout=timeout
    ):
        if err:
            last_error = err
        if line and (line.startswith("event:") or line.startswith("data:")):
            events += 1

    if last_error:
        return ScenarioResult(
            name=f"Stream Claude Messages ({model})",
            passed=False,
            detail=f"error: {last_error}",
        )
    if events == 0:
        return ScenarioResult(
            name=f"Stream Claude Messages ({model})",
            passed=False,
            detail="no events received",
        )
    return ScenarioResult(
        name=f"Stream Claude Messages ({model})",
        passed=True,
        detail=f"{events} events",
    )
