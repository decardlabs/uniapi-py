"""Tests for protocol conversion (Anthropic Messages ↔ OpenAI Chat Completions).

TDD: write failing tests first, then implement converter.py.
"""
import pytest


class TestAnthropicToChat:
    """Anthropic Messages → OpenAI Chat Completions conversion."""

    def test_basic_message(self):
        """Simple user message should convert correctly."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hello"}]}],
            "max_tokens": 100,
        }
        result = anthropic_to_chat(body)
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["messages"][0]["role"] == "user"
        assert "content" in result["messages"][0]
        assert result["max_tokens"] == 100

    def test_system_prompt(self):
        """System array should flatten to messages[0].role='system'."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-opus-4",
            "system": [{"type": "text", "text": "You are a helpful assistant."}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        }
        result = anthropic_to_chat(body)
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "You are a helpful assistant."
        assert result["messages"][1]["role"] == "user"

    def test_tool_definitions(self):
        """Anthropic tools should convert to OpenAI function format."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-opus-4",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "weather?"}]}],
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "input_schema": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
                }
            ],
        }
        result = anthropic_to_chat(body)
        assert len(result["tools"]) == 1
        assert result["tools"][0]["type"] == "function"
        assert result["tools"][0]["function"]["name"] == "get_weather"
        assert "parameters" in result["tools"][0]["function"]

    def test_tool_choice_mapping(self):
        """tool_choice object should map to OpenAI string."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-opus-4",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            "tool_choice": {"type": "auto"},
        }
        result = anthropic_to_chat(body)
        assert result["tool_choice"] == "auto"

        body["tool_choice"] = {"type": "any"}
        result = anthropic_to_chat(body)
        assert result["tool_choice"] == "required"

    def test_thinking_stripped(self):
        """thinking field should be removed (no OpenAI equivalent)."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-opus-4",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "think"}]}],
            "thinking": {"type": "enabled", "budget_tokens": 2048},
        }
        result = anthropic_to_chat(body)
        assert "thinking" not in result

    def test_stop_sequences(self):
        """stop_sequences should rename to stop."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-opus-4",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            "stop_sequences": ["\n\n", "."],
        }
        result = anthropic_to_chat(body)
        assert result["stop"] == ["\n\n", "."]
        assert "stop_sequences" not in result

    def test_top_k_stripped(self):
        """top_k should be removed (no OpenAI equivalent)."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-opus-4",
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
            "top_k": 20,
        }
        result = anthropic_to_chat(body)
        assert "top_k" not in result

    def test_image_content_removed(self):
        """Image content blocks should be stripped (OpenAI Chat uses different format)."""
        from app.relay.converter import anthropic_to_chat
        body = {
            "model": "claude-opus-4",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "what is this"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
                ],
            }],
        }
        result = anthropic_to_chat(body)
        # Image blocks are stripped; text blocks are kept
        assert "image" not in result["messages"][0]["content"]


class TestChatToAnthropic:
    """OpenAI Chat Completions → Anthropic Messages conversion."""

    def test_basic_message(self):
        """Simple user message should convert correctly."""
        from app.relay.converter import chat_to_anthropic
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
        }
        result = chat_to_anthropic(body)
        assert result["model"] == "gpt-4"
        assert result["messages"][0]["role"] == "user"
        assert isinstance(result["messages"][0]["content"], list)
        assert result["messages"][0]["content"][0]["type"] == "text"
        assert result["messages"][0]["content"][0]["text"] == "hello"

    def test_system_extraction(self):
        """messages[0].role='system' should extract to top-level system."""
        from app.relay.converter import chat_to_anthropic
        body = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "ok"},
            ],
        }
        result = chat_to_anthropic(body)
        assert result["system"] == "Be helpful."
        assert result["messages"][0]["role"] == "user"

    def test_tool_calls_in_history(self):
        """Assistant tool_calls should convert to content blocks."""
        from app.relay.converter import chat_to_anthropic
        body = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "weather"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city":"Beijing"}'},
                    }],
                },
                {
                    "role": "tool",
                    "tool_call_id": "call_123",
                    "content": "25°C",
                },
            ],
        }
        result = chat_to_anthropic(body)
        # Assistant message should have tool_use content block
        asst = result["messages"][1]
        assert asst["content"][0]["type"] == "tool_use"
        assert asst["content"][0]["name"] == "get_weather"
        # Tool message should have tool_result content block
        tool_msg = result["messages"][2]
        assert tool_msg["content"][0]["type"] == "tool_result"

    def test_tool_choice_conversion(self):
        """Tool choice strings should map to Anthropic format."""
        from app.relay.converter import chat_to_anthropic
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "tool_choice": "auto",
        }
        result = chat_to_anthropic(body)
        assert result["tool_choice"] == {"type": "auto"}

        body["tool_choice"] = "required"
        result = chat_to_anthropic(body)
        assert result["tool_choice"] == {"type": "any"}

    def test_n_gt_one_stripped(self):
        """n > 1 should be removed (Anthropic doesn't support)."""
        from app.relay.converter import chat_to_anthropic
        body = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hi"}],
            "n": 3,
        }
        result = chat_to_anthropic(body)
        assert "n" not in result


class TestRoundTrip:
    """Round-trip conversion should preserve semantic content."""

    def test_chat_to_anthropic_to_chat_basic(self):
        """chat→anthropic→chat round-trip for basic message."""
        from app.relay.converter import anthropic_to_chat, chat_to_anthropic
        original = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "hello"}],
            "temperature": 0.7,
        }
        anthropic = chat_to_anthropic(original)
        chat = anthropic_to_chat(anthropic)
        assert chat["messages"][0]["role"] == "user"
        assert chat["temperature"] == 0.7

    def test_anthropic_to_chat_to_anthropic_with_system(self):
        """anthropic→chat→anthropic round-trip preserves system prompt."""
        from app.relay.converter import anthropic_to_chat, chat_to_anthropic
        original = {
            "model": "claude-opus-4",
            "system": [{"type": "text", "text": "Be helpful."}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        }
        chat = anthropic_to_chat(original)
        result = chat_to_anthropic(chat)
        assert result["system"] == "Be helpful."
        assert result["messages"][0]["role"] == "user"


class TestConversionIntegration:
    """ConvertClaudeRequest should be callable from the adaptor."""

    def test_base_adaptor_convert_claude(self):
        """BaseAdaptor.convert_claude_request should use the generic converter."""
        from app.relay.adaptor import BaseAdaptor

        class TestAdp(BaseAdaptor):
            provider_name = "test"
            NATIVE_FORMATS = {"chat_completions"}  # no claude support
            def get_request_url(self, meta, mode=1): return "http://test"
            def setup_request_headers(self, key=""): return {}
            async def convert_request(self, body, meta): return body
            def get_supported_models(self): return {}

        adp = TestAdp()
        result = adp.convert_claude_request({
            "model": "claude-opus-4",
            "system": [{"type": "text", "text": "Be helpful."}],
            "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
        })
        assert result["messages"][0]["role"] == "system"
        assert result["messages"][0]["content"] == "Be helpful."
