"""Tests for Channel CRUD API."""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_list_channels(client: AsyncClient):
    """GET /api/channel/ should return paginated channel list."""
    cookies = await _login(client)
    resp = await client.get("/api/channel/?p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data.get("data"), list)
    assert isinstance(data.get("total"), int)


@pytest.mark.asyncio
async def test_create_channel(client: AsyncClient):
    """POST /api/channel/ should create a new channel."""
    cookies = await _login(client)
    resp = await client.post("/api/channel/", json={
        "name": "Test DeepSeek",
        "type": 39,
        "key": "sk-test-key",
        "base_url": "https://api.deepseek.com/v1",
        "models": "deepseek-v4-pro,deepseek-v4-flash",
        "group": "default",
    }, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Test DeepSeek"
    assert data["data"]["id"] > 0


@pytest.mark.asyncio
async def test_get_channel(client: AsyncClient):
    """GET /api/channel/{id} should return a single channel."""
    cookies = await _login(client)
    # Create first
    create = await client.post("/api/channel/", json={
        "name": "Get Test", "type": 39, "key": "sk-key",
    }, cookies=cookies)
    cid = create.json()["data"]["id"]

    resp = await client.get(f"/api/channel/{cid}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "Get Test"
    assert data["data"]["id"] == cid


@pytest.mark.asyncio
async def test_update_channel(client: AsyncClient):
    """PUT /api/channel/ should update channel fields."""
    cookies = await _login(client)
    create = await client.post("/api/channel/", json={
        "name": "Update Test", "type": 39, "key": "sk-old",
    }, cookies=cookies)
    cid = create.json()["data"]["id"]

    resp = await client.put("/api/channel/", json={
        "id": cid, "name": "Updated Name", "key": "sk-new",
    }, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_channel_status(client: AsyncClient):
    """PUT /api/channel/?status_only=1 should toggle channel status."""
    cookies = await _login(client)
    create = await client.post("/api/channel/", json={
        "name": "Status Test", "type": 39, "key": "sk-key",
    }, cookies=cookies)
    cid = create.json()["data"]["id"]

    # Disable
    resp = await client.put("/api/channel/?status_only=1", json={
        "id": cid, "status": 2,
    }, cookies=cookies)
    assert resp.status_code == 200

    # Verify
    get = await client.get(f"/api/channel/{cid}", cookies=cookies)
    assert get.json()["data"]["status"] == 2


@pytest.mark.asyncio
async def test_delete_channel(client: AsyncClient):
    """DELETE /api/channel/{id} should delete a channel."""
    cookies = await _login(client)
    create = await client.post("/api/channel/", json={
        "name": "Delete Test", "type": 39, "key": "sk-key",
    }, cookies=cookies)
    cid = create.json()["data"]["id"]

    resp = await client.delete(f"/api/channel/{cid}", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify deleted
    get = await client.get(f"/api/channel/{cid}", cookies=cookies)
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_search_channels(client: AsyncClient):
    """GET /api/channel/search should find channels by keyword."""
    cookies = await _login(client)
    await client.post("/api/channel/", json={
        "name": "Alpha Search Me", "type": 39, "key": "sk-a",
    }, cookies=cookies)
    await client.post("/api/channel/", json={
        "name": "Beta Other", "type": 41, "key": "sk-b",
    }, cookies=cookies)

    resp = await client.get("/api/channel/search?keyword=Search&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1
    assert "Search" in data["data"][0]["name"]


@pytest.mark.asyncio
async def test_channel_requires_auth(client: AsyncClient):
    """Unauthenticated requests should be rejected."""
    resp = await client.get("/api/channel/?p=0&size=10")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_test_channel_endpoint(client: AsyncClient):
    """GET /api/channel/test/{id} should return a result (may be an error)."""
    cookies = await _login(client)
    create = await client.post("/api/channel/", json={
        "name": "Test Conn", "type": 39, "key": "sk-test",
        "base_url": "https://api.deepseek.com/v1",
    }, cookies=cookies)
    cid = create.json()["data"]["id"]

    resp = await client.get(f"/api/channel/test/{cid}", cookies=cookies)
    # Should return 200 even if the test fails (the test result is in the body)
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_test_channel_uses_adaptor_headers(client: AsyncClient, monkeypatch):
    """GET /api/channel/test/{id} should use adaptor-specific auth headers."""
    cookies = await _login(client)
    create = await client.post("/api/channel/", json={
        "name": "Test GLM Conn",
        "type": 41,
        "key": "test-id.test-secret",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    }, cookies=cookies)
    cid = create.json()["data"]["id"]

    captured = {"headers": {}}

    class _FakeResponse:
        status_code = 200
        is_success = True
        text = "ok"

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None):
            captured["headers"] = headers or {}
            return _FakeResponse()

    import app.routers.api.channel as channel_module

    monkeypatch.setattr(channel_module.httpx, "AsyncClient", _FakeAsyncClient)

    resp = await client.get(f"/api/channel/test/{cid}", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert captured["headers"]["Authorization"].startswith("eyJ")
