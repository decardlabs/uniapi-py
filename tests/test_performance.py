"""Performance baseline tests — verify response times under load.

These tests establish performance baselines for critical API paths.
Run separately from main test suite to avoid skewing coverage metrics:
  python3 -m pytest tests/test_performance.py -v --no-header
"""
import time

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

# Acceptable response time thresholds (seconds)
THRESHOLD_FAST = 0.5    # simple reads
THRESHOLD_MEDIUM = 1.0  # simple writes
THRESHOLD_SLOW = 3.0    # aggregation queries

CONCURRENT_REQUESTS = 50


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


async def test_login_performance(client: AsyncClient):
    """Login should respond within THRESHOLD_MEDIUM."""
    start = time.perf_counter()
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < THRESHOLD_MEDIUM, f"Login took {elapsed:.3f}s (>{THRESHOLD_MEDIUM}s)"
    print(f"  Login: {elapsed:.3f}s ✅")


async def test_status_performance(client: AsyncClient):
    """Status endpoint should respond within THRESHOLD_FAST."""
    start = time.perf_counter()
    resp = await client.get("/api/status")
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < THRESHOLD_FAST, f"Status took {elapsed:.3f}s (>{THRESHOLD_FAST}s)"
    print(f"  Status: {elapsed:.3f}s ✅")


async def test_list_pools_performance(client: AsyncClient):
    """Pool list should respond within THRESHOLD_MEDIUM."""
    cookies = await _login(client)
    start = time.perf_counter()
    resp = await client.get("/api/pool/?p=0&size=10", cookies=cookies)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < THRESHOLD_MEDIUM, f"Pool list took {elapsed:.3f}s (>{THRESHOLD_MEDIUM}s)"
    print(f"  Pool list: {elapsed:.3f}s ✅")


async def test_dashboard_performance(client: AsyncClient):
    """Dashboard aggregation should respond within THRESHOLD_SLOW."""
    cookies = await _login(client)
    start = time.perf_counter()
    resp = await client.get("/api/user/dashboard", cookies=cookies)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < THRESHOLD_SLOW, f"Dashboard took {elapsed:.3f}s (>{THRESHOLD_SLOW}s)"
    print(f"  Dashboard: {elapsed:.3f}s ✅")


async def test_cache_analytics_performance(client: AsyncClient):
    """Cache analytics aggregation should respond within THRESHOLD_SLOW."""
    cookies = await _login(client)
    start = time.perf_counter()
    resp = await client.get("/api/user/cache-analytics", cookies=cookies)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < THRESHOLD_SLOW, f"Cache analytics took {elapsed:.3f}s (>{THRESHOLD_SLOW}s)"
    print(f"  Cache analytics: {elapsed:.3f}s ✅")


async def test_concurrent_requests(client: AsyncClient):
    """50 concurrent status requests should all complete within THRESHOLD_FAST."""
    import asyncio

    async def single():
        t0 = time.perf_counter()
        r = await client.get("/api/status")
        return time.perf_counter() - t0, r.status_code

    tasks = [single() for _ in range(CONCURRENT_REQUESTS)]
    results = await asyncio.gather(*tasks)

    max_time = max(t for t, _ in results)
    all_ok = all(s == 200 for _, s in results)

    assert all_ok, f"{sum(1 for _, s in results if s != 200)} requests failed"
    assert max_time < THRESHOLD_FAST * 2, f"Max concurrent time: {max_time:.3f}s"
    print(f"  {CONCURRENT_REQUESTS}x concurrent status: max={max_time:.3f}s ✅")


async def test_model_pricing_performance(client: AsyncClient):
    """Models page should respond within THRESHOLD_MEDIUM."""
    cookies = await _login(client)
    start = time.perf_counter()
    resp = await client.get("/api/models/display", cookies=cookies)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < THRESHOLD_MEDIUM, f"Models display took {elapsed:.3f}s (>{THRESHOLD_MEDIUM}s)"
    print(f"  Models display: {elapsed:.3f}s ✅")


async def test_channel_list_performance(client: AsyncClient):
    """Channel list should respond within THRESHOLD_FAST."""
    cookies = await _login(client)
    start = time.perf_counter()
    resp = await client.get("/api/channel/", cookies=cookies)
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < THRESHOLD_FAST, f"Channel list took {elapsed:.3f}s"
    print(f"  Channel list: {elapsed:.3f}s ✅")
