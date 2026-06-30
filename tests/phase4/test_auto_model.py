"""Tests for model='auto' selection logic.

Covers 9 behavioral scenarios for _select_auto_channel() including
priority ranking, price tiebreaking, token model allowlist filtering,
cooldown skipping, group access control, and empty-model fallback.
"""

import pytest
from sqlalchemy import select

from app.database import async_session_factory, engine
from app.exceptions import RelayException
from app.models.base import Base
from app.models.channel import Channel
from app.models.token import Token
from app.models.user import User
from app.routers.v1.relay import (
    _cooldown_channel,
    _select_auto_channel,
)
from app.routers.v1.relay import _channel_cooldowns as relay_cooldowns


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables for each test and clean up afterward.

    Also resets the in-memory cooldown state to avoid cross-test pollution.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    relay_cooldowns.clear()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    """Get a fresh DB session."""
    async with async_session_factory() as session:
        yield session


# ── Test 1: Highest priority wins ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_highest_priority(db):
    """Higher priority channel wins over a cheaper but lower-priority model."""
    ch_a = Channel(
        id=1001, type=39, name="high-pri", priority=100,
        models="deepseek-v4-pro", status=1,
    )
    ch_b = Channel(
        id=1002, type=39, name="low-pri", priority=10,
        models="deepseek-v4-flash", status=1,
    )
    db.add_all([ch_a, ch_b])
    await db.flush()

    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="")

    model, channel = await _select_auto_channel(db, user, token)
    assert model == "deepseek-v4-pro"
    assert channel.id == 1001


# ── Test 2: Same priority, cheaper wins ───────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_cheaper_wins_on_tie(db):
    """When priority is equal, the cheaper model is chosen.

    deepseek-v4-pro: ¥3.0 + ¥6.0 = ¥9.0 / 1M tokens
    deepseek-v4-flash: ¥1.0 + ¥2.0 = ¥3.0 / 1M tokens
    """
    ch_a = Channel(
        id=2001, type=39, name="pro-channel", priority=50,
        models="deepseek-v4-pro", status=1,
    )
    ch_b = Channel(
        id=2002, type=39, name="flash-channel", priority=50,
        models="deepseek-v4-flash", status=1,
    )
    db.add_all([ch_a, ch_b])
    await db.flush()

    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="")

    model, channel = await _select_auto_channel(db, user, token)
    assert model == "deepseek-v4-flash"
    assert channel.id == 2002


# ── Test 3: Token restricted models ───────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_token_restricted(db):
    """Token allowlist restricts which models are considered."""
    ch_a = Channel(
        id=3001, type=39, name="pro-only", priority=100,
        models="deepseek-v4-pro", status=1,
    )
    ch_b = Channel(
        id=3002, type=39, name="flash-only", priority=10,
        models="deepseek-v4-flash", status=1,
    )
    db.add_all([ch_a, ch_b])
    await db.flush()

    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="deepseek-v4-flash")

    model, channel = await _select_auto_channel(db, user, token)
    assert model == "deepseek-v4-flash"
    assert channel.id == 3002


# ── Test 4: Token restricted, no match ────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_token_no_match_raises(db):
    """When token allowlist excludes every candidate model, raise an error."""
    ch = Channel(
        id=4001, type=39, name="deepseek-only", priority=50,
        models="deepseek-v4-pro", status=1,
    )
    db.add(ch)
    await db.flush()

    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="nonexistent-model")

    with pytest.raises(RelayException) as exc_info:
        await _select_auto_channel(db, user, token)

    assert exc_info.value.code == "UNIAPI_TOKEN_MODEL_NOT_ALLOWED"


# ── Test 5: No enabled channels ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_no_channels_raises(db):
    """When no channels exist at all, raise an error."""
    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="")

    with pytest.raises(RelayException) as exc_info:
        await _select_auto_channel(db, user, token)

    assert exc_info.value.code == "UNIAPI_CHANNEL_UNAVAILABLE"


# ── Test 6: Cooldown channel skipped ──────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_skips_cooldown(db):
    """A channel in 429 cooldown is skipped when alternatives exist."""
    ch_a = Channel(
        id=6001, type=39, name="available", priority=10,
        models="deepseek-v4-flash", status=1,
    )
    ch_b = Channel(
        id=6002, type=39, name="in-cooldown", priority=100,
        models="deepseek-v4-pro", status=1,
    )
    db.add_all([ch_a, ch_b])
    await db.flush()

    # Put ch_b into 429 cooldown
    _cooldown_channel(6002)

    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="")

    model, channel = await _select_auto_channel(db, user, token)
    assert model == "deepseek-v4-flash"
    assert channel.id == 6001


# ── Test 7: All channels in cooldown ──────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_all_cooldown_fallback(db):
    """When all channels are in cooldown, the best one is used anyway."""
    ch_a = Channel(
        id=7001, type=39, name="flash", priority=10,
        models="deepseek-v4-flash", status=1,
    )
    ch_b = Channel(
        id=7002, type=39, name="pro", priority=100,
        models="deepseek-v4-pro", status=1,
    )
    db.add_all([ch_a, ch_b])
    await db.flush()

    # Put both into cooldown
    _cooldown_channel(7001)
    _cooldown_channel(7002)

    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="")

    model, channel = await _select_auto_channel(db, user, token)
    # Highest priority wins when all are in cooldown
    assert model == "deepseek-v4-pro"
    assert channel.id == 7002


# ── Test 8: Group filtering ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auto_select_group_filtering(db):
    """Channels with a specific group are only accessible to users in that group."""
    ch_a = Channel(
        id=8001, type=39, name="group-a-ch", priority=100,
        models="deepseek-v4-pro", status=1, group="group_a",
    )
    ch_b = Channel(
        id=8002, type=39, name="group-b-ch", priority=10,
        models="deepseek-v4-flash", status=1, group="group_b",
    )
    db.add_all([ch_a, ch_b])
    await db.flush()

    user = User(id=999, username="test", password="x", group="group_a")
    token = Token(id=999, models="")

    model, channel = await _select_auto_channel(db, user, token)
    assert model == "deepseek-v4-pro"
    assert channel.id == 8001


# ── Test 9: Channel with empty models uses adaptor defaults ───────────────


@pytest.mark.asyncio
async def test_auto_select_empty_models_falls_back_to_adaptor(db):
    """When a channel has no models field, the adaptor's supported models are used."""
    ch = Channel(
        id=9001, type=39, name="no-models", priority=10,
        models="", status=1,  # empty-string models field
    )
    db.add(ch)
    await db.flush()

    user = User(id=999, username="test", password="x", group="default")
    token = Token(id=999, models="")

    model, channel = await _select_auto_channel(db, user, token)
    # Should fall back to adaptor defaults and pick the cheapest:
    # deepseek-v4-flash (¥3/M) < deepseek-v4-pro (¥9/M)
    assert model == "deepseek-v4-flash"
    assert channel.id == 9001
