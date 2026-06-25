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
        "password": "NewPass789",
        "old_password": "123456",
    }, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Login with new password
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "NewPass789",
    })
    assert resp.status_code == 200

    # Restore old password
    cookies2 = resp.cookies
    await client.put("/api/user/self", json={
        "password": "123456",
        "old_password": "NewPass789",
    }, cookies=cookies2)


@pytest.mark.asyncio
async def test_update_user_self_wrong_old_password(client: AsyncClient):
    """PUT /api/user/self with wrong old_password should fail."""
    cookies = await _login(client)
    resp = await client.put("/api/user/self", json={
        "password": "NewPass789",
        "old_password": "wrong-password",
    }, cookies=cookies)
    data = resp.json()
    assert data["success"] is False
    assert "incorrect" in data["message"].lower()

    # Verify still can login with original password
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_user_self_empty_new_password(client: AsyncClient):
    """PUT /api/user/self with empty new_password is ignored (no change)."""
    cookies = await _login(client)
    resp = await client.put("/api/user/self", json={
        "password": "",
        "old_password": "123456",
    }, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True  # empty string is falsy → skipped, no error


@pytest.mark.asyncio
async def test_update_user_self_weak_password(client: AsyncClient):
    """PUT /api/user/self with weak new password should be rejected."""
    cookies = await _login(client)
    resp = await client.put("/api/user/self", json={
        "password": "short",
        "old_password": "123456",
    }, cookies=cookies)
    data = resp.json()
    assert data["success"] is False
    assert "8 characters" in data["message"]

    resp = await client.put("/api/user/self", json={
        "password": "nouppercase1",
        "old_password": "123456",
    }, cookies=cookies)
    data = resp.json()
    assert data["success"] is False
    assert "uppercase" in data["message"].lower()

    resp = await client.put("/api/user/self", json={
        "password": "NODIGITS",
        "old_password": "123456",
    }, cookies=cookies)
    data = resp.json()
    assert data["success"] is False
    assert "digit" in data["message"].lower()


@pytest.mark.asyncio
async def test_update_user_self_not_logged_in(client: AsyncClient):
    """PUT /api/user/self without session should fail."""
    resp = await client.put("/api/user/self", json={
        "display_name": "Hacker",
    })
    data = resp.json()
    assert data["success"] is False
    assert "not logged in" in data["message"].lower()


@pytest.mark.asyncio
async def test_update_user_self_strong_password(client: AsyncClient):
    """PUT /api/user/self with a strong password should succeed."""
    cookies = await _login(client)
    new_strong_pwd = "Str0ngPass!"

    resp = await client.put("/api/user/self", json={
        "password": new_strong_pwd,
        "old_password": "123456",
    }, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Login with new password
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": new_strong_pwd,
    })
    assert resp.status_code == 200

    # Restore
    cookies = resp.cookies
    await client.put("/api/user/self", json={
        "password": "123456",
        "old_password": new_strong_pwd,
    }, cookies=cookies)


@pytest.mark.asyncio
async def test_user_aff(client: AsyncClient):
    """GET /api/user/aff should return affiliate info."""
    cookies = await _login(client)
    resp = await client.get("/api/user/aff", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
