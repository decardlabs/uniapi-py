"""Base adapter interface for all model providers in the fusion pipeline."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator

from app.fusion.schemas import ModelRequest, ModelResponse


class BaseAdapter(ABC):
    provider_name: str = "base"
    openai_base_url: str = ""
    anthropic_base_url: str = ""
    api_key: str = ""

    def __init__(self, provider_name: str, openai_base_url: str, anthropic_base_url: str, api_key: str, **kwargs):
        self.provider_name = provider_name
        self.openai_base_url = openai_base_url.rstrip("/")
        self.anthropic_base_url = anthropic_base_url.rstrip("/")
        self.api_key = api_key
        self.extra_config = kwargs

    @abstractmethod
    async def chat(self, request: ModelRequest) -> ModelResponse:
        ...

    @abstractmethod
    async def stream_chat(self, request: ModelRequest) -> AsyncGenerator[str, None]:
        ...
        yield

    @abstractmethod
    def adapt_request(self, openai_request: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def adapt_response(self, native_response: dict[str, Any]) -> ModelResponse:
        ...
