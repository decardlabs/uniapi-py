"""Full HTTP integration tests for /api/recharge/ and /api/topup/ endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def _login_admin(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def _login_user(client: AsyncClient) -> tuple[dict, int]:
    """Create a regular user and return cookies + user_id."""
    cookies = await _login_admin(client)
    resp = await client.post(
        "/api/user/",
        json={"username": "testuser_recharge", "password": "pass123", "quota": 0},
        cookies=cookies,
    )
    assert resp.status_code == 200
    user_id = resp.json()["data"]["id"]

    # Login as the new user
    login = await client.post("/api/user/login", json={
        "username": "testuser_recharge", "password": "pass123",
    })
    return login.cookies, user_id


class TestRechargeEndpoints:
    @pytest.mark.asyncio
    async def test_user_create_recharge(self, client: AsyncClient):
        """User can create a recharge request."""
        user_cookies, _ = await _login_user(client)
        resp = await client.post(
            "/api/recharge/",
            json={"amount": 500000, "remark": "need quota"},
            cookies=user_cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["id"] > 0

    @pytest.mark.asyncio
    async def test_admin_list_recharges(self, client: AsyncClient):
        """Admin can list all recharge requests."""
        # First create one
        user_cookies, _ = await _login_user(client)
        await client.post("/api/recharge/", json={"amount": 300000}, cookies=user_cookies)

        # Admin lists
        admin_cookies = await _login_admin(client)
        resp = await client.get("/api/recharge/?p=0&size=10", cookies=admin_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] >= 1
        assert len(data["data"]) >= 1
        assert data["data"][0]["amount"] == 300000
        assert data["data"][0]["status"] == 1  # pending

    @pytest.mark.asyncio
    async def test_user_list_self_recharges(self, client: AsyncClient):
        """User can list own recharge requests."""
        user_cookies, user_id = await _login_user(client)
        await client.post("/api/recharge/", json={"amount": 100000}, cookies=user_cookies)
        await client.post("/api/recharge/", json={"amount": 200000}, cookies=user_cookies)

        resp = await client.get("/api/recharge/self?p=0&size=10", cookies=user_cookies)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_admin_approve_recharge(self, client: AsyncClient):
        """Admin can approve a pending recharge request and user quota increases."""
        user_cookies, user_id = await _login_user(client)
        create_resp = await client.post("/api/recharge/", json={"amount": 1000000}, cookies=user_cookies)
        recharge_id = create_resp.json()["data"]["id"]

        admin_cookies = await _login_admin(client)

        # Create a budget pool (no allocation — pool is the single global pool)
        pool_resp = await client.post("/api/pool/", json={
            "name": "test pool", "total_funded": 1000.0, "period_type": "monthly", "period_key": "2026-06",
        }, cookies=admin_cookies)
        pool_id = pool_resp.json()["data"]["id"]

        resp = await client.post(
            f"/api/recharge/{recharge_id}/approve",
            json={"pool_id": pool_id},
            cookies=admin_cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify user quota increased
        self_resp = await client.get("/api/user/self", cookies=user_cookies)
        assert self_resp.json()["data"]["balance"] >= 1000000

    @pytest.mark.asyncio
    async def test_admin_reject_recharge(self, client: AsyncClient):
        """Admin can reject a recharge request with a reason."""
        user_cookies, _ = await _login_user(client)
        create_resp = await client.post("/api/recharge/", json={"amount": 500000}, cookies=user_cookies)
        recharge_id = create_resp.json()["data"]["id"]

        admin_cookies = await _login_admin(client)
        resp = await client.post(
            f"/api/recharge/{recharge_id}/reject",
            json={"admin_remark": "Insufficient documentation"},
            cookies=admin_cookies,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Check request shows rejected
        list_resp = await client.get("/api/recharge/?p=0&size=10", cookies=admin_cookies)
        reqs = list_resp.json()["data"]
        target = next(r for r in reqs if r["id"] == recharge_id)
        assert target["status"] == 3
        assert target["admin_remark"] == "Insufficient documentation"

    @pytest.mark.asyncio
    async def test_admin_direct_topup(self, client: AsyncClient):
        """Admin can directly top-up a user's quota via POST /api/topup/."""
        user_cookies, user_id = await _login_user(client)
        admin_cookies = await _login_admin(client)

        # Ensure an active pool exists (admin_topup auto-finds it)
        await client.post("/api/pool/", json={
            "name": "topup pool", "total_funded": 1000.0, "period_type": "monthly", "period_key": "2026-06",
        }, cookies=admin_cookies)

        resp = await client.post(
            "/api/topup/",
            json={"user_id": user_id, "amount": 2.0, "remark": "bonus"},
            cookies=admin_cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify user balance increased (2 yuan = 2,000,000 micro-yuan)
        self_resp = await client.get("/api/user/self", cookies=user_cookies)
        assert self_resp.json()["data"]["balance"] >= 2000000
