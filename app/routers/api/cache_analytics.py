"""Cache analytics API endpoint.

Returns structured cache analytics data (summary, timeseries, breakdown, compare).
Currently returns empty data since cache tracking requires relay-path instrumentation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.schemas.common import GenericApiResponse

router = APIRouter(tags=["cache-analytics"])


@router.get("/api/user/cache-analytics")
async def cache_analytics(
    request: Request,
    from_date: str = Query(""),
    to_date: str = Query(""),
    model_name: str = Query(""),
    channel_id: str = Query(""),
    request_format: str = Query(""),
    compare_date: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Return cache analytics data (placeholder — returns empty structure)."""
    return GenericApiResponse(data={
        "summary": {
            "request_count": 0,
            "prompt_tokens": 0,
            "cached_prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_completion_tokens": 0,
            "quota": 0,
            "cache_hit_rate": 0,
            "estimated_savings_rate": 0,
        },
        "timeseries": [],
        "breakdown": [],
        "compare": {
            "compare_date": compare_date or from_date,
            "before": {
                "request_count": 0,
                "prompt_tokens": 0,
                "cached_prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_completion_tokens": 0,
                "quota": 0,
                "cache_hit_rate": 0,
                "estimated_savings_rate": 0,
            },
            "after": {
                "request_count": 0,
                "prompt_tokens": 0,
                "cached_prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_completion_tokens": 0,
                "quota": 0,
                "cache_hit_rate": 0,
                "estimated_savings_rate": 0,
            },
        },
    })
