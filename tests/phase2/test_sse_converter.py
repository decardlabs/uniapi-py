"""Tests for SSE stream conversion (OpenAI Chat ↔ Anthropic Messages)."""
import pytest


class TestChatToAnthropicSSE:
    """OpenAI Chat SSE chunks → Anthropic SSE events."""

    def test_text_content_stream(self):
        """Simple text stream should produce content_block events."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        chunks = [
            'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":5,"completion_tokens":3,"total_tokens":8}}',
            'data: [DONE]',
        ]
        events = list(chat_to_anthropic_sse(iter(chunks)))
        assert len(events) > 3

        # Should start with message_start
        assert events[0]["event"] == "message_start"
        assert events[0]["data"]["type"] == "message_start"

        # Should have content_block_start
        start_events = [e for e in events if e["event"] == "content_block_start"]
        assert len(start_events) >= 1
        assert start_events[0]["data"]["content_block"]["type"] == "text"

        # Should have text deltas
        delta_events = [e for e in events if e["event"] == "content_block_delta"]
        assert len(delta_events) >= 1
        assert delta_events[0]["data"]["delta"]["type"] == "text_delta"

        # Should end with message_stop
        assert events[-1]["event"] == "message_stop"

    def test_tool_call_stream(self):
        """Tool call chunks should produce tool_use content blocks."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        chunks = [
            'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function","function":{"name":"get_weather","arguments":""}}]},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"city\\":\\"Bei"}}]},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"jing\\"}"}}]},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":50,"completion_tokens":20,"total_tokens":70}}',
            'data: [DONE]',
        ]
        events = list(chat_to_anthropic_sse(iter(chunks)))

        # Should have tool_use content_block_start
        tool_starts = [e for e in events
                       if e["event"] == "content_block_start"
                       and e["data"]["content_block"]["type"] == "tool_use"]
        assert len(tool_starts) >= 1
        assert tool_starts[0]["data"]["content_block"]["name"] == "get_weather"

        # Should have input_json_delta
        json_deltas = [e for e in events
                       if e["event"] == "content_block_delta"
                       and e["data"]["delta"]["type"] == "input_json_delta"]
        assert len(json_deltas) >= 1

        # Should have message_delta with stop_reason=tool_use
        msg_deltas = [e for e in events if e["event"] == "message_delta"]
        assert len(msg_deltas) == 1
        assert msg_deltas[0]["data"]["delta"]["stop_reason"] == "tool_use"

    def test_usage_in_message_delta(self):
        """Usage from final chunk should appear in message_delta."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        chunks = [
            'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}',
            'data: [DONE]',
        ]
        events = list(chat_to_anthropic_sse(iter(chunks)))
        msg_deltas = [e for e in events if e["event"] == "message_delta"]
        assert len(msg_deltas) == 1
        usage = msg_deltas[0]["data"]["usage"]
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 5

    def test_stop_reason_mapping(self):
        """Finish reasons should map correctly."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        cases = [("stop", "end_turn"), ("length", "max_tokens"), ("tool_calls", "tool_use")]
        for fr, expected in cases:
            chunks = [
                'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
                'data: {"id":"x","choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":null}]}',
                f'data: {{"id":"x","choices":[{{"index":0,"delta":{{}},"finish_reason":"{fr}"}}],"usage":{{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}}}',
                'data: [DONE]',
            ]
            events = list(chat_to_anthropic_sse(iter(chunks)))
            msg_deltas = [e for e in events if e["event"] == "message_delta"]
            assert len(msg_deltas) == 1
            assert msg_deltas[0]["data"]["delta"]["stop_reason"] == expected


class TestChatToAnthropicSSEOutput:
    """SSE converter output format."""

    def test_output_is_sse_event_dicts(self):
        """Each output item should have event and data keys."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        chunks = [
            'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}',
            'data: [DONE]',
        ]
        for item in chat_to_anthropic_sse(iter(chunks)):
            assert "event" in item
            assert "data" in item

    def test_format_to_sse_string(self):
        """_format_anthropic_sse should produce correct SSE wire format."""
        from app.relay.sse_converter import _format_anthropic_sse
        result = _format_anthropic_sse("message_start", {"type": "message_start", "message": {}})
        assert "event: message_start" in result
        assert "data: " in result
        assert result.endswith("\n\n")


class TestFormatAnthropicSSE:
    """_format_anthropic_sse wire format."""

    def test_produces_valid_sse(self):
        from app.relay.sse_converter import _format_anthropic_sse
        s = _format_anthropic_sse("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "hi"},
        })
        assert s.startswith("event: content_block_delta\n")
        assert "data: " in s
        assert s.count("\n\n") == 1  # single trailing blank line


class TestEdgeCases:
    """Edge cases for SSE conversion."""

    def test_empty_stream(self):
        """No chunks should yield no events."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        events = list(chat_to_anthropic_sse(iter([])))
        assert events == []

    def test_no_content_stream(self):
        """Chunks with no content should not produce message_start."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        chunks = [
            'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
            'data: [DONE]',
        ]
        events = list(chat_to_anthropic_sse(iter(chunks)))
        # Should have no message_start since no content
        msg_starts = [e for e in events if e["event"] == "message_start"]
        assert len(msg_starts) == 0

    def test_multiple_tool_calls(self):
        """Multiple parallel tool calls should each get their own content block."""
        from app.relay.sse_converter import chat_to_anthropic_sse
        chunks = [
            'data: {"id":"x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call_a","type":"function","function":{"name":"func_a","arguments":""}},{"index":1,"id":"call_b","type":"function","function":{"name":"func_b","arguments":""}}]},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{}"}},{"index":1,"function":{"arguments":"{}"}}]},"finish_reason":null}]}',
            'data: {"id":"x","choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}',
            'data: [DONE]',
        ]
        events = list(chat_to_anthropic_sse(iter(chunks)))
        tool_starts = [e for e in events
                       if e["event"] == "content_block_start"
                       and e["data"]["content_block"]["type"] == "tool_use"]
        assert len(tool_starts) == 2
        assert tool_starts[0]["data"]["content_block"]["name"] == "func_a"
        assert tool_starts[1]["data"]["content_block"]["name"] == "func_b"

    def test_full_conversion_round_trip(self):
        """Verify the full SSE string conversion produces valid Anthropic stream."""
        from app.relay.sse_converter import chat_to_anthropic_sse, _format_anthropic_sse
        chunks = [
            'data: {"id":"chatcmpl-x","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-x","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}',
            'data: {"id":"chatcmpl-x","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":1,"total_tokens":3}}',
            'data: [DONE]',
        ]
        events = list(chat_to_anthropic_sse(iter(chunks)))
        # Convert events back to SSE wire format
        sse_strings = [_format_anthropic_sse(e["event"], e["data"]) for e in events]
        full_output = "".join(sse_strings)
        # Verify structure
        assert "event: message_start" in full_output
        assert "event: content_block_start" in full_output
        assert "event: content_block_delta" in full_output
        assert "event: content_block_stop" in full_output
        assert "event: message_delta" in full_output
        assert "event: message_stop" in full_output
        assert "text_delta" in full_output
