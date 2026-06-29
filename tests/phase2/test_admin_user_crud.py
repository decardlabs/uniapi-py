"""Phase 2a: Admin user CRUD - write tests first (TDD)."""

import pytest
from httpx import AsyncClient


async def _admin_login(client: AsyncClient) -> dict:
    """Helper: login as admin and return session cookies."""
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    assert resp.status_code == 200
    return resp.cookies


@pytest.mark.asyncio
async def test_admin_list_users(client: AsyncClient):
    cookies = await _admin_login(client)
    resp = await client.get("/api/user/?p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_admin_get_user_by_id(client: AsyncClient):
    cookies = await _admin_login(client)
    # Get user list first
    list_resp = await client.get("/api/user/?p=0&size=10", cookies=cookies)
    users = list_resp.json()["data"]
    target_id = users[0]["id"]

    resp = await client.get(f"/api/user/{target_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] == target_id
    assert "username" in data["data"]


@pytest.mark.asyncio
async def test_admin_create_user(client: AsyncClient):
    cookies = await _admin_login(client)
    resp = await client.post(
        "/api/user/",
        json={"username": "newuser", "password": "password123", "display_name": "New"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message"] == "User created"


@pytest.mark.asyncio
async def test_admin_create_duplicate_user_fails(client: AsyncClient):
    cookies = await _admin_login(client)
    await client.post(
        "/api/user/",
        json={"username": "dupuser", "password": "password123"},
        cookies=cookies,
    )
    resp = await client.post(
        "/api/user/",
        json={"username": "dupuser", "password": "password123"},
        cookies=cookies,
    )
    assert resp.status_code in (400, 409)


@pytest.mark.asyncio
async def test_admin_update_user(client: AsyncClient):
    cookies = await _admin_login(client)
    # First create
    create_resp = await client.post(
        "/api/user/",
        json={"username": "upduser", "password": "password123", "quota": 5000},
        cookies=cookies,
    )
    assert create_resp.status_code == 200

    list_resp = await client.get("/api/user/?p=0&size=50", cookies=cookies)
    users = [u for u in list_resp.json()["data"] if u["username"] == "upduser"]
    target_id = users[0]["id"]

    resp = await client.put(
        "/api/user/",
        json={"id": target_id, "quota": 9999, "display_name": "Updated"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_admin_delete_user(client: AsyncClient):
    cookies = await _admin_login(client)
    create_resp = await client.post(
        "/api/user/",
        json={"username": "deluser", "password": "password123"},
        cookies=cookies,
    )
    assert create_resp.status_code == 200

    list_resp = await client.get("/api/user/?p=0&size=50", cookies=cookies)
    users = [u for u in list_resp.json()["data"] if u["username"] == "deluser"]
    target_id = users[0]["id"]

    resp = await client.delete(f"/api/user/{target_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_admin_search_users(client: AsyncClient):
    cookies = await _admin_login(client)
    resp = await client.get("/api/user/search?keyword=root", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert any(u["username"] == "root" for u in data["data"])


@pytest.mark.asyncio
async def test_unauthorized_user_access_fails(client: AsyncClient):
    """Non-admin should get 403 for admin endpoints."""
    resp = await client.post(
        "/api/user/register",
        json={"username": "regular", "password": "password123"},
    )
    cookies = resp.cookies
    list_resp = await client.get("/api/user/", cookies=cookies)
    assert list_resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_groups(client: AsyncClient):
    cookies = await _admin_login(client)
    resp = await client.get("/api/group/", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
