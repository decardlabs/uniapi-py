"""Tests for user self-service and dashboard endpoints."""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_update_user_self(client: AsyncClient):
    """PUT /api/user/self should update display_name."""
    cookies = await _login(client)
    resp = await client.put("/api/user/self", json={
        "display_name": "Updated Root",
    }, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify
    get = await client.get("/api/user/self", cookies=cookies)
    assert get.json()["data"]["display_name"] == "Updated Root"


@pytest.mark.asyncio
async def test_update_user_self_password(client: AsyncClient):
    """PUT /api/user/self should change password."""
    cookies = await _login(client)
    resp = await client.put("/api/user/self", json={
        "password": "newpass456",
        "old_password": "123456",
    }, cookies=cookies)
    assert resp.status_code == 200

    # Login with new password
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "newpass456",
    })
    assert resp.status_code == 200

    # Restore old password
    cookies2 = resp.cookies
    await client.put("/api/user/self", json={
        "password": "123456",
        "old_password": "newpass456",
    }, cookies=cookies2)


@pytest.mark.asyncio
async def test_user_aff(client: AsyncClient):
    """GET /api/user/aff should return affiliate info."""
    cookies = await _login(client)
    resp = await client.get("/api/user/aff", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
