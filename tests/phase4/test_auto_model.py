"""Tests for model='auto' selection logic."""
import pytest


@pytest.mark.asyncio
async def test_auto_function_exists():
    """Verify _select_auto_channel is importable."""
    from app.routers.v1.relay import _select_auto_channel
    assert callable(_select_auto_channel)
