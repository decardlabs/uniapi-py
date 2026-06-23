"""Phase 4: Provider extensibility - adaptor registry + second provider (TDD).

Verifies that new providers can be added by:
1. Registering in the global registry
2. Implementing BaseAdaptor
3. Being selected at relay time
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_registry_register_and_get(client: AsyncClient):
    """Registry should store and return adaptor instances."""
    from app.relay.registry import registry

    class MockAdaptor:
        provider_name = "mock"
        def get_supported_models(self): return {"mock-model": None}

    registry.register(999, MockAdaptor)
    adp = registry.get(999)
    assert adp is not None
    assert adp.provider_name == "mock"

    # Cleanup
    registry._registry.pop(999, None)


@pytest.mark.asyncio
async def test_registry_returns_none_for_unknown(client: AsyncClient):
    """Registry.get should return None for unregistered types."""
    from app.relay.registry import registry
    assert registry.get(-1) is None


@pytest.mark.asyncio
async def test_registry_all_adaptors(client: AsyncClient):
    """Registry.all_adaptors should list all registered adaptors."""
    from app.relay.registry import registry
    adaptors = registry.all_adaptors()
    assert len(adaptors) >= 1
    names = [a.provider_name for a in adaptors]
    assert "deepseek" in names


@pytest.mark.asyncio
async def test_new_adaptor_implements_base(client: AsyncClient):
    """A new provider adaptor must implement BaseAdaptor ABC."""
    from app.relay.adaptor import BaseAdaptor, ModelConfig
    from app.relay.meta import RelayMeta

    class OpenAIAdaptor(BaseAdaptor):
        provider_name = "openai"
        NATIVE_FORMATS = {"chat_completions", "response_api"}
        DEFAULT_BASE_URL = "https://api.openai.com/v1"

        def get_request_url(self, meta: RelayMeta, relay_mode: int = 1) -> str:
            return f"{meta.base_url or self.DEFAULT_BASE_URL}/chat/completions"

        def setup_request_headers(self, api_key: str) -> dict[str, str]:
            return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        async def convert_request(self, body: dict, meta: RelayMeta) -> dict:
            return body

        def get_supported_models(self) -> dict[str, ModelConfig]:
            return {
                "gpt-4o": ModelConfig(max_tokens=128000),
                "gpt-4o-mini": ModelConfig(max_tokens=128000),
            }

    adp = OpenAIAdaptor()
    assert "chat_completions" in adp.NATIVE_FORMATS
    assert "response_api" in adp.NATIVE_FORMATS
    assert "claude_messages" not in adp.NATIVE_FORMATS
    assert "gpt-4o" in adp.get_supported_models()
    assert not adp.supports_native_format(12)  # 12=ClaudeMessages


@pytest.mark.asyncio
async def test_new_adaptor_registered_and_used(client: AsyncClient):
    """A newly registered adaptor should be selectable via registry."""
    from app.relay.adaptor import BaseAdaptor, ModelConfig
    from app.relay.meta import RelayMeta
    from app.relay.registry import registry
    from app.relay.adaptors.deepseek.adaptor import DEEPSEEK_CHANNEL_TYPE

    class TestAdaptor(BaseAdaptor):
        provider_name = "test-provider"
        async def convert_request(self, body, meta): return body
        def get_request_url(self, meta, relay_mode=1): return "http://test/chat"
        def setup_request_headers(self, api_key=""): return {}
        def get_supported_models(self): return {"test-model": ModelConfig(max_tokens=128000)}

    # Register at a unique channel type
    registry.register(9999, TestAdaptor)
    adp = registry.get(9999)
    assert adp is not None
    assert adp.provider_name == "test-provider"

    # The DeepSeek adaptor should still work
    deepseek_adp = registry.get(DEEPSEEK_CHANNEL_TYPE)
    assert deepseek_adp is not None
    assert deepseek_adp.provider_name == "deepseek"

    # Cleanup
    registry._registry.pop(9999, None)


@pytest.mark.asyncio
async def test_supports_native_format_api(client: AsyncClient):
    """supports_native_format should work correctly."""
    from app.relay.adaptors.deepseek.adaptor import DeepSeekAdaptor
    adp = DeepSeekAdaptor()

    # DeepSeek supports claude_messages natively
    assert adp.supports_native_format(12) is True  # ClaudeMessages=12
    # DeepSeek supports chat natively
    assert adp.supports_native_format(1) is True   # ChatCompletions=1
    # DeepSeek doesn't support images natively
    assert adp.supports_native_format(5) is False  # ImagesGenerations=5
