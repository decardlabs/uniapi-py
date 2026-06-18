"""
Qwen (Alibaba Cloud / Bailian Platform) adapter.

Qwen API supports both protocols natively:
  - OpenAI:   https://dashscope.aliyuncs.com/compatible-mode/v1 → /chat/completions
  - Anthropic: https://dashscope.aliyuncs.com/apps/anthropic      → /v1/messages

Special feature: Bailian Anthropic endpoint supports calling OTHER providers too
  (DeepSeek V4, Kimi K2.x, GLM-5.x, MiniMax M2.x) with a single Bailian API Key.

Key features:
  - qwen3.7-max: flagship
  - qwen3-coder-plus: programming specialist
  - qwen3.6-flash: lightweight, cost-effective
  - qwen3-coder-plus is the ONLY domestic model supporting OpenAI Responses API
"""

import logging
from typing import Any, AsyncGenerator

import httpx

from src.adapters.base import BaseAdapter
from src.models.schemas import ModelRequest, ModelResponse, UsageInfo

logger = logging.getLogger(__name__)


class QwenAdapter(BaseAdapter):
    """Adapter for Qwen/Bailian API (dual-protocol)."""

    provider_name = "qwen"

    async def chat(self, request: ModelRequest) -> ModelResponse:
        payload = self.adapt_request(request.to_dict())
        url = f"{self.openai_base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return self.adapt_response(data)

    async def stream_chat(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        payload = self.adapt_request(request.to_dict())
        payload["stream"] = True
        url = f"{self.openai_base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        import json
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

    def adapt_request(self, openai_request: dict[str, Any]) -> dict[str, Any]:
        """Qwen adaptation: mostly passthrough, Bailian is highly OpenAI-compatible."""
        payload = dict(openai_request)
        return payload

    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        """Parse Qwen/Bailian response into normalized ModelResponse."""
        choice = native_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # Qwen may return reasoning/thinking in some models
        reasoning = message.get("reasoning_content", "")
        if reasoning:
            content = f"<reasoning>\n{reasoning}\n</reasoning>\n\n{content}"

        usage = native_response.get("usage", {})

        return ModelResponse(
            model=native_response.get("model", self.provider_name),
            content=content,
            reasoning=reasoning,
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", "stop"),
            raw=native_response,
        )
