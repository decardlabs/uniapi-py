"""Tests for user self-service endpoints."""
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
async def test_session_rotated_on_password_change(client: AsyncClient):
    """Password change rotates the session cookie, making old sessions invalid."""
    # Login and capture old session cookie
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    old_session_value = resp.cookies.get("session")
    assert old_session_value is not None

    # Change password — should return a new session cookie
    resp = await client.put("/api/user/self", json={
        "password": "NewPass789",
        "old_password": "123456",
    }, cookies=resp.cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    new_session_value = resp.cookies.get("session")
    assert new_session_value is not None
    assert new_session_value != old_session_value, "session token must change after password update"

    # Old session should be invalid now (session_version mismatch)
    get = await client.get("/api/user/self", cookies={"session": old_session_value})
    data = get.json()
    assert data["success"] is False
    assert "not logged in" in data["message"].lower()

    # New session should still work
    get2 = await client.get("/api/user/self", cookies={"session": new_session_value})
    assert get2.json()["success"] is True

    # Restore original password
    await client.put("/api/user/self", json={
        "password": "123456",
        "old_password": "NewPass789",
    }, cookies={"session": new_session_value})
