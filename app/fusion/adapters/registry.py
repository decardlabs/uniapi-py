"""Adapter registry for the fusion pipeline."""
from __future__ import annotations

import logging
from typing import Any

from app.fusion.adapters.base import BaseAdapter
from app.fusion.adapters.deepseek import DeepSeekAdapter
from app.fusion.adapters.minimax import MiniMaxAdapter
from app.fusion.adapters.glm import GLMAdapter
from app.fusion.adapters.kimi import KimiAdapter
from app.fusion.adapters.qwen import QwenAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
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
        self._adapters[model_id] = adapter
        self._model_to_provider[model_id] = adapter.provider_name

    def get(self, model_id: str) -> BaseAdapter | None:
        return self._adapters.get(model_id)

    def list_models(self) -> list[str]:
        return list(self._adapters.keys())

    def register_provider(self, provider_name: str, openai_base_url: str, anthropic_base_url: str, api_key: str, models: list[dict[str, Any]]) -> None:
        adapter_class = self.PROVIDER_CLASSES.get(provider_name)
        if adapter_class is None:
            logger.warning("Unknown fusion provider: %s", provider_name)
            return
        for model_cfg in models:
            model_id = model_cfg.get("id", "")
            if not model_id:
                continue
            adapter = adapter_class(
                provider_name=provider_name,
                openai_base_url=openai_base_url,
                anthropic_base_url=anthropic_base_url,
                api_key=api_key,
                model_config=model_cfg,
            )
            self.register(model_id, adapter)
