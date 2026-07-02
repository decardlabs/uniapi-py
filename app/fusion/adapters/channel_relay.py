"""Channel-relay adapter: routes fusion model calls through the channel system."""
from __future__ import annotations

import logging
from typing import Any, Callable

import httpx

from app.fusion.adapters.base import BaseAdapter
from app.fusion.schemas import ModelRequest, ModelResponse, UsageInfo
from app.models.channel import Channel
from app.relay.meta import RelayMeta
from app.relay.mode import RelayMode

logger = logging.getLogger(__name__)


class ChannelRelayAdapter(BaseAdapter):
    """Adapter that relays fusion calls through the channel system.

    Instead of calling the upstream API directly with a provider API key,
    this adapter uses a channel picker callback to select a channel,
    then makes the upstream call using the channel's key and base URL.

    FusionEngine / JudgeModule / SynthesizerModule all call ``chat()``
    the same way as with a regular adapter — the channel routing is
    transparent to them.
    """

    def __init__(
        self,
        provider_name: str,
        channel_picker: Callable[[], Any],
        adaptor: Any,
    ):
        self.provider_name = provider_name
        self.channel_picker = channel_picker  # async callable: () -> (Channel, str)
        self.adaptor = adaptor                # relay BaseAdaptor subclass

    async def chat(self, request: ModelRequest) -> ModelResponse:
        """Send a non-streaming chat completion via a selected channel."""
        # 1. Pick a channel
        channel: Channel
        upstream_model: str
        channel, upstream_model = await self.channel_picker()

        # 2. Build the upstream URL and headers
        api_key = channel.key or ""
        base_url = (channel.base_url or "").rstrip("/")
        relay_meta = RelayMeta(
            api_key=api_key,
            base_url=base_url or self.adaptor.DEFAULT_BASE_URL,
        )
        url = self.adaptor.get_request_url(relay_meta, RelayMode.CHAT_COMPLETIONS)
        headers = self.adaptor.setup_request_headers(api_key)

        # 3. Prepare the request body
        body = {
            "model": upstream_model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if request.tools:
            body["tools"] = request.tools
        if request.extra_params:
            body.update(request.extra_params)

        # 4. Send upstream request (non-streaming)
        timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

        # 5. Parse response into ModelResponse
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {}) or {}
        usage_raw = data.get("usage") or {}
        content = message.get("content") or ""
        if isinstance(content, list):
            # Handle multi-modal content parts
            texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            content = "\n".join(texts)

        return ModelResponse(
            model=data.get("model", upstream_model),
            content=content,
            usage=UsageInfo(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            ),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def stream_chat(self, request: ModelRequest):
        raise NotImplementedError("ChannelRelayAdapter only supports non-streaming chat")

    def adapt_request(self, openai_request: dict[str, Any]) -> dict[str, Any]:
        return openai_request

    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        raise NotImplementedError("Use chat() instead")
