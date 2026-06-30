"""Tests for MCP Server management API (CRUD + sync/test actions)."""

import pytest
from httpx import AsyncClient

BASE = "/api/mcp_servers"


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
async def cookies(client: AsyncClient):
    return await _login(client)


@pytest.fixture
async def created_server_id(client: AsyncClient, cookies: dict) -> int:
    """Create a minimal MCP server and return its id."""
    resp = await client.post(BASE + "/", json={
        "name": "Test MCP Server",
        "base_url": "https://mcp-test.example.com",
        "protocol": "streamable_http",
        "auth_type": "none",
        "status": 1,
    }, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    return data["data"]["id"]


# ── CRUD ─────────────────────────────────────────────────────────────────

class TestCreate:
    async def _create(self, client, cookies, **overrides):
        payload = {
            "name": "My MCP Server",
            "base_url": "https://mcp.example.com",
            "protocol": "streamable_http",
            "auth_type": "none",
            "status": 1,
            "priority": 0,
            "auto_sync_enabled": True,
            "auto_sync_interval_minutes": 60,
        }
        payload.update(overrides)
        return await client.post(BASE + "/", json=payload, cookies=cookies)

    @pytest.mark.asyncio
    async def test_basic_create(self, client: AsyncClient, cookies: dict):
        resp = await self._create(client, cookies)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_create_with_json_fields(self, client: AsyncClient, cookies: dict):
        resp = await self._create(client, cookies,
            headers={"Authorization": "Bearer test"},
            tool_whitelist=["get_weather", "search"],
            tool_blacklist=["admin_delete"],
            tool_pricing={"get_weather": 0.001},
        )
        assert resp.status_code == 200
        sid = resp.json()["data"]["id"]

        # Verify JSON fields round-trip
        get_resp = await client.get(f"{BASE}/{sid}", cookies=cookies)
        assert get_resp.status_code == 200
        srv = get_resp.json()["data"]
        assert srv["headers"] == {"Authorization": "Bearer test"}
        assert "get_weather" in srv["tool_whitelist"]

    @pytest.mark.asyncio
    async def test_create_rejects_extra_fields(self, client, cookies):
        """MCP create should reject unexpected fields."""
        resp = await client.post(BASE + "/", json={
            "name": "valid-server",
            "injected_field": "malicious",
        }, cookies=cookies)
        assert resp.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_with_auth(self, client: AsyncClient, cookies: dict):
        resp = await self._create(client, cookies,
            auth_type="bearer",
            api_key="sk-test-key-12345",
        )
        assert resp.status_code == 200
        sid = resp.json()["data"]["id"]
        get_resp = await client.get(f"{BASE}/{sid}", cookies=cookies)
        assert get_resp.json()["data"]["api_key"] == "sk-test-key-12345"


class TestRead:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient, cookies: dict):
        resp = await client.get(f"{BASE}/?p=0&size=10", cookies=cookies)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "total" in body

    @pytest.mark.asyncio
    async def test_list_after_create(self, client: AsyncClient, cookies: dict, created_server_id: int):
        resp = await client.get(f"{BASE}/?p=0&size=10", cookies=cookies)
        assert resp.status_code == 200
        body = resp.json()
        ids = [item["server"]["id"] for item in body["data"]]
        assert created_server_id in ids

    @pytest.mark.asyncio
    async def test_get_detail(self, client: AsyncClient, cookies: dict, created_server_id: int):
        resp = await client.get(f"{BASE}/{created_server_id}", cookies=cookies)
        assert resp.status_code == 200
        srv = resp.json()["data"]
        assert srv["id"] == created_server_id
        assert srv["name"] == "Test MCP Server"
        assert srv["base_url"] == "https://mcp-test.example.com"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient, cookies: dict):
        resp = await client.get(f"{BASE}/99999", cookies=cookies)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_pagination(self, client: AsyncClient, cookies: dict, created_server_id: int):
        # Small page that should include our item
        resp = await client.get(f"{BASE}/?p=0&size=5", cookies=cookies)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 5


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_name_and_priority(self, client: AsyncClient, cookies: dict, created_server_id: int):
        sid = created_server_id
        resp = await client.put(f"{BASE}/{sid}", json={
            "name": "Updated MCP",
            "priority": 5,
        }, cookies=cookies)
        assert resp.status_code == 200

        get_resp = await client.get(f"{BASE}/{sid}", cookies=cookies)
        srv = get_resp.json()["data"]
        assert srv["name"] == "Updated MCP"
        assert srv["priority"] == 5

    @pytest.mark.asyncio
    async def test_update_json_fields(self, client: AsyncClient, cookies: dict, created_server_id: int):
        sid = created_server_id
        resp = await client.put(f"{BASE}/{sid}", json={
            "tool_whitelist": ["tool_a", "tool_b"],
            "headers": {"X-Custom": "value"},
        }, cookies=cookies)
        assert resp.status_code == 200

        get_resp = await client.get(f"{BASE}/{sid}", cookies=cookies)
        srv = get_resp.json()["data"]
        assert "tool_a" in srv["tool_whitelist"]
        assert srv["headers"]["X-Custom"] == "value"

    @pytest.mark.asyncio
    async def test_update_toggle_auto_sync(self, client: AsyncClient, cookies: dict, created_server_id: int):
        sid = created_server_id
        resp = await client.put(f"{BASE}/{sid}", json={"auto_sync_enabled": False}, cookies=cookies)
        assert resp.status_code == 200

        get_resp = await client.get(f"{BASE}/{sid}", cookies=cookies)
        assert get_resp.json()["data"]["auto_sync_enabled"] == 0

    @pytest.mark.asyncio
    async def test_update_rejects_extra_fields(self, client, cookies, created_server_id):
        """MCP update should reject unexpected fields."""
        resp = await client.put(f"{BASE}/{created_server_id}", json={
            "name": "still-valid",
            "injected_field": "malicious",
        }, cookies=cookies)
        assert resp.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient, cookies: dict):
        resp = await client.put(f"{BASE}/99999", json={"name": "Nope"}, cookies=cookies)
        assert resp.status_code == 404


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete(self, client: AsyncClient, cookies: dict, created_server_id: int):
        sid = created_server_id
        resp = await client.delete(f"{BASE}/{sid}", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted"] is True

        # Verify deletion
        get_resp = await client.get(f"{BASE}/{sid}", cookies=cookies)
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient, cookies: dict):
        resp = await client.delete(f"{BASE}/99999", cookies=cookies)
        assert resp.status_code == 404


# ── Actions (sync / test / tools) ────────────────────────────────────────

class TestActions:
    @pytest.mark.asyncio
    async def test_sync(self, client: AsyncClient, cookies: dict, created_server_id: int):
        resp = await client.post(f"{BASE}/{created_server_id}/sync", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["data"]["synced"] is True

    @pytest.mark.asyncio
    async def test_test(self, client: AsyncClient, cookies: dict, created_server_id: int):
        resp = await client.post(f"{BASE}/{created_server_id}/test", cookies=cookies)
        assert resp.status_code == 200
        assert "tool_count" in resp.json()["data"]

    @pytest.mark.asyncio
    async def test_list_tools(self, client: AsyncClient, cookies: dict, created_server_id: int):
        resp = await client.get(f"{BASE}/{created_server_id}/tools", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_actions_not_found(self, client: AsyncClient, cookies: dict):
        resp = await client.post(f"{BASE}/99999/sync", cookies=cookies)
        assert resp.status_code == 404


# ── Auth guard ───────────────────────────────────────────────────────────

class TestAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_create_returns_401(self, client: AsyncClient):
        resp = await client.post(BASE + "/", json={"name": "x", "base_url": "http://x"})
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_unauthenticated_list_returns_401(self, client: AsyncClient):
        resp = await client.get(f"{BASE}/")
        assert resp.status_code in (401, 403)
