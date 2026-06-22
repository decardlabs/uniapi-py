"""Test configuration for phase6 service tests."""
import os

import pytest

# Use a test-specific database
os.environ.setdefault("SQLITE_PATH", "/tmp/uniapi_test.db")

from app.database import engine
from app.models.base import Base


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables for each test and drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
