"""Tests for dashboard API."""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_dashboard(client: AsyncClient):
    """GET /api/user/dashboard should return stats."""
    cookies = await _login(client)
    resp = await client.get("/api/user/dashboard", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "quota" in data["data"]
    assert "used_quota" in data["data"]


@pytest.mark.asyncio
async def test_dashboard_users(client: AsyncClient):
    """GET /api/user/dashboard/users should return user stats (admin)."""
    cookies = await _login(client)
    resp = await client.get("/api/user/dashboard/users", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
