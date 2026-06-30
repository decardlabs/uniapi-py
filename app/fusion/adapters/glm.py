"""GLM (Zhipu AI) adapter for the fusion pipeline."""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

import httpx

from app.fusion.adapters.base import BaseAdapter
from app.fusion.schemas import ModelRequest, ModelResponse, UsageInfo
from app.relay.adaptors.glm.auth import generate_glm_token

logger = logging.getLogger(__name__)


class GLMAdapter(BaseAdapter):
    provider_name = "glm"

    async def chat(self, request: ModelRequest) -> ModelResponse:
        payload = self.adapt_request(request.to_dict())
        url = f"{self.openai_base_url}/chat/completions"
        token = generate_glm_token(self.api_key)
        headers = {"Authorization": token, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return self.adapt_response(data)

    async def stream_chat(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        payload = self.adapt_request(request.to_dict())
        payload["stream"] = True
        url = f"{self.openai_base_url}/chat/completions"
        token = generate_glm_token(self.api_key)
        headers = {"Authorization": token, "Content-Type": "application/json"}
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
        model = payload.get("model", "")
        if "5.2" in model or "5.1" in model or "5" in model:
            payload.setdefault("extra_body", {})
            payload["extra_body"]["thinking"] = {"type": "enabled"}
        messages = payload.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        img = item.get("image_url", {})
                        if isinstance(img, dict) and "url" in img:
                            item["image_url"] = img["url"]
        return payload

    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        choice = native_response.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
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
