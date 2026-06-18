"""Test configuration and fixtures."""

import os
import pytest
from httpx import ASGITransport, AsyncClient

# Use a test-specific database
os.environ.setdefault("SQLITE_PATH", "/tmp/uniapi_test.db")

from app.main import app
from app.database import engine
from app.models.base import Base
from app.models.user import User
from app.models.token import Token
from app.models.option import Option
from app.services.auth import hash_password


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
                quota=1000000000,
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
            }.items():
                result = await db.execute(select(Option).where(Option.key == key))
                if not result.scalar_one_or_none():
                    db.add(Option(key=key, value=value, created_at=now))

            await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
