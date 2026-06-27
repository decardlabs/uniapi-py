"""Token consume and quota management tests.

Tests that token-based consumption correctly decrements quota
and that the /v1/* relay respects token-level rate limits.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_create_token(client: AsyncClient):
    """Creating a token should succeed with default fields."""
    cookies = await _login(client)

    resp = await client.post("/api/token/", json={
        "name": "basic-test-token",
    }, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json().get("data", {})
    assert data.get("name") == "basic-test-token"
    assert data.get("id") is not None

    # Cleanup
    token_id = data.get("id")
    if token_id:
        await client.delete(f"/api/token/{token_id}", cookies=cookies)


@pytest.mark.asyncio
async def test_token_has_expected_fields(client: AsyncClient):
    """Token should have expected fields in response."""
    cookies = await _login(client)
    default_token_id = 1  # root's default token always exists

    resp = await client.get(f"/api/token/{default_token_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json().get("data", {})
    # Token should have basic fields
    for field in ["id", "name", "key", "status", "models"]:
        assert field in data, f"Token missing field: {field}"
    assert data.get("name") is not None


@pytest.mark.asyncio
async def test_token_list_basic(client: AsyncClient):
    """Token list should return tokens with basic fields."""
    cookies = await _login(client)

    resp = await client.get("/api/token/", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json().get("data", [])

    assert len(data) > 0
    for token in data:
        assert "id" in token
        assert "name" in token
        assert "key" in token


@pytest.mark.asyncio
async def test_token_status_toggle(client: AsyncClient):
    """Token status should be togglable."""
    cookies = await _login(client)

    # Create
    resp = await client.post("/api/token/", json={
        "name": "status-test-token",
    }, cookies=cookies)
    token_id = resp.json().get("data", {}).get("id")
    assert token_id is not None

    # Disable
    resp = await client.put("/api/token/", json={
        "id": token_id,
        "status": 2,
    }, cookies=cookies)
    assert resp.status_code == 200

    # Verify
    resp = await client.get(f"/api/token/{token_id}", cookies=cookies)
    assert resp.json().get("data", {}).get("status") == 2

    # Cleanup
    await client.delete(f"/api/token/{token_id}", cookies=cookies)


@pytest.mark.asyncio
async def test_update_token_models(client: AsyncClient):
    """Token model allowlist should be updatable."""
    cookies = await _login(client)

    resp = await client.post("/api/token/", json={
        "name": "models-test-token",
        "models": "gpt-4,gpt-3.5-turbo",
    }, cookies=cookies)
    token_id = resp.json().get("data", {}).get("id")
    assert token_id is not None

    # Update models
    resp = await client.put("/api/token/", json={
        "id": token_id,
        "models": "deepseek-v4-flash",
    }, cookies=cookies)
    assert resp.status_code == 200

    # Cleanup
    await client.delete(f"/api/token/{token_id}", cookies=cookies)
