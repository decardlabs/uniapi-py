"""Integration tests: recharge approval + budget pool deduction.

Verifies that approving a recharge request:
  1. Increases user's balance by the requested amount
  2. Decreases pool's total_consumed by the equivalent yuan amount
  3. Creates a PoolTransaction with type='consume'
  4. The reconciliation endpoint correctly reflects the deduction
"""
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> dict:
    resp = await client.post("/api/user/login", json={
        "username": "root", "password": "123456",
    })
    return resp.cookies


async def _create_pool(client: AsyncClient, cookies: dict, total_funded: float = 6000.0) -> int:
    resp = await client.post("/api/pool/", json={
        "name": "Integration Test Pool",
        "total_funded": total_funded,
        "period_type": "monthly",
        "period_key": "2026-06",
    }, cookies=cookies)
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_approve_recharge_deducts_pool(client: AsyncClient):
    """Approving a recharge should increase pool.total_consumed by the yuan amount."""
    cookies = await _login(client)

    # Get initial user balance
    user_resp = await client.get("/api/user/self", cookies=cookies)
    initial_balance = user_resp.json()["data"]["balance"]

    # Create pool
    pool_id = await _create_pool(client, cookies, 6000.0)

    # Initial pool state
    pool_resp = await client.get(f"/api/pool/{pool_id}", cookies=cookies)
    initial_consumed = pool_resp.json()["data"]["total_consumed"]

    # Create recharge request for ¥7 (7,000,000 micro-yuan)
    recharge_resp = await client.post("/api/recharge/", json={
        "amount": 7_000_000,
        "remark": "integration test recharge ¥7",
    }, cookies=cookies)
    assert recharge_resp.status_code == 200
    recharge_id = recharge_resp.json()["data"]["id"]

    # Approve the recharge
    approve_resp = await client.post(f"/api/recharge/{recharge_id}/approve", json={
        "pool_id": pool_id,
    }, cookies=cookies)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["approved"] is True

    # 1. User balance increased by exactly ¥7 (7,000,000 micro-yuan)
    user_resp = await client.get("/api/user/self", cookies=cookies)
    new_balance = user_resp.json()["data"]["balance"]
    assert new_balance == initial_balance + 7_000_000, \
        f"Balance should increase by ¥7: {initial_balance} → {new_balance}"

    # 2. Pool total_consumed increased by exactly ¥7
    pool_resp = await client.get(f"/api/pool/{pool_id}", cookies=cookies)
    new_consumed = pool_resp.json()["data"]["total_consumed"]
    assert new_consumed == pytest.approx(initial_consumed + 7.0, rel=0.001), \
        f"Pool consumed should increase by ¥7: {initial_consumed} → {new_consumed}"

    # 3. Pool available decreased by exactly ¥7
    pool_detail = pool_resp.json()["data"]
    available = pool_detail["total_funded"] - pool_detail["total_consumed"]
    assert available == pytest.approx(6000.0 - 7.0, rel=0.001)

    # 4. PoolTransaction created with type='consume'
    tx_resp = await client.get(f"/api/pool/{pool_id}/transactions?p=0&size=50", cookies=cookies)
    txs = tx_resp.json()["data"]
    consume_txns = [t for t in txs if t["type"] == "consume"]
    assert len(consume_txns) >= 1
    last_consume = consume_txns[-1]
    assert last_consume["amount"] == pytest.approx(7.0, rel=0.001)
    assert last_consume["user_id"] == 1

    # 5. Reconciliation endpoint agrees
    reconf_resp = await client.get(f"/api/pool/{pool_id}/reconciliation", cookies=cookies)
    reconf = reconf_resp.json()["data"]["pool"]
    assert reconf["total_consumed"] == pytest.approx(7.0, rel=0.01), \
        "Reconciliation must reflect the recharge"

    # 6. PoolTransaction list includes the recharge approval entry
    assert any("Recharge approval" in t.get("remark", "") for t in txs), \
        "Recharge approval remark should appear in pool transactions"


@pytest.mark.asyncio
async def test_recharge_insufficient_pool_balance(client: AsyncClient):
    """Recharge exceeding pool balance should be rejected."""
    cookies = await _login(client)
    pool_id = await _create_pool(client, cookies, 50.0)  # only ¥50

    # Recharge for ¥200 (200,000,000 micro-yuan) — exceeds pool
    recharge_resp = await client.post("/api/recharge/", json={
        "amount": 200_000_000,
        "remark": "test over-limit recharge",
    }, cookies=cookies)
    recharge_id = recharge_resp.json()["data"]["id"]

    # Approve should fail
    approve_resp = await client.post(f"/api/recharge/{recharge_id}/approve", json={
        "pool_id": pool_id,
    }, cookies=cookies)
    assert approve_resp.json()["success"] is False
    assert "Insufficient" in approve_resp.json().get("message", "")


@pytest.mark.asyncio
async def test_recharge_no_active_pool(client: AsyncClient):
    """Without an active pool, recharge approval should fail."""
    cookies = await _login(client)
    # Do NOT create any pool

    recharge_resp = await client.post("/api/recharge/", json={
        "amount": 1_000_000,
        "remark": "test no pool",
    }, cookies=cookies)
    recharge_id = recharge_resp.json()["data"]["id"]

    approve_resp = await client.post(f"/api/recharge/{recharge_id}/approve", json={
        "pool_id": 0,  # auto-find
    }, cookies=cookies)
    assert approve_resp.json()["success"] is False


@pytest.mark.asyncio
async def test_reject_recharge_no_pool_change(client: AsyncClient):
    """Rejecting a recharge should NOT affect pool or user balance."""
    cookies = await _login(client)
    pool_id = await _create_pool(client, cookies, 5000.0)

    # Get initial state
    user_resp = await client.get("/api/user/self", cookies=cookies)
    initial_balance = user_resp.json()["data"]["balance"]

    pool_resp = await client.get(f"/api/pool/{pool_id}", cookies=cookies)
    initial_consumed = pool_resp.json()["data"]["total_consumed"]

    # Create and reject recharge
    recharge_resp = await client.post("/api/recharge/", json={
        "amount": 5_000_000,  # ¥5
        "remark": "test rejected recharge",
    }, cookies=cookies)
    recharge_id = recharge_resp.json()["data"]["id"]

    reject_resp = await client.post(f"/api/recharge/{recharge_id}/reject", json={
        "admin_remark": "Test rejection",
    }, cookies=cookies)
    assert reject_resp.status_code == 200

    # User balance unchanged
    user_resp = await client.get("/api/user/self", cookies=cookies)
    assert user_resp.json()["data"]["balance"] == initial_balance

    # Pool unchanged
    pool_resp = await client.get(f"/api/pool/{pool_id}", cookies=cookies)
    assert pool_resp.json()["data"]["total_consumed"] == pytest.approx(initial_consumed, rel=0.001)


@pytest.mark.asyncio
async def test_admin_topup_deducts_pool(client: AsyncClient):
    """Admin direct topup should also deduct from the pool."""
    cookies = await _login(client)
    pool_id = await _create_pool(client, cookies, 10000.0)

    user_resp = await client.get("/api/user/self", cookies=cookies)
    initial_balance = user_resp.json()["data"]["balance"]

    pool_resp = await client.get(f"/api/pool/{pool_id}", cookies=cookies)
    initial_consumed = pool_resp.json()["data"]["total_consumed"]

    # Admin direct topup
    topup_resp = await client.post("/api/topup/", json={
        "user_id": 1,
        "amount": 15.0,  # ¥15 (in yuan, not micro-yuan)
        "pool_id": pool_id,
        "remark": "test admin topup",
    }, cookies=cookies)
    assert topup_resp.status_code == 200

    # User balance increased
    user_resp = await client.get("/api/user/self", cookies=cookies)
    # Topup amount is in yuan, so balance should increase by 15 * 1,000,000
    assert user_resp.json()["data"]["balance"] >= initial_balance

    # Pool consumed increased
    pool_resp = await client.get(f"/api/pool/{pool_id}", cookies=cookies)
    new_consumed = pool_resp.json()["data"]["total_consumed"]
    expected_consumed = initial_consumed + 15.0
    assert new_consumed >= expected_consumed - 0.001, \
        f"Pool consumed should increase by at least ¥15: {initial_consumed} → {new_consumed}"
