from __future__ import annotations

"""DeepSeek adaptor implementation.

Maps the UniAPI relay pipeline to DeepSeek's API.
DeepSeek natively supports:
  - chat_completions (OpenAI format)
  - claude_messages (Anthropic Claude format)
"""

from app.relay.adaptor import BaseAdaptor, ModelConfig
from app.relay.adaptors.deepseek import pricing
from app.relay.adaptors.deepseek.request import normalize_request
from app.relay.meta import RelayMeta

DEEPSEEK_CHANNEL_TYPE = 39
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"

# Relay mode constants matching app.relay.mode.RelayMode
_CHAT = 1       # ChatCompletions
_RESPONSE = 11  # ResponseAPI
_CLAUDE = 12    # ClaudeMessages


class DeepSeekAdaptor(BaseAdaptor):
    provider_name = "deepseek"
    NATIVE_FORMATS = {"chat_completions", "claude_messages"}
    DEFAULT_BASE_URL = DEFAULT_BASE_URL

    def get_request_url(self, meta: RelayMeta, relay_mode: int = 1) -> str:
        if relay_mode == _CLAUDE:
            return f"{ANTHROPIC_BASE_URL}/v1/messages"
        base = meta.base_url or self.DEFAULT_BASE_URL
        path = self._get_path_for_mode(relay_mode)
        return f"{base.rstrip('/')}{path}"

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == _CLAUDE:
            return f"{ANTHROPIC_BASE_URL}/v1/messages"
        return "/chat/completions"

    def setup_request_headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def convert_request(self, body: dict, meta: RelayMeta) -> dict:
        return normalize_request(body)

    def get_supported_models(self) -> dict[str, ModelConfig]:
        return dict(pricing.MODEL_PRICING)

    def get_channel_type(self) -> int:
        return DEEPSEEK_CHANNEL_TYPE
