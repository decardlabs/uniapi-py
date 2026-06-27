"""Tests for DeepSeek request normalization."""


from app.relay.adaptors.deepseek.request import (
    backfill_tool_message_names,
    inject_reasoning_content,
    normalize_thinking_type,
    normalize_tool_message_content,
    strip_unsupported_fields,
)


class TestNormalizeThinkingType:
    def test_adaptive_to_enabled(self):
        result = normalize_thinking_type({"type": "adaptive", "budget_tokens": 1024})
        assert result is not None
        assert result["type"] == "enabled"
        assert result["budget_tokens"] == 1024

    def test_enabled_passthrough(self):
        result = normalize_thinking_type({"type": "enabled", "budget_tokens": 2048})
        assert result is not None
        assert result["type"] == "enabled"

    def test_disabled_passthrough(self):
        result = normalize_thinking_type({"type": "disabled"})
        assert result is None

    def test_empty_with_budget(self):
        result = normalize_thinking_type({"budget_tokens": 4096})
        assert result is not None
        assert result["type"] == "enabled"

    def test_empty_without_budget(self):
        result = normalize_thinking_type({})
        assert result is None

    def test_none_input(self):
        assert normalize_thinking_type(None) is None


class TestInjectReasoningContent:
    def test_existing_content_preserved(self):
        messages = [
            {"role": "assistant", "content": "Hello", "reasoning_content": "Let me think...", "tool_calls": [{"id": "tc1"}]}
        ]
        result = inject_reasoning_content(messages)
        assert result[0]["reasoning_content"] == "Let me think..."

    def test_missing_content_injected_empty(self):
        """Only tool-call assistants need reasoning_content injected."""
        messages = [
            {"role": "assistant", "content": "Hello", "tool_calls": [{"id": "tc1"}]}
        ]
        result = inject_reasoning_content(messages)
        assert result[0]["reasoning_content"] == ""

    def test_plain_assistant_unchanged(self):
        """Plain assistants (no tool_calls) are left alone for cache stability."""
        messages = [
            {"role": "assistant", "content": "Hello"}
        ]
        result = inject_reasoning_content(messages)
        assert "reasoning_content" not in result[0]

    def test_openrouter_reasoning_moved(self):
        messages = [
            {"role": "assistant", "content": "Hello", "reasoning": "Thinking...", "tool_calls": [{"id": "tc1"}]}
        ]
        result = inject_reasoning_content(messages)
        assert "reasoning" not in result[0]
        assert result[0]["reasoning_content"] == "Thinking..."

    def test_openrouter_reasoning_plain_unchanged(self):
        """Plain assistant: reasoning field is left in place (not converted)."""
        messages = [
            {"role": "assistant", "content": "Hello", "reasoning": "Thinking..."}
        ]
        result = inject_reasoning_content(messages)
        assert result[0].get("reasoning") == "Thinking..."

    def test_claude_thinking_moved(self):
        messages = [
            {"role": "assistant", "content": "Hello", "thinking": "Claude thinks...", "tool_calls": [{"id": "tc1"}]}
        ]
        result = inject_reasoning_content(messages)
        assert "thinking" not in result[0]
        assert result[0]["reasoning_content"] == "Claude thinks..."

    def test_user_message_unchanged(self):
        messages = [{"role": "user", "content": "Hi"}]
        result = inject_reasoning_content(messages)
        assert "reasoning_content" not in result[0]


class TestNormalizeToolMessageContent:
    def test_string_content_unchanged(self):
        messages = [{"role": "tool", "content": "Result: 42"}]
        result = normalize_tool_message_content(messages)
        assert result[0]["content"] == "Result: 42"

    def test_none_to_empty(self):
        messages = [{"role": "tool", "content": None}]
        result = normalize_tool_message_content(messages)
        assert result[0]["content"] == ""

    def test_array_to_string(self):
        messages = [
            {"role": "tool", "content": [{"text": "part1"}, {"text": "part2"}]}
        ]
        result = normalize_tool_message_content(messages)
        assert result[0]["content"] == "part1part2"

    def test_non_tool_message_unchanged(self):
        messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]
        result = normalize_tool_message_content(messages)
        assert isinstance(result[0]["content"], list)


class TestBackfillToolMessageNames:
    def test_name_backfilled(self):
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "function": {"name": "get_weather"},
                    }
                ],
            },
            {
                "role": "tool",
                "content": "Sunny",
                "tool_call_id": "call_123",
            },
        ]
        result = backfill_tool_message_names(messages)
        assert result[1]["name"] == "get_weather"

    def test_existing_name_preserved(self):
        messages = [
            {
                "role": "tool",
                "content": "Sunny",
                "tool_call_id": "call_123",
                "name": "get_weather",
            }
        ]
        result = backfill_tool_message_names(messages)
        assert result[0]["name"] == "get_weather"

    def test_no_match_no_name(self):
        messages = [
            {"role": "tool", "content": "Sunny", "tool_call_id": "call_unknown"}
        ]
        result = backfill_tool_message_names(messages)
        assert "name" not in result[0]


class TestStripUnsupportedFields:
    def test_reasoning_effort_removed(self):
        body = {"model": "deepseek-v4-pro", "reasoning_effort": "high"}
        result = strip_unsupported_fields(body)
        assert "reasoning_effort" not in result

    def test_top_k_removed(self):
        body = {"model": "deepseek-v4-pro", "top_k": 50}
        result = strip_unsupported_fields(body)
        assert "top_k" not in result

    def test_other_fields_preserved(self):
        body = {"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "hi"}]}
        result = strip_unsupported_fields(body)
        assert result["model"] == "deepseek-v4-pro"
