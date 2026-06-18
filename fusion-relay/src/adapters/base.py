"""
Base adapter: unified interface for all model providers.

All adapters implement this interface. The Fusion Engine interacts
only through this abstraction, making it trivial to add new providers.

Key design: each adapter holds TWO base URLs (OpenAI + Anthropic),
since all 5 major domestic providers natively support both protocols.
The adapter selects which endpoint to use based on protocol context.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from src.models.schemas import ModelRequest, ModelResponse


class BaseAdapter(ABC):
    """
    Abstract base class for model adapters.

    Each provider (DeepSeek, MiniMax, GLM, Kimi, Qwen, ...) implements this interface.

    Dual-protocol support:
      - openai_base_url: endpoint for OpenAI Chat Completions format
      - anthropic_base_url: endpoint for Anthropic Messages format

    Since all major domestic providers support both protocols natively,
    the adapter can forward requests in either format without conversion.
    The Fusion Engine internally uses OpenAI format; protocol selection
    happens only at the inbound/outbound boundary (handled by routes.py).
    """

    provider_name: str = "base"
    openai_base_url: str = ""
    anthropic_base_url: str = ""
    api_key: str = ""

    def __init__(
        self,
        provider_name: str,
        openai_base_url: str,
        anthropic_base_url: str,
        api_key: str,
        **kwargs,
    ):
        self.provider_name = provider_name
        self.openai_base_url = openai_base_url.rstrip("/")
        self.anthropic_base_url = anthropic_base_url.rstrip("/")
        self.api_key = api_key
        self.extra_config = kwargs

    @abstractmethod
    async def chat(self, request: ModelRequest) -> ModelResponse:
        """
        Non-streaming chat completion (via OpenAI endpoint).

        Args:
            request: Normalized model request (OpenAI-like internal format)

        Returns:
            ModelResponse with content, usage, and metadata.
        """
        ...

    @abstractmethod
    async def stream_chat(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion (via OpenAI endpoint). Yields content chunks.

        Args:
            request: Normalized model request.

        Yields:
            str: Content chunks as they arrive.
        """
        ...
        yield  # type: ignore[unreachable]

    @abstractmethod
    def adapt_request(self, openai_request: dict[str, Any]) -> dict[str, Any]:
        """
        Prepare OpenAI-format request for this provider.

        Most providers are already OpenAI-compatible, so this is
        often a near-identity transform with minor field remapping.
        """
        ...

    @abstractmethod
    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        """
        Parse provider response into normalized ModelResponse.
        """
        ...
