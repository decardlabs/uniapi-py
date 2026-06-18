from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from app.config import settings
from app.database import async_session_factory, engine
from app.exceptions import AppException, app_exception_handler
from app.models.base import Base
from app.relay.registry import registry
from app.relay.adaptors.deepseek.adaptor import DeepSeekAdaptor, DEEPSEEK_CHANNEL_TYPE


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: initialize DB and register adaptors."""
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default data
    await _seed_defaults()

    # Register DeepSeek adaptor
    registry.register(DEEPSEEK_CHANNEL_TYPE, DeepSeekAdaptor)

    yield

    # Cleanup
    await engine.dispose()


async def _seed_defaults():
    """Create root user and default options if they don't exist."""
    from app.models.option import Option
    from app.models.user import User
    from app.services.auth import hash_password

    async with async_session_factory() as db:
        # Create root user if not exists
        result = await db.execute(select(User).where(User.username == "root"))
        if not result.scalar_one_or_none():
            now = int(time.time() * 1000)
            root = User(
                username="root",
                password=hash_password("123456"),
                display_name="Root",
                role=100,
                status=1,
                quota=1000000000,
                used_quota=0,
                group="default",
                access_token="root-access-token",
                created_at=now,
                updated_at=now,
            )
            db.add(root)
            await db.flush()

            from app.services.auth import create_default_token

            await create_default_token(db, root.id)

        # Add default options
        from app.models.token import Token

        default_options = {
            "SystemName": "UniAPI",
            "Logo": "",
            "Footer": "",
            "Notice": "",
            "About": "",
            "HomePageContent": "",
            "ServerAddress": "",
            "PasswordLoginEnabled": "true",
            "PasswordRegisterEnabled": "true",
            "RegisterEnabled": "true",
            "EmailVerificationEnabled": "false",
        }
        for key, value in default_options.items():
            result = await db.execute(select(Option).where(Option.key == key))
            if not result.scalar_one_or_none():
                db.add(Option(key=key, value=value, created_at=int(time.time() * 1000)))

        await db.commit()


def create_app() -> FastAPI:
    app = FastAPI(
        title="UniAPI Python Backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(AppException, app_exception_handler)

    # Register routers
    from app.routers.api.auth import router as auth_router
    from app.routers.api.status import router as status_router
    from app.routers.api.web import router as web_router
    from app.routers.api.admin_user import router as admin_user_router
    from app.routers.api.token import router as token_router
    from app.routers.api.log import router as log_router
    from app.routers.api.options import router as options_router
    from app.routers.api.channel_types import router as channel_types_router
    from app.routers.v1.relay import router as relay_router

    app.include_router(status_router)
    app.include_router(auth_router)
    app.include_router(admin_user_router)
    app.include_router(token_router)
    app.include_router(log_router)
    app.include_router(options_router)
    app.include_router(channel_types_router)
    app.include_router(web_router)
    app.include_router(relay_router)

    return app


app = create_app()
