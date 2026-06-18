"""
Adapter registry: maps model IDs to their adapter instances.

Loaded from models.yaml at startup. Supports hot-reload of configuration.

Key design: each provider config includes dual endpoints (openai + anthropic),
since all major domestic providers natively support both protocols.
"""

import logging
from typing import Any

from src.adapters.base import BaseAdapter
from src.adapters.deepseek import DeepSeekAdapter
from src.adapters.minimax import MiniMaxAdapter
from src.adapters.glm import GLMAdapter
from src.adapters.kimi import KimiAdapter
from src.adapters.qwen import QwenAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    Registry that holds all model adapters.

    Maps model_id -> adapter instance.
    Built from models.yaml config at startup.
    """

    # Provider class mapping
    PROVIDER_CLASSES = {
        "deepseek": DeepSeekAdapter,
        "minimax": MiniMaxAdapter,
        "glm": GLMAdapter,
        "kimi": KimiAdapter,
        "qwen": QwenAdapter,
    }

    def __init__(self):
        self._adapters: dict[str, BaseAdapter] = {}
        self._model_to_provider: dict[str, str] = {}

    def register(self, model_id: str, adapter: BaseAdapter) -> None:
        """Register an adapter for a model ID."""
        self._adapters[model_id] = adapter
        self._model_to_provider[model_id] = adapter.provider_name
        logger.info("Registered adapter: %s -> %s", model_id, adapter.provider_name)

    def get(self, model_id: str) -> BaseAdapter | None:
        """Get adapter by model ID. Returns None if not found."""
        return self._adapters.get(model_id)

    def list_models(self) -> list[str]:
        """List all registered model IDs."""
        return list(self._adapters.keys())

    def load_from_config(self, config: dict[str, Any]) -> None:
        """
        Load all adapters from models.yaml config.

        Expected config structure:
            providers:
              deepseek:
                openai_base_url: https://api.deepseek.com
                anthropic_base_url: https://api.deepseek.com/anthropic
                api_key: ${DEEPSEEK_API_KEY}
                models: [{id: deepseek-v4-pro, ...}, ...]
              minimax: ...
              glm: ...
              kimi: ...
              qwen: ...
        """
        providers = config.get("providers", {})
        for provider_name, provider_config in providers.items():
            adapter_class = self.PROVIDER_CLASSES.get(provider_name)
            if adapter_class is None:
                logger.warning(
                    "Unknown provider: %s, skipping. Known: %s",
                    provider_name,
                    list(self.PROVIDER_CLASSES.keys()),
                )
                continue

            # Dual-protocol endpoints
            openai_base_url = provider_config.get("openai_base_url", "")
            anthropic_base_url = provider_config.get("anthropic_base_url", "")
            api_key = provider_config.get("api_key", "")

            # Resolve env var placeholders like ${DEEPSEEK_API_KEY}
            api_key = self._resolve_env_var(api_key)

            models = provider_config.get("models", [])
            for model_config in models:
                model_id = model_config.get("id", "")
                if not model_id:
                    continue

                adapter = adapter_class(
                    provider_name=provider_name,
                    openai_base_url=openai_base_url,
                    anthropic_base_url=anthropic_base_url,
                    api_key=api_key,
                    model_config=model_config,
                )
                self.register(model_id, adapter)

        logger.info(
            "Adapter registry loaded: %d models from %d providers",
            len(self._adapters),
            len(providers),
        )

    def _resolve_env_var(self, value: str) -> str:
        """Resolve ${VAR_NAME} placeholders from environment."""
        import os
        import re

        def replace(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(r"\$\{(\w+)\}", replace, value)
