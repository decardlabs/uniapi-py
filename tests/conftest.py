"""Test configuration and fixtures."""

import os
import pytest
from httpx import ASGITransport, AsyncClient

# Use a test-specific database
os.environ.setdefault("SQLITE_PATH", "/tmp/uniapi_test.db")

from app.main import app
from app.database import engine, async_session_factory
from app.models.base import Base
from app.models.user import User
from app.models.token import Token
from app.models.option import Option
from app.services.auth import hash_password


class FakeRedisClient:
    """In-memory mock of BudgetRedisClient for tests.

    Implements the same interface as BudgetRedisClient without real Redis.
    """

    def __init__(self):
        self._store: dict[str, float] = {}
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    async def initialize(self):
        pass

    async def get_consumed(self, user_id: int, period: str) -> float:
        return self._store.get(f"budget:consumed:{user_id}:{period}", 0.0)

    async def get_frozen(self, user_id: int, period: str) -> float:
        return self._store.get(f"budget:frozen:{user_id}:{period}", 0.0)

    async def freeze(self, user_id: int, period: str, amount: float) -> float:
        key = f"budget:frozen:{user_id}:{period}"
        self._store[key] = self._store.get(key, 0.0) + amount
        return self._store[key]

    async def settle(self, user_id: int, period: str, frozen_amount: float, actual_cost: float):
        frozen_key = f"budget:frozen:{user_id}:{period}"
        consumed_key = f"budget:consumed:{user_id}:{period}"
        current_frozen = self._store.get(frozen_key, 0.0)
        self._store[frozen_key] = max(0.0, current_frozen - frozen_amount)
        self._store[consumed_key] = self._store.get(consumed_key, 0.0) + actual_cost
        return self._store[consumed_key], self._store[frozen_key]

    async def close(self):
        pass


@pytest.fixture(scope="function")
async def client():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed test data
    from sqlalchemy import select
    from app.database import async_session_factory

    async with async_session_factory() as db:
        # Create root user
        result = await db.execute(select(User).where(User.username == "root"))
        if not result.scalar_one_or_none():
            import time

            now = int(time.time() * 1000)
            root = User(
                username="root",
                password=hash_password("123456"),
                display_name="Root",
                role=100,
                status=1,
                group="default",
                access_token="root-access-token-test",
                created_at=now,
                updated_at=now,
            )
            db.add(root)
            await db.flush()

            from app.services.auth import create_default_token
            await create_default_token(db, root.id)

            for key, value in {
                "SystemName": "UniAPI",
                "PasswordLoginEnabled": "true",
                "PasswordRegisterEnabled": "true",
                "RegisterEnabled": "true",
                "EmailVerificationEnabled": "false",
                "TurnstileCheckEnabled": "false",
                "TurnstileSiteKey": "",
                "GitHubOAuthEnabled": "false",
                "GitHubClientId": "",
                "QuotaPerUnit": "500000",
                "DisplayInCurrencyEnabled": "false",
                "Theme": "modern",
                "LogConsumeEnabled": "true",
            }.items():
                result = await db.execute(select(Option).where(Option.key == key))
                if not result.scalar_one_or_none():
                    db.add(Option(key=key, value=value, created_at=now))

            await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
