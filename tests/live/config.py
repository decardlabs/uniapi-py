"""Live test configuration from environment variables."""

from __future__ import annotations

import os


class LiveConfig:
    """Configuration for live tests, read from environment variables."""

    def __init__(self):
        self.api_base: str = os.getenv("UNIAPI_BASE", "http://localhost:8000")
        self.api_token: str = os.getenv("UNIAPI_TOKEN", "")

        # DeepSeek direct comparison
        self.deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base: str = os.getenv("DEEPSEEK_BASE", "https://api.deepseek.com")

        # GLM direct comparison
        self.glm_api_key: str = os.getenv("GLM_API_KEY", "")
        self.glm_base: str = os.getenv("GLM_BASE", "https://open.bigmodel.cn/api/paas/v4")

        # Test control
        self.provider: str = os.getenv("UNIAPI_PROVIDER", "all")  # deepseek, glm, all
        self.models_deepseek: list[str] = (
            os.getenv("UNIAPI_MODELS_DEEPSEEK", "deepseek-v4-pro,deepseek-v4-flash").split(",")
        )
        self.models_glm: list[str] = (
            os.getenv("UNIAPI_MODELS_GLM", "glm-5.2,glm-4").split(",")
        )
        self.timeout: int = int(os.getenv("TEST_TIMEOUT", "120"))
        self.stream_timeout: int = int(os.getenv("TEST_STREAM_TIMEOUT", "30"))

    @property
    def is_valid(self) -> bool:
        return bool(self.api_token)

    @property
    def has_deepseek(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def has_glm(self) -> bool:
        return bool(self.glm_api_key)

    def headers(self, extra: dict | None = None) -> dict:
        h = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }
        if extra:
            h.update(extra)
        return h


config = LiveConfig()
