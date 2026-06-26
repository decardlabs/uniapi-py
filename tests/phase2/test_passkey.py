"""Tests for Passkey (WebAuthn) endpoints.

Mocks the webauthn cryptographic layer so tests run offline.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.fixture
async def cookies(client: AsyncClient):
    return await _login(client)


MOCK_REG_OPTS = {
    "rp": {"name": "UniAPI", "id": "localhost"},
    "user": {"id": "1", "name": "root", "displayName": "Root"},
    "challenge": "mock-challenge-bytes",
    "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
    "timeout": 60000,
}

MOCK_AUTH_OPTS = {
    "challenge": "mock-auth-challenge",
    "timeout": 60000,
    "rpId": "localhost",
    "allowCredentials": [],
}

MOCK_VERIFY_RESULT = {
    "credential_id": "mock-credential-id-abc123",
    "public_key": b'\x04\x00\x01\x02\x03\x04\x05\x06',
    "sign_count": 1,
}


# ---------------------------------------------------------------------------
# Registration flow
# ---------------------------------------------------------------------------

class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_begin(self, client: AsyncClient, cookies: dict):
        with patch("app.routers.api.passkey.generate_registration_opts", return_value=MOCK_REG_OPTS):
            resp = await client.post("/api/user/passkey/register/begin", cookies=cookies)
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert "publicKey" in data
            assert data["publicKey"]["rp"]["name"] == "UniAPI"

    @pytest.mark.asyncio
    async def test_register_finish_missing_body(self, client: AsyncClient, cookies: dict):
        resp = await client.post("/api/user/passkey/register/finish?name=TestKey", json={}, cookies=cookies)
        # Without proper credential body, verify_registration returns None
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_register_finish_success(self, client: AsyncClient, cookies: dict):
        with patch("app.routers.api.passkey.verify_registration", return_value=MOCK_VERIFY_RESULT):
            resp = await client.post(
                "/api/user/passkey/register/finish?name=TestKey",
                json={"id": "mock-cred", "response": {"transports": ["internal"]}},
                cookies=cookies,
            )
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_register_duplicate_credential(self, client: AsyncClient, cookies: dict):
        """Registering the same credential_id twice should be rejected."""
        with patch("app.routers.api.passkey.verify_registration", return_value=MOCK_VERIFY_RESULT):
            # First registration
            await client.post(
                "/api/user/passkey/register/finish?name=Key1",
                json={"id": "mock-cred", "response": {"transports": ["internal"]}},
                cookies=cookies,
            )
            # Second registration with same credential_id
            resp = await client.post(
                "/api/user/passkey/register/finish?name=Key2",
                json={"id": "mock-cred", "response": {"transports": ["internal"]}},
                cookies=cookies,
            )
            assert resp.status_code == 200
            # Should be rejected as duplicate
            assert resp.json()["success"] is False


# ---------------------------------------------------------------------------
# List and Delete
# ---------------------------------------------------------------------------

class TestManagement:
    @pytest.mark.asyncio
    async def test_list_passkeys(self, client: AsyncClient, cookies: dict):
        resp = await client.get("/api/user/passkey", cookies=cookies)
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)

    @pytest.mark.asyncio
    async def test_list_after_registration(self, client: AsyncClient, cookies: dict):
        with patch("app.routers.api.passkey.verify_registration", return_value=MOCK_VERIFY_RESULT):
            await client.post(
                "/api/user/passkey/register/finish?name=MyKey",
                json={"id": "mock-cred", "response": {"transports": []}},
                cookies=cookies,
            )

        resp = await client.get("/api/user/passkey", cookies=cookies)
        data = resp.json()["data"]
        assert len(data) >= 1
        assert any(c["credential_name"] == "MyKey" for c in data)

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, client: AsyncClient, cookies: dict):
        resp = await client.delete("/api/user/passkey/99999", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_delete_passkey(self, client: AsyncClient, cookies: dict):
        with patch("app.routers.api.passkey.verify_registration", return_value=MOCK_VERIFY_RESULT):
            await client.post(
                "/api/user/passkey/register/finish?name=ToDelete",
                json={"id": "mock-cred", "response": {"transports": []}},
                cookies=cookies,
            )

        # Find the passkey ID
        list_resp = await client.get("/api/user/passkey", cookies=cookies)
        keys = list_resp.json()["data"]
        to_delete = next(k for k in keys if k["credential_name"] == "ToDelete")

        resp = await client.delete(f"/api/user/passkey/{to_delete['id']}", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify gone
        list_resp2 = await client.get("/api/user/passkey", cookies=cookies)
        remaining = list_resp2.json()["data"]
        assert all(k["id"] != to_delete["id"] for k in remaining)


# ---------------------------------------------------------------------------
# Authentication (login) flow
# ---------------------------------------------------------------------------

class TestAuthentication:
    @pytest.mark.asyncio
    async def test_login_begin(self, client: AsyncClient):
        with patch("app.routers.api.passkey.generate_authentication_opts", return_value=MOCK_AUTH_OPTS):
            resp = await client.post("/api/user/passkey/login/begin")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert "publicKey" in data

    @pytest.mark.asyncio
    async def test_login_finish_missing_id(self, client: AsyncClient):
        resp = await client.post("/api/user/passkey/login/finish", json={})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_login_finish_nonexistent_credential(self, client: AsyncClient):
        resp = await client.post(
            "/api/user/passkey/login/finish",
            json={"id": "nonexistent-credential-id"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is False


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuth:
    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/user/passkey")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_register_begin_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/user/passkey/register/begin")
        assert resp.status_code in (401, 403)
