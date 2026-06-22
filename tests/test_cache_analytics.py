"""Tests for cache analytics API endpoint.

The endpoint must return real aggregated data from the Log table,
which already has cached_prompt_tokens populated by the relay pipeline.
"""
import time

import pytest
from httpx import AsyncClient

from app.database import async_session_factory
from app.models.channel import Channel
from app.models.log import Log

# ── Helpers ──────────────────────────────────────────────────────────


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


async def _seed_logs(entries: list[dict]) -> None:
    """Insert Log rows directly via DB session."""
    async with async_session_factory() as db:
        for e in entries:
            db.add(Log(**e))
        await db.commit()


async def _seed_channel(cid: int, name: str, ctype: int) -> None:
    """Insert a Channel row."""
    async with async_session_factory() as db:
        db.add(Channel(
            id=cid,
            name=name,
            type=ctype,
            key="sk-test",
            status=1,
        ))
        await db.commit()


def _compute_quota(pt: int, ct: int, cached: int, ir: float, or_: float, cir: float) -> int:
    """Replicate the relay pipeline's quota calculation."""
    miss = pt - cached
    return int(cached * cir + miss * ir + ct * or_)


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_requires_admin(client: AsyncClient):
    """Unauthenticated requests should be rejected."""
    resp = await client.get("/api/user/cache-analytics")
    assert resp.status_code in (401, 403), f"Expected auth error, got {resp.status_code}"


@pytest.mark.asyncio
async def test_empty_database(client: AsyncClient):
    """No log data → all zeros / empty arrays."""
    cookies = await _login(client)
    resp = await client.get("/api/user/cache-analytics", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    s = data["data"]["summary"]
    assert s["request_count"] == 0
    assert s["prompt_tokens"] == 0
    assert s["cached_prompt_tokens"] == 0
    assert s["cache_hit_rate"] == 0.0
    assert s["estimated_savings_rate"] == 0.0

    assert data["data"]["timeseries"] == []
    assert data["data"]["breakdown"] == []


@pytest.mark.asyncio
async def test_summary(client: AsyncClient):
    """Summary aggregation with 3 log rows using deepseek-v4-flash."""
    now = int(time.time() * 1000)
    ir, or_, cir = 1.0, 2.0, 0.02
    entries = [
        dict(
            user_id=1, created_at=now - 86400_000, type=2,
            model_name="deepseek-v4-flash", channel_id=39, request_id="r1",
            prompt_tokens=1000, completion_tokens=200, cached_prompt_tokens=500,
            cached_completion_tokens=0,
            quota=_compute_quota(1000, 200, 500, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now - 86400_000, type=2,
            model_name="deepseek-v4-flash", channel_id=39, request_id="r2",
            prompt_tokens=500, completion_tokens=100, cached_prompt_tokens=200,
            cached_completion_tokens=0,
            quota=_compute_quota(500, 100, 200, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now - 86400_000, type=2,
            model_name="deepseek-v4-flash", channel_id=39, request_id="r3",
            prompt_tokens=300, completion_tokens=50, cached_prompt_tokens=0,
            cached_completion_tokens=0,
            quota=_compute_quota(300, 50, 0, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
    ]
    await _seed_logs(entries)

    cookies = await _login(client)
    resp = await client.get("/api/user/cache-analytics", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    s = data["data"]["summary"]

    # Raw aggregations
    assert s["request_count"] == 3
    assert s["prompt_tokens"] == 1800
    assert s["cached_prompt_tokens"] == 700
    assert s["completion_tokens"] == 350
    assert s["cached_completion_tokens"] == 0
    assert s["quota"] == 910 + 504 + 400  # 1814

    # cache_hit_rate = 700 / 1800
    assert s["cache_hit_rate"] == pytest.approx(700 / 1800, rel=1e-6)

    # estimated_savings_rate = (cost_without_cache - cost_with_cache) / cost_without_cache
    # cost_without_cache = 1800*1.0 + 350*2.0 = 2500
    # cost_with_cache = 1814
    assert s["estimated_savings_rate"] == pytest.approx((2500 - 1814) / 2500, rel=1e-6)


@pytest.mark.asyncio
async def test_timeseries(client: AsyncClient):
    """Daily timeseries with logs spanning 3 days."""
    now = int(time.time() * 1000)
    day_ms = 86400_000
    ir, or_, cir = 3.0, 6.0, 0.025
    # 3 days: day1 (2 days ago), day2 (yesterday), day3 (today)
    entries = [
        dict(
            user_id=1, created_at=now - 2 * day_ms, type=2,
            model_name="deepseek-v4-pro", channel_id=39, request_id="r1",
            prompt_tokens=1000, completion_tokens=200, cached_prompt_tokens=500,
            cached_completion_tokens=0,
            quota=_compute_quota(1000, 200, 500, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-pro",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now - 1 * day_ms, type=2,
            model_name="deepseek-v4-pro", channel_id=39, request_id="r2",
            prompt_tokens=500, completion_tokens=100, cached_prompt_tokens=200,
            cached_completion_tokens=0,
            quota=_compute_quota(500, 100, 200, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-pro",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now, type=2,
            model_name="deepseek-v4-pro", channel_id=39, request_id="r3",
            prompt_tokens=300, completion_tokens=50, cached_prompt_tokens=0,
            cached_completion_tokens=0,
            quota=_compute_quota(300, 50, 0, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-pro",
            token_name="default", username="root",
        ),
    ]
    await _seed_logs(entries)

    cookies = await _login(client)
    resp = await client.get("/api/user/cache-analytics", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    ts = data["data"]["timeseries"]

    assert len(ts) == 3, f"Expected 3 daily rows, got {len(ts)}"

    # Verify the order is ASC (day1, day2, day3)
    days = [r["day"] for r in ts]
    assert days == sorted(days), f"Days not sorted ascending: {days}"

    # Each row should have correct fields
    for row in ts:
        assert "request_count" in row
        assert "prompt_tokens" in row
        assert "cached_prompt_tokens" in row
        assert "completion_tokens" in row
        assert "cached_completion_tokens" in row
        assert "quota" in row
        assert "cache_hit_rate" in row
        assert "estimated_savings_rate" in row


@pytest.mark.asyncio
async def test_breakdown(client: AsyncClient):
    """Breakdown by (model, channel, format) with LEFT JOIN on Channel."""
    now = int(time.time() * 1000)
    # Create 2 channels
    await _seed_channel(39, "DeepSeek Official", 39)
    await _seed_channel(41, "GLM Official", 41)

    # 2 models × 2 channels = 4 groups, each with 1 log
    entries = [
        dict(
            user_id=1, created_at=now, type=2,
            model_name="deepseek-v4-flash", channel_id=39, request_id="r1",
            prompt_tokens=100, completion_tokens=20, cached_prompt_tokens=50,
            cached_completion_tokens=0,
            quota=_compute_quota(100, 20, 50, 1.0, 2.0, 0.02),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now, type=2,
            model_name="deepseek-v4-pro", channel_id=39, request_id="r2",
            prompt_tokens=100, completion_tokens=20, cached_prompt_tokens=30,
            cached_completion_tokens=0,
            quota=_compute_quota(100, 20, 30, 3.0, 6.0, 0.025),
            content="ChatCompletion with deepseek-v4-pro",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now, type=2,
            model_name="deepseek-v4-flash", channel_id=41, request_id="r3",
            prompt_tokens=200, completion_tokens=40, cached_prompt_tokens=100,
            cached_completion_tokens=0,
            quota=_compute_quota(200, 40, 100, 1.0, 2.0, 0.02),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now, type=2,
            model_name="deepseek-v4-pro", channel_id=41, request_id="r4",
            prompt_tokens=200, completion_tokens=40, cached_prompt_tokens=80,
            cached_completion_tokens=0,
            quota=_compute_quota(200, 40, 80, 3.0, 6.0, 0.025),
            content="ChatCompletion with deepseek-v4-pro",
            token_name="default", username="root",
        ),
    ]
    await _seed_logs(entries)

    cookies = await _login(client)
    resp = await client.get("/api/user/cache-analytics", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    bd = data["data"]["breakdown"]

    assert len(bd) == 4, f"Expected 4 breakdown rows, got {len(bd)}"

    for row in bd:
        assert "model_name" in row
        assert "channel_id" in row
        assert "request_format" in row
        assert "channel_name" in row
        assert row["request_format"] == "ChatCompletion"
        assert "cache_hit_rate" in row
        assert "estimated_savings_rate" in row

    # Verify channel_name for channels that have a Channel row
    deepseek_rows = [r for r in bd if r["channel_id"] == 39]
    glm_rows = [r for r in bd if r["channel_id"] == 41]
    for r in deepseek_rows:
        assert r["channel_name"] == "DeepSeek Official"
    for r in glm_rows:
        assert r["channel_name"] == "GLM Official"


@pytest.mark.asyncio
async def test_compare(client: AsyncClient):
    """Compare before/after a compare_date."""
    now = int(time.time() * 1000)
    day_ms = 86400_000
    ir, or_, cir = 1.0, 2.0, 0.02

    # 5 days ago (before compare_date)
    before_ts = now - 5 * day_ms
    # 1 day ago (after compare_date)
    after_ts = now - 1 * day_ms

    before_log = dict(
        user_id=1, created_at=before_ts, type=2,
        model_name="deepseek-v4-flash", channel_id=39, request_id="r1",
        prompt_tokens=1000, completion_tokens=200, cached_prompt_tokens=500,
        cached_completion_tokens=0,
        quota=_compute_quota(1000, 200, 500, ir, or_, cir),
        content="ChatCompletion with deepseek-v4-flash",
        token_name="default", username="root",
    )
    after_log = dict(
        user_id=1, created_at=after_ts, type=2,
        model_name="deepseek-v4-flash", channel_id=39, request_id="r2",
        prompt_tokens=500, completion_tokens=100, cached_prompt_tokens=200,
        cached_completion_tokens=0,
        quota=_compute_quota(500, 100, 200, ir, or_, cir),
        content="ChatCompletion with deepseek-v4-flash",
        token_name="default", username="root",
    )
    await _seed_logs([before_log, after_log])

    # Set compare_date to 3 days ago (a date that splits before and after)
    compare_date_dt = now - 3 * day_ms
    import datetime
    compare_date_str = datetime.datetime.fromtimestamp(
        compare_date_dt / 1000, tz=datetime.timezone.utc
    ).strftime("%Y-%m-%d")

    cookies = await _login(client)
    resp = await client.get(
        f"/api/user/cache-analytics?compare_date={compare_date_str}",
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    comp = data["data"]["compare"]

    assert comp["compare_date"] == compare_date_str
    # Before: only the "before" log (pt=1000, cpt=500)
    assert comp["before"]["request_count"] == 1
    assert comp["before"]["prompt_tokens"] == 1000
    assert comp["before"]["cached_prompt_tokens"] == 500
    # After: only the "after" log (pt=500, cpt=200)
    assert comp["after"]["request_count"] == 1
    assert comp["after"]["prompt_tokens"] == 500
    assert comp["after"]["cached_prompt_tokens"] == 200


@pytest.mark.asyncio
async def test_filters(client: AsyncClient):
    """model_name and channel_id filters work correctly."""
    now = int(time.time() * 1000)
    ir, or_, cir = 3.0, 6.0, 0.025

    entries = [
        dict(
            user_id=1, created_at=now, type=2,
            model_name="deepseek-v4-pro", channel_id=39, request_id="r1",
            prompt_tokens=1000, completion_tokens=200, cached_prompt_tokens=500,
            cached_completion_tokens=0,
            quota=_compute_quota(1000, 200, 500, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-pro",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=now, type=2,
            model_name="deepseek-v4-flash", channel_id=41, request_id="r2",
            prompt_tokens=500, completion_tokens=100, cached_prompt_tokens=200,
            cached_completion_tokens=0,
            quota=_compute_quota(500, 100, 200, 1.0, 2.0, 0.02),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
    ]
    await _seed_logs(entries)

    cookies = await _login(client)

    # Filter by model_name
    resp = await client.get(
        "/api/user/cache-analytics?model_name=deepseek-v4-pro",
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["summary"]["request_count"] == 1
    assert data["data"]["summary"]["prompt_tokens"] == 1000

    # Filter by channel_id
    resp = await client.get(
        "/api/user/cache-analytics?channel_id=41",
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["summary"]["request_count"] == 1
    assert data["data"]["summary"]["prompt_tokens"] == 500


@pytest.mark.asyncio
async def test_date_range(client: AsyncClient):
    """from_date / to_date filters work correctly."""
    now = int(time.time() * 1000)
    day_ms = 86400_000
    ir, or_, cir = 1.0, 2.0, 0.02

    import datetime
    # Days: 5 days ago, 3 days ago, today
    old_ts = now - 5 * day_ms
    mid_ts = now - 3 * day_ms
    today_ts = now

    entries = [
        dict(
            user_id=1, created_at=old_ts, type=2,
            model_name="deepseek-v4-flash", channel_id=39, request_id="r1",
            prompt_tokens=1000, completion_tokens=200, cached_prompt_tokens=500,
            cached_completion_tokens=0,
            quota=_compute_quota(1000, 200, 500, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=mid_ts, type=2,
            model_name="deepseek-v4-flash", channel_id=39, request_id="r2",
            prompt_tokens=500, completion_tokens=100, cached_prompt_tokens=200,
            cached_completion_tokens=0,
            quota=_compute_quota(500, 100, 200, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
        dict(
            user_id=1, created_at=today_ts, type=2,
            model_name="deepseek-v4-flash", channel_id=39, request_id="r3",
            prompt_tokens=300, completion_tokens=50, cached_prompt_tokens=0,
            cached_completion_tokens=0,
            quota=_compute_quota(300, 50, 0, ir, or_, cir),
            content="ChatCompletion with deepseek-v4-flash",
            token_name="default", username="root",
        ),
    ]
    await _seed_logs(entries)

    cookies = await _login(client)

    # Convert mid_ts to date string (the day mid_ts falls on)
    mid_date = datetime.datetime.fromtimestamp(mid_ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
    today_date = datetime.datetime.fromtimestamp(today_ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
    old_date = datetime.datetime.fromtimestamp(old_ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")

    # Filter: from_date = old_date, to_date = mid_date
    # Should include old_ts and mid_ts, but NOT today_ts
    resp = await client.get(
        f"/api/user/cache-analytics?from_date={old_date}&to_date={mid_date}",
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["summary"]["request_count"] == 2
    assert data["data"]["summary"]["prompt_tokens"] == 1500  # 1000 + 500
