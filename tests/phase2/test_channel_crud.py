"""Tests for Channel CRUD API."""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


def test_mask_api_key():
    """API keys returned to the frontend must be masked (partial)."""
    from app.routers.api.channel import _mask_key

    full_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890abcdefgh"
    masked = _mask_key(full_key)
    assert masked != full_key, "Key must be masked"
    assert masked.startswith("sk-abc"), "Should show first 7 chars"
    assert masked.endswith("fgh"), "Should show last 3 chars"
    assert "..." in masked, "Should have ellipsis"


@pytest.mark.asyncio
async def test_channel_sort_injection_safe(client: AsyncClient):
    """Invalid sort parameter should fallback to default sort."""
    cookies = await _login(client)
    resp = await client.get("/api/channel/?sort=__class__", cookies=cookies)
    assert resp.status_code == 200  # Should not crash
    resp = await client.get("/api/channel/?sort=nonexistent", cookies=cookies)
    assert resp.status_code == 200  # Should fallback gracefully


def test_mask_api_key_short():
    """Short keys should not be masked (likely already truncated or test keys)."""
    from app.routers.api.channel import _mask_key

    short_key = "sk-test"
    assert _mask_key(short_key) == short_key, "Short keys unchanged"


def test_mask_api_key_empty():
    """Empty keys should stay empty."""
    from app.routers.api.channel import _mask_key

    assert _mask_key("") == ""
    assert _mask_key(None) is None


@pytest.mark.asyncio
async def test_channel_list_masks_keys(client: AsyncClient):
    """GET /api/channel/ should return masked API keys."""
    cookies = await _login(client)
    # First create a channel so we have data
    await client.post("/api/channel/", json={
        "name": "KeyMask Test",
        "type": 39,
        "key": "sk-test-key-masked-1234567890",
        "models": "deepseek-v4-flash",
        "group": "default",
    }, cookies=cookies)

    resp = await client.get("/api/channel/?p=0&size=100", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    channels = data.get("data", [])
    for ch in channels:
        if ch.get("key"):
            # The returned key should be masked (not the full value we sent)
            assert "sk-test-key" not in ch["key"], "Key should be masked"
            assert "..." in ch["key"] or len(ch["key"]) < 20, (
                f"Key should be masked or truncated: {ch['key']}"
            )



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
async def test_create_channel_with_multiple_keys(client: AsyncClient):
    """POST /api/channel/ with multiline key should create one channel per key."""
    cookies = await _login(client)
    resp = await client.post("/api/channel/", json={
        "name": "Multi-Key DeepSeek",
        "type": 39,
        "key": "sk-key-1\nsk-key-2\nsk-key-3",
        "models": "deepseek-v4-pro",
        "group": "default",
    }, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["data"]["id"] > 0

    # Verify 3 channels were created with different keys
    list_resp = await client.get("/api/channel/?p=0&size=100", cookies=cookies)
    channels = list_resp.json()["data"]
    multi_key_channels = [c for c in channels if c["name"] == "Multi-Key DeepSeek"]
    assert len(multi_key_channels) == 3
    keys = [c["key"] for c in multi_key_channels]
    assert "sk-key-1" in keys
    assert "sk-key-2" in keys
    assert "sk-key-3" in keys


@pytest.mark.asyncio
async def test_create_channel_ignores_blank_key_lines(client: AsyncClient):
    """POST /api/channel/ with blank lines in key should skip blanks."""
    cookies = await _login(client)
    resp = await client.post("/api/channel/", json={
        "name": "Blank Lines",
        "type": 39,
        "key": "sk-a\n\n\nsk-b\n  \nsk-c",
        "group": "default",
    }, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    list_resp = await client.get("/api/channel/?p=0&size=100", cookies=cookies)
    channels = list_resp.json()["data"]
    blank_channels = [c for c in channels if c["name"] == "Blank Lines"]
    assert len(blank_channels) == 3


@pytest.mark.asyncio
async def test_create_channel_single_key_unchanged(client: AsyncClient):
    """POST /api/channel/ with single-line key should behave exactly as before."""
    cookies = await _login(client)
    resp = await client.post("/api/channel/", json={
        "name": "Single Key",
        "type": 39,
        "key": "sk-only-one",
        "models": "deepseek-v4-pro",
        "group": "default",
    }, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert resp.json()["data"]["key"] == "sk-only-one"

    list_resp = await client.get("/api/channel/?p=0&size=100", cookies=cookies)
    channels = list_resp.json()["data"]
    single_channels = [c for c in channels if c["name"] == "Single Key"]
    assert len(single_channels) == 1


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
