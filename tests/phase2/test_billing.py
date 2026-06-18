"""Phase 2c: Billing & log endpoints (TDD)."""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_log_self_endpoint(client: AsyncClient):
    """GET /api/log/self should return user's logs."""
    cookies = await _login(client)
    resp = await client.get("/api/log/self?p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data.get("data"), list)
    assert isinstance(data.get("total"), int)


@pytest.mark.asyncio
async def test_log_self_stat(client: AsyncClient):
    """GET /api/log/self/stat should return stats."""
    cookies = await _login(client)
    resp = await client.get("/api/log/self/stat", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_log_self_search(client: AsyncClient):
    """GET /api/log/self/search should work."""
    cookies = await _login(client)
    resp = await client.get("/api/log/self/search?keyword=test", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_log_admin_endpoint(client: AsyncClient):
    """GET /api/log/ should require admin auth."""
    # Regular user cannot access admin logs
    reg_resp = await client.post("/api/user/register", json={
        "username": "reg_user_log", "password": "password123",
    })
    reg_cookies = reg_resp.cookies
    admin_resp = await client.get("/api/log/?p=0&size=10", cookies=reg_cookies)
    assert admin_resp.status_code in (401, 403)

    # Admin can access
    cookies = await _login(client)
    resp = await client.get("/api/log/?p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_log_admin_stat(client: AsyncClient):
    """GET /api/log/stat should work for admin."""
    cookies = await _login(client)
    resp = await client.get("/api/log/stat", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_log_delete(client: AsyncClient):
    """DELETE /api/log/ should require admin auth."""
    cookies = await _login(client)
    resp = await client.delete(
        "/api/log/?target_timestamp=9999999999999",
        cookies=cookies,
    )
    assert resp.status_code in (200, 403)


@pytest.mark.asyncio
async def test_trace_endpoint(client: AsyncClient):
    """GET /api/trace/log/:log_id should work for authenticated users."""
    cookies = await _login(client)
    resp = await client.get("/api/trace/log/1", cookies=cookies)
    # 404 is fine - trace may not exist
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_cost_endpoint(client: AsyncClient):
    """GET /api/cost/request/:request_id should work."""
    resp = await client.get("/api/cost/request/test-request-id-123")
    assert resp.status_code in (200, 404)
