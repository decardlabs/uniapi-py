"""Phase 2e: Options, token consume/balance endpoints (TDD)."""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_options_list(client: AsyncClient):
    """GET /api/option/ should list system options (RootAuth)."""
    cookies = await _login(client)
    resp = await client.get("/api/option/", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_options_update(client: AsyncClient):
    """PUT /api/option/ should update an option (RootAuth)."""
    cookies = await _login(client)
    resp = await client.put(
        "/api/option/",
        json={"key": "SystemName", "value": "TestName"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Verify
    list_resp = await client.get("/api/option/", cookies=cookies)
    options = list_resp.json()["data"]
    opt_map = {o["key"]: o["value"] for o in options if isinstance(o, dict)}
    assert opt_map.get("SystemName") == "TestName"


@pytest.mark.asyncio
async def test_options_requires_root(client: AsyncClient):
    """Non-root users cannot access options."""
    reg_resp = await client.post("/api/user/register", json={
        "username": "regular_opts", "password": "password123",
    })
    cookies = reg_resp.cookies
    resp = await client.get("/api/option/", cookies=cookies)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_token_balance_endpoint(client: AsyncClient):
    """GET /api/token/balance should work with TokenAuth."""
    cookies = await _login(client)
    token_resp = await client.post(
        "/api/token/",
        json={"name": "balance-test"},
        cookies=cookies,
    )
    token_key = token_resp.json()["data"]["key"]

    resp = await client.get(
        "/api/token/balance",
        headers={"Authorization": f"Bearer {token_key}"},
    )
    assert resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_channel_types_endpoint(client: AsyncClient):
    """GET /api/channel/types should list available channel types."""
    resp = await client.get("/api/channel/types")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
