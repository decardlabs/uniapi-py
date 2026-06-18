"""
DeepSeek adapter.

DeepSeek API supports both protocols natively:
  - OpenAI:   https://api.deepseek.com          → /chat/completions
  - Anthropic: https://api.deepseek.com/anthropic → /v1/messages

This adapter uses the OpenAI endpoint for Fusion Engine internal calls.
Anthropic endpoint is available for direct passthrough when inbound is Anthropic.

Key features:
  - reasoning_content extraction (DeepSeek V4 specific)
  - Model auto-mapping: claude-opus-* → deepseek-v4-pro
  - Model auto-mapping: claude-sonnet-* / claude-haiku-* → deepseek-v4-flash
"""

import logging
from typing import Any, AsyncGenerator

import httpx

from src.adapters.base import BaseAdapter
from src.models.schemas import ModelRequest, ModelResponse, UsageInfo

logger = logging.getLogger(__name__)


class DeepSeekAdapter(BaseAdapter):
    """Adapter for DeepSeek API (dual-protocol)."""

    provider_name = "deepseek"

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
        """DeepSeek is OpenAI-compatible, minimal transformation needed."""
        payload = dict(openai_request)

        # DeepSeek V4 models support reasoning via reasoning_content in response
        model = payload.get("model", "")
        if "v4-pro" in model or "v4-flash" in model:
            # Enable reasoning output (DeepSeek specific)
            payload.setdefault("extra_body", {})
            payload["extra_body"]["enable_reasoning"] = True

        return payload

    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        """Parse DeepSeek response into normalized ModelResponse."""
        choice = native_response.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Extract reasoning_content if present (DeepSeek V4 specific)
        reasoning = message.get("reasoning_content", "")
        content = message.get("content", "")

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
