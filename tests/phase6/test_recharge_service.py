"""Service-level tests for recharge and admin top-up."""
import time

import pytest
from sqlalchemy import select

from app.database import async_session_factory
from app.models.log import Log
from app.models.recharge import RechargeRequest
from app.models.user import User
from app.services import recharge as recharge_service
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
    """Approving a recharge adds the amount to user's quota."""
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

        req = await recharge_service.create_recharge(db, user.id, 500000, "please approve")
        assert req.status == 1

        approved = await recharge_service.approve_recharge(db, req.id, admin.id)
        assert approved.status == 2
        assert approved.reviewer_id == admin.id
        assert approved.reviewed_time is not None

        # Verify user quota increased
        result = await db.execute(select(User).where(User.id == user.id))
        updated_user = result.scalar_one()
        assert updated_user.balance == 500000  # 1000 + 500000


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

        req = await recharge_service.create_recharge(db, user.id, 100000)
        await recharge_service.approve_recharge(db, req.id, admin.id)
        with pytest.raises(ValueError, match="not pending"):
            await recharge_service.approve_recharge(db, req.id, admin.id)


@pytest.mark.asyncio
async def test_admin_topup():
    """Admin direct top-up adds quota immediately."""
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

        result = await recharge_service.admin_topup(db, admin.id, user.id, 1000000, pool_id=0)
        assert result["balance"] == 2000000  # 500 + 1000000

        # Verify log was created
        log_result = await db.execute(select(Log).where(Log.type == 1).where(Log.user_id == user.id))
        logs = log_result.scalars().all()
        assert len(logs) == 1
        assert logs[0].cost == 2000000


@pytest.mark.asyncio
async def test_admin_topup_nonexistent_user():
    """Top-up on non-existent user raises ValueError."""
    async with async_session_factory() as db:
        admin = User(username="admin5", password=hash_password("p"), role=10)
        db.add(admin)
        await db.flush()
        with pytest.raises(ValueError, match="not found"):
            await recharge_service.admin_topup(db, admin.id, 9999, 100000, pool_id=0)
