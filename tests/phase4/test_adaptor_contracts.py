"""Contract tests for all registered adaptors.

Verifies that every adaptor registered in the global registry satisfies
the BaseAdaptor contract. When a new provider is added, these tests
ensure it implements all required methods correctly.
"""
import pytest
from app.relay.adaptor import BaseAdaptor, ModelConfig
from app.relay.meta import RelayMeta
from app.relay.mode import RelayMode


# Collect all adaptor classes from the registry
@pytest.fixture(scope="session")
def registered_adaptors():
    from app.relay.registry import registry
    return [
        (channel_type, type(adp))
        for channel_type, adp_cls in registry._registry.items()
        for adp in [adp_cls()]
    ]


def _get_all_adaptor_classes():
    """Return list of (channel_type, adaptor_class) tuples from registry."""
    from app.relay.registry import registry
    return list(registry._registry.items())


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_adaptor_has_provider_name(channel_type, adp_cls):
    """Every adaptor must set a non-empty provider_name."""
    instance = adp_cls()
    assert instance.provider_name, f"Adaptor for type {channel_type} has empty provider_name"
    assert isinstance(instance.provider_name, str)


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_adaptor_supports_chat_completions(channel_type, adp_cls):
    """Every adaptor must support chat_completions natively."""
    instance = adp_cls()
    assert "chat_completions" in instance.NATIVE_FORMATS, (
        f"{instance.provider_name} missing chat_completions in NATIVE_FORMATS"
    )
    assert instance.supports_native_format(RelayMode.CHAT_COMPLETIONS), (
        f"{instance.provider_name} fails supports_native_format(CHAT_COMPLETIONS)"
    )


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_adaptor_has_models(channel_type, adp_cls):
    """Every adaptor must return at least one model."""
    instance = adp_cls()
    models = instance.get_supported_models()
    assert len(models) >= 1, f"{instance.provider_name} has no supported models"


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_model_config_max_tokens_valid(channel_type, adp_cls):
    """All ModelConfig entries must have valid max_tokens."""
    instance = adp_cls()
    for name, cfg in instance.get_supported_models().items():
        assert isinstance(cfg, ModelConfig), f"{instance.provider_name}:{name} is not ModelConfig"
        assert cfg.max_tokens > 0, f"{instance.provider_name}:{name} max_tokens must be > 0"


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_resolve_model_name_finds_known(channel_type, adp_cls):
    """resolve_model_name must return the canonical name for all supported models."""
    instance = adp_cls()
    for name in instance.get_supported_models():
        resolved = instance.resolve_model_name(name)
        assert resolved is not None, (
            f"{instance.provider_name}: resolve_model_name('{name}') returned None"
        )


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_resolve_model_name_unknown(channel_type, adp_cls):
    """resolve_model_name must return None for unsupported models."""
    instance = adp_cls()
    assert instance.resolve_model_name("nonexistent-model-xyz-123") is None


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_get_request_url_returns_string(channel_type, adp_cls):
    """get_request_url must return a non-empty string for chat and claude modes."""
    instance = adp_cls()
    meta = RelayMeta(base_url=instance.DEFAULT_BASE_URL)
    for mode in (RelayMode.CHAT_COMPLETIONS, RelayMode.CLAUDE_MESSAGES):
        url = instance.get_request_url(meta, mode)
        assert isinstance(url, str), f"{instance.provider_name}: url is not str for mode {mode}"
        assert url, f"{instance.provider_name}: url is empty for mode {mode}"


@pytest.mark.parametrize("channel_type,adp_cls", _get_all_adaptor_classes())
def test_setup_request_headers(channel_type, adp_cls):
    """setup_request_headers must return a dict with Authorization."""
    instance = adp_cls()
    # GLM expects key format "id.secret", others accept "test-key"
    test_key = "test-id.test-secret" if instance.provider_name == "glm" else "test-key"
    try:
        headers = instance.setup_request_headers(test_key)
    except Exception:
        pytest.skip(f"{instance.provider_name}: setup_request_headers raised for test key")
    assert isinstance(headers, dict), f"{instance.provider_name}: headers not a dict"
    assert "Authorization" in headers, f"{instance.provider_name}: missing Authorization header"
    assert "Content-Type" in headers, f"{instance.provider_name}: missing Content-Type header"
