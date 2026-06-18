"""GLM (Zhipu/智谱) adaptor.

GLM natively supports:
  - chat_completions → /api/paas/v4/chat/completions
  - claude_messages → https://open.bigmodel.cn/api/anthropic (direct passthrough)
"""

from __future__ import annotations

from app.relay.adaptor import BaseAdaptor, ModelConfig
from app.relay.adaptors.glm import pricing
from app.relay.adaptors.glm.auth import generate_glm_token
from app.relay.meta import RelayMeta

GLM_CHANNEL_TYPE = 41  # matches Go's channeltype.GLM
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
ANTHROPIC_BASE_URL = "https://open.bigmodel.cn/api/anthropic"


class GLMAdaptor(BaseAdaptor):
    provider_name = "glm"
    NATIVE_FORMATS = {"chat_completions", "claude_messages"}
    DEFAULT_BASE_URL = DEFAULT_BASE_URL

    def get_request_url(self, meta: RelayMeta, relay_mode: int = 1) -> str:
        if relay_mode == 12:  # CLAUDE_MESSAGES
            return ANTHROPIC_BASE_URL
        base = meta.base_url or self.DEFAULT_BASE_URL
        return f"{base.rstrip('/')}/api/paas/v4/chat/completions"

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == 12:
            return ANTHROPIC_BASE_URL
        return f"{self.DEFAULT_BASE_URL}/api/paas/v4/chat/completions"

    def setup_request_headers(self, api_key: str) -> dict[str, str]:
        token = generate_glm_token(api_key)
        return {
            "Authorization": token,
            "Content-Type": "application/json",
        }

    async def convert_request(self, body: dict, meta: RelayMeta) -> dict:
        # GLM OpenAI-compatible for v4 models. Pass through directly.
        return body

    def get_supported_models(self) -> dict[str, ModelConfig]:
        return dict(pricing.MODEL_PRICING)

    def get_channel_type(self) -> int:
        return GLM_CHANNEL_TYPE
