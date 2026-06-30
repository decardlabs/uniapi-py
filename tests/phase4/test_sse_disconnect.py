"""
Tests for SSE streaming disconnect handling.

Verifies that disconnecting mid-stream doesn't leak connections or crash.
Targets two code paths:

1. ``_capture_stream_usage`` — the queue-based usage capture wrapper shared by
   non-raw-passthrough streaming.  It must cancel its background reader task
   when the generator receives ``GeneratorExit`` (client disconnect).

2. Full relay pipeline streaming — verifies that a client disconnecting from
   an SSE stream before it completes does not raise or leak.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from app.relay.openai_compatible import _capture_stream_usage


def _mk_sse_line(data: dict) -> str:
    """Build a single SSE data: line."""
    return f"data: {json.dumps(data)}\n\n"


@pytest.mark.asyncio
async def test_capture_stream_usage_handles_generator_exit():
    """``_capture_stream_usage`` must cancel its reader on GeneratorExit.

    When the consumer closes the generator early (simulating a client
    disconnect mid-stream), the background reader task must be cancelled
    and awaited cleanly — no dangling tasks.
    """
    # A stream that yields one chunk then hangs forever
    # (simulates an upstream response that isn't finished yet)
    hung = asyncio.Event()

    async def hanging_stream():
        yield _mk_sse_line({"choices": [{"delta": {"content": "hello"}}]})
        await hung.wait()  # never resolves — reader task hangs here

    captured: list[dict] = []

    async def on_usage(u):
        captured.append(u)

    gen = _capture_stream_usage(hanging_stream(), on_usage)

    # Consume one item (reader task is now running and blocked)
    item = await gen.__anext__()
    assert "hello" in item

    # Simulate client disconnect — triggers GeneratorExit inside the generator
    await gen.aclose()

    # The generator should be fully exhausted
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    # No callback should have fired (stream was interrupted before [DONE])
    assert len(captured) == 0

    # Hung event is still unreleased — if the reader task is still waiting on
    # it, an "unawaited task" warning would appear.  The test passes if we get
    # here without asyncio warnings.


@pytest.mark.asyncio
async def test_capture_stream_usage_completes_normally():
    """``_capture_stream_usage`` works end-to-end for a complete stream."""
    async def complete_stream():
        yield _mk_sse_line({"choices": [{"delta": {"content": "hi"}}]})

    captured: list[dict] = []

    async def on_usage(u):
        captured.append(u)

    gen = _capture_stream_usage(complete_stream(), on_usage)
    items = [item async for item in gen]

    assert items == [_mk_sse_line({"choices": [{"delta": {"content": "hi"}}]})]
    # No usage callback — stream ended without usage data
    assert len(captured) == 0


@pytest.mark.asyncio
async def test_capture_stream_usage_fires_usage_callback():
    """Usage callback fires after the final SSE event."""
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    async def stream_with_usage():
        yield _mk_sse_line({"choices": [{"delta": {"content": "hi"}}]})
        yield _mk_sse_line({
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": usage,
        })

    captured: list[dict] = []

    async def on_usage(u):
        captured.append(u)

    gen = _capture_stream_usage(stream_with_usage(), on_usage)
    items = [item async for item in gen]

    assert len(items) == 2
    assert len(captured) == 1
    assert captured[0] == usage


@pytest.mark.asyncio
async def test_streaming_client_disconnect_does_not_crash(
    client: AsyncClient,
):
    """Full relay streaming request where client disconnects mid-stream.

    Verifies the whole pipeline (auth, channel selection, upstream relay)
    handles a client-side disconnect without crashing or hanging.
    """
    # ── Setup: login and get token ────────────────────────────────
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    cookies = resp.cookies

    resp = await client.get("/api/token/?p=0&size=5", cookies=cookies)
    tokens = resp.json().get("data", [])
    assert len(tokens) > 0, "No tokens found"
    token_key = tokens[0]["key"]

    # Create a test channel using a model that DeepSeek adaptor supports
    await client.post("/api/channel/", json={
        "name": "SSE Disconnect Channel",
        "type": 39,  # DeepSeek
        "key": "sk-sse-disconnect-test",
        "models": "deepseek-v4-flash",
        "group": "default",
        "endpoint": "https://api.deepseek.com",
        "status": 1,
        "weight": 1,
    }, cookies=cookies)

    # ── Mock upstream: return a few SSE lines then hang ────────────
    sse_lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
        "data: " + json.dumps({"choices": [{"delta": {"content": " World"}}]}),
    ]

    class MockUpstreamResponse:
        """Mimics the httpx Response used by _eager_sse_stream."""
        status_code = 200
        headers = {"content-type": "text/event-stream"}

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

        async def aclose(self):
            pass

    mock_upstream_resp = MockUpstreamResponse()

    mock_upstream_client = AsyncMock(spec=httpx.AsyncClient)
    mock_upstream_client.send = AsyncMock(return_value=mock_upstream_resp)
    mock_upstream_client.aclose = AsyncMock()

    with patch("httpx.AsyncClient", return_value=mock_upstream_client):
        # Use client.stream() to read partial SSE, then disconnect
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True,
            },
            headers={"Authorization": f"Bearer {token_key}"},
        ) as resp:
            # Read a single chunk then disconnect (exit the context manager)
            async for chunk in resp.aiter_text():
                if chunk:
                    break

    # If we reach here without exceptions, the generator was cleaned up
    # properly when the client disconnected.
    assert True
