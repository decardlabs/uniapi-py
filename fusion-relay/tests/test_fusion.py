"""
Fusion pipeline integration test.

Run: python -m pytest tests/test_fusion.py -v

Note: Requires API keys in .env to actually call upstream models.
For offline testing, mock the adapters.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.schemas import (
    ChatRequest,
    ChatResponse,
    ModelRequest,
    ModelResponse,
    UsageInfo,
)
from src.core.fusion_engine import FusionEngine, FusionConfig
from src.adapters.registry import AdapterRegistry


@pytest.fixture
def mock_registry():
    """Create a registry with 3 mock adapters."""
    registry = AdapterRegistry()

    for model_id in ["deepseek-v4-pro", "minimax-abab7", "glm-4-plus"]:
        mock_adapter = MagicMock()
        mock_response = ModelResponse(
            model=model_id,
            content=f"Answer from {model_id}: The answer is 42.",
            usage=UsageInfo(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )
        mock_adapter.chat = AsyncMock(return_value=mock_response)
        mock_adapter.provider_name = model_id.split("-")[0]
        registry.register(model_id, mock_adapter)

    return registry


@pytest.fixture
def fusion_config():
    return FusionConfig(
        panel=["deepseek-v4-pro", "minimax-abab7", "glm-4-plus"],
        judge="minimax-abab7",
        synthesizer="deepseek-v4-pro",
        timeout_seconds=5,
        retry_count=1,
        fallback_model="deepseek-v4-pro",
    )


@pytest.fixture
def sample_request():
    return ChatRequest(
        model="fusion",
        messages=[{"role": "user", "content": "What is the meaning of life?"}],
    )


@pytest.mark.asyncio
async def test_fusion_pipeline(mock_registry, fusion_config, sample_request):
    """Test that fusion engine runs the full pipeline."""
    engine = FusionEngine(mock_registry, fusion_config)
    response = await engine.execute(sample_request)

    assert response is not None
    assert response.model == "fusion"
    assert len(response.choices) > 0
    assert response.fusion_meta is not None
    assert len(response.fusion_meta.panel_models) == 3


@pytest.mark.asyncio
async def test_fusion_fallback(mock_registry, fusion_config, sample_request):
    """Test fallback when all panel models fail."""
    # Make all adapters fail
    for model_id in ["deepseek-v4-pro", "minimax-abab7", "glm-4-plus"]:
        adapter = mock_registry.get(model_id)
        adapter.chat = AsyncMock(side_effect=Exception("Connection failed"))

    engine = FusionEngine(mock_registry, fusion_config)
    response = await engine.execute(sample_request)

    # Should fallback gracefully
    assert response is not None
    assert response.fusion_meta.fallback_triggered == True


@pytest.mark.asyncio
async def test_passthrough_mode(mock_registry):
    """Test direct model access (non-fusion)."""
    from src.models.schemas import ChatRequest

    request = ChatRequest(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert not request.is_fusion

    fusion_request = ChatRequest(
        model="fusion",
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert fusion_request.is_fusion
