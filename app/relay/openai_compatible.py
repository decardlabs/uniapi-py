from __future__ import annotations

"""OpenAI-compatible shared relay utilities.

Provides SSE streaming helpers and response processing for
OpenAI-compatible providers (including DeepSeek).
"""

import json
import time
import uuid
from typing import Any, AsyncGenerator, Optional

import httpx
from fastapi.responses import StreamingResponse


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
    output_format: str = "chat",
) -> dict | StreamingResponse:
    """Handle both streaming and non-streaming chat completion requests.

    Parameters
    ----------
    output_format : str
        "chat" (default, OpenAI format) or "anthropic" (convert SSE to Anthropic format).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if stream:
        client = httpx.AsyncClient()
        raw_stream = stream_chat_completion(client, upstream_url, body, headers)

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
