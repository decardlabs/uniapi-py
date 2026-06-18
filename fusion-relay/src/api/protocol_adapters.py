"""
Protocol boundary adapters: Anthropic ↔ OpenAI format wrapping.

These functions are ONLY used at the inbound/outbound boundary of the relay.
They are NOT used for panel model calls — since all 5 major domestic providers
natively support both OpenAI and Anthropic protocols, the Fusion Engine's
panel dispatch always uses OpenAI format internally.

Architecture:
  Inbound Anthropic request → thin wrapping to ChatRequest → Fusion Engine (OpenAI internally)
  Fusion Engine result → thin wrapping back to Anthropic response → outbound to Agent

The "conversion" here is minimal format wrapping (system field positioning,
content blocks flattening, tool schema reshaping), NOT deep protocol translation.

Codex v0.81+ (Responses API) is NOT handled here — use CC-Switch or codex-bridge
as a separate sidecar proxy.
"""

from dataclasses import dataclass, field
from typing import Any

from src.models.schemas import ChatRequest, ChatResponse, UsageInfo


# ──────────────────────────────────────────────
# Anthropic Request Schema (入站)
# ──────────────────────────────────────────────

@dataclass
class AnthropicMessagesRequest:
    """Anthropic Messages API request format (thin parse, no deep conversion)."""

    model: str = ""
    max_tokens: int = 4096
    system: str | list[dict[str, Any]] | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    temperature: float | None = None
    tools: list[dict[str, Any]] | None = None
    stream: bool = False
    stop_sequences: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnthropicMessagesRequest":
        return cls(
            model=data.get("model", ""),
            max_tokens=data.get("max_tokens", 4096),
            system=data.get("system"),
            messages=data.get("messages", []),
            temperature=data.get("temperature"),
            tools=data.get("tools"),
            stream=data.get("stream", False),
            stop_sequences=data.get("stop_sequences"),
            metadata=data.get("metadata", {}),
        )


# ──────────────────────────────────────────────
# Anthropic Response Schema (出站回 Agent)
# ──────────────────────────────────────────────

@dataclass
class AnthropicMessagesResponse:
    """Anthropic Messages API response format."""

    id: str = ""
    type: str = "message"
    role: str = "assistant"
    content: list[dict[str, Any]] = field(default_factory=list)
    model: str = ""
    stop_reason: str = "end_turn"
    stop_sequence: str | None = None
    usage: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "role": self.role,
            "content": self.content,
            "model": self.model,
            "stop_reason": self.stop_reason,
            "stop_sequence": self.stop_sequence,
            "usage": self.usage,
        }


# ──────────────────────────────────────────────
# Boundary wrapping: Anthropic → Internal (入站)
# ──────────────────────────────────────────────

def anthropic_to_internal(request: AnthropicMessagesRequest) -> ChatRequest:
    """
    Thin wrapping: Anthropic request → ChatRequest for Fusion Engine.

    This is NOT protocol "conversion" — it's format wrapping so the
    Fusion Engine (which uses OpenAI-like internal schemas) can process it.
    The actual model calls use each provider's OpenAI endpoint (all 5 providers
    natively support OpenAI format), so no Anthropic→OpenAI conversion
    happens at the model call level.

    Key wrapping points:
    1. system (top-level) → prepend as system message
    2. tool_use/tool_result content blocks → OpenAI tool_calls/tool messages
    3. model mapping: claude-* → fusion trigger (Agent stays unaware)
    """
    messages = []

    # 1. System prompt extraction
    if request.system:
        if isinstance(request.system, str):
            messages.append({"role": "system", "content": request.system})
        elif isinstance(request.system, list):
            system_text = ""
            for block in request.system:
                if block.get("type") == "text":
                    system_text += block.get("text", "")
            if system_text:
                messages.append({"role": "system", "content": system_text})

    # 2. Message content wrapping
    for msg in request.messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})

        elif isinstance(content, list):
            text_parts = []
            tool_calls = []
            tool_results = []

            for block in content:
                block_type = block.get("type", "text")

                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                elif block_type == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": block.get("input", {}),
                        },
                    })
                elif block_type == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        result_text = ""
                        for rb in result_content:
                            if rb.get("type") == "text":
                                result_text += rb.get("text", "")
                        result_content = result_text
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "content": str(result_content),
                    })

            if text_parts:
                combined = "\n".join(text_parts)
                if tool_calls:
                    messages.append({"role": role, "content": combined, "tool_calls": tool_calls})
                else:
                    messages.append({"role": role, "content": combined})
            elif tool_calls:
                messages.append({"role": role, "content": None, "tool_calls": tool_calls})

            for tr in tool_results:
                messages.append(tr)

        elif content is None:
            messages.append({"role": role, "content": ""})

    # 3. Tool schema wrapping
    openai_tools = None
    if request.tools:
        openai_tools = []
        for tool in request.tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })

    # 4. Model name: claude-* triggers fusion (Agent doesn't know it's behind relay)
    model_name = request.model
    is_fusion_model = model_name.startswith("claude-") or model_name.lower() == "fusion"

    return ChatRequest(
        model="fusion" if is_fusion_model else model_name,
        messages=messages,
        temperature=request.temperature if request.temperature is not None else 0.7,
        max_tokens=request.max_tokens,
        stream=request.stream,
        tools=openai_tools,
        extra_body={
            "_source_protocol": "anthropic",
            "_original_model": request.model,
        },
    )


# ──────────────────────────────────────────────
# Boundary wrapping: Internal → Anthropic (出站回 Agent)
# ──────────────────────────────────────────────

def internal_to_anthropic(response: ChatResponse) -> AnthropicMessagesResponse:
    """
    Thin wrapping: ChatResponse → Anthropic response for outbound.

    Minimal wrapping: text → content blocks, finish_reason → stop_reason,
    prompt/completion_tokens → input/output_tokens.
    """
    content_blocks = []

    for choice in response.choices:
        message = choice.get("message", {})
        text = message.get("content", "")
        if text:
            content_blocks.append({"type": "text", "text": text})

        tool_calls = message.get("tool_calls", [])
        for tc in tool_calls:
            func = tc.get("function", {})
            content_blocks.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{response.id}"),
                "name": func.get("name", ""),
                "input": func.get("arguments", {}),
            })

    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    # finish_reason → stop_reason
    finish_reason = response.choices[0].get("finish_reason", "stop") if response.choices else "stop"
    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }

    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    if response.usage.fusion_breakdown:
        usage["fusion_breakdown"] = {
            "panel": response.usage.fusion_breakdown.panel,
            "judge_model": response.usage.fusion_breakdown.judge_model,
            "synthesizer_model": response.usage.fusion_breakdown.synthesizer_model,
        }

    return AnthropicMessagesResponse(
        id=response.id.replace("chatcmpl-", "msg_"),
        type="message",
        role="assistant",
        content=content_blocks,
        model=response.model,
        stop_reason=stop_reason_map.get(finish_reason, "end_turn"),
        usage=usage,
    )


# ──────────────────────────────────────────────
# Streaming helpers (Anthropic SSE format)
# ──────────────────────────────────────────────

def anthropic_stream_start(message_id: str, model: str) -> list[str]:
    """Generate Anthropic SSE stream start events."""
    import json

    return [
        f"event: message_start\n"
        f"data: {json.dumps({'type': 'message_start', 'message': {'id': message_id, 'type': 'message', 'role': 'assistant', 'content': [], 'model': model, 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 0, 'output_tokens': 0}}})}\n",
        f"event: content_block_start\n"
        f"data: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n",
    ]


def anthropic_stream_stop() -> str:
    """Generate Anthropic SSE content_block_stop event."""
    import json
    return f"event: content_block_stop\ndata: {json.dumps({'type': 'content_block_stop', 'index': 0})}\n"
