"""Turnstile verification integration tests.

Tests that Turnstile check can be toggled and that the login/register
endpoints reject requests when Turnstile is enabled but the token is missing.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _set_option(client: AsyncClient, cookies: dict, key: str, value: str):
    """Helper to set a system option."""
    resp = await client.put("/api/option/", json={"key": key, "value": value}, cookies=cookies)
    return resp


async def _login_root(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_turnstile_disabled_login_succeeds(client: AsyncClient):
    """When Turnstile is disabled, login should succeed without a token."""
    # Ensure Turnstile is disabled
    admin_cookies = await _login_root(client)
    await _set_option(client, admin_cookies, "TurnstileCheckEnabled", "false")

    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True


@pytest.mark.asyncio
async def test_turnstile_enabled_register_rejected(client: AsyncClient):
    """When Turnstile is enabled, registration without token should fail."""
    admin_cookies = await _login_root(client)

    # Enable Turnstile and set site key
    await _set_option(client, admin_cookies, "TurnstileCheckEnabled", "true")
    await _set_option(client, admin_cookies, "TurnstileSiteKey", "1x00000000000000000000AA")

    # Register without Turnstile token
    import random
    uname = f"ts_user_{random.randint(10000, 99999)}"
    resp = await client.post("/api/user/register", json={
        "username": uname, "password": "TestPass123",
    })
    # Should fail because Turnstile verification endpoint doesn't exist in test env
    assert resp.status_code in (200, 400, 422, 500)
    data = resp.json()
    # At minimum, success should not be True
    if data.get("success") is True:
        # If it somehow succeeded, that's a bug
        pytest.fail("Registration succeeded without Turnstile token!")

    # Restore
    await _set_option(client, admin_cookies, "TurnstileCheckEnabled", "false")


@pytest.mark.asyncio
async def test_turnstile_toggle(client: AsyncClient):
    """Toggling Turnstile should not break the option endpoint itself."""
    admin_cookies = await _login_root(client)

    # Toggle on
    resp_on = await _set_option(client, admin_cookies, "TurnstileCheckEnabled", "true")
    assert resp_on.status_code == 200

    # Verify the option was set
    resp_check = await client.get("/api/option/", cookies=admin_cookies)
    options = resp_check.json().get("data", [])
    ts_setting = next(
        (o for o in options if o.get("key") == "TurnstileCheckEnabled"),
        None,
    )
    assert ts_setting is not None
    assert ts_setting.get("value") == "true"

    # Toggle off
    resp_off = await _set_option(client, admin_cookies, "TurnstileCheckEnabled", "false")
    assert resp_off.status_code == 200
