"""MiniMax adaptor.

MiniMax natively supports:
  - chat_completions (OpenAI format)
  - claude_messages (Anthropic Claude format)
"""
from __future__ import annotations

from app.relay.adaptor import BaseAdaptor, ModelConfig
from app.relay.adaptors.minimax import pricing
from app.relay.meta import RelayMeta
from app.relay.mode import RelayMode

MINIMAX_CHANNEL_TYPE = 27
DEFAULT_BASE_URL = "https://api.minimaxi.com/v1"
ANTHROPIC_BASE_URL = "https://api.minimaxi.com/anthropic"


class MiniMaxAdaptor(BaseAdaptor):
    provider_name = "minimax"
    NATIVE_FORMATS = {"chat_completions", "claude_messages"}
    DEFAULT_BASE_URL = DEFAULT_BASE_URL

    def get_request_url(self, meta: RelayMeta, relay_mode: int = 1) -> str:
        if relay_mode == RelayMode.CLAUDE_MESSAGES:
            return ANTHROPIC_BASE_URL
        base = meta.base_url or self.DEFAULT_BASE_URL
        return f"{base.rstrip('/')}/chat/completions"

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == RelayMode.CLAUDE_MESSAGES:
            return ANTHROPIC_BASE_URL
        return "/chat/completions"

    def setup_request_headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def convert_request(self, body: dict, meta: RelayMeta) -> dict:
        return body

    def get_supported_models(self) -> dict[str, ModelConfig]:
        return dict(pricing.MODEL_PRICING)

    def resolve_model_name(self, name: str) -> str | None:
        """Case-insensitive model name resolution.

        Returns the canonical (PascalCase) name if found, or None.
        """
        if name in pricing.MODEL_PRICING:
            return name
        canonical = pricing.MODEL_ALIASES.get(name.lower())
        return canonical

    def get_channel_type(self) -> int:
        return MINIMAX_CHANNEL_TYPE
