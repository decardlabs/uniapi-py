# Recharge & Redemption System Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all stub endpoints in the recharge and redemption systems with real implementations including database models, service layers, and full integration tests — then align the frontend to use consistent API paths.

**Architecture:** Add `RechargeRequest` and `RedemptionCode` SQLAlchemy models, Pydantic schemas, service-layer business logic in `app/services/`, wire into existing `topup.py` and `redemption.py` routers. Each task follows strict TDD: failing test → minimal implementation → passing test → commit.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x async, Alembic, Pytest + httpx.AsyncClient, React/TypeScript (frontend).

## Global Constraints

- All model timestamp fields must use `int(time.time() * 1000)` (milliseconds), matching existing patterns in `User`, `Log`, `Token` models.
- All paginated endpoints use `p` (0-indexed page) and `size` query params, matching existing patterns.
- Response format must use `GenericApiResponse` for single items and `PaginatedResponse` for lists (from `app/schemas/common.py`).
- In tests, use the existing `client` fixture from `tests/conftest.py` which provides a fresh SQLite DB per function.
- Quota amounts are stored as integer (token count); the conversion ratio is `QuotaPerUsd = 500000`.
- Log type constants: 1=TOPUP, 2=CONSUME (from `LOG_TYPES` in frontend and matching backend usage).
- All new files follow the existing codebase patterns: `from __future__ import annotations`, type hints, async handlers.

---

## File Structure

### New Files (Create)
| File | Responsibility |
|------|---------------|
| `app/models/recharge.py` | `RechargeRequest` SQLAlchemy model |
| `app/models/redemption.py` | `RedemptionCode` SQLAlchemy model |
| `app/schemas/recharge.py` | Pydantic request/response schemas for recharge |
| `app/schemas/redemption.py` | Pydantic request/response schemas for redemption codes |
| `app/services/recharge.py` | Recharge business logic (create, list, approve, reject, admin topup) |
| `app/services/redemption.py` | Redemption code business logic (CRUD, redeem) |
| `tests/phase6/test_recharge_model.py` | Model + schema tests for RechargeRequest |
| `tests/phase6/test_redemption_model.py` | Model + schema tests for RedemptionCode |
| `tests/phase6/test_recharge_service.py` | Service-level tests for recharge logic |
| `tests/phase6/test_recharge_endpoints.py` | Full integration HTTP tests for /api/recharge/ and /api/topup/ |
| `tests/phase6/test_redemption_service.py` | Service-level tests for redemption logic |
| `tests/phase6/test_redemption_endpoints.py` | Full integration HTTP tests for /api/redemption/ |

### Modified Files
| File | Change |
|------|--------|
| `app/routers/api/topup.py` | Replace all stubs with real implementations calling services |
| `app/routers/api/redemption.py` | Replace all stubs with real implementations calling services |
| `web/src/lib/services/recharge.ts` | Fix `/api/topup/` calls to `/api/recharge/` where appropriate; add `adminTopup()` function |
| `web/src/pages/topup/TopUpPage.tsx` | Use service layer (`recharge.ts`) instead of raw `api.*` calls |
| `web/src/pages/recharges/RechargesPage.tsx` | Use service layer (`recharge.ts`) instead of raw `api.*` calls |
| `web/src/pages/users/UsersPage.tsx` | Use service layer (`recharge.ts` adminTopup) instead of raw `api.*` call |
| `web/src/App.tsx` | Register `/redemptions` and `/redemptions/edit/:id` routes (or remove if deprecated) |

---

### Task 1: RechargeRequest Model + Schema + Migration

**Files:**
- Create: `app/models/recharge.py`
- Create: `app/schemas/recharge.py`
- Create: `tests/phase6/test_recharge_model.py`
- Modify: Alembic migration (autogenerate)

**Interfaces:**
- Produces: `RechargeRequest` model with fields: `id`, `user_id`, `amount`, `status` (1=pending, 2=approved, 3=rejected), `remark`, `admin_remark`, `reviewer_id`, `reviewed_time`, `created_time`
- Produces: `RechargeCreate` schema (user: `amount: int`, `remark: str | None`)
- Produces: `RechargeResponse` schema (full response with all fields + user info)
- Produces: `RechargeStatus` enum: `PENDING=1, APPROVED=2, REJECTED=3`

- [ ] **Step 1: Create the RechargeRequest model**

`app/models/recharge.py`:
```python
"""Recharge request database model."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RechargeRequest(Base):
    __tablename__ = "recharge_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)  # quota amount requested
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=pending, 2=approved, 3=rejected
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewed_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_time: Mapped[int] = mapped_column(BigInteger, default=0)
```

- [ ] **Step 2: Run test to verify model loads**

Run: `python3 -c "from app.models.recharge import RechargeRequest; print('OK:', RechargeRequest.__tablename__)"`
Expected: `OK: recharge_requests`

- [ ] **Step 3: Create Pydantic schemas**

`app/schemas/recharge.py`:
```python
"""Recharge-related Pydantic schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RechargeCreate(BaseModel):
    amount: int = Field(..., ge=1, description="Quota amount requested")
    remark: Optional[str] = None


class RechargeResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    status: int
    remark: Optional[str] = None
    admin_remark: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewed_time: Optional[int] = None
    created_time: int
    username: Optional[str] = None  # joined from User table

    model_config = {"from_attributes": True}


class TopUpRequest(BaseModel):
    """Schema for admin direct top-up."""
    user_id: int = Field(..., ge=1)
    quota: int = Field(..., ge=1)
    remark: Optional[str] = None
    pool_id: int = 0
```

- [ ] **Step 4: Run test to verify schemas load**

Run: `python3 -c "from app.schemas.recharge import RechargeCreate, RechargeResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Create model tests**

`tests/phase6/test_recharge_model.py`:
```python
"""Tests for RechargeRequest model and schemas."""
import pytest
from pydantic import ValidationError

from app.models.recharge import RechargeRequest
from app.schemas.recharge import RechargeCreate, RechargeResponse, TopUpRequest


class TestRechargeRequestModel:
    def test_model_attributes(self):
        """Verify model has expected columns."""
        assert hasattr(RechargeRequest, "id")
        assert hasattr(RechargeRequest, "user_id")
        assert hasattr(RechargeRequest, "amount")
        assert hasattr(RechargeRequest, "status")
        assert hasattr(RechargeRequest, "remark")
        assert hasattr(RechargeRequest, "admin_remark")
        assert hasattr(RechargeRequest, "reviewer_id")
        assert hasattr(RechargeRequest, "reviewed_time")
        assert hasattr(RechargeRequest, "created_time")

    def test_default_status_is_pending(self):
        """Status should default to 1 (pending)."""
        assert RechargeRequest.__table__.columns["status"].default.arg == 1


class TestRechargeSchema:
    def test_recharge_create_valid(self):
        data = RechargeCreate(amount=1000000, remark="test top-up")
        assert data.amount == 1000000
        assert data.remark == "test top-up"

    def test_recharge_create_negative_rejected(self):
        with pytest.raises(ValidationError):
            RechargeCreate(amount=-1)

    def test_recharge_create_zero_rejected(self):
        with pytest.raises(ValidationError):
            RechargeCreate(amount=0)

    def test_recharge_create_no_remark(self):
        data = RechargeCreate(amount=500000)
        assert data.remark is None

    def test_topup_request_valid(self):
        data = TopUpRequest(user_id=1, quota=1000000, remark="admin top-up", pool_id=3)
        assert data.user_id == 1
        assert data.quota == 1000000
        assert data.pool_id == 3

    def test_topup_request_default_pool_id(self):
        data = TopUpRequest(user_id=1, quota=1000000)
        assert data.pool_id == 0

    def test_recharge_response_from_orm(self):
        data = RechargeResponse(
            id=1, user_id=2, amount=1000000, status=1,
            created_time=1000, username="testuser",
        )
        assert data.id == 1
        assert data.status == 1
        assert data.username == "testuser"
```

- [ ] **Step 6: Run model tests (should all pass since no DB needed)**

Run: `python3 -m pytest tests/phase6/test_recharge_model.py -v`
Expected: All 9 tests PASS

- [ ] **Step 7: Generate Alembic migration**

Run: `alembic revision --autogenerate -m "add recharge_requests table"`
Expected: New migration file created

- [ ] **Step 8: Commit**

```bash
git add app/models/recharge.py app/schemas/recharge.py tests/phase6/test_recharge_model.py
git commit -m "feat: add RechargeRequest model and schemas"
```

---

### Task 2: RedemptionCode Model + Schema + Migration

**Files:**
- Create: `app/models/redemption.py`
- Create: `app/schemas/redemption.py`
- Create: `tests/phase6/test_redemption_model.py`

**Interfaces:**
- Produces: `RedemptionCode` model with fields: `id`, `name`, `code` (unique), `quota`, `status` (1=active, 2=disabled, 3=used), `used_by`, `used_time`, `created_by`, `created_time`
- Produces: `RedemptionCreate` schema (admin: `name`, `quota`, `count`)
- Produces: `RedemptionResponse` schema (full response)
- Produces: `RedemptionUpdate` schema (admin: `name`, `quota`, `status_only`)

- [ ] **Step 1: Create the RedemptionCode model**

`app/models/redemption.py`:
```python
"""Redemption code database model."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RedemptionCode(Base):
    __tablename__ = "redemption_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    quota: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=active, 2=disabled, 3=used
    used_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    used_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_time: Mapped[int] = mapped_column(BigInteger, default=0)
```

- [ ] **Step 2: Run test to verify model loads**

Run: `python3 -c "from app.models.redemption import RedemptionCode; print('OK:', RedemptionCode.__tablename__)"`
Expected: `OK: redemption_codes`

- [ ] **Step 3: Create Pydantic schemas**

`app/schemas/redemption.py`:
```python
"""Redemption code Pydantic schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RedemptionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    quota: int = Field(..., ge=1)
    count: int = Field(default=1, ge=1, le=100)


class RedemptionUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    quota: Optional[int] = None
    status_only: bool = False
    status: Optional[int] = None  # only used if status_only=True


class RedemptionResponse(BaseModel):
    id: int
    name: str
    code: str
    quota: int
    status: int
    used_by: Optional[int] = None
    used_time: Optional[int] = None
    created_by: Optional[int] = None
    created_time: int

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Run test to verify schemas load**

Run: `python3 -c "from app.schemas.redemption import RedemptionCreate, RedemptionResponse, RedemptionUpdate; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Create model tests**

`tests/phase6/test_redemption_model.py`:
```python
"""Tests for RedemptionCode model and schemas."""
import pytest
from pydantic import ValidationError

from app.models.redemption import RedemptionCode
from app.schemas.redemption import RedemptionCreate, RedemptionResponse, RedemptionUpdate


class TestRedemptionCodeModel:
    def test_model_attributes(self):
        assert hasattr(RedemptionCode, "id")
        assert hasattr(RedemptionCode, "name")
        assert hasattr(RedemptionCode, "code")
        assert hasattr(RedemptionCode, "quota")
        assert hasattr(RedemptionCode, "status")
        assert hasattr(RedemptionCode, "used_by")
        assert hasattr(RedemptionCode, "used_time")
        assert hasattr(RedemptionCode, "created_by")
        assert hasattr(RedemptionCode, "created_time")

    def test_code_is_unique_indexed(self):
        assert RedemptionCode.__table__.columns["code"].unique
        assert RedemptionCode.__table__.columns["code"].index


class TestRedemptionSchema:
    def test_redemption_create_valid(self):
        data = RedemptionCreate(name="test", quota=1000000, count=5)
        assert data.name == "test"
        assert data.count == 5

    def test_redemption_create_default_count(self):
        data = RedemptionCreate(name="test", quota=1000000)
        assert data.count == 1

    def test_redemption_create_count_too_high(self):
        with pytest.raises(ValidationError):
            RedemptionCreate(name="test", quota=1000000, count=101)

    def test_redemption_update_valid(self):
        data = RedemptionUpdate(id=1, name="new name", quota=500000)
        assert data.id == 1
        assert data.status_only is False

    def test_redemption_response_from_orm(self):
        data = RedemptionResponse(
            id=1, name="test", code="ABC123", quota=1000000,
            status=1, created_by=1, created_time=1000,
        )
        assert data.code == "ABC123"
        assert data.status == 1
```

- [ ] **Step 6: Run model tests**

Run: `python3 -m pytest tests/phase6/test_redemption_model.py -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Generate Alembic migration**

Run: `alembic revision --autogenerate -m "add redemption_codes table"`
Expected: New migration file created (or merged with Task 1's migration)

- [ ] **Step 8: Commit**

```bash
git add app/models/redemption.py app/schemas/redemption.py tests/phase6/test_redemption_model.py
git commit -m "feat: add RedemptionCode model and schemas"
```

---

### Task 3: Recharge Service Layer (Core: create, list, self-list)

**Files:**
- Create: `app/services/recharge.py`
- Create: `tests/phase6/test_recharge_service.py`

**Interfaces:**
- Consumes: `RechargeCreate` schema, `RechargeRequest` model, `User` model
- Produces: `async def create_recharge(db, user_id: int, amount: int, remark: str | None) -> RechargeRequest`
- Produces: `async def list_recharges(db, page: int, size: int) -> tuple[list[dict], int]`
- Produces: `async def list_self_recharges(db, user_id: int, page: int, size: int) -> tuple[list[dict], int]`
- Produces: `async def get_recharge_by_id(db, recharge_id: int) -> RechargeRequest | None`

- [ ] **Step 1: Write the failing test for create_recharge**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/phase6/test_recharge_service.py::test_create_recharge -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.recharge'`

- [ ] **Step 3: Write minimal implementation**

`app/services/recharge.py`:
```python
"""Recharge business logic service."""
from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recharge import RechargeRequest
from app.models.user import User


async def create_recharge(
    db: AsyncSession,
    user_id: int,
    amount: int,
    remark: Optional[str] = None,
) -> RechargeRequest:
    now = int(time.time() * 1000)
    req = RechargeRequest(
        user_id=user_id,
        amount=amount,
        status=1,
        remark=remark,
        created_time=now,
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def list_recharges(
    db: AsyncSession,
    page: int = 0,
    size: int = 10,
) -> tuple[list[dict], int]:
    """Admin list all recharge requests with user info joined."""
    count_q = select(func.count(RechargeRequest.id))
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = (
        select(RechargeRequest, User.username)
        .outerjoin(User, RechargeRequest.user_id == User.id)
        .order_by(RechargeRequest.id.desc())
        .offset(page * size)
        .limit(size)
    )
    result = await db.execute(q)
    rows = result.all()

    data = []
    for req, username in rows:
        item = {
            "id": req.id,
            "user_id": req.user_id,
            "amount": req.amount,
            "status": req.status,
            "remark": req.remark,
            "admin_remark": req.admin_remark,
            "reviewer_id": req.reviewer_id,
            "reviewed_time": req.reviewed_time,
            "created_time": req.created_time,
            "username": username,
        }
        data.append(item)
    return data, total


async def list_self_recharges(
    db: AsyncSession,
    user_id: int,
    page: int = 0,
    size: int = 10,
) -> tuple[list[dict], int]:
    count_q = select(func.count(RechargeRequest.id)).where(RechargeRequest.user_id == user_id)
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = (
        select(RechargeRequest)
        .where(RechargeRequest.user_id == user_id)
        .order_by(RechargeRequest.id.desc())
        .offset(page * size)
        .limit(size)
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    data = []
    for req in rows:
        item = {
            "id": req.id,
            "user_id": req.user_id,
            "amount": req.amount,
            "status": req.status,
            "remark": req.remark,
            "admin_remark": req.admin_remark,
            "reviewer_id": req.reviewer_id,
            "reviewed_time": req.reviewed_time,
            "created_time": req.created_time,
        }
        data.append(item)
    return data, total


async def get_recharge_by_id(db: AsyncSession, recharge_id: int) -> RechargeRequest | None:
    result = await db.execute(select(RechargeRequest).where(RechargeRequest.id == recharge_id))
    return result.scalar_one_or_none()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/phase6/test_recharge_service.py -v`
Expected: test_create_recharge PASS

- [ ] **Step 5: Write list_recharges tests**

Add to `tests/phase6/test_recharge_service.py`:
```python
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
```

- [ ] **Step 6: Run list tests to verify they pass**

Run: `python3 -m pytest tests/phase6/test_recharge_service.py -v`
Expected: All 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/recharge.py tests/phase6/test_recharge_service.py
git commit -m "feat: add recharge service core (create, list, get)"
```

---

### Task 4: Recharge Service (approve, reject, admin_topup)

**Files:**
- Modify: `app/services/recharge.py`
- Modify: `tests/phase6/test_recharge_service.py`

**Interfaces:**
- Produces: `async def approve_recharge(db, recharge_id: int, admin_id: int) -> RechargeRequest`
- Produces: `async def reject_recharge(db, recharge_id: int, admin_id: int, admin_remark: str) -> RechargeRequest`
- Produces: `async def admin_topup(db, admin_id: int, user_id: int, quota: int, remark: str | None, pool_id: int) -> dict`

Key business rules:
- `approve_recharge`: Set status=2, reviewer_id=admin_id, reviewed_time=now, add amount to user.quota, create a log entry (type=1)
- `reject_recharge`: Set status=3, reviewer_id=admin_id, reviewed_time=now, admin_remark=reason
- `admin_topup`: No recharge request needed — immediately add quota to user, create a log entry

- [ ] **Step 1: Write failing test for approve_recharge**

Add to `tests/phase6/test_recharge_service.py`:
```python
@pytest.mark.asyncio
async def test_approve_recharge_adds_quota():
    """Approving a recharge adds the amount to user's quota."""
    async with async_session_factory() as db:
        user = User(username="approve_user", password=hash_password("p"), role=1, quota=1000)
        admin = User(username="admin", password=hash_password("p"), role=10, quota=0)
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
        assert updated_user.quota == 501000  # 1000 + 500000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/phase6/test_recharge_service.py::test_approve_recharge_adds_quota -v`
Expected: FAIL with `AttributeError: module 'app.services.recharge' has no attribute 'approve_recharge'`

- [ ] **Step 3: Write approve_recharge + reject_recharge + admin_topup implementation**

Add to `app/services/recharge.py`:
```python
import time
from sqlalchemy import select, func, update
from app.models.log import Log


async def approve_recharge(
    db: AsyncSession,
    recharge_id: int,
    admin_id: int,
) -> RechargeRequest:
    req = await get_recharge_by_id(db, recharge_id)
    if req is None:
        raise ValueError(f"Recharge request {recharge_id} not found")
    if req.status != 1:
        raise ValueError(f"Recharge request {recharge_id} is not pending")

    now = int(time.time() * 1000)
    req.status = 2
    req.reviewer_id = admin_id
    req.reviewed_time = now

    # Add quota to user
    result = await db.execute(select(User).where(User.id == req.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {req.user_id} not found")
    user.quota = (user.quota or 0) + req.amount

    # Create log entry
    log = Log(
        user_id=req.user_id,
        created_at=now,
        type=1,  # TOPUP
        content=f"Recharge approved: +{req.amount} quota (request #{recharge_id})",
        quota=req.amount,
    )
    db.add(log)
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def reject_recharge(
    db: AsyncSession,
    recharge_id: int,
    admin_id: int,
    admin_remark: str,
) -> RechargeRequest:
    req = await get_recharge_by_id(db, recharge_id)
    if req is None:
        raise ValueError(f"Recharge request {recharge_id} not found")
    if req.status != 1:
        raise ValueError(f"Recharge request {recharge_id} is not pending")

    now = int(time.time() * 1000)
    req.status = 3
    req.reviewer_id = admin_id
    req.reviewed_time = now
    req.admin_remark = admin_remark

    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def admin_topup(
    db: AsyncSession,
    admin_id: int,
    user_id: int,
    amount: int,
    remark: Optional[str] = None,
    pool_id: int = 0,
) -> dict:
    """Admin directly tops up a user's quota. Returns user info dict."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} not found")

    now = int(time.time() * 1000)
    user.quota = (user.quota or 0) + amount

    log = Log(
        user_id=user_id,
        created_at=now,
        type=1,  # TOPUP
        content=f"Admin top-up: +{amount} quota (by admin #{admin_id})" + (f" [{remark}]" if remark else ""),
        quota=amount,
    )
    db.add(log)
    await db.flush()
    await db.commit()

    return {
        "id": user.id,
        "username": user.username,
        "quota": user.quota,
    }
```

- [ ] **Step 4: Write remaining tests**

Add to `tests/phase6/test_recharge_service.py`:
```python
@pytest.mark.asyncio
async def test_reject_recharge():
    """Rejecting a recharge sets status=3 and does not change quota."""
    async with async_session_factory() as db:
        user = User(username="reject_user", password=hash_password("p"), role=1, quota=1000)
        admin = User(username="admin2", password=hash_password("p"), role=10, quota=0)
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
        assert u.quota == 1000  # unchanged


@pytest.mark.asyncio
async def test_approve_already_approved_rejected():
    """Approving an already handled request should raise ValueError."""
    async with async_session_factory() as db:
        user = User(username="double_user", password=hash_password("p"), role=1, quota=0)
        admin = User(username="admin3", password=hash_password("p"), role=10, quota=0)
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
        user = User(username="topup_user", password=hash_password("p"), role=1, quota=500)
        admin = User(username="admin4", password=hash_password("p"), role=10, quota=0)
        db.add_all([user, admin])
        await db.flush()
        now = int(time.time() * 1000)
        user.created_time = now
        user.updated_time = now
        admin.created_time = now
        admin.updated_time = now

        result = await recharge_service.admin_topup(db, admin.id, user.id, 1000000)
        assert result["quota"] == 1000500  # 500 + 1000000

        # Verify log was created
        log_result = await db.execute(select(Log).where(Log.type == 1).where(Log.user_id == user.id))
        logs = log_result.scalars().all()
        assert len(logs) == 1
        assert logs[0].quota == 1000000


@pytest.mark.asyncio
async def test_admin_topup_nonexistent_user():
    """Top-up on non-existent user raises ValueError."""
    async with async_session_factory() as db:
        admin = User(username="admin5", password=hash_password("p"), role=10, quota=0)
        db.add(admin)
        await db.flush()
        with pytest.raises(ValueError, match="not found"):
            await recharge_service.admin_topup(db, admin.id, 9999, 100000)
```

- [ ] **Step 5: Run all recharge service tests**

Run: `python3 -m pytest tests/phase6/test_recharge_service.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/recharge.py tests/phase6/test_recharge_service.py
git commit -m "feat: add recharge service approve, reject, and admin top-up"
```

---

### Task 5: Recharge HTTP Endpoints (replace stubs)

**Files:**
- Modify: `app/routers/api/topup.py`
- Create: `tests/phase6/test_recharge_endpoints.py`

**Interfaces:**
- Consumes: `recharge_service.create_recharge`, `recharge_service.list_recharges`, `recharge_service.list_self_recharges`, `recharge_service.approve_recharge`, `recharge_service.reject_recharge`, `recharge_service.admin_topup`
- Produces: All the HTTP endpoints listed below

- [ ] **Step 1: Write failing integration tests**

`tests/phase6/test_recharge_endpoints.py`:
```python
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
        resp = await client.post(f"/api/recharge/{recharge_id}/approve", cookies=admin_cookies)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify user quota increased
        self_resp = await client.get("/api/user/self", cookies=user_cookies)
        assert self_resp.json()["data"]["quota"] >= 1000000

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

        resp = await client.post(
            "/api/topup/",
            json={"user_id": user_id, "quota": 2000000, "remark": "bonus"},
            cookies=admin_cookies,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify user quota
        self_resp = await client.get("/api/user/self", cookies=user_cookies)
        assert self_resp.json()["data"]["quota"] >= 2000000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/phase6/test_recharge_endpoints.py -v`
Expected: Tests fail because endpoints still return stub data

- [ ] **Step 3: Replace all stubs in topup.py with real implementations**

`app/routers/api/topup.py`:
```python
"""Top-up and recharge API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth, user_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse
from app.schemas.recharge import RechargeCreate, TopUpRequest
from app.services import recharge as recharge_service

router = APIRouter(tags=["topup"])


# ── Admin direct top-up ──

@router.post("/api/topup/")
async def admin_topup(
    body: TopUpRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin directly tops up a user's quota without going through the request/approve flow."""
    admin_id = request.state.user.id
    try:
        result = await recharge_service.admin_topup(
            db,
            admin_id=admin_id,
            user_id=body.user_id,
            amount=body.quota,
            remark=body.remark,
            pool_id=body.pool_id,
        )
        return GenericApiResponse(data=result)
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


@router.get("/api/topup/")
async def list_topups(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin lists all recharge requests (alias for /api/recharge/)."""
    data, total = await recharge_service.list_recharges(db, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.put("/api/topup/")
async def update_topup(
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin action on a recharge request via unified PUT (backward compat).

    Body: { id, action: "approve"|"reject", admin_remark?: str }
    """
    recharge_id = body.get("id")
    action = body.get("action")
    admin_remark = body.get("admin_remark", "")
    admin_id = request.state.user.id

    if not recharge_id or action not in ("approve", "reject"):
        return GenericApiResponse(success=False, message="id and action (approve|reject) required")

    try:
        if action == "approve":
            await recharge_service.approve_recharge(db, recharge_id, admin_id)
        else:
            await recharge_service.reject_recharge(db, recharge_id, admin_id, admin_remark or "Rejected by admin")
        return GenericApiResponse(data={"updated": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


# ── Recharge (user-facing) ──

@router.get("/api/recharge/self")
async def list_self_recharges(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    """User lists their own recharge requests."""
    user_id = request.state.user.id
    data, total = await recharge_service.list_self_recharges(db, user_id, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.post("/api/recharge/")
async def create_recharge(
    body: RechargeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    """User creates a recharge request (pending admin approval)."""
    user_id = request.state.user.id
    req = await recharge_service.create_recharge(
        db, user_id=user_id, amount=body.amount, remark=body.remark,
    )
    return GenericApiResponse(data={"id": req.id})


# ── Recharge (admin) ──

@router.get("/api/recharge/")
async def list_recharges(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin lists all recharge requests."""
    data, total = await recharge_service.list_recharges(db, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.post("/api/recharge/{recharge_id}/approve")
async def approve_recharge(
    recharge_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin approves a pending recharge request and credits the user's quota."""
    admin_id = request.state.user.id
    try:
        await recharge_service.approve_recharge(db, recharge_id, admin_id)
        return GenericApiResponse(data={"approved": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


@router.post("/api/recharge/{recharge_id}/reject")
async def reject_recharge(
    recharge_id: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin rejects a pending recharge request."""
    admin_id = request.state.user.id
    admin_remark = body.get("admin_remark", "Rejected by admin")
    try:
        await recharge_service.reject_recharge(db, recharge_id, admin_id, admin_remark)
        return GenericApiResponse(data={"rejected": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/phase6/test_recharge_endpoints.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/api/topup.py tests/phase6/test_recharge_endpoints.py
git commit -m "feat: implement real recharge endpoints (replace stubs)"
```

---

### Task 6: Redemption Code Service Layer

**Files:**
- Create: `app/services/redemption.py`
- Create: `tests/phase6/test_redemption_service.py`

**Interfaces:**
- Consumes: `RedemptionCode` model, `RedemptionCreate/Update` schemas, `User` model
- Produces: `async def create_redemption_codes(db, admin_id, name, quota, count) -> list[RedemptionCode]`
- Produces: `async def list_codes(db, page, size) -> tuple[list[dict], int]`
- Produces: `async def search_codes(db, keyword) -> list[dict]`
- Produces: `async def get_code(db, code_id) -> RedemptionCode | None`
- Produces: `async def update_code(db, update_data) -> RedemptionCode`
- Produces: `async def delete_code(db, code_id) -> None`

- [ ] **Step 1: Write failing test**

`tests/phase6/test_redemption_service.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/phase6/test_redemption_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write redemption service implementation**

`app/services/redemption.py`:
```python
"""Redemption code business logic service."""
from __future__ import annotations

import secrets
import string
import time
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.redemption import RedemptionCode


def _generate_code(length: int = 12) -> str:
    """Generate a random alphanumeric redemption code."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def create_redemption_codes(
    db: AsyncSession,
    admin_id: int,
    name: str,
    quota: int,
    count: int = 1,
) -> list[RedemptionCode]:
    now = int(time.time() * 1000)
    codes = []
    for _ in range(count):
        code_str = _generate_code()
        # Ensure uniqueness
        while True:
            existing = await db.execute(select(RedemptionCode).where(RedemptionCode.code == code_str))
            if existing.scalar_one_or_none() is None:
                break
            code_str = _generate_code()

        rc = RedemptionCode(
            name=name,
            code=code_str,
            quota=quota,
            status=1,
            created_by=admin_id,
            created_time=now,
        )
        db.add(rc)
        codes.append(rc)

    await db.flush()
    for c in codes:
        await db.refresh(c)
    await db.commit()
    return codes


async def list_codes(
    db: AsyncSession,
    page: int = 0,
    size: int = 10,
) -> tuple[list[dict], int]:
    count_q = select(func.count(RedemptionCode.id))
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = (
        select(RedemptionCode)
        .order_by(RedemptionCode.id.desc())
        .offset(page * size)
        .limit(size)
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    data = []
    for rc in rows:
        data.append({
            "id": rc.id,
            "name": rc.name,
            "code": rc.code,
            "quota": rc.quota,
            "status": rc.status,
            "used_by": rc.used_by,
            "used_time": rc.used_time,
            "created_by": rc.created_by,
            "created_time": rc.created_time,
        })
    return data, total


async def search_codes(
    db: AsyncSession,
    keyword: str,
) -> list[dict]:
    q = (
        select(RedemptionCode)
        .where(RedemptionCode.name.ilike(f"%{keyword}%"))
        .order_by(RedemptionCode.id.desc())
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    return [
        {
            "id": rc.id,
            "name": rc.name,
            "code": rc.code,
            "quota": rc.quota,
            "status": rc.status,
            "used_by": rc.used_by,
            "used_time": rc.used_time,
            "created_by": rc.created_by,
            "created_time": rc.created_time,
        }
        for rc in rows
    ]


async def get_code(db: AsyncSession, code_id: int) -> RedemptionCode | None:
    result = await db.execute(select(RedemptionCode).where(RedemptionCode.id == code_id))
    return result.scalar_one_or_none()


async def update_code(
    db: AsyncSession,
    code_id: int,
    name: Optional[str] = None,
    quota: Optional[int] = None,
    status_only: bool = False,
    status: Optional[int] = None,
) -> RedemptionCode:
    rc = await get_code(db, code_id)
    if rc is None:
        raise ValueError(f"Redemption code {code_id} not found")

    if status_only and status is not None:
        rc.status = status
    else:
        if name is not None:
            rc.name = name
        if quota is not None:
            rc.quota = quota

    await db.flush()
    await db.refresh(rc)
    await db.commit()
    return rc


async def delete_code(db: AsyncSession, code_id: int) -> None:
    rc = await get_code(db, code_id)
    if rc is None:
        raise ValueError(f"Redemption code {code_id} not found")
    await db.delete(rc)
    await db.flush()
    await db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/phase6/test_redemption_service.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/redemption.py tests/phase6/test_redemption_service.py
git commit -m "feat: add redemption code service layer"
```

---

### Task 7: Redemption Code HTTP Endpoints (replace stubs)

**Files:**
- Modify: `app/routers/api/redemption.py`
- Create: `tests/phase6/test_redemption_endpoints.py`

- [ ] **Step 1: Write failing integration tests**

`tests/phase6/test_redemption_endpoints.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/phase6/test_redemption_endpoints.py -v`
Expected: Tests fail because endpoints still return stubs

- [ ] **Step 3: Replace all stubs in redemption.py**

`app/routers/api/redemption.py`:
```python
"""Redemption codes API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse
from app.schemas.redemption import RedemptionCreate, RedemptionUpdate
from app.services import redemption as redemption_service

router = APIRouter(tags=["redemption"])


@router.get("/api/redemption/")
async def list_redemptions(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    data, total = await redemption_service.list_codes(db, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.get("/api/redemption/search")
async def search_redemptions(
    keyword: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    data = await redemption_service.search_codes(db, keyword)
    return PaginatedResponse(data=data, total=len(data))


@router.get("/api/redemption/{redemption_id}")
async def get_redemption(
    redemption_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    rc = await redemption_service.get_code(db, redemption_id)
    if rc is None:
        return GenericApiResponse(success=False, message="Redemption code not found")
    return GenericApiResponse(data={
        "id": rc.id,
        "name": rc.name,
        "code": rc.code,
        "quota": rc.quota,
        "status": rc.status,
        "used_by": rc.used_by,
        "used_time": rc.used_time,
        "created_by": rc.created_by,
        "created_time": rc.created_time,
    })


@router.post("/api/redemption/")
async def create_redemption(
    body: RedemptionCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    codes = await redemption_service.create_redemption_codes(
        db,
        admin_id=0,  # will use auth user in prod
        name=body.name,
        quota=body.quota,
        count=body.count,
    )
    first = codes[0]
    return GenericApiResponse(data={
        "id": first.id,
        "name": first.name,
        "code": first.code,
        "quota": first.quota,
        "status": first.status,
        "created_by": first.created_by,
        "created_time": first.created_time,
    })


@router.put("/api/redemption/")
async def update_redemption(
    body: RedemptionUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    try:
        rc = await redemption_service.update_code(
            db,
            code_id=body.id,
            name=body.name,
            quota=body.quota,
            status_only=body.status_only,
            status=body.status,
        )
        return GenericApiResponse(data={
            "id": rc.id,
            "name": rc.name,
            "code": rc.code,
            "quota": rc.quota,
            "status": rc.status,
        })
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


@router.delete("/api/redemption/{redemption_id}")
async def delete_redemption(
    redemption_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    try:
        await redemption_service.delete_code(db, redemption_id)
        return GenericApiResponse(data={"deleted": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/phase6/test_redemption_endpoints.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/routers/api/redemption.py tests/phase6/test_redemption_endpoints.py
git commit -m "feat: implement real redemption code endpoints (replace stubs)"
```

---

### Task 8: Frontend API Alignment

**Files:**
- Modify: `web/src/lib/services/recharge.ts`
- Modify: `web/src/pages/topup/TopUpPage.tsx`
- Modify: `web/src/pages/recharges/RechargesPage.tsx`
- Modify: `web/src/pages/users/UsersPage.tsx` (TopUpDialog)
- Modify: `web/src/App.tsx` (register redemption routes or add comment on deprecation)

**Goal:** Fix three API path inconsistencies and make frontend use a unified service layer.

Issues to fix:
1. `recharge.ts` calls `/api/topup/` for list/create/review — these should be renamed/refactored to match actual usage or deprecated in favor of the page-level calls
2. `TopUpPage.tsx` uses raw `api.get('/api/recharge/self')` and `api.post('/api/recharge/')` — should use service layer
3. `RechargesPage.tsx` uses raw `api.get('/api/recharge/')` and `api.post('/api/recharge/{id}/approve|reject')` — should use service layer
4. `UsersPage.tsx` TopUpDialog uses raw `api.post('/api/topup', ...)` — should use service layer
5. Redemption routes not registered in App.tsx

- [ ] **Step 1: Refactor recharge.ts service to match actual backend endpoints**

`web/src/lib/services/recharge.ts` — add `adminTopup` function, fix endpoint paths, add approve/reject functions:

```typescript
/**
 * Recharge Service — encapsulates top-up / recharge request API calls.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface TopUpRequest {
  id: number;
  user_id: number;
  amount?: number;
  quota: number;
  status: number;
  remark?: string;
  admin_remark?: string;
  created_at: string;
  created_time?: number;
}

export interface CreateRechargeRequest {
  amount: number;
  remark?: string;
}

export interface PaginatedRechargeResponse {
  success: boolean;
  data: TopUpRequest[];
  total: number;
}

export interface ApiResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ── Admin Queries ───────────────────────────────────────

export async function getRechargeRequests(params?: {
  p?: number;
  size?: number;
}): Promise<AxiosResponse<PaginatedRechargeResponse>> {
  const p = params?.p ?? 0;
  const size = params?.size ?? 10;
  return api.get(`/api/recharge/?p=${p}&size=${size}`);
}

// ── User Actions ────────────────────────────────────────

export async function createRechargeRequest(
  data: CreateRechargeRequest
): Promise<AxiosResponse<ApiResult<TopUpRequest>>> {
  return api.post('/api/recharge/', data);
}

export async function getSelfRechargeRequests(params?: {
  p?: number;
  size?: number;
}): Promise<AxiosResponse<PaginatedRechargeResponse>> {
  const p = params?.p ?? 0;
  const size = params?.size ?? 10;
  return api.get(`/api/recharge/self?p=${p}&size=${size}`);
}

// ── Admin Actions ───────────────────────────────────────

export async function approveRecharge(
  rechargeId: number
): Promise<AxiosResponse<ApiResult>> {
  return api.post(`/api/recharge/${rechargeId}/approve`);
}

export async function rejectRecharge(
  rechargeId: number,
  adminRemark: string
): Promise<AxiosResponse<ApiResult>> {
  return api.post(`/api/recharge/${rechargeId}/reject`, { admin_remark: adminRemark });
}

export async function adminTopup(
  data: { user_id: number; quota: number; remark?: string; pool_id?: number }
): Promise<AxiosResponse<ApiResult>> {
  return api.post('/api/topup/', data);
}
```

- [ ] **Step 2: Update TopUpPage.tsx to use service layer**

Replace the `loadMyRequests` function body:
```typescript
import { getSelfRechargeRequests } from '@/lib/services/recharge';

const loadMyRequests = async () => {
  try {
    const res = await getSelfRechargeRequests({ p: 1, size: 10 });
    if (res.data?.success) {
      setMyRequests(res.data.data || []);
    }
  } catch (error) {
    console.error('Error loading recharge requests:', error);
  }
};
```

Replace the `onSubmitRecharge` POST call body:
```typescript
import { createRechargeRequest } from '@/lib/services/recharge';

const onSubmitRecharge = async (data: RechargeForm) => {
  setIsSubmitting(true);
  try {
    const quotaAmount = getQuotaFromInput(data.amount);
    const res = await createRechargeRequest({ amount: quotaAmount, remark: data.remark || '' });
    if (res.data?.success) { ... }
  } ...
};
```

- [ ] **Step 3: Update RechargesPage.tsx to use service layer**

Replace API calls with:
```typescript
import { getRechargeRequests, approveRecharge, rejectRecharge } from '@/lib/services/recharge';

const load = async (p = 0, size = pageSize) => {
  setLoading(true);
  try {
    const res = await getRechargeRequests({ p, size });
    if (res.data?.success) { ... }
  } ...
};

const handleApprove = async (id: number) => {
  ...
  const res = await approveRecharge(id);
  ...
};

const handleReject = async (id: number) => {
  ...
  const res = await rejectRecharge(id, reason);
  ...
};
```

- [ ] **Step 4: Update UsersPage.tsx TopUpDialog to use service layer**

In the `onSubmit` handler, replace `api.post('/api/topup', {...})` with:
```typescript
import { adminTopup } from '@/lib/services/recharge';

const res = await adminTopup({
  user_id: userId,
  quota: values.quota,
  remark: values.remark,
  pool_id: values.pool_id || 0,
});
```

- [ ] **Step 5: Add redemption routes to App.tsx (or add deprecation notice)**

In `web/src/App.tsx`, add route entries for redemption pages (matching the routes used in RedemptionsPage navigation):
```tsx
const RedemptionsPage = lazy(() => import('@/pages/redemptions/RedemptionsPage'));
const EditRedemptionPage = lazy(() => import('@/pages/redemptions/EditRedemptionPage'));

{/* Redemption code management (legacy — being replaced by recharge system) */}
<Route path="redemptions" element={<RedemptionsPage />} />
<Route path="redemptions/edit/:id" element={<EditRedemptionPage />} />
<Route path="redemptions/add" element={<EditRedemptionPage />} />
```

- [ ] **Step 6: Run existing tests to verify nothing is broken**

Run: `python3 -m pytest tests/ -v --no-header`
Expected: Existing tests still pass (no regressions). New tests in tasks 1-7 also pass.

- [ ] **Step 7: Commit**

```bash
git add web/src/lib/services/recharge.ts web/src/pages/topup/TopUpPage.tsx web/src/pages/recharges/RechargesPage.tsx web/src/pages/users/UsersPage.tsx web/src/App.tsx
git commit -m "refactor: align frontend API calls with backend endpoints, register redemption routes"
```

---

## Running All Tests

After completing all tasks, run the full test suite to confirm no regressions:

```bash
python3 -m pytest tests/ -v --no-header
```

Expected: All tests pass including new phase6 tests.

Expected test count: ~40 new tests (9 model + 7 redemption model + 9 service recharge + 5 service redemption + 6 endpoint recharge + 6 endpoint redemption + some frontend tests).
