"""Seed script for CI E2E tests - creates root user and default options."""
import asyncio, os

os.environ['SQLITE_PATH'] = '/tmp/uniapi_ci.db'

from app.database import engine, async_session_factory
from app.models.base import Base
from app.models.user import User
from app.services.auth import hash_password, create_default_token
from app.models.option import Option
from sqlalchemy import select


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.username == 'root'))
        if not result.scalar_one_or_none():
            import time
            now = int(time.time() * 1000)
            root = User(
                username='root',
                password=hash_password('123456'),
                display_name='Root',
                role=100,
                status=1,
                group='default',
                access_token='root-access-token-ci',
                created_at=now,
                updated_at=now,
            )
            db.add(root)
            await create_default_token(db, root.id)
            for key, value in [
                ('SystemName', 'UniAPI'),
                ('PasswordLoginEnabled', 'true'),
                ('RegisterEnabled', 'true'),
                ('LogConsumeEnabled', 'true'),
                ('QuotaPerUnit', '500000'),
            ]:
                db.add(Option(key=key, value=value, created_at=now))
            await db.commit()

asyncio.run(seed())
