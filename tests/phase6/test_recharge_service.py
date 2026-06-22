"""Service-level tests for recharge and admin top-up."""
import time

import pytest
from sqlalchemy import select

from app.database import async_session_factory
from app.models.recharge import RechargeRequest
from app.models.user import User
from app.services import recharge as recharge_service
from app.services.auth import hash_password


@pytest.mark.asyncio
async def test_create_recharge():
    """Creating a recharge request should persist it with status=1."""
    async with async_session_factory() as db:
        user = User(username="recharge_user", password=hash_password("pass"), role=1, quota=0)
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
        user = User(username="self_user", password=hash_password("pass"), role=1, quota=0)
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
        u1 = User(username="u1", password=hash_password("p"), role=1, quota=0)
        u2 = User(username="u2", password=hash_password("p"), role=1, quota=0)
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
