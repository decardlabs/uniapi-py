"""Qwen (AliBailian/百炼) adapter for the fusion pipeline."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from app.fusion.adapters.base import BaseAdapter
from app.fusion.schemas import ModelRequest, ModelResponse, UsageInfo

logger = logging.getLogger(__name__)


class QwenAdapter(BaseAdapter):
    provider_name = "qwen"

    async def chat(self, request: ModelRequest) -> ModelResponse:
        payload = self.adapt_request(request.to_dict())
        url = f"{self.openai_base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return self.adapt_response(data)

    async def stream_chat(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        payload = self.adapt_request(request.to_dict())
        payload["stream"] = True
        url = f"{self.openai_base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content

    def adapt_request(self, openai_request: dict[str, Any]) -> dict[str, Any]:
        payload = dict(openai_request)
        messages = payload.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                if text_parts:
                    msg["content"] = "".join(text_parts)
        return payload

    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        choice = native_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = native_response.get("usage", {})
        return ModelResponse(
            model=native_response.get("model", self.provider_name),
            content=message.get("content", ""),
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", "stop"),
            raw=native_response,
        )
