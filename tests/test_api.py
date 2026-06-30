"""Tests for API endpoints of the FastAPI application."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_status_endpoint(client: AsyncClient):
    response = await client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["version"] is not None
    assert isinstance(data["data"]["version"], str)
    assert data["data"]["system_name"] == "UniAPI"
    # Registration/security flags should be booleans matching seed values
    assert data["data"]["register_enabled"] is True
    assert data["data"]["password_login_enabled"] is True
    assert data["data"]["password_register_enabled"] is True
    assert data["data"]["email_verification_enabled"] is False
    assert data["data"]["turnstile_check"] is False
    assert isinstance(data["data"]["turnstile_site_key"], str)
    assert data["data"]["github_oauth"] is False
    assert isinstance(data["data"]["github_client_id"], str)
    assert isinstance(data["data"]["theme"], str)
    assert isinstance(data["data"]["quota_per_unit"], int)


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    register_resp = await client.post(
        "/api/user/register",
        json={"username": "testuser", "password": "Testpass123"},
    )
    assert register_resp.status_code == 200
    data = register_resp.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"

    # Login
    login_resp = await client.post(
        "/api/user/login",
        json={"username": "testuser", "password": "Testpass123"},
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
    # Models display returns configured channels; test DB has none
    assert isinstance(data["data"], dict)


@pytest.mark.asyncio
async def test_models_display_groups_by_channel_type(client: AsyncClient):
    """Channels of the same provider type should be merged into one display entry."""
    from app.database import async_session_factory
    from app.models.channel import Channel
    import time

    now_s = int(time.time())
    now_ms = now_s * 1000

    async with async_session_factory() as db:
        # Create two channels of type 27 (MiniMax) with same name
        ch1 = Channel(
            id=100, type=27, name="MiniMax", key="sk-mm-e2e-1",
            status=1, group="default", weight=1,
            models="MiniMax-M3",
            created_time=now_s, created_at=now_ms, updated_at=now_ms,
        )
        ch2 = Channel(
            id=101, type=27, name="MiniMax", key="sk-mm-e2e-2",
            status=1, group="default", weight=1,
            models="MiniMax-M3",
            created_time=now_s, created_at=now_ms, updated_at=now_ms,
        )
        # Create one channel of type 39 (DeepSeek) — different type
        ch3 = Channel(
            id=102, type=39, name="DeepSeek", key="sk-ds-e2e-1",
            status=1, group="default", weight=1,
            models="deepseek-v4-flash",
            created_time=now_s, created_at=now_ms, updated_at=now_ms,
        )
        db.add_all([ch1, ch2, ch3])
        await db.commit()

    response = await client.get("/api/models/display")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    display = data["data"]

    # Should have 2 entries (one per type), not 3 (one per channel)
    assert len(display) == 2, f"Expected 2 type groups, got {len(display)}: {list(display.keys())}"

    # Both MiniMax channels should be merged into one entry
    minimax_entries = [k for k in display if "MiniMax" in k]
    assert len(minimax_entries) == 1, f"Expected 1 MiniMax entry, got {len(minimax_entries)}: {minimax_entries}"


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


@pytest.mark.asyncio
async def test_update_token_with_expired_time(client: AsyncClient):
    """Token update should accept expired_time as string (frontend sends '-1')."""
    from app.database import async_session_factory
    from app.models.token import Token

    # Create a token directly
    async with async_session_factory() as db:
        token = Token(name="update-test", key="sk-update-test-key", user_id=1, status=1, created_time=1000)
        db.add(token)
        await db.commit()
        token_id = token.id

    # Login
    login_resp = await client.post(
        "/api/user/login",
        json={"username": "root", "password": "123456"},
    )
    assert login_resp.status_code == 200

    # Update with all fields the frontend sends (expired_time as string)
    update_resp = await client.put(
        "/api/token/",
        json={
            "id": token_id,
            "name": "updated-name",
            "expired_time": "-1",
            "models": "",
            "subnet": "",
            "status": 1,
        },
        cookies=login_resp.cookies,
    )
    assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
    data = update_resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "updated-name"
    assert data["data"]["status"] == 1
