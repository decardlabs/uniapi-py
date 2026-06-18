"""
Kimi (Moonshot AI) adapter.

Kimi API supports both protocols natively:
  - OpenAI:   https://api.moonshot.cn/v1          → /chat/completions
  - Anthropic: https://api.moonshot.cn/anthropic   → /v1/messages

Key features:
  - K2.6: latest flagship, 13-hour autonomous coding
  - K2.5: multimodal, tool calling, JSON mode
  - Auto context caching
  - Long timeout recommended (API_TIMEOUT_MS=600000)
"""

import logging
from typing import Any, AsyncGenerator

import httpx

from src.adapters.base import BaseAdapter
from src.models.schemas import ModelRequest, ModelResponse, UsageInfo

logger = logging.getLogger(__name__)


class KimiAdapter(BaseAdapter):
    """Adapter for Kimi/Moonshot API (dual-protocol)."""

    provider_name = "kimi"

    async def chat(self, request: ModelRequest) -> ModelResponse:
        payload = self.adapt_request(request.to_dict())
        url = f"{self.openai_base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:  # Kimi needs longer timeout
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

        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min for long tasks
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
        """Kimi adaptation: auto caching + thinking param."""
        payload = dict(openai_request)

        # Kimi supports thinking via extra_body
        model = payload.get("model", "")
        if "k2.6" in model or "k2.7" in model:
            payload.setdefault("extra_body", {})
            payload["extra_body"]["thinking"] = True

        return payload

    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        """Parse Kimi response into normalized ModelResponse."""
        choice = native_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        usage = native_response.get("usage", {})

        return ModelResponse(
            model=native_response.get("model", self.provider_name),
            content=content,
            reasoning="",
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", "stop"),
            raw=native_response,
        )
