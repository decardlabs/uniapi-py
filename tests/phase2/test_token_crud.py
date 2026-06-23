"""Phase 2b: Token CRUD - write tests first (TDD)."""

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient, username="root", password="123456") -> dict:
    resp = await client.post("/api/user/login", json={
        "username": username, "password": password,
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_token_list(client: AsyncClient):
    cookies = await _login(client)
    resp = await client.get("/api/token/?p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["data"], list)
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_token_get_by_id(client: AsyncClient):
    cookies = await _login(client)
    list_resp = await client.get("/api/token/?p=0&size=10", cookies=cookies)
    tokens = list_resp.json()["data"]
    assert len(tokens) > 0
    target_id = tokens[0]["id"]

    resp = await client.get(f"/api/token/{target_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["id"] == target_id


@pytest.mark.asyncio
async def test_token_create(client: AsyncClient):
    cookies = await _login(client)
    resp = await client.post(
        "/api/token/",
        json={"name": "test-token"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "test-token"
    assert len(data["data"]["key"]) > 20  # sk-... format


@pytest.mark.asyncio
async def test_token_create_unlimited(client: AsyncClient):
    cookies = await _login(client)
    resp = await client.post(
        "/api/token/",
        json={"name": "unlimited-token"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    

@pytest.mark.asyncio
async def test_token_create_with_models(client: AsyncClient):
    cookies = await _login(client)
    resp = await client.post(
        "/api/token/",
        json={"name": "model-token", "models": "deepseek-v4-pro,deepseek-v4-flash"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["models"] is not None
    assert "deepseek-v4-pro" in data["data"]["models"]


@pytest.mark.asyncio
async def test_token_update(client: AsyncClient):
    cookies = await _login(client)
    create_resp = await client.post(
        "/api/token/",
        json={"name": "update-me"},
        cookies=cookies,
    )
    token_id = create_resp.json()["data"]["id"]

    resp = await client.put(
        "/api/token/",
        json={"id": token_id, "name": "updated-name"},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_token_delete(client: AsyncClient):
    cookies = await _login(client)
    create_resp = await client.post(
        "/api/token/",
        json={"name": "delete-me"},
        cookies=cookies,
    )
    token_id = create_resp.json()["data"]["id"]

    resp = await client.delete(f"/api/token/{token_id}", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_token_search(client: AsyncClient):
    cookies = await _login(client)
    # Create a token with a distinctive name
    await client.post(
        "/api/token/",
        json={"name": "zebratoken_searchme"},
        cookies=cookies,
    )
    resp = await client.get(
        "/api/token/search?keyword=zebratoken", cookies=cookies
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_token_status_toggle(client: AsyncClient):
    cookies = await _login(client)
    create_resp = await client.post(
        "/api/token/",
        json={"name": "toggle-token"},
        cookies=cookies,
    )
    token_id = create_resp.json()["data"]["id"]

    resp = await client.put(
        "/api/token/",
        json={"id": token_id, "status": 2},  # Disable
        cookies=cookies,
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/token/{token_id}", cookies=cookies)
    assert get_resp.json()["data"]["status"] == 2


@pytest.mark.asyncio
async def test_token_list_pagination(client: AsyncClient):
    cookies = await _login(client)
    resp = await client.get("/api/token/?p=0&size=5", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) <= 5


@pytest.mark.asyncio
async def test_token_key_prefix(client: AsyncClient):
    cookies = await _login(client)
    resp = await client.post(
        "/api/token/",
        json={"name": "prefix-test"},
        cookies=cookies,
    )
    data = resp.json()["data"]
    assert data["key"].startswith("sk-")
