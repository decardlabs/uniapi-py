"""Protocol conversion between Anthropic Messages and OpenAI Chat Completions.

Stateless pure functions. No provider-specific logic.
Reference: docs/API中转站协议转换架构讨论.md §4
"""
from __future__ import annotations

import copy


# ---------------------------------------------------------------------------
# Anthropic Messages → OpenAI Chat Completions
# ---------------------------------------------------------------------------


def anthropic_to_chat(body: dict) -> dict:
    """Convert an Anthropic Messages request body to OpenAI Chat Completions format."""
    result = copy.deepcopy(body)

    # 1. System: flatten array to single system message
    system = result.pop("system", None)
    messages = result.get("messages", [])

    if system:
        system_text = _flatten_anthropic_system(system)
        if system_text:
            messages.insert(0, {"role": "system", "content": system_text})

    # 2. Messages: flatten content arrays
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    # tool_use in assistant messages → tool_calls
                    if "tool_calls" not in msg:
                        msg["tool_calls"] = []
                    msg["tool_calls"].append({
                        "id": block.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": _serialize_tool_input(block.get("input", {})),
                        },
                    })
                elif block.get("type") == "tool_result":
                    # tool_result in user/tool messages → simple string
                    text_parts.append(str(block.get("content", "")))
                # image blocks are stripped (OpenAI Chat format differs)
            msg["content"] = "".join(text_parts) if text_parts else ""

    result["messages"] = messages

    # 3. Tools: rename fields
    tools = result.get("tools")
    if tools:
        result["tools"] = [_convert_tool(t) for t in tools]

    # 4. Tool choice: object → string
    tc = result.get("tool_choice")
    if isinstance(tc, dict):
        tc_type = tc.get("type", "auto")
        _tc_map = {"auto": "auto", "any": "required", "tool": "required", "none": "none"}
        result["tool_choice"] = _tc_map.get(tc_type, "auto")

    # 5. Field renames / strips
    if "stop_sequences" in result:
        result["stop"] = result.pop("stop_sequences")
    result.pop("thinking", None)
    result.pop("top_k", None)

    return result


def _flatten_anthropic_system(system):
    """Convert Anthropic system array/string to plain text."""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        texts = []
        for item in system:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)
    return ""


def _convert_tool(tool: dict) -> dict:
    """Convert Anthropic tool definition to OpenAI function format."""
    return {
        "type": "function",
        "function": {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {}),
        },
    }


def _serialize_tool_input(input_data) -> str:
    """Serialize tool call arguments to JSON string."""
    import json
    if isinstance(input_data, str):
        return input_data
    try:
        return json.dumps(input_data)
    except (TypeError, ValueError):
        return str(input_data)


# ---------------------------------------------------------------------------
# OpenAI Chat Completions → Anthropic Messages
# ---------------------------------------------------------------------------


def chat_to_anthropic(body: dict) -> dict:
    """Convert an OpenAI Chat Completions request body to Anthropic Messages format."""
    result = copy.deepcopy(body)

    # 1. System: extract from messages[0]
    messages = result.get("messages", [])
    system_text = None
    cleaned = []
    for msg in messages:
        if msg.get("role") == "system" and system_text is None:
            system_text = msg.get("content", "")
            continue
        cleaned.append(msg)

    if system_text:
        result["system"] = system_text
    result["messages"] = cleaned

    # 2. Messages: convert tool_calls to content blocks
    for msg in result["messages"]:
        role = msg.get("role", "")

        # Assistant tool_calls → tool_use content blocks
        if role == "assistant" and msg.get("tool_calls"):
            content_blocks = []
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                args = fn.get("arguments", "{}")
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        pass
                block = {
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": args,
                }
                content_blocks.append(block)
            msg["content"] = content_blocks
            msg.pop("tool_calls")

        # Tool role messages → tool_result content blocks
        elif role == "tool":
            msg["content"] = [{
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            }]
            msg.pop("tool_call_id", None)

        # Regular messages: wrap string content in text blocks
        elif role in ("user", "assistant"):
            content = msg.get("content", "")
            if isinstance(content, str):
                msg["content"] = [{"type": "text", "text": content}]

    # 3. Tools: flatten function wrapper
    tools = result.get("tools")
    if tools:
        result["tools"] = [_convert_chat_tool(t) for t in tools]

    # 4. Tool choice: string → object
    tc = result.get("tool_choice")
    if isinstance(tc, str):
        _tc_map = {"auto": {"type": "auto"}, "required": {"type": "any"}, "none": {"type": "none"}}
        result["tool_choice"] = _tc_map.get(tc, {"type": "auto"})

    # 5. Field renames / strips
    if "stop" in result:
        result["stop_sequences"] = result.pop("stop")
    result.pop("seed", None)
    result.pop("response_format", None)
    result.pop("n", None)
    result.pop("logit_bias", None)
    result.pop("frequency_penalty", None)
    result.pop("presence_penalty", None)

    return result


def _convert_chat_tool(tool: dict) -> dict:
    """Convert OpenAI function tool to Anthropic format."""
    fn = tool.get("function", {})
    return {
        "name": fn.get("name", ""),
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {}),
    }
