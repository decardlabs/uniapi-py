from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.relay.meta import RelayMeta
from app.relay.mode import RelayMode


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
            RelayMode.CHAT_COMPLETIONS: "chat_completions",
            RelayMode.COMPLETIONS: "completions",
            RelayMode.EMBEDDINGS: "embeddings",
            RelayMode.MODERATIONS: "moderations",
            RelayMode.IMAGES_GENERATIONS: "images_generations",
            RelayMode.IMAGES_EDITS: "images_edits",
            RelayMode.AUDIO_SPEECH: "audio_speech",
            RelayMode.AUDIO_TRANSCRIPTION: "audio_transcription",
            RelayMode.AUDIO_TRANSLATION: "audio_translation",
            RelayMode.RERANK: "rerank",
            RelayMode.RESPONSE_API: "response_api",
            RelayMode.CLAUDE_MESSAGES: "claude_messages",
            RelayMode.REALTIME: "realtime",
            RelayMode.VIDEOS: "videos",
            RelayMode.OCR: "ocr",
            RelayMode.PROXY: "proxy",
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

    def resolve_model_name(self, name: str) -> str | None:
        """Resolve a model name to its canonical form.

        Override to support case-insensitive or aliased lookups.
        Returns None when the model is not recognised.
        """
        if name in self.get_supported_models():
            return name
        return None

    def convert_claude_request(self, body: dict) -> dict:
        """Convert Claude Messages request to OpenAI Chat format.

        Override in adaptors that do NOT natively support claude_messages.
        Default implementation uses the generic converter.
        """
        from app.relay.converter import anthropic_to_chat
        return anthropic_to_chat(body)

    def normalize_request_body(self, body: dict) -> dict:
        """Normalize the request body before upstream relay.

        Override to apply provider-specific pre-processing (e.g. stripping
        fields that break prefix caching). Called only in the native-format
        (non-conversion) relay path.
        """
        return body

    def convert_image_request(self, body: dict) -> dict:
        raise NotImplementedError("Image generation not supported")
