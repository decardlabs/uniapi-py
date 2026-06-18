"""Tests for API endpoints of the FastAPI application."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_status_endpoint(client: AsyncClient):
    response = await client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["version"] == "0.1.0"
    assert data["data"]["system_name"] == "UniAPI"


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    register_resp = await client.post(
        "/api/user/register",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert register_resp.status_code == 200
    data = register_resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"

    # Login
    login_resp = await client.post(
        "/api/user/login",
        json={"username": "testuser", "password": "testpass123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"
    assert "session" in login_resp.cookies

    # Get self with session cookie
    self_resp = await client.get(
        "/api/user/self",
        cookies=login_resp.cookies,
    )
    assert self_resp.status_code == 200
    data = self_resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient):
    # Login first
    login_resp = await client.post(
        "/api/user/login",
        json={"username": "root", "password": "123456"},
    )
    assert login_resp.status_code == 200

    # Logout
    logout_resp = await client.get(
        "/api/user/logout",
        cookies=login_resp.cookies,
    )
    assert logout_resp.status_code == 200
    data = logout_resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_models_display(client: AsyncClient):
    response = await client.get("/api/models/display")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "DeepSeek" in data["data"]
    assert "deepseek-v4-pro" in data["data"]["DeepSeek"]["models"]


@pytest.mark.asyncio
async def test_root_login(client: AsyncClient):
    response = await client.post(
        "/api/user/login",
        json={"username": "root", "password": "123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["role"] == 100
