from __future__ import annotations

"""OpenAI-compatible shared relay utilities.

Provides SSE streaming helpers and response processing for
OpenAI-compatible providers (including DeepSeek).
"""

import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Callable, Optional

import httpx
from fastapi.responses import StreamingResponse


async def _capture_stream_usage(
    raw_stream: AsyncGenerator[str, None],
    on_usage: Callable[[dict[str, Any]], None],
) -> AsyncGenerator[str, None]:
    """Wrap an SSE stream to capture the final usage chunk.

    The last SSE event before [DONE] may carry token usage. This wrapper
    captures that usage and calls ``on_usage`` after the stream ends.
    """
    last_usage: dict[str, Any] | None = None
    async for line in raw_stream:
        if line.startswith("data: ") and '"usage"' in line:
            try:
                data = json.loads(line[6:].strip())
                choices = data.get("choices") or []
                # Only the final chunk carries usage + finish_reason
                if choices and choices[0].get("finish_reason"):
                    last_usage = data.get("usage")
            except json.JSONDecodeError:
                pass
        yield line
    if last_usage is not None:
        await on_usage(last_usage)


def make_chat_completion_response(
    model: str,
    content: str,
    usage: dict[str, int],
    reasoning_content: Optional[str] = None,
) -> dict:
    """Build a standard OpenAI Chat Completion response dict."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if reasoning_content:
        message["reasoning_content"] = reasoning_content

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "prompt_tokens_details": {
                "cached_tokens": usage.get("cached_tokens", 0),
            },
            "completion_tokens_details": {
                "reasoning_tokens": usage.get("reasoning_tokens", 0),
            },
        },
    }


async def stream_chat_completion(
    client: httpx.AsyncClient,
    url: str,
    body: dict,
    headers: dict[str, str],
) -> AsyncGenerator[str, None]:
    """Stream SSE events from upstream, transparently proxying to client."""
    async with client.stream(
        "POST", url, json=body, headers=headers, timeout=300
    ) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                yield line + "\n\n"
                if line.strip() == "data: [DONE]":
                    break
            elif line.strip():
                yield f"data: {line}\n\n"


async def relay_chat_completion(
    body: dict,
    upstream_url: str,
    api_key: str,
    stream: bool = False,
    request_headers: Optional[dict[str, str]] = None,
    output_format: str = "chat",
    on_stream_usage: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict | StreamingResponse:
    """Handle both streaming and non-streaming chat completion requests.

    Parameters
    ----------
    output_format : str
        "chat" (default, OpenAI format) or "anthropic" (convert SSE to Anthropic format).
    on_stream_usage : callable, optional
        Called with usage dict after a streaming SSE stream ends.
        Only used when ``stream=True``.
    """
    headers = request_headers or {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if stream:
        client = httpx.AsyncClient()
        raw_stream = stream_chat_completion(client, upstream_url, body, headers)

        # Wrap with usage capture when a callback is provided
        if on_stream_usage is not None:
            raw_stream = _capture_stream_usage(raw_stream, on_stream_usage)

        if output_format == "anthropic":
            from app.relay.sse_converter import chat_to_anthropic_sse, _format_anthropic_sse

            async def converted_stream():
                lines: list[str] = []
                async for line in raw_stream:
                    if line.startswith("data: "):
                        lines.append(line.strip())
                    elif line.strip() == "data: [DONE]":
                        lines.append("data: [DONE]")

                # Yield events one at a time as the generator produces them
                for event in chat_to_anthropic_sse(iter(lines)):
                    yield _format_anthropic_sse(event["event"], event["data"])

            return StreamingResponse(
                converted_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        return StreamingResponse(
            raw_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            upstream_url, json=body, headers=headers, timeout=300
        )
        resp.raise_for_status()
        return resp.json()
