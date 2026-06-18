from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.relay.meta import RelayMeta


class ModelConfig:
    def __init__(
        self,
        input_ratio: float = 1.0,
        output_ratio: float = 1.0,
        cached_input_ratio: float = 0.1,
        max_tokens: int = 128000,
    ):
        self.input_ratio = input_ratio
        self.output_ratio = output_ratio
        self.cached_input_ratio = cached_input_ratio
        self.max_tokens = max_tokens


class BaseAdaptor(ABC):
    """Abstract base class for provider adaptors.

    Each AI provider implements this interface to plug into the relay pipeline.

    NATIVE_FORMATS: set of API formats this provider supports natively.
    When a request arrives in a format the provider natively understands,
    it is proxied directly without conversion.
    """
    provider_name: str = ""
    NATIVE_FORMATS: set[str] = {"chat_completions"}
    DEFAULT_BASE_URL: str = ""

    @abstractmethod
    def get_request_url(self, meta: RelayMeta, relay_mode: int = 1) -> str:
        """Construct the upstream API URL for the given relay mode."""
        ...

    def _get_path_for_mode(self, relay_mode: int) -> str:
        """Return the API path for a given relay mode.

        Override in subclasses that natively support non-chat formats.
        """
        return "/v1/chat/completions"

    def _format_from_mode(self, relay_mode: int) -> str:
        """Map relay mode to format name used in NATIVE_FORMATS."""
        mapping = {
            1: "chat_completions",
            2: "completions",
            3: "embeddings",
            4: "moderations",
            5: "images_generations",
            6: "images_edits",
            7: "audio_speech",
            8: "audio_transcription",
            9: "audio_translation",
            10: "rerank",
            11: "response_api",
            12: "claude_messages",
            13: "realtime",
        }
        return mapping.get(relay_mode, "chat_completions")

    def supports_native_format(self, relay_mode: int) -> bool:
        """Check if this adaptor natively supports the given relay mode."""
        fmt = self._format_from_mode(relay_mode)
        return fmt in self.NATIVE_FORMATS

    @abstractmethod
    def setup_request_headers(self, api_key: str) -> dict[str, str]:
        """Set auth + content-type headers."""
        ...

    @abstractmethod
    async def convert_request(self, body: dict, meta: RelayMeta) -> dict:
        """Convert the relay request body to provider-native format."""
        ...

    @abstractmethod
    def get_supported_models(self) -> dict[str, ModelConfig]:
        """Return dict of model_name -> ModelConfig."""
        ...

    def convert_claude_request(self, body: dict) -> dict:
        """Convert Claude Messages request to OpenAI Chat format.

        Override in adaptors that do NOT natively support claude_messages.
        Default implementation uses the generic converter.
        """
        from app.relay.converter import anthropic_to_chat
        return anthropic_to_chat(body)

    def convert_image_request(self, body: dict) -> dict:
        raise NotImplementedError("Image generation not supported")
