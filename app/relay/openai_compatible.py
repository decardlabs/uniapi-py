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

    Supports three SSE usage patterns:
    1. OpenAI Chat format: ``choices[0].finish_reason`` present
    2. Anthropic SSE format: ``type == "message_delta"``
    3. Usage-only chunk: ``choices`` is empty but ``usage`` present (GLM)
    """
    last_usage: dict[str, Any] | None = None
    async for line in raw_stream:
        if line.startswith("data: ") and '"usage"' in line:
            try:
                data = json.loads(line[6:].strip())
                choices = data.get("choices") or []
                usage = data.get("usage")
                # Skip empty usage dicts — some providers send usage={} early
                # without overwriting a previously captured valid last_usage
                if usage and not any(usage.values()):
                    usage = None
                # OpenAI Chat format: final chunk has choices[0].finish_reason
                if choices and choices[0].get("finish_reason") and usage:
                    last_usage = usage
                # Anthropic SSE format: message_delta carries usage at stream end
                elif data.get("type") == "message_delta" and usage:
                    last_usage = usage
                # Usage-only chunk: empty choices but usage present (e.g. GLM)
                elif usage:
                    last_usage = usage
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



async def relay_chat_completion(
    body: dict,
    upstream_url: str,
    api_key: str,
    stream: bool = False,
    request_headers: Optional[dict[str, str]] = None,
    output_format: str = "chat",
    on_stream_usage: Optional[Callable[[dict[str, Any]], None]] = None,
    raw_passthrough: bool = False,
) -> dict | StreamingResponse:
    """Handle both streaming and non-streaming chat completion requests.

    Parameters
    ----------
    output_format : str
        "chat" (default, OpenAI format) or "anthropic" (convert SSE to Anthropic format).
        Ignored when ``raw_passthrough=True``.
    on_stream_usage : callable, optional
        Called with usage dict after a streaming SSE stream ends.
        Only used when ``stream=True``.
    raw_passthrough : bool
        When True and ``stream=True``, raw upstream bytes are yielded as-is
        without any line processing or format conversion.  Use this for
        upstreams that already return the exact SSE format the downstream
        client expects (e.g. native Anthropic SSE passthrough).
    """
    headers = request_headers or {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if stream:
        client = httpx.AsyncClient()

        if raw_passthrough:
            # Eagerly check upstream status so 4xx/5xx errors propagate
            # to _handle_relay()'s try/except.
            req = client.build_request("POST", upstream_url, json=body, headers=headers)
            try:
                resp = await client.send(req, stream=True)
            except Exception:
                await client.aclose()
                raise
            if resp.status_code >= 400:
                await resp.aclose()
                await client.aclose()
                resp.raise_for_status()

            async def _eager_raw_stream():
                """Raw byte-level SSE passthrough — preserves original wire format.

                Light-scans the byte stream for Anthropic SSE message_delta
                events to capture actual token usage.
                """
                try:
                    last_usage: dict[str, Any] | None = None
                    scanner = b""

                    # NOTE: httpx.Response does NOT support async with when using
                    # client.send(stream=True). Use try/finally + aclose() instead.
                    try:
                        async for chunk in resp.aiter_bytes(chunk_size=4096):
                            yield chunk

                            if not last_usage:
                                scanner += chunk
                                # Also match `"type":"message_delta"` directly for
                                # providers whose Anthropic emulation omits the
                                # `event:` prefix line (e.g. MiniMax).
                                if (
                                    b'"usage"' in scanner
                                    and b'type":"message_delta"' in scanner
                                ):
                                    # Find the data: line nearest to message_delta
                                    idx = scanner.rfind(b'type":"message_delta"')
                                    data_prefix = b"data: "
                                    data_start = scanner.rfind(data_prefix, 0, idx)
                                    if data_start >= 0:
                                        data_start += len(data_prefix)
                                        data_end = scanner.find(b"\n", data_start)
                                        if data_end < 0:
                                            data_end = len(scanner)
                                        try:
                                            data_line = scanner[data_start:data_end]
                                            event_data = json.loads(data_line.decode("utf-8"))
                                            usage = event_data.get("usage")
                                            if usage and any(usage.values()):
                                                last_usage = usage
                                        except (json.JSONDecodeError, UnicodeDecodeError):
                                            pass

                                if len(scanner) > 16384:
                                    scanner = scanner[-8192:]

                        if last_usage is not None and on_stream_usage is not None:
                            await on_stream_usage(last_usage)
                    finally:
                        await resp.aclose()
                finally:
                    await client.aclose()

            return StreamingResponse(
                _eager_raw_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        # ── Eagerly establish upstream connection ────────────────────────
        # Use client.send() with stream=True to get response headers
        # WITHOUT consuming the body.  This way 4xx/5xx errors are raised
        # HERE — inside relay_chat_completion() — so _handle_relay()'s
        # try/except catches them and can record channel failures,
        # refund quota, and attempt failover.
        req = client.build_request("POST", upstream_url, json=body, headers=headers)
        try:
            resp = await client.send(req, stream=True)
        except Exception:
            await client.aclose()
            raise
        if resp.status_code >= 400:
            await resp.aclose()
            await client.aclose()
            resp.raise_for_status()

        # ── Stream from the established connection ──────────────────────
        async def _eager_sse_stream():
            """Read SSE lines from the already-validated upstream response."""
            try:
                # NOTE: httpx.Response does NOT support async with when using
                # client.send(stream=True). Use try/finally + aclose() instead.
                try:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            yield line + "\n\n"
                            if line.strip() == "data: [DONE]":
                                break
                        elif line.strip():
                            yield f"data: {line}\n\n"
                finally:
                    await resp.aclose()
            finally:
                await client.aclose()

        raw_stream = _eager_sse_stream()

        # Wrap with usage capture when a callback is provided
        if on_stream_usage is not None:
            raw_stream = _capture_stream_usage(raw_stream, on_stream_usage)

        if output_format == "anthropic":
            from app.relay.sse_converter import ChatToAnthropicSSE, _format_anthropic_sse

            async def converted_stream():
                converter = ChatToAnthropicSSE()
                async for line in raw_stream:
                    for event in converter.feed(line):
                        yield _format_anthropic_sse(event["event"], event["data"])
                # Flush remaining events (stream ended without [DONE] or buffered content)
                for event in converter.flush():
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
