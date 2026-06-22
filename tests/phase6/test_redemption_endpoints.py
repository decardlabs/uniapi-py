"""Full HTTP integration tests for /api/redemption/ endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def _login_admin(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


class TestRedemptionEndpoints:
    @pytest.mark.asyncio
    async def test_create_redemption_code(self, client: AsyncClient):
        cookies = await _login_admin(client)
        resp = await client.post(
            "/api/redemption/",
            json={"name": "test-code", "quota": 500000, "count": 1},
            cookies=cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] > 0
        assert len(data["data"]["code"]) >= 8

    @pytest.mark.asyncio
    async def test_list_redemption_codes(self, client: AsyncClient):
        cookies = await _login_admin(client)
        resp = await client.get("/api/redemption/?p=0&size=10", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_get_redemption_code_by_id(self, client: AsyncClient):
        cookies = await _login_admin(client)
        create = await client.post(
            "/api/redemption/", json={"name": "get-test", "quota": 100000, "count": 1},
            cookies=cookies,
        )
        code_id = create.json()["data"]["id"]

        resp = await client.get(f"/api/redemption/{code_id}", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == code_id

    @pytest.mark.asyncio
    async def test_update_redemption_code(self, client: AsyncClient):
        cookies = await _login_admin(client)
        create = await client.post(
            "/api/redemption/", json={"name": "update-test", "quota": 100000, "count": 1},
            cookies=cookies,
        )
        code_id = create.json()["data"]["id"]

        resp = await client.put(
            "/api/redemption/",
            json={"id": code_id, "name": "updated-name", "quota": 200000},
            cookies=cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        get_resp = await client.get(f"/api/redemption/{code_id}", cookies=cookies)
        assert get_resp.json()["data"]["name"] == "updated-name"

    @pytest.mark.asyncio
    async def test_delete_redemption_code(self, client: AsyncClient):
        cookies = await _login_admin(client)
        create = await client.post(
            "/api/redemption/", json={"name": "delete-test", "quota": 100000, "count": 1},
            cookies=cookies,
        )
        code_id = create.json()["data"]["id"]

        resp = await client.delete(f"/api/redemption/{code_id}", cookies=cookies)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        get_resp = await client.get(f"/api/redemption/{code_id}", cookies=cookies)
        assert get_resp.json()["success"] is False  # not found

    @pytest.mark.asyncio
    async def test_search_redemption_codes(self, client: AsyncClient):
        cookies = await _login_admin(client)
        await client.post(
            "/api/redemption/", json={"name": "searchable-promo", "quota": 100000, "count": 2},
            cookies=cookies,
        )

        resp = await client.get("/api/redemption/search?keyword=searchable", cookies=cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]) >= 2
