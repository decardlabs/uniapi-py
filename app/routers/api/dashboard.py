"""Dashboard API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth, user_auth
from app.models.log import Log
from app.models.user import User
from app.schemas.common import GenericApiResponse

router = APIRouter(tags=["dashboard"])


@router.get("/api/user/dashboard")
async def dashboard(
    request: Request,
    from_date: str = Query(""),
    to_date: str = Query(""),
    user_id: str = Query("0"),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard stats: usage aggregated by day/model/user/token."""
    user = await user_auth(request, db)
    is_admin = user.role >= 10

    # Build filter: user scope
    conditions = [Log.user_id == user.id]
    if is_admin and user_id not in ("", "0", "all"):
        try:
            uid = int(user_id)
            conditions = [Log.user_id == uid]
        except (ValueError, TypeError):
            pass

    # Date filter
    import time
    now = int(time.time() * 1000)
    week_ago = now - 7 * 24 * 3600 * 1000  # default: last 7 days
    if from_date:
        try:
            from datetime import datetime
            dt = datetime.strptime(from_date, "%Y-%m-%d")
            week_ago = int(dt.timestamp() * 1000)
        except ValueError:
            pass

    conditions.append(Log.created_at >= week_ago)

    # Optional end date filter
    if to_date:
        try:
            from datetime import datetime
            dt = datetime.strptime(to_date, "%Y-%m-%d")
            # End of the selected day
            end_ts = int(dt.timestamp() * 1000) + 86400_000
            conditions.append(Log.created_at <= end_ts)
        except ValueError:
            pass

    # Model-level aggregation
    from sqlalchemy import text
    model_q = (
        select(
            func.date(Log.created_at / 1000, "unixepoch").label("Day"),
            Log.model_name.label("ModelName"),
            func.count().label("RequestCount"),
            func.coalesce(func.sum(Log.cost), 0).label("Quota"),
            func.sum(Log.prompt_tokens).label("PromptTokens"),
            func.sum(Log.completion_tokens).label("CompletionTokens"),
        )
        .where(*conditions)
        .group_by(text("Day"), Log.model_name)
        .order_by(text("Day DESC"))
    )
    result = await db.execute(model_q)
    logs = [dict(r._mapping) for r in result.all()]

    # User-level aggregation (admin only)
    user_logs = []
    if is_admin:
        user_q = (
            select(
                func.date(Log.created_at / 1000, "unixepoch").label("Day"),
                Log.username.label("Username"),
                Log.user_id.label("UserId"),
                func.count().label("RequestCount"),
                func.coalesce(func.sum(Log.cost), 0).label("Quota"),
                func.sum(Log.prompt_tokens).label("PromptTokens"),
                func.sum(Log.completion_tokens).label("CompletionTokens"),
            )
            .where(*conditions)
            .group_by(text("Day"), Log.user_id)
            .order_by(text("Day DESC"))
        )
        result = await db.execute(user_q)
        user_logs = [dict(r._mapping) for r in result.all()]

    # Token-level aggregation (admin only)
    token_logs = []
    if is_admin:
        token_q = (
            select(
                func.date(Log.created_at / 1000, "unixepoch").label("Day"),
                Log.username.label("Username"),
                Log.token_name.label("TokenName"),
                Log.user_id.label("UserId"),
                func.count().label("RequestCount"),
                func.coalesce(func.sum(Log.cost), 0).label("Quota"),
                func.sum(Log.prompt_tokens).label("PromptTokens"),
                func.sum(Log.completion_tokens).label("CompletionTokens"),
            )
            .where(*conditions)
            .group_by(text("Day"), Log.token_name)
            .order_by(text("Day DESC"))
        )
        result = await db.execute(token_q)
        token_logs = [dict(r._mapping) for r in result.all()]

    return GenericApiResponse(data={
        "logs": logs,
        "user_logs": user_logs,
        "token_logs": token_logs,
        "quota": 0,
        "used_quota": 0,
    })


@router.get("/api/user/dashboard/users")
async def dashboard_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """List all users for dashboard filter (admin only)."""
    result = await db.execute(
        select(User.id, User.username).where(User.status == 1).order_by(User.id)
    )
    users = [{"id": r.id, "username": r.username} for r in result.all()]
    return GenericApiResponse(data=users)
