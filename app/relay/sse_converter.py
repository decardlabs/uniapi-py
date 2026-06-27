"""SSE stream conversion between OpenAI Chat and Anthropic Messages formats.

Reference: docs/API中转站协议转换架构讨论.md §4.2
"""
from __future__ import annotations

import json
from typing import Any, Generator, Iterator


class ChatToAnthropicSSE:
    """Stateful converter: feed SSE lines one at a time, get Anthropic events back.

    Use ``feed(line)`` for each SSE line and ``flush()`` at stream end.
    This preserves real-time streaming behavior (no buffering).

    Some upstream Chat APIs (e.g. GLM) may send ``usage`` in a separate
    SSE chunk with ``choices: []``.  This converter stores such usage
    and includes it in the ``message_delta`` event.
    """

    def __init__(self):
        self.chat_id = ""
        self.text_buffer = ""
        self.tool_buffers: dict[int, dict[str, str]] = {}
        self.text_index = 0
        self.tool_index = 1
        self.text_block_started = False
        self.tool_block_started: dict[int, bool] = {}
        self.has_content = False
        self._done = False
        self._pending_usage: dict[str, Any] | None = None  # usage from separate chunk

    def _normalize_usage(self, usage: dict[str, Any] | None) -> dict[str, int] | None:
        """Normalize upstream usage to Anthropic format.

        Supports both OpenAI keys (prompt_tokens/completion_tokens) and
        Anthropic keys (input_tokens/output_tokens). Returns None when
        usage is empty or all-zero.
        """
        if not usage:
            return None
        inp = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        out = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        if inp == 0 and out == 0:
            return None
        return {"input_tokens": inp, "output_tokens": out}

    def feed(self, line: str) -> list[dict[str, Any]]:
        """Process one SSE line. Returns list of Anthropic event dicts."""
        events: list[dict[str, Any]] = []

        line = line.strip()
        if not line.startswith("data: "):
            return events

        payload = line[6:]
        if payload == "[DONE]":
            self._done = True
            if self.text_buffer and self.text_block_started:
                events.append(_make_event("content_block_stop", {"type": "content_block_stop", "index": self.text_index}))
            for ti in sorted(self.tool_buffers.keys()):
                if self.tool_block_started.get(ti):
                    events.append(_make_event("content_block_stop", {"type": "content_block_stop", "index": ti}))
            # Emit message_delta with pending usage if the finish_reason
            # chunk arrived before the usage-only chunk (e.g. GLM).
            if self._pending_usage and self.has_content:
                events.append(_make_event("message_delta", {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": self._pending_usage,
                }))
                self._pending_usage = None
            events.append(_make_event("message_stop", {"type": "message_stop"}))
            return events

        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            return events

        if not self.chat_id:
            self.chat_id = chunk.get("id", "")

        choices = chunk.get("choices", [])

        # Handle usage-only chunks (upstream may send usage in a separate
        # chunk with empty choices).  Store for later ``message_delta``.
        if not choices:
            usage = chunk.get("usage")
            if usage:
                normalized = self._normalize_usage(usage)
                if normalized:
                    self._pending_usage = normalized
            return events

        delta = choices[0].get("delta", {})
        finish_reason = choices[0].get("finish_reason")

        # Prefer usage from this chunk; fall back to pending usage from
        # a prior usage-only chunk; discard pending once consumed.
        usage = self._normalize_usage(chunk.get("usage")) or self._pending_usage
        self._pending_usage = None

        # --- message_start on first chunk with role ---
        if delta.get("role") == "assistant" and not self.has_content:
            self.has_content = True
            events.append(_make_event("message_start", {
                "type": "message_start",
                "message": {
                    "id": self.chat_id or f"msg_{self.chat_id}",
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": chunk.get("model", ""),
                    # Anthropic API requires usage in message_start
                    # (input_tokens=0 as placeholder; real tokens
                    # come in message_delta when GLM returns usage
                    # in a separate chunk after finish_reason).
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            }))

        # --- Text delta ---
        # GLM-5.2 sends content in ``reasoning_content`` with empty ``content``.
        # Merge reasoning_content into text so the Anthropic stream has actual output.
        text = delta.get("content") or delta.get("reasoning_content")
        if text:
            self.text_buffer += text
            if not self.text_block_started:
                self.text_block_started = True
                events.append(_make_event("content_block_start", {
                    "type": "content_block_start",
                    "index": self.text_index,
                    "content_block": {"type": "text", "text": ""},
                }))
            events.append(_make_event("content_block_delta", {
                "type": "content_block_delta",
                "index": self.text_index,
                "delta": {"type": "text_delta", "text": text},
            }))

        # --- Tool call deltas ---
        tool_calls = delta.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                idx = tc.get("index", 0)
                fn = tc.get("function", {})
                if idx not in self.tool_buffers:
                    self.tool_buffers[idx] = {"id": tc.get("id", ""), "name": fn.get("name", ""), "arguments": ""}
                if fn.get("name"):
                    self.tool_buffers[idx]["name"] = fn["name"]
                if tc.get("id"):
                    self.tool_buffers[idx]["id"] = tc["id"]
                if fn.get("arguments"):
                    self.tool_buffers[idx]["arguments"] += fn["arguments"]
                    if not self.tool_block_started.get(idx):
                        self.tool_block_started[idx] = True
                        events.append(_make_event("content_block_start", {
                            "type": "content_block_start",
                            "index": idx + self.tool_index,
                            "content_block": {
                                "type": "tool_use",
                                "id": self.tool_buffers[idx]["id"],
                                "name": self.tool_buffers[idx]["name"],
                                "input": {},
                            },
                        }))
                    events.append(_make_event("content_block_delta", {
                        "type": "content_block_delta",
                        "index": idx + self.tool_index,
                        "delta": {"type": "input_json_delta", "partial_json": fn["arguments"]},
                    }))

        # --- message_delta on finish_reason ---
        if finish_reason and self.has_content:
            if self.text_block_started:
                events.append(_make_event("content_block_stop", {"type": "content_block_stop", "index": self.text_index}))
                self.text_block_started = False
            for ti in sorted(self.tool_buffers.keys()):
                if self.tool_block_started.get(ti):
                    events.append(_make_event("content_block_stop", {"type": "content_block_stop", "index": ti + self.tool_index}))
                    self.tool_block_started[ti] = False

            sr_map = {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use", "content_filter": "end_turn"}
            stop_reason = sr_map.get(finish_reason, "end_turn")

            md: dict[str, Any] = {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            }
            if usage:
                md["usage"] = usage  # already normalized to Anthropic format
            events.append(_make_event("message_delta", md))

        return events

    def flush(self) -> list[dict[str, Any]]:
        """Return remaining events if the stream ended without [DONE]."""
        if self._done:
            return []
        events: list[dict[str, Any]] = []
        if self.has_content:
            if self.text_block_started:
                events.append(_make_event("content_block_stop", {"type": "content_block_stop", "index": self.text_index}))
            for ti in sorted(self.tool_buffers.keys()):
                if self.tool_block_started.get(ti):
                    events.append(_make_event("content_block_stop", {"type": "content_block_stop", "index": ti + self.tool_index}))
            events.append(_make_event("message_stop", {"type": "message_stop"}))
        self._done = True
        return events


def chat_to_anthropic_sse(
    chat_chunks: Iterator[str],
) -> Generator[dict[str, Any], None, None]:
    """Convert OpenAI Chat Completions SSE chunks to Anthropic SSE event dicts.

    Yields dicts with keys: event (str), data (dict).

    Convenience wrapper around ``ChatToAnthropicSSE`` for batch use.
    """
    converter = ChatToAnthropicSSE()
    for line in chat_chunks:
        for event in converter.feed(line):
            yield event
    for event in converter.flush():
        yield event


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
