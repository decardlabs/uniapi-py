from __future__ import annotations

"""DeepSeek adaptor implementation.

Maps the UniAPI relay pipeline to DeepSeek's API.
DeepSeek natively supports:
  - chat_completions (OpenAI format)
  - claude_messages (Anthropic Claude format)
"""

import copy

from app.relay.adaptor import BaseAdaptor, ModelConfig
from app.relay.adaptors.deepseek import pricing
from app.relay.adaptors.deepseek.request import normalize_request
from app.relay.meta import RelayMeta
from app.relay.mode import RelayMode

DEEPSEEK_CHANNEL_TYPE = 39
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"



class DeepSeekAdaptor(BaseAdaptor):
    provider_name = "deepseek"
    NATIVE_FORMATS = {"chat_completions", "claude_messages"}
    DEFAULT_BASE_URL = DEFAULT_BASE_URL

    def get_request_url(self, meta: RelayMeta, relay_mode: int = 1) -> str:
        if relay_mode == RelayMode.CLAUDE_MESSAGES:
            return f"{ANTHROPIC_BASE_URL}/v1/messages"
        base = meta.base_url or self.DEFAULT_BASE_URL
        path = self._get_path_for_mode(relay_mode)
        return f"{base.rstrip('/')}{path}"

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == RelayMode.CLAUDE_MESSAGES:
            return f"{ANTHROPIC_BASE_URL}/v1/messages"
        return "/chat/completions"

    def setup_request_headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def normalize_request_body(self, body: dict) -> dict:
        """Strip reasoning_content from non-tool assistant turns.

        Re-sent reasoning content is billable prompt input that never hits
        the prefix cache. Stripping it keeps the request prefix byte-stable
        so DeepSeek's automatic prefix cache stays warm.

        Tool-call assistant turns are exempted because DeepSeek requires
        reasoning_content to be passed back on a cache-miss replay.
        """
        body = copy.deepcopy(body)
        messages = body.get("messages", [])
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            if msg.get("tool_calls"):
                continue  # tool-call turn: must keep reasoning_content
            msg.pop("reasoning_content", None)
            msg.pop("reasoning", None)
        return body

    async def convert_request(self, body: dict, meta: RelayMeta) -> dict:
        return normalize_request(body)

    def get_supported_models(self) -> dict[str, ModelConfig]:
        return dict(pricing.MODEL_PRICING)

    def get_channel_type(self) -> int:
        return DEEPSEEK_CHANNEL_TYPE
