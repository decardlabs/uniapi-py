from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from starlette.responses import FileResponse

router = APIRouter(tags=["web"])


@router.get("/")
async def index():
    """Serve SPA root."""
    try:
        with open("web/build/modern/index.html") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>UniAPI Python Backend (Phase 1 MVP)</h1>")


@router.get("/login")
async def login_page():
    """SPA login page fallback."""
    try:
        with open("web/build/modern/index.html") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Login - UniAPI</h1>")


@router.get("/{path:path}")
async def spa_fallback(path: str):
    """Serve SPA for all non-API, non-v1 paths."""
    if path.startswith(("api/", "v1/")):
        from fastapi import HTTPException

        raise HTTPException(status_code=404)

    try:
        with open("web/build/modern/index.html") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse(f"<h1>UniAPI Python Backend</h1><p>Path: /{path}</p>")
