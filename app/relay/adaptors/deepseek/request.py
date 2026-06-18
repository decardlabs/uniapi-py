from __future__ import annotations

"""DeepSeek request normalization utilities.

Port of Go's deepseekcompat package for handling DeepSeek-specific requirements:
1. Thinking type normalization ("adaptive" -> "enabled")
2. reasoning_content injection on assistant messages
3. Tool message content string normalization
4. Tool message name backfilling
5. Field stripping (reasoning_effort, top_k)
6. response_format downgrade (json_schema not supported)
"""

from typing import Any, Optional


def normalize_thinking_type(thinking: Optional[dict]) -> Optional[dict]:
    """Normalize DeepSeek thinking type.

    DeepSeek V4 supports only "enabled" or "disabled".
    "adaptive" must be converted to "enabled".
    """
    if thinking is None:
        return None

    t = thinking.copy()
    thinking_type = t.get("type", "")
    budget = t.get("budget_tokens", 0)

    if thinking_type == "adaptive":
        t["type"] = "enabled"
    elif not thinking_type and budget:
        t["type"] = "enabled"
    elif not thinking_type:
        t["type"] = "disabled"

    return t if t.get("type") == "enabled" else None


def inject_reasoning_content(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure every assistant message carries reasoning_content.

    DeepSeek in thinking mode requires reasoning_content on all
    assistant messages in the conversation history. Missing it
    causes API errors.
    """
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        if msg.get("reasoning_content") is not None:
            message_has_reasoning = True
            continue
        if msg.get("reasoning") is not None:
            msg["reasoning_content"] = msg.pop("reasoning")
            if msg.get("thinking") is not None:
                msg.pop("thinking")
            return messages
        if msg.get("thinking") is not None:
            msg["reasoning_content"] = msg.pop("thinking")
            return messages
        # Inject empty string to prevent DeepSeek error
        msg["reasoning_content"] = ""
    return messages


def normalize_tool_message_content(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert non-string tool message content to string.

    DeepSeek rejects arrays/objects as messages[].content for role=tool.
    """
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if content is None:
            msg["content"] = ""
        elif isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(part.get("text", ""))
                else:
                    parts.append(str(part))
            msg["content"] = "".join(parts)
        elif not isinstance(content, str):
            msg["content"] = str(content)
    return messages


def backfill_tool_message_names(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """DeepSeek requires 'name' on tool messages.

    Backfill by matching tool_call_id to prior assistant tool_calls.
    """
    tool_call_map: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tid = tc.get("id", tc.get("tool_call_id", ""))
                tname = tc.get("function", {}).get("name", "")
                if tid and tname:
                    tool_call_map[tid] = tname

    for msg in messages:
        if msg.get("role") == "tool" and not msg.get("name"):
            tcid = msg.get("tool_call_id", "")
            if tcid in tool_call_map:
                msg["name"] = tool_call_map[tcid]
    return messages


def strip_unsupported_fields(body: dict) -> dict:
    """Remove fields DeepSeek does not support."""
    body.pop("reasoning_effort", None)
    body.pop("top_k", None)
    return body


def downgrade_response_format(body: dict) -> dict:
    """DeepSeek does not support response_format with json_schema.

    Extract instruction and set response_format to None.
    """
    rf = body.get("response_format")
    if rf and isinstance(rf, dict) and rf.get("type") == "json_schema":
        schema = rf.get("json_schema", {})
        name = schema.get("name", "")
        instruction = schema.get("strict", False)
        # Ensure instruction is in system message or first user message
        if name and body.get("messages"):
            for msg in body["messages"]:
                if msg.get("role") in ("system", "user"):
                    existing = msg.get("content", "")
                    if isinstance(existing, str):
                        msg["content"] = (
                            f"You must respond with valid JSON following this schema. "
                            f"Schema instruction: {instruction}. "
                            + existing
                        )
                    break
        body["response_format"] = {"type": "text"}
    return body


def normalize_request(body: dict) -> dict:
    """Apply all DeepSeek-specific normalizations to a request body.

    This is the main entry point for request conversion.
    """
    body = strip_unsupported_fields(body)
    body["messages"] = backfill_tool_message_names(body.get("messages", []))
    body["messages"] = normalize_tool_message_content(body["messages"])
    body = downgrade_response_format(body)

    # Handle thinking parameter
    if "thinking" in body:
        body["thinking"] = normalize_thinking_type(body.get("thinking"))
    elif thinking := body.pop("thinking", None):
        body["thinking"] = normalize_thinking_type(thinking)

    body["messages"] = inject_reasoning_content(body.get("messages", []))
    return body
