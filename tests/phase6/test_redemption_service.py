"""Service-level tests for redemption code logic."""
import pytest
from sqlalchemy import select

from app.database import async_session_factory
from app.models.redemption import RedemptionCode
from app.models.user import User
from app.services import redemption as redemption_service
from app.services.auth import hash_password


@pytest.mark.asyncio
async def test_create_single_code():
    """Creating a single redemption code generates a unique code string."""
    async with async_session_factory() as db:
        admin = User(username="red_admin", password=hash_password("p"), role=10, quota=0)
        db.add(admin)
        await db.flush()

        codes = await redemption_service.create_redemption_codes(db, admin.id, "test code", 500000, 1)
        assert len(codes) == 1
        assert codes[0].name == "test code"
        assert codes[0].quota == 500000
        assert len(codes[0].code) >= 8  # generated code
        assert codes[0].status == 1  # active
        assert codes[0].created_by == admin.id


@pytest.mark.asyncio
async def test_create_multiple_codes():
    """Creating multiple codes generates unique code strings."""
    async with async_session_factory() as db:
        admin = User(username="red_admin2", password=hash_password("p"), role=10, quota=0)
        db.add(admin)
        await db.flush()

        codes = await redemption_service.create_redemption_codes(db, admin.id, "bulk", 100000, 5)
        assert len(codes) == 5
        codes_list = [c.code for c in codes]
        assert len(set(codes_list)) == 5  # all unique


@pytest.mark.asyncio
async def test_list_codes():
    """Listing codes returns all with correct total."""
    async with async_session_factory() as db:
        admin = User(username="red_admin3", password=hash_password("p"), role=10, quota=0)
        db.add(admin)
        await db.flush()
        await redemption_service.create_redemption_codes(db, admin.id, "batch1", 100000, 3)
        await redemption_service.create_redemption_codes(db, admin.id, "batch2", 200000, 2)

        data, total = await redemption_service.list_codes(db)
        assert total == 5
        assert len(data) == 5


@pytest.mark.asyncio
async def test_search_codes():
    """Searching codes by name keyword returns matching codes."""
    async with async_session_factory() as db:
        admin = User(username="red_admin4", password=hash_password("p"), role=10, quota=0)
        db.add(admin)
        await db.flush()
        await redemption_service.create_redemption_codes(db, admin.id, "promo2024", 100000, 2)
        await redemption_service.create_redemption_codes(db, admin.id, "welcome", 50000, 1)

        results = await redemption_service.search_codes(db, "promo")
        assert len(results) == 2
        assert all("promo" in r["name"] for r in results)


@pytest.mark.asyncio
async def test_delete_code():
    """Deleting a code removes it from the database."""
    async with async_session_factory() as db:
        admin = User(username="red_admin5", password=hash_password("p"), role=10, quota=0)
        db.add(admin)
        await db.flush()
        codes = await redemption_service.create_redemption_codes(db, admin.id, "delete_me", 100000, 1)
        code_id = codes[0].id

        await redemption_service.delete_code(db, code_id)
        result = await db.execute(select(RedemptionCode).where(RedemptionCode.id == code_id))
        assert result.scalar_one_or_none() is None
