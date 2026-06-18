"""
MiniMax adapter.

MiniMax API supports both protocols natively:
  - OpenAI:   https://api.minimax.io/v1          → /chat/completions
  - Anthropic: https://api.minimax.io/anthropic   → /v1/messages

Key features:
  - Model name mapping (MiniMax-M3, M2.5, M2.1, etc.)
  - Long context optimization (1M context for M3)
  - Thinking mode control (M3: default off, M2.x: always on)
  - service_tier: standard vs priority
"""

import logging
from typing import Any, AsyncGenerator

import httpx

from src.adapters.base import BaseAdapter
from src.models.schemas import ModelRequest, ModelResponse, UsageInfo

logger = logging.getLogger(__name__)


class MiniMaxAdapter(BaseAdapter):
    """Adapter for MiniMax API (dual-protocol)."""

    provider_name = "minimax"

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
        """MiniMax adaptation: latest model IDs + long context handling."""
        payload = dict(openai_request)

        # MiniMax ignores these OpenAI params: presence_penalty, frequency_penalty, logit_bias
        # n only supports 1
        for key in ["presence_penalty", "frequency_penalty", "logit_bias"]:
            payload.pop(key, None)

        # Set max_tokens if not provided (MiniMax defaults are generous)
        if "max_tokens" not in payload:
            payload["max_tokens"] = 8192

        # MiniMax-specific: enable long context optimization for M3
        model = payload.get("model", "")
        if "M3" in model or "m3" in model:
            payload.setdefault("extra_body", {})
            payload["extra_body"]["long_context_mode"] = True

        return payload

    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        """Parse MiniMax response into normalized ModelResponse."""
        choice = native_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # MiniMax thinking content (M2.x always has it, M3 optional)
        thinking = message.get("thinking", "")
        if thinking:
            content = f"<thinking>\n{thinking}\n</thinking>\n\n{content}"

        usage = native_response.get("usage", {})

        return ModelResponse(
            model=native_response.get("model", self.provider_name),
            content=content,
            reasoning=thinking,
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", "stop"),
            raw=native_response,
        )
