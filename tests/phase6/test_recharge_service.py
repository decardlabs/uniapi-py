"""Service-level tests for recharge and admin top-up."""
import time

import pytest
from sqlalchemy import select

from app.database import async_session_factory
from app.models.log import Log
from app.models.recharge import RechargeRequest
from app.models.user import User
from app.models.budget import BudgetPool, PoolTransaction
from app.services import recharge as recharge_service
from app.services.pool_sync import sync_consumption_to_pool
from app.services.auth import hash_password


@pytest.mark.asyncio
async def test_create_recharge():
    """Creating a recharge request should persist it with status=1."""
    async with async_session_factory() as db:
        user = User(username="recharge_user", password=hash_password("pass"), role=1)
        db.add(user)
        await db.flush()
        user_id = user.id
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now

        req = await recharge_service.create_recharge(db, user_id=user_id, amount=500000, remark="my topup")
        assert req.id is not None and req.id > 0
        assert req.user_id == user_id
        assert req.amount == 500000
        assert req.status == 1  # pending
        assert req.remark == "my topup"


@pytest.mark.asyncio
async def test_list_recharges_empty():
    """Admin lists recharges when none exist."""
    async with async_session_factory() as db:
        data, total = await recharge_service.list_recharges(db)
        assert total == 0
        assert data == []


@pytest.mark.asyncio
async def test_list_self_recharges():
    """User lists own recharge requests."""
    async with async_session_factory() as db:
        user = User(username="self_user", password=hash_password("pass"), role=1)
        db.add(user)
        await db.flush()
        uid = user.id
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now

        req1 = await recharge_service.create_recharge(db, uid, 100000, "first")
        req2 = await recharge_service.create_recharge(db, uid, 200000, "second")

        data, total = await recharge_service.list_self_recharges(db, uid)
        assert total == 2
        assert len(data) == 2
        assert data[0]["id"] == req2.id  # most recent first
        assert data[1]["id"] == req1.id


@pytest.mark.asyncio
async def test_list_recharges_with_multiple_users():
    """Admin sees all users' recharge requests."""
    async with async_session_factory() as db:
        u1 = User(username="u1", password=hash_password("p"), role=1)
        u2 = User(username="u2", password=hash_password("p"), role=1)
        db.add_all([u1, u2])
        await db.flush()
        now = int(time.time() * 1000)
        u1.created_time = now
        u2.created_time = now
        u1.updated_time = now
        u2.updated_time = now

        await recharge_service.create_recharge(db, u1.id, 100000)
        await recharge_service.create_recharge(db, u2.id, 200000)

        data, total = await recharge_service.list_recharges(db)
        assert total == 2
        assert data[0]["username"] in ("u1", "u2")


@pytest.mark.asyncio
async def test_get_recharge_by_id_not_found():
    async with async_session_factory() as db:
        req = await recharge_service.get_recharge_by_id(db, 9999)
        assert req is None


@pytest.mark.asyncio
async def test_approve_recharge_adds_quota():
    """Approving a recharge adds to user balance and deducts from pool."""
    async with async_session_factory() as db:
        user = User(username="approve_user", password=hash_password("p"), role=1)
        admin = User(username="admin", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        # Create a budget pool (no allocation needed — pool is the single global pool)
        pool = BudgetPool(
            name="test pool", total_funded=1000.0, total_consumed=0.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=now,
        )
        db.add(pool)
        await db.flush()

        req = await recharge_service.create_recharge(db, user.id, 500000, "please approve")
        assert req.status == 1

        approved = await recharge_service.approve_recharge(db, req.id, admin.id, pool_id=pool.id)
        assert approved.status == 2
        assert approved.reviewer_id == admin.id
        assert approved.reviewed_time is not None

        # Verify user balance increased: 500,000 micro-yuan = ¥0.5
        result = await db.execute(select(User).where(User.id == user.id))
        updated_user = result.scalar_one()
        assert updated_user.balance == 500000

        # Verify pool total_consumed increased (no allocation — pool is the ledger)
        pool_result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool.id))
        updated_pool = pool_result.scalar_one()
        assert updated_pool.total_consumed == 0.5  # 500000 micro-yuan = ¥0.5


@pytest.mark.asyncio
async def test_approve_recharge_auto_find_pool():
    """Approve without pool_id should auto-find the active pool."""
    async with async_session_factory() as db:
        user = User(username="auto_pool_user", password=hash_password("p"), role=1)
        admin = User(username="admin_auto", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        pool = BudgetPool(
            name="auto pool", total_funded=500.0, total_consumed=0.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=now,
        )
        db.add(pool)
        await db.flush()

        req = await recharge_service.create_recharge(db, user.id, 200000)
        # Call without pool_id — should auto-find
        approved = await recharge_service.approve_recharge(db, req.id, admin.id)
        assert approved.status == 2

        pool_result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool.id))
        updated_pool = pool_result.scalar_one()
        assert updated_pool.total_consumed == 0.2  # ¥0.2


@pytest.mark.asyncio
async def test_approve_recharge_insufficient_pool():
    """Approving with insufficient pool balance raises ValueError."""
    async with async_session_factory() as db:
        user = User(username="poor_user", password=hash_password("p"), role=1)
        admin = User(username="admin_poor", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        # Pool has only ¥10, but recharge is ¥100
        pool = BudgetPool(
            name="small pool", total_funded=10.0, total_consumed=0.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=now,
        )
        db.add(pool)
        await db.flush()

        req = await recharge_service.create_recharge(db, user.id, 100000000)  # ¥100
        with pytest.raises(ValueError, match="Insufficient pool balance"):
            await recharge_service.approve_recharge(db, req.id, admin.id, pool_id=pool.id)


@pytest.mark.asyncio
async def test_approve_recharge_no_active_pool():
    """Approving with no active pool raises ValueError."""
    async with async_session_factory() as db:
        user = User(username="no_pool_user", password=hash_password("p"), role=1)
        admin = User(username="admin_no_pool", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        req = await recharge_service.create_recharge(db, user.id, 100000)
        with pytest.raises(ValueError, match="No active budget pool"):
            await recharge_service.approve_recharge(db, req.id, admin.id)


@pytest.mark.asyncio
async def test_reject_recharge():
    """Rejecting a recharge sets status=3 and does not change quota."""
    async with async_session_factory() as db:
        user = User(username="reject_user", password=hash_password("p"), role=1)
        admin = User(username="admin2", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        req = await recharge_service.create_recharge(db, user.id, 300000)
        rejected = await recharge_service.reject_recharge(db, req.id, admin.id, "Invalid request")
        assert rejected.status == 3
        assert rejected.admin_remark == "Invalid request"

        result = await db.execute(select(User).where(User.id == user.id))
        u = result.scalar_one()
        assert u.balance == 0  # unchanged


@pytest.mark.asyncio
async def test_approve_already_approved_rejected():
    """Approving an already handled request should raise ValueError."""
    async with async_session_factory() as db:
        user = User(username="double_user", password=hash_password("p"), role=1)
        admin = User(username="admin3", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        pool = BudgetPool(
            name="test pool 2", total_funded=1000.0, total_consumed=0.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=now,
        )
        db.add(pool)
        await db.flush()

        req = await recharge_service.create_recharge(db, user.id, 100000)
        await recharge_service.approve_recharge(db, req.id, admin.id, pool_id=pool.id)
        with pytest.raises(ValueError, match="not pending"):
            await recharge_service.approve_recharge(db, req.id, admin.id, pool_id=pool.id)


@pytest.mark.asyncio
async def test_admin_topup():
    """Admin direct top-up adds quota immediately and deducts from pool (auto-find)."""
    async with async_session_factory() as db:
        user = User(username="topup_user", password=hash_password("p"), role=1)
        admin = User(username="admin4", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        # Pool is required — admin_topup auto-finds active pool even when pool_id=0
        pool = BudgetPool(
            name="auto pool", total_funded=500.0, total_consumed=10.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=now,
        )
        db.add(pool)
        await db.flush()

        result = await recharge_service.admin_topup(db, admin.id, user.id, 2.0, pool_id=0)
        assert result["balance"] == 2000000  # 2 yuan = 2,000,000 micro-yuan

        # Verify pool was deducted
        pool_result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool.id))
        updated_pool = pool_result.scalar_one()
        assert updated_pool.total_consumed == 12.0  # 10 + 2

        # Verify log was created
        log_result = await db.execute(select(Log).where(Log.type == 1).where(Log.user_id == user.id))
        logs = log_result.scalars().all()
        assert len(logs) == 1
        assert logs[0].cost == 2000000


@pytest.mark.asyncio
async def test_admin_topup_with_pool():
    """Admin direct top-up with pool_id deducts from pool."""
    async with async_session_factory() as db:
        user = User(username="topup_pool_user", password=hash_password("p"), role=1)
        admin = User(username="admin_topup_pool", password=hash_password("p"), role=10)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        pool = BudgetPool(
            name="topup pool", total_funded=100.0, total_consumed=0.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=now,
        )
        db.add(pool)
        await db.flush()

        result = await recharge_service.admin_topup(db, admin.id, user.id, 5.0, pool_id=pool.id)
        assert result["balance"] == 5000000  # 5 yuan = 5,000,000 micro-yuan

        pool_result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool.id))
        updated_pool = pool_result.scalar_one()
        assert updated_pool.total_consumed == 5.0  # ¥5 deducted from pool


@pytest.mark.asyncio
async def test_admin_topup_nonexistent_user():
    """Top-up on non-existent user raises ValueError."""
    async with async_session_factory() as db:
        admin = User(username="admin5", password=hash_password("p"), role=10)
        db.add(admin)
        await db.flush()
        with pytest.raises(ValueError, match="not found"):
            await recharge_service.admin_topup(db, admin.id, 9999, 100000, pool_id=0)


@pytest.mark.asyncio
async def test_sync_consumption_to_pool():
    """sync_consumption_to_pool deducts from pool total_consumed."""
    async with async_session_factory() as db:
        pool = BudgetPool(
            name="sync pool", total_funded=1000.0, total_consumed=0.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=int(time.time() * 1000),
        )
        db.add(pool)
        await db.flush()

        await sync_consumption_to_pool(db, user_id=1, cost_yuan=50.0, model_name="test-model")
        await db.commit()

        pool_result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool.id))
        updated_pool = pool_result.scalar_one()
        assert updated_pool.total_consumed == 50.0

        # Verify PoolTransaction was created
        tx_result = await db.execute(
            select(PoolTransaction).where(PoolTransaction.pool_id == pool.id)
        )
        txs = tx_result.scalars().all()
        assert len(txs) == 1
        assert txs[0].amount == 50.0
        assert "test-model" in txs[0].remark


@pytest.mark.asyncio
async def test_sync_consumption_to_pool_no_pool():
    """sync_consumption_to_pool with no active pool is a no-op (not an error)."""
    async with async_session_factory() as db:
        # No pool created — should not raise
        await sync_consumption_to_pool(db, user_id=1, cost_yuan=10.0)
        await db.commit()
        # No assertion needed — just verify no exception


@pytest.mark.asyncio
async def test_sync_consumption_to_pool_insufficient():
    """sync_consumption_to_pool with cost exceeding available deducts what it can."""
    async with async_session_factory() as db:
        pool = BudgetPool(
            name="tiny pool", total_funded=1.0, total_consumed=0.0,
            period_type="monthly", period_key="2026-06", status="active", created_at=int(time.time() * 1000),
        )
        db.add(pool)
        await db.flush()

        # Cost ¥50 but pool only has ¥1 — should deduct ¥1 (all remaining)
        await sync_consumption_to_pool(db, user_id=1, cost_yuan=50.0)
        await db.commit()

        pool_result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool.id))
        updated_pool = pool_result.scalar_one()
        assert updated_pool.total_consumed == 1.0  # capped at available
