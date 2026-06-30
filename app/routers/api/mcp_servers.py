"""MCP (Model Context Protocol) server management endpoints."""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.models.mcp_server import MCPServer
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["mcp"])


# ── Request schemas ─────────────────────────────────────────────────────

class MCPServerCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    status: int = Field(default=1, ge=0, le=1)
    priority: int = Field(default=0)
    base_url: str | None = Field(default=None, max_length=1024)
    protocol: str = Field(default="streamable_http")
    auth_type: str = Field(default="none")
    api_key: str | None = Field(default=None, max_length=512)
    headers: dict | None = None
    tool_whitelist: list | None = None
    tool_blacklist: list | None = None
    tool_pricing: dict | None = None
    auto_sync_enabled: bool = True
    auto_sync_interval_minutes: int = 60


class MCPServerUpdateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    status: int | None = Field(default=None, ge=0, le=1)
    priority: int | None = None
    base_url: str | None = Field(default=None, max_length=1024)
    protocol: str | None = None
    auth_type: str | None = None
    api_key: str | None = Field(default=None, max_length=512)
    headers: dict | None = None
    tool_whitelist: list | None = None
    tool_blacklist: list | None = None
    tool_pricing: dict | None = None
    auto_sync_enabled: bool | None = None
    auto_sync_interval_minutes: int | None = None


# ── Serialization helpers ──────────────────────────────────────────────

def _json_str(val):
    """Serialize a value to a JSON string for DB storage."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def _load_json(val, default=None):
    """Deserialize a JSON string from DB to a Python object."""
    if val is None or val == "":
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def _server_to_dict(s: MCPServer) -> dict:
    """Convert an MCPServer ORM object to a plain dict for API responses."""
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description or "",
        "status": s.status,
        "priority": s.priority,
        "base_url": s.base_url,
        "protocol": s.protocol,
        "auth_type": s.auth_type,
        "api_key": s.api_key or "",
        "headers": _load_json(s.headers, {}),
        "tool_whitelist": _load_json(s.tool_whitelist, []),
        "tool_blacklist": _load_json(s.tool_blacklist, []),
        "tool_pricing": _load_json(s.tool_pricing, {}),
        "auto_sync_enabled": s.auto_sync_enabled,
        "auto_sync_interval_minutes": s.auto_sync_interval_minutes,
        "last_sync_at": s.last_sync_at,
        "last_sync_status": s.last_sync_status,
        "last_test_at": s.last_test_at,
        "last_test_status": s.last_test_status,
        "tool_count": s.tool_count,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


# ── Fields that arrive as JSON objects/arrays from the frontend ────────
_JSON_FIELDS = {"headers", "tool_whitelist", "tool_blacklist", "tool_pricing"}


# ── Static routes (defined before parameterized routes) ────────────────

@router.get("/api/mcp_servers/")
async def list_mcp_servers(
    request: Request,
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    sort: str = "id",
    order: str = "desc",
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    ALLOWED_MCP_SORT_COLUMNS = {"id", "name", "type", "status", "priority", "created_time", "created_at"}
    sort = sort if sort in ALLOWED_MCP_SORT_COLUMNS else "id"
    sort_col = getattr(MCPServer, sort, MCPServer.id)
    order_fn = sort_col.desc() if order == "desc" else sort_col.asc()

    total = await db.scalar(select(func.count()).select_from(MCPServer)) or 0
    result = await db.execute(
        select(MCPServer).order_by(order_fn).offset(p * size).limit(size)
    )
    servers = result.scalars().all()

    return PaginatedResponse(
        data=[
            {"server": _server_to_dict(s), "tool_count": s.tool_count}
            for s in servers
        ],
        total=total,
    )


@router.post("/api/mcp_servers/")
async def create_mcp_server(
    body: MCPServerCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    now_ms = int(time.time() * 1000)
    data = body.model_dump()

    auto_sync_enabled = data.get("auto_sync_enabled", True)
    if isinstance(auto_sync_enabled, bool):
        auto_sync_enabled = 1 if auto_sync_enabled else 0

    server = MCPServer(
        name=data.get("name", ""),
        description=data.get("description"),
        status=data.get("status", 1),
        priority=data.get("priority", 0),
        base_url=data.get("base_url", ""),
        protocol=data.get("protocol", "streamable_http"),
        auth_type=data.get("auth_type", "none"),
        api_key=data.get("api_key"),
        headers=_json_str(data.get("headers")),
        tool_whitelist=_json_str(data.get("tool_whitelist")),
        tool_blacklist=_json_str(data.get("tool_blacklist")),
        tool_pricing=_json_str(data.get("tool_pricing")),
        auto_sync_enabled=auto_sync_enabled,
        auto_sync_interval_minutes=data.get("auto_sync_interval_minutes", 60),
        created_at=now_ms,
        updated_at=now_ms,
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    return GenericApiResponse(data={"id": server.id})


# ── {server_id} sub-routes (static paths before parameterized) ─────────

@router.post("/api/mcp_servers/{server_id}/sync")
async def sync_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return GenericApiResponse(data={"synced": True})


@router.post("/api/mcp_servers/{server_id}/test")
async def test_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return GenericApiResponse(data={"tool_count": 0})


@router.get("/api/mcp_servers/{server_id}/tools")
async def list_mcp_server_tools(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return GenericApiResponse(data=[])


# ── Parameterized routes (defined last) ────────────────────────────────

@router.get("/api/mcp_servers/{server_id}")
async def get_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return GenericApiResponse(data=_server_to_dict(server))


@router.put("/api/mcp_servers/{server_id}")
async def update_mcp_server(
    server_id: int,
    body: MCPServerUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    data = body.model_dump(exclude_none=True)

    for field in (
        "name",
        "description",
        "status",
        "priority",
        "base_url",
        "protocol",
        "auth_type",
        "api_key",
        "headers",
        "tool_whitelist",
        "tool_blacklist",
        "tool_pricing",
        "auto_sync_interval_minutes",
    ):
        if field in data:
            val = data[field]
            if field in _JSON_FIELDS:
                val = _json_str(val)
            setattr(server, field, val)

    # Handle auto_sync_enabled with bool -> int conversion
    if "auto_sync_enabled" in data:
        val = data["auto_sync_enabled"]
        server.auto_sync_enabled = 1 if val else 0

    server.updated_at = int(time.time() * 1000)
    await db.commit()
    await db.refresh(server)

    return GenericApiResponse(data={"id": server.id})


@router.delete("/api/mcp_servers/{server_id}")
async def delete_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    await db.delete(server)
    await db.commit()

    return GenericApiResponse(data={"deleted": True})
