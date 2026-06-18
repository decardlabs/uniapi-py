"""SSE stream conversion between OpenAI Chat and Anthropic Messages formats.

Reference: docs/API中转站协议转换架构讨论.md §4.2
"""
from __future__ import annotations

import json
from typing import Any, Generator, Iterator


def chat_to_anthropic_sse(
    chat_chunks: Iterator[str],
) -> Generator[dict[str, Any], None, None]:
    """Convert OpenAI Chat Completions SSE chunks to Anthropic SSE event dicts.

    Yields dicts with keys: event (str), data (dict).
    """
    chat_id = ""
    text_buffer = ""
    tool_buffers: dict[int, dict] = {}  # index -> {id, name, arguments}
    text_index = 0
    tool_index = 1
    text_block_started = False
    tool_block_started: dict[int, bool] = {}
    has_content = False

    for line in chat_chunks:
        line = line.strip()
        if not line.startswith("data: "):
            continue

        payload = line[6:]
        if payload == "[DONE]":
            # Emit remaining content blocks
            if text_buffer and text_block_started:
                yield _make_event("content_block_stop", {"type": "content_block_stop", "index": text_index})
            for ti in sorted(tool_buffers.keys()):
                if tool_block_started.get(ti):
                    yield _make_event("content_block_stop", {"type": "content_block_stop", "index": ti})
            yield _make_event("message_stop", {"type": "message_stop"})
            return

        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if not chat_id:
            chat_id = chunk.get("id", "")

        choices = chunk.get("choices", [])
        if not choices:
            continue

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")
        usage = chunk.get("usage")

        # --- message_start on first chunk with role ---
        if delta.get("role") == "assistant" and not has_content:
            has_content = True
            yield _make_event("message_start", {
                "type": "message_start",
                "message": {
                    "id": chat_id or f"msg_{chat_id}",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": chunk.get("model", ""),
                },
            })

        # --- Text delta ---
        text = delta.get("content")
        if text:
            text_buffer += text
            if not text_block_started:
                text_block_started = True
                yield _make_event("content_block_start", {
                    "type": "content_block_start",
                    "index": text_index,
                    "content_block": {"type": "text", "text": ""},
                })
            yield _make_event("content_block_delta", {
                "type": "content_block_delta",
                "index": text_index,
                "delta": {"type": "text_delta", "text": text},
            })

        # --- Tool call deltas ---
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                idx = tc.get("index", 0)
                fn = tc.get("function", {})
                if idx not in tool_buffers:
                    tool_buffers[idx] = {"id": tc.get("id", ""), "name": fn.get("name", ""), "arguments": ""}
                if fn.get("name"):
                    tool_buffers[idx]["name"] = fn["name"]
                if tc.get("id"):
                    tool_buffers[idx]["id"] = tc["id"]
                if fn.get("arguments"):
                    tool_buffers[idx]["arguments"] += fn["arguments"]
                    if not tool_block_started.get(idx):
                        tool_block_started[idx] = True
                        yield _make_event("content_block_start", {
                            "type": "content_block_start",
                            "index": idx + tool_index,
                            "content_block": {
                                "type": "tool_use",
                                "id": tool_buffers[idx]["id"],
                                "name": tool_buffers[idx]["name"],
                                "input": {},
                            },
                        })
                    yield _make_event("content_block_delta", {
                        "type": "content_block_delta",
                        "index": idx + tool_index,
                        "delta": {"type": "input_json_delta", "partial_json": fn["arguments"]},
                    })

        # --- message_delta on finish_reason ---
        if finish_reason and has_content:
            # Close text block if open
            if text_block_started:
                yield _make_event("content_block_stop", {"type": "content_block_stop", "index": text_index})
                text_block_started = False
            # Close tool blocks
            for ti in sorted(tool_buffers.keys()):
                if tool_block_started.get(ti):
                    yield _make_event("content_block_stop", {"type": "content_block_stop", "index": ti + tool_index})
                    tool_block_started[ti] = False

            # Map finish_reason
            sr_map = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use", "content_filter": "end_turn"}
            stop_reason = sr_map.get(finish_reason, "end_turn")

            md = {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            }
            if usage:
                md["usage"] = {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                }
            yield _make_event("message_delta", md)

    # Fallback: close if stream ended without [DONE]
    if has_content:
        if text_block_started:
            yield _make_event("content_block_stop", {"type": "content_block_stop", "index": text_index})
        for ti in sorted(tool_buffers.keys()):
            if tool_block_started.get(ti):
                yield _make_event("content_block_stop", {"type": "content_block_stop", "index": ti + tool_index})
        yield _make_event("message_stop", {"type": "message_stop"})


def anthropic_to_chat_sse(
    anthropic_events: Iterator[dict[str, Any]],
) -> Generator[str, None, None]:
    """Convert Anthropic SSE event dicts to OpenAI Chat Completions SSE chunks.

    Input: iterator of dicts with keys: event (str), data (dict).
    Yields: SSE data lines (strings) in OpenAI Chat format.

    This is the reverse of chat_to_anthropic_sse.
    """
    chat_id = ""
    model = ""
    tool_buffers: dict[int, dict] = {}  # index -> {id, name, arguments}
    first_chunk = True

    for ev in anthropic_events:
        event_type = ev.get("event", "")
        data = ev.get("data", {})

        if event_type == "message_start":
            msg = data.get("message", {})
            chat_id = msg.get("id", chat_id)
            model = msg.get("model", model)
            yield _format_chat_chunk(chat_id, model, {"role": "assistant"})

        elif event_type == "content_block_start":
            block = data.get("content_block", {})
            idx = data.get("index", 0)
            btype = block.get("type", "")

            if btype == "tool_use":
                tool_id = block.get("id", "")
                tool_name = block.get("name", "")
                tool_buffers[idx] = {"id": tool_id, "name": tool_name, "arguments": ""}
                yield _format_chat_chunk(chat_id, model, {
                    "tool_calls": [{
                        "index": idx,
                        "id": tool_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": ""},
                    }],
                })

        elif event_type == "content_block_delta":
            delta = data.get("delta", {})
            dtype = delta.get("type", "")
            idx = data.get("index", 0)

            if dtype == "text_delta":
                text = delta.get("text", "")
                yield _format_chat_chunk(chat_id, model, {"content": text})

            elif dtype == "input_json_delta":
                partial = delta.get("partial_json", "")
                if idx not in tool_buffers:
                    tool_buffers[idx] = {"id": "", "name": "", "arguments": ""}
                tool_buffers[idx]["arguments"] += partial
                yield _format_chat_chunk(chat_id, model, {
                    "tool_calls": [{
                        "index": idx,
                        "function": {"arguments": partial},
                    }],
                })

        elif event_type == "message_delta":
            msg_delta = data.get("delta", {})
            stop_reason = msg_delta.get("stop_reason")
            usage = data.get("usage", {})

            sr_map = {"end_turn": "stop", "max_tokens": "length", "tool_use": "tool_calls"}
            chat_finish = sr_map.get(stop_reason, "stop") if stop_reason else None

            final_chunk = {}
            if chat_finish:
                final_chunk["finish_reason"] = chat_finish
                if usage:
                    final_chunk["usage"] = {
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                        "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                    }
            yield _format_chat_chunk(chat_id, model, {}, finish_reason=chat_finish, usage=final_chunk.get("usage"))

        elif event_type == "message_stop":
            yield "data: [DONE]\n\n"


def _format_chat_chunk(
    chat_id: str,
    model: str,
    delta: dict,
    finish_reason: str | None = None,
    usage: dict | None = None,
) -> str:
    """Format a chunk as an OpenAI Chat SSE data line."""
    chunk = {
        "id": chat_id or f"chatcmpl-{int(__import__('time').time())}",
        "object": "chat.completion.chunk",
        "model": model or "unknown",
        "choices": [{"index": 0, "delta": delta}],
    }
    if finish_reason:
        chunk["choices"][0]["finish_reason"] = finish_reason
    if usage:
        chunk["usage"] = usage
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def _make_event(event: str, data: dict) -> dict[str, Any]:
    """Create an SSE event dict."""
    return {"event": event, "data": data}


def _format_anthropic_sse(event: str, data: dict) -> str:
    """Format an SSE event dict to wire format string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
