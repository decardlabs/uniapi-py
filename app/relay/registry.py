from __future__ import annotations

from typing import Optional

from app.relay.adaptor import BaseAdaptor


class AdaptorRegistry:
    """Registry mapping channel type codes to adaptor classes."""

    def __init__(self):
        self._registry: dict[int, type[BaseAdaptor]] = {}

    def register(self, channel_type: int, adaptor_cls: type[BaseAdaptor]):
        self._registry[channel_type] = adaptor_cls

    def get(self, channel_type: int) -> Optional[BaseAdaptor]:
        cls = self._registry.get(channel_type)
        if cls:
            return cls()
        return None

    def all_adaptors(self) -> list[BaseAdaptor]:
        return [cls() for cls in self._registry.values()]


# Global registry - auto-register DeepSeek
registry = AdaptorRegistry()

from app.relay.adaptors.deepseek.adaptor import DEEPSEEK_CHANNEL_TYPE, DeepSeekAdaptor  # noqa: E402
registry.register(DEEPSEEK_CHANNEL_TYPE, DeepSeekAdaptor)
