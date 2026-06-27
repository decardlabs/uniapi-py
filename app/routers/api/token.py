from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import token_auth, user_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse
from app.schemas.management import TokenCreateRequest, TokenUpdateRequest
from app.schemas.user import TokenResponse
from app.services import token as token_service

router = APIRouter(tags=["tokens"])


def _token_to_response(t) -> dict:
    key_display = t.key
    if not key_display.startswith("sk-"):
        key_display = "sk-" + key_display
    return TokenResponse(
        id=t.id,
        name=t.name,
        key=key_display,
        status=t.status,
        created_time=t.created_time // 1000 if t.created_time else 0,
        accessed_time=t.accessed_time // 1000 if t.accessed_time else 0,
        expired_time=t.expired_time // 1000 if t.expired_time else 0,
        models=t.models,
        subnet=t.subnet,
        created_at=t.created_at // 1000 if t.created_at else 0,
        updated_at=t.updated_at // 1000 if t.updated_at else 0,
    ).model_dump()


# Specific routes before parameterized ones




@router.get("/api/token/balance")
async def token_balance(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(token_auth),
):
    user = request.state.user
    return GenericApiResponse(data={"balance": user.balance if hasattr(user, 'balance') else user.quota})


@router.get("/api/token/transactions")
async def token_transactions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(token_auth),
):
    return GenericApiResponse(data=[])


@router.get("/api/token/logs")
async def token_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(token_auth),
):
    return GenericApiResponse(data=[])


# Standard CRUD routes


@router.get("/api/token/")
async def list_tokens(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    tokens, total = await token_service.list_tokens(db, user_id=user.id, page=p, size=size)
    return PaginatedResponse(
        data=[_token_to_response(t) for t in tokens],
        total=total,
    )


@router.get("/api/token/search")
async def search_tokens(
    keyword: str = "",
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    tokens, total = await token_service.search_tokens(
        db, user_id=user.id, keyword=keyword, page=p, size=size
    )
    return PaginatedResponse(
        data=[_token_to_response(t) for t in tokens],
        total=total,
    )


@router.get("/api/token/{token_id}")
async def get_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    token = await token_service.get_token_by_id(db, user.id, token_id)
    if not token:
        return GenericApiResponse(success=False, message="Token not found")
    return GenericApiResponse(data=_token_to_response(token))


@router.post("/api/token/")
async def create_token(
    body: TokenCreateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    token = await token_service.create_token(
        db,
        user_id=user.id,
        name=body.name or "default",
        expired_time=int(body.expired_time) if body.expired_time else -1,
        models=body.models or None,
        subnet=body.subnet or None,
    )
    return GenericApiResponse(data=_token_to_response(token))


@router.put("/api/token/")
async def update_token(
    body: TokenUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    token_id = body.id
    if not token_id:
        return GenericApiResponse(success=False, message="Token ID required")

    token = await token_service.update_token(
        db,
        user_id=user.id,
        token_id=token_id,
        name=body.name,
        expired_time=body.expired_time,
        models=body.models,
        subnet=body.subnet,
        status=body.status,
    )
    return GenericApiResponse(data=_token_to_response(token))


@router.delete("/api/token/{token_id}")
async def delete_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    await token_service.delete_token(db, user.id, token_id)
    return GenericApiResponse(message="Token deleted")
