"""Tests for Budget Pool API endpoints."""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


@pytest.mark.asyncio
async def test_list_pools_empty(client: AsyncClient):
    """GET /api/pool/ should return empty list initially."""
    cookies = await _login(client)
    resp = await client.get("/api/pool/?p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data.get("data"), list)
    assert isinstance(data.get("total"), int)


@pytest.mark.asyncio
async def test_create_pool(client: AsyncClient):
    """POST /api/pool/ should create a pool."""
    cookies = await _login(client)
    resp = await client.post("/api/pool/", json={
        "name": "June 2026 Pool",
        "total_funded": 5000.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "June 2026 Pool"
    assert data["data"]["total_funded"] == 5000.0
    assert data["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_create_pool_requires_admin(client: AsyncClient):
    """Regular user should not be able to create pools."""
    reg = await client.post("/api/user/register", json={
        "username": "reg_pool_user", "password": "pass123",
    })
    resp = await client.post("/api/pool/", json={
        "name": "Test", "total_funded": 100, "period_key": "2026-06",
    }, cookies=reg.cookies)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_fund_pool(client: AsyncClient):
    """POST /api/pool/{id}/fund should add funds."""
    cookies = await _login(client)

    # Create pool
    create_resp = await client.post("/api/pool/", json={
        "name": "Fund Test Pool",
        "total_funded": 1000.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    pool_id = create_resp.json()["data"]["id"]

    # Fund more
    resp = await client.post(f"/api/pool/{pool_id}/fund", json={
        "amount": 500.0, "remark": "Additional fund",
    }, cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["data"]["total_funded"] == 1500.0


@pytest.mark.asyncio
async def test_allocate_and_recall_flow(client: AsyncClient):
    """Allocate then recall should update pool totals and user budget."""
    cookies = await _login(client)

    # Create pool
    create_resp = await client.post("/api/pool/", json={
        "name": "Alloc Test Pool",
        "total_funded": 2000.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    pool_id = create_resp.json()["data"]["id"]

    # Allocate to root (user_id=1)
    alloc_resp = await client.post(f"/api/pool/{pool_id}/allocate", json={
        "user_id": 1, "amount": 500.0,
    }, cookies=cookies)
    assert alloc_resp.status_code == 200
    alloc_data = alloc_resp.json()["data"]
    assert alloc_data["amount"] == 500.0
    assert alloc_data["user_id"] == 1

    # Check pool totals
    pool_resp = await client.get(f"/api/pool/{pool_id}", cookies=cookies)
    assert pool_resp.json()["data"]["total_allocated"] >= 499.99

    # Check user budget increased (query DB directly; budget_arbiter not in test env)
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.budget import Budget
    async with async_session_factory() as db:
        result = await db.execute(select(Budget).where(Budget.user_id == 1))
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.monthly_budget >= 500.0

    # Recall 200 from user
    recall_resp = await client.post(f"/api/pool/{pool_id}/recall", json={
        "user_id": 1, "amount": 200.0, "remark": "Test recall",
    }, cookies=cookies)
    assert recall_resp.status_code == 200

    # Check reconciliation
    recon_resp = await client.get(f"/api/pool/{pool_id}/reconciliation", cookies=cookies)
    assert recon_resp.status_code == 200


@pytest.mark.asyncio
async def test_allocate_over_balance_rejected(client: AsyncClient):
    """Allocating more than pool's available balance should be rejected."""
    cookies = await _login(client)

    create_resp = await client.post("/api/pool/", json={
        "name": "Over Alloc Test",
        "total_funded": 100.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    pool_id = create_resp.json()["data"]["id"]

    resp = await client.post(f"/api/pool/{pool_id}/allocate", json={
        "user_id": 1, "amount": 99999.0,
    }, cookies=cookies)
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_close_pool(client: AsyncClient):
    """Close pool should set status to closed."""
    cookies = await _login(client)

    create_resp = await client.post("/api/pool/", json={
        "name": "Close Test",
        "total_funded": 100.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    pool_id = create_resp.json()["data"]["id"]

    resp = await client.post(f"/api/pool/{pool_id}/close", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "closed"


@pytest.mark.asyncio
async def test_list_pools_with_filter(client: AsyncClient):
    """GET /api/pool/ should support status and period_type filters."""
    cookies = await _login(client)

    # Create a pool
    await client.post("/api/pool/", json={
        "name": "Filter Test",
        "total_funded": 100.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)

    # Filter by type
    resp = await client.get("/api/pool/?period_type=monthly&p=0&size=10", cookies=cookies)
    assert resp.status_code == 200
    assert resp.json()["total"] > 0


@pytest.mark.asyncio
async def test_pool_transactions(client: AsyncClient):
    """GET /api/pool/{id}/transactions should return transaction log."""
    cookies = await _login(client)

    create_resp = await client.post("/api/pool/", json={
        "name": "Tx Test",
        "total_funded": 1000.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    pool_id = create_resp.json()["data"]["id"]

    resp = await client.get(f"/api/pool/{pool_id}/transactions?p=0&size=50", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1  # at least the initial funding tx


@pytest.mark.asyncio
async def test_rollover_pool(client: AsyncClient):
    """Rollover should close old pool and create new one with carry-forward."""
    cookies = await _login(client)

    create_resp = await client.post("/api/pool/", json={
        "name": "Rollover Test",
        "total_funded": 2000.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    pool_id = create_resp.json()["data"]["id"]

    resp = await client.post(f"/api/pool/{pool_id}/rollover", json={
        "new_period_key": "2026-07",
        "new_name": "July 2026 Pool",
    }, cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["old_pool"]["status"] == "closed"
    assert data["new_pool"]["status"] == "active"
    assert data["new_pool"]["period_key"] == "2026-07"
    assert data["carried_forward"] == pytest.approx(2000.0, rel=0.01)


@pytest.mark.asyncio
async def test_recall_all_from_user(client: AsyncClient):
    """Recall all should return remaining balance."""
    cookies = await _login(client)

    create_resp = await client.post("/api/pool/", json={
        "name": "Recall All Test",
        "total_funded": 1000.0,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    pool_id = create_resp.json()["data"]["id"]

    await client.post(f"/api/pool/{pool_id}/allocate", json={
        "user_id": 1, "amount": 500.0,
    }, cookies=cookies)

    resp = await client.post(f"/api/pool/{pool_id}/recall_all", json={
        "user_id": 1,
    }, cookies=cookies)
    assert resp.status_code == 200
