"""Channel connectivity tests — verify channel config consistency.

Tests that channel configurations are valid (models match adaptors,
pricing is defined, etc.) without actually making upstream API calls.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.relay.registry import registry
from app.relay.adaptor import BaseAdaptor


pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_all_channels_have_valid_type(client: AsyncClient):
    """Every channel's type should map to a registered adaptor."""
    from app.database import async_session_factory
    from app.models.channel import Channel

    async with async_session_factory() as db:
        result = await db.execute(select(Channel))
        channels = result.scalars().all()

    for ch in channels:
        adaptor = registry.get(ch.type)
        assert adaptor is not None, \
            f"Channel #{ch.id} '{ch.name}' has unknown type={ch.type}"


@pytest.mark.asyncio
async def test_all_channels_have_valid_models(client: AsyncClient):
    """Channel models should be a subset of the adaptor's supported models."""
    from app.database import async_session_factory
    from app.models.channel import Channel

    async with async_session_factory() as db:
        result = await db.execute(select(Channel))
        channels = result.scalars().all()

    for ch in channels:
        if not ch.models:
            continue  # empty = all models allowed
        adaptor = registry.get(ch.type)
        if not adaptor:
            continue
        supported = adaptor.get_supported_models()
        model_names = [m.strip() for m in ch.models.split(",")]
        for name in model_names:
            assert name in supported, \
                f"Channel #{ch.id} '{ch.name}': model '{name}' not in adaptor's supported models"
            assert supported[name].max_tokens is not None, \
                f"Channel #{ch.id} '{ch.name}': model '{name}' has no max_tokens"


@pytest.mark.asyncio
async def test_channel_model_configs_parse(client: AsyncClient):
    """Channel model_configs should be valid JSON with expected fields."""
    from app.database import async_session_factory
    from app.models.channel import Channel
    import json

    async with async_session_factory() as db:
        result = await db.execute(select(Channel))
        channels = result.scalars().all()

    for ch in channels:
        if not ch.model_configs:
            continue
        try:
            parsed = json.loads(ch.model_configs)
        except json.JSONDecodeError:
            pytest.fail(f"Channel #{ch.id} '{ch.name}': model_configs is not valid JSON")

        assert isinstance(parsed, dict), \
            f"Channel #{ch.id} '{ch.name}': model_configs must be a dict"

        for model_name, config in parsed.items():
            # Must have at least one pricing field
            has_new = any(k in config for k in ["input_price", "output_price", "cache_hit_price"])
            has_old = any(k in config for k in ["ratio", "completion_ratio"])
            assert has_new or has_old, \
                f"Channel #{ch.id} '{ch.name}': model '{model_name}' has no pricing fields"


@pytest.mark.asyncio
async def test_channel_api_endpoints(client: AsyncClient):
    """Channel CRUD API should work correctly."""
    cookies = await _login(client)

    # List channels
    resp = await client.get("/api/channel/", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    channels = data.get("data", [])

    if len(channels) == 0:
        pytest.skip("No channels configured in test DB")

    # Verify each channel has required fields
    for ch in channels:
        assert "id" in ch
        assert "name" in ch
        assert "type" in ch
        assert "key" in ch  # should be masked for long keys
        key_val = ch.get("key", "")
        if len(key_val) >= 12:
            assert "..." in key_val, \
                f"Channel #{ch['id']} long key not masked: {key_val}"

    # Get individual channel
    first_id = channels[0]["id"]
    resp = await client.get(f"/api/channel/{first_id}", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == first_id
