from __future__ import annotations

import logging
from typing import Optional

from app.relay.adaptor import BaseAdaptor

logger = logging.getLogger(__name__)


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

    def all_types(self) -> list[int]:
        return list(self._registry.keys())

    def resolve_channel_type(self, model_name: str) -> int | None:
        """Find which registered channel type supports the given model.

        Returns channel_type (int) or None if no adaptor supports this model.
        """
        for channel_type, adaptor_cls in self._registry.items():
            adaptor = adaptor_cls()
            if adaptor.resolve_model_name(model_name) is not None:
                return channel_type
        return None


# Global registry - auto-register all known adaptors
registry = AdaptorRegistry()

try:
    from app.relay.adaptors.deepseek.adaptor import DEEPSEEK_CHANNEL_TYPE, DeepSeekAdaptor  # noqa: E402
    registry.register(DEEPSEEK_CHANNEL_TYPE, DeepSeekAdaptor)
except ImportError as e:
    logger.warning("Failed to load DeepSeek adaptor: %s", e)

try:
    from app.relay.adaptors.glm.adaptor import GLM_CHANNEL_TYPE, GLMAdaptor  # noqa: E402
    registry.register(GLM_CHANNEL_TYPE, GLMAdaptor)
except ImportError as e:
    logger.warning("Failed to load GLM adaptor: %s", e)

try:
    from app.relay.adaptors.kimi.adaptor import KIMI_CHANNEL_TYPE, KimiAdaptor  # noqa: E402
    registry.register(KIMI_CHANNEL_TYPE, KimiAdaptor)
except ImportError as e:
    logger.warning("Failed to load Kimi adaptor: %s", e)

try:
    from app.relay.adaptors.minimax.adaptor import MINIMAX_CHANNEL_TYPE, MiniMaxAdaptor  # noqa: E402
    registry.register(MINIMAX_CHANNEL_TYPE, MiniMaxAdaptor)
except ImportError as e:
    logger.warning("Failed to load MiniMax adaptor: %s", e)

try:
    from app.relay.adaptors.qwen.adaptor import QWEN_CHANNEL_TYPE, QwenAdaptor  # noqa: E402
    registry.register(QWEN_CHANNEL_TYPE, QwenAdaptor)
except ImportError as e:
    logger.warning("Failed to load Qwen adaptor: %s", e)
