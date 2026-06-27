"""Tests for admin budget management API."""
import time

import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


async def _create_extra_user(client: AsyncClient, cookies: dict, username: str):
    """Create a non-root user for testing."""
    resp = await client.post(
        "/api/user/",
        json={"username": username, "password": "test123", "quota": 1000000},
        cookies=cookies,
    )
    return resp.json().get("data", {})


@pytest.mark.asyncio
async def test_admin_list_budgets(client: AsyncClient):
    """GET /api/v1/admin/budgets should return paginated budget list."""
    cookies = await _login(client)
    resp = await client.get("/api/v1/admin/budgets?p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data.get("data"), list)
    assert isinstance(data.get("total"), int)


@pytest.mark.asyncio
async def test_admin_list_budgets_requires_admin(client: AsyncClient):
    """Regular user should not access admin budgets."""
    # Register a regular user
    reg = await client.post("/api/user/register", json={
        "username": "reg_budget_user", "password": "pass123",
    })
    reg_cookies = reg.cookies
    resp = await client.get("/api/v1/admin/budgets?p=0&size=10", cookies=reg_cookies)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_budget_stats(client: AsyncClient):
    """GET /api/v1/admin/budgets/stats should return aggregate info."""
    cookies = await _login(client)
    resp = await client.get("/api/v1/admin/budgets/stats", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "total_budgets" in data["data"]
    assert "total_monthly" in data["data"]
    assert "top_spenders" in data["data"]


@pytest.mark.asyncio
async def test_admin_update_budget(client: AsyncClient):
    """PUT /api/v1/admin/budgets/{user_id} should update monthly_budget."""
    from app.database import async_session_factory
    from app.models.budget import Budget

    cookies = await _login(client)
    # Create a budget record directly in DB
    async with async_session_factory() as db:
        now = int(time.time() * 1000)
        budget = Budget(user_id=1, monthly_budget=800.0, consumed=0.0, frozen=0.0,
                         budget_period="2026-06", created_at=now, updated_at=now)
        db.add(budget)
        await db.commit()

    # Update root's budget
    resp = await client.put("/api/v1/admin/budgets/1",
        json={"monthly_budget": 2000.0},
        cookies=cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["monthly_budget"] == 2000.0


@pytest.mark.asyncio
async def test_admin_reset_budget(client: AsyncClient):
    """POST /api/v1/admin/budgets/reset/{user_id} should reset consumed/frozen."""
    from app.database import async_session_factory
    from app.models.budget import Budget

    cookies = await _login(client)
    # Create a budget record with consumed > 0
    async with async_session_factory() as db:
        now = int(time.time() * 1000)
        budget = Budget(user_id=1, monthly_budget=800.0, consumed=100.0, frozen=0.0,
                         budget_period="2026-06", created_at=now, updated_at=now)
        db.add(budget)
        await db.commit()

    resp = await client.post("/api/v1/admin/budgets/reset/1", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "previous_consumed" in data["data"]
