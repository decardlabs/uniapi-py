"""MCP (Model Context Protocol) server management endpoints (placeholder).

Full implementation requires MCP server database model and business logic.
Currently returns empty structures to allow frontend to render.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import user_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["mcp"])


@router.get("/api/mcp_servers/")
async def list_mcp_servers(
    request: Request,
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    sort: str = "id",
    order: str = "desc",
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    return PaginatedResponse(data=[], total=0)


@router.get("/api/mcp_servers/{server_id}")
async def get_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    raise HTTPException(status_code=404, detail="MCP server not found")


@router.post("/api/mcp_servers/")
async def create_mcp_server(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    return GenericApiResponse(data={"id": 0})


@router.put("/api/mcp_servers/{server_id}")
async def update_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    return GenericApiResponse(data={"id": server_id})


@router.delete("/api/mcp_servers/{server_id}")
async def delete_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    return GenericApiResponse(data={"deleted": True})


@router.post("/api/mcp_servers/{server_id}/sync")
async def sync_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    raise HTTPException(status_code=404, detail="MCP server not found")


@router.post("/api/mcp_servers/{server_id}/test")
async def test_mcp_server(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    raise HTTPException(status_code=404, detail="MCP server not found")


@router.get("/api/mcp_servers/{server_id}/tools")
async def list_mcp_server_tools(
    server_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    return GenericApiResponse(data=[])
