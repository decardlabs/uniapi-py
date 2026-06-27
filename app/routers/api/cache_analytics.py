"""Cache analytics API endpoint.

Returns structured cache analytics data (summary, timeseries, breakdown, compare)
aggregated from the ``Log`` table, which already has ``cached_prompt_tokens``
populated by the relay pipeline.
"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.pricing import get_model_pricing
from app.database import get_db
from app.dependencies import admin_auth
from app.models.channel import Channel
from app.models.log import Log
from app.schemas.common import GenericApiResponse

router = APIRouter(tags=["cache-analytics"])

# ── Helpers ────────────────────────────────────────────────────────


def _empty_summary() -> dict[str, Any]:
    return {
        "request_count": 0,
        "prompt_tokens": 0,
        "cached_prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_completion_tokens": 0,
        "quota": 0,
        "cache_hit_rate": 0.0,
        "estimated_savings_rate": 0.0,
    }


def _get_model_prices(model_name: str) -> tuple[float, float]:
    """Return (input_price_per_1M, output_price_per_1M) from pricing table.

    Falls back to (1.0, 1.0) when the model is not found.
    """
    try:
        p = get_model_pricing(model_name)
        return p["input"], p["output"]
    except KeyError:
        return 1.0, 1.0


def _hit_rate(pt: int, cpt: int) -> float:
    if pt > 0:
        return min(cpt / pt, 1.0)
    return 0.0


def _enrich_summary_with_rates(
    row: dict[str, Any],
    breakdown_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Enrich a raw summary row with cache_hit_rate and estimated_savings_rate."""
    pt = row.get("prompt_tokens", 0) or 0
    cpt = row.get("cached_prompt_tokens", 0) or 0
    result = dict(row)
    result["cache_hit_rate"] = _hit_rate(pt, cpt)

    # Compute estimated_savings_rate from breakdown rows (per-model aggregates)
    total_without_cache = 0.0
    total_quota = 0.0
    for br in breakdown_rows:
        model = br.get("model_name", "") or ""
        pt_b = br.get("prompt_tokens", 0) or 0
        ct_b = br.get("completion_tokens", 0) or 0
        q_b = br.get("quota", 0) or 0
        input_price, output_price = _get_model_prices(model)
        total_without_cache += pt_b * input_price + ct_b * output_price
        total_quota += q_b

    if total_without_cache > 0:
        result["estimated_savings_rate"] = (total_without_cache - total_quota) / total_without_cache
    else:
        result["estimated_savings_rate"] = 0.0

    return result


def _enrich_timeseries_with_rates(
    timeseries_rows: list[dict[str, Any]],
    daily_model_rows: list[dict[str, Any]],
) -> None:
    """Enrich timeseries rows with cache_hit_rate and estimated_savings_rate in-place."""
    day_models: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in daily_model_rows:
        day_models[row["day"]].append(row)

    for ts_row in timeseries_rows:
        day = ts_row["day"]
        # cache_hit_rate
        pt = ts_row.get("prompt_tokens", 0) or 0
        cpt = ts_row.get("cached_prompt_tokens", 0) or 0
        ts_row["cache_hit_rate"] = _hit_rate(pt, cpt)

        # estimated_savings_rate from per-model breakdown for this day
        model_rows = day_models.get(day, [])
        total_without = 0.0
        total_q = 0.0
        for mr in model_rows:
            input_price, output_price = _get_model_prices(mr["model_name"])
            total_without += (mr["prompt_tokens"] or 0) * input_price + (mr["completion_tokens"] or 0) * output_price
            total_q += mr["quota"] or 0

        if total_without > 0:
            ts_row["estimated_savings_rate"] = (total_without - total_q) / total_without
        else:
            ts_row["estimated_savings_rate"] = 0.0


def _estimate_savings_rate_from_row(row: dict[str, Any]) -> float:
    """Compute estimated_savings_rate from summary row alone using 1:1 default pricing.

    Used by compare path where per-model breakdown is not available.
    """
    pt = row.get("prompt_tokens", 0) or 0
    ct = row.get("completion_tokens", 0) or 0
    q = row.get("quota", 0) or 0
    cost_without = pt + ct  # default 1:1 price per token
    if cost_without > 0:
        return (cost_without - q) / cost_without
    return 0.0


def _enrich_breakdown_with_rates(
    breakdown_rows: list[dict[str, Any]],
) -> None:
    """Enrich breakdown rows with cache_hit_rate and estimated_savings_rate in-place."""
    for row in breakdown_rows:
        if row.get("channel_name") is None:
            row["channel_name"] = ""
        if row.get("request_format") is None or row.get("request_format") == "":
            row["request_format"] = "chat"

        pt = row.get("prompt_tokens", 0) or 0
        cpt = row.get("cached_prompt_tokens", 0) or 0
        ct_b = row.get("completion_tokens", 0) or 0
        q_b = row.get("quota", 0) or 0
        model = row.get("model_name", "") or ""

        row["cache_hit_rate"] = _hit_rate(pt, cpt)

        input_price, output_price = _get_model_prices(model)
        cost_without = pt * input_price + ct_b * output_price
        if cost_without > 0:
            row["estimated_savings_rate"] = (cost_without - q_b) / cost_without
        else:
            row["estimated_savings_rate"] = 0.0


async def _query_summary(
    db: AsyncSession,
    conditions: list,
) -> dict[str, Any]:
    """Run a summary aggregation query and return the raw row."""
    stmt = (
        select(
            func.count().label("request_count"),
            func.sum(Log.prompt_tokens).label("prompt_tokens"),
            func.sum(Log.cached_prompt_tokens).label("cached_prompt_tokens"),
            func.sum(Log.completion_tokens).label("completion_tokens"),
            func.sum(Log.cached_completion_tokens).label("cached_completion_tokens"),
            func.coalesce(func.sum(Log.cost), 0).label("quota"),
        )
        .where(*conditions)
    )
    result = await db.execute(stmt)
    row = result.one()._mapping
    return {
        "request_count": row.request_count or 0,
        "prompt_tokens": row.prompt_tokens or 0,
        "cached_prompt_tokens": row.cached_prompt_tokens or 0,
        "completion_tokens": row.completion_tokens or 0,
        "cached_completion_tokens": row.cached_completion_tokens or 0,
        "quota": row.quota or 0,
    }


def _parse_date(date_str: str) -> int | None:
    """Parse YYYY-MM-DD to millisecond timestamp, or return None."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


# Default date range: last 7 days
_DEFAULT_RANGE_DAYS = 7


def _build_filters(
    from_date: str,
    to_date: str,
    model_name: str,
    channel_id: str,
    request_format: str,
) -> tuple[list, int, int]:
    """Build filter conditions and return (conditions, start_ts, end_ts)."""
    now_ms = int(time.time() * 1000)
    start_ts = now_ms - _DEFAULT_RANGE_DAYS * 24 * 3600 * 1000
    end_ts = 0

    conditions = [Log.type == 2]  # only consume-type logs

    # Date range
    parsed_from = _parse_date(from_date)
    if parsed_from is not None:
        start_ts = parsed_from
    conditions.append(Log.created_at >= start_ts)

    parsed_to = _parse_date(to_date)
    if parsed_to is not None:
        end_ts = parsed_to + 86400_000  # end of day
        conditions.append(Log.created_at <= end_ts)

    # Model name filter
    if model_name:
        conditions.append(Log.model_name == model_name)

    # Channel ID filter
    if channel_id:
        try:
            conditions.append(Log.channel_id == int(channel_id))
        except (ValueError, TypeError):
            pass

    # Request format filter (first word of content field)
    if request_format:
        conditions.append(Log.content.startswith(request_format + " "))

    return conditions, start_ts, end_ts


# ── Request format extraction expression ────────────────────────────
# The content field stores e.g. "ChatCompletion with deepseek-v4-pro"
# Extract the first word as the request format.
_FormatExpr = case(
    (
        Log.content.is_not(None) & (func.instr(Log.content, " ") > 0),
        func.substr(Log.content, 1, func.instr(Log.content, " ") - 1),
    ),
    else_=literal_column("'chat'"),
).label("request_format")


# ── Route ──────────────────────────────────────────────────────────


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
    """Return cache analytics data aggregated from relay logs."""
    conditions, start_ts, end_ts = _build_filters(
        from_date, to_date, model_name, channel_id, request_format,
    )

    # ── 1. Summary ────────────────────────────────────────────────
    summary_row = await _query_summary(db, conditions)

    # ── 2. Timeseries (daily) ─────────────────────────────────────
    ts_stmt = (
        select(
            func.date(Log.created_at / 1000, "unixepoch").label("day"),
            func.count().label("request_count"),
            func.sum(Log.prompt_tokens).label("prompt_tokens"),
            func.sum(Log.cached_prompt_tokens).label("cached_prompt_tokens"),
            func.sum(Log.completion_tokens).label("completion_tokens"),
            func.sum(Log.cached_completion_tokens).label("cached_completion_tokens"),
            func.coalesce(func.sum(Log.cost), 0).label("quota"),
        )
        .where(*conditions)
        .group_by(text("day"))
        .order_by(text("day ASC"))
    )
    result = await db.execute(ts_stmt)
    timeseries_rows = [dict(r._mapping) for r in result.all()]

    # ── 3. Daily-model breakdown for savings computation ──────────
    daily_model_stmt = (
        select(
            func.date(Log.created_at / 1000, "unixepoch").label("day"),
            Log.model_name.label("model_name"),
            func.sum(Log.prompt_tokens).label("prompt_tokens"),
            func.sum(Log.completion_tokens).label("completion_tokens"),
            func.coalesce(func.sum(Log.cost), 0).label("quota"),
        )
        .where(*conditions)
        .group_by(text("day"), Log.model_name)
        .order_by(text("day ASC"))
    )
    result = await db.execute(daily_model_stmt)
    daily_model_rows = [dict(r._mapping) for r in result.all()]

    # ── 4. Breakdown (model × channel × format) ──────────────────
    breakdown_stmt = (
        select(
            Log.model_name.label("model_name"),
            Log.channel_id.label("channel_id"),
            _FormatExpr,
            Channel.name.label("channel_name"),
            func.count().label("request_count"),
            func.sum(Log.prompt_tokens).label("prompt_tokens"),
            func.sum(Log.cached_prompt_tokens).label("cached_prompt_tokens"),
            func.sum(Log.completion_tokens).label("completion_tokens"),
            func.sum(Log.cached_completion_tokens).label("cached_completion_tokens"),
            func.coalesce(func.sum(Log.cost), 0).label("quota"),
        )
        .outerjoin(Channel, Log.channel_id == Channel.id)
        .where(*conditions)
        .group_by(Log.model_name, Log.channel_id, _FormatExpr)
        .order_by(Log.model_name, Log.channel_id)
    )
    result = await db.execute(breakdown_stmt)
    breakdown_rows = [dict(r._mapping) for r in result.all()]

    # ── 5. Compare (before/after a date) ──────────────────────────
    compare_data: dict[str, Any] = {
        "compare_date": compare_date or from_date,
        "before": _empty_summary(),
        "after": _empty_summary(),
    }

    compare_ts = _parse_date(compare_date or from_date)
    if compare_ts is not None:
        # Before: start_ts ≤ created_at < compare_ts
        before_conditions = [Log.type == 2, Log.created_at >= start_ts, Log.created_at < compare_ts]
        if end_ts > 0:
            before_conditions.append(Log.created_at <= end_ts)
        if model_name:
            before_conditions.append(Log.model_name == model_name)

        before_row = await _query_summary(db, before_conditions)

        # After: compare_ts ≤ created_at ≤ end_ts
        after_conditions = [Log.type == 2, Log.created_at >= compare_ts]
        if end_ts > 0:
            after_conditions.append(Log.created_at <= end_ts)
        if model_name:
            after_conditions.append(Log.model_name == model_name)

        after_row = await _query_summary(db, after_conditions)

        # Enrich compare summary rows with rates (lightweight, no per-model breakdown)
        for key, row in [("before", before_row), ("after", after_row)]:
            enriched = dict(row)
            pt = row.get("prompt_tokens", 0) or 0
            cpt = row.get("cached_prompt_tokens", 0) or 0
            enriched["cache_hit_rate"] = _hit_rate(pt, cpt)
            enriched["estimated_savings_rate"] = _estimate_savings_rate_from_row(row)
            compare_data[key] = enriched

    # ── 6. Enrich with computed rates ─────────────────────────────
    summary = _enrich_summary_with_rates(summary_row, breakdown_rows)
    _enrich_timeseries_with_rates(timeseries_rows, daily_model_rows)
    _enrich_breakdown_with_rates(breakdown_rows)

    return GenericApiResponse(data={
        "summary": summary,
        "timeseries": timeseries_rows,
        "breakdown": breakdown_rows,
        "compare": compare_data,
    })
