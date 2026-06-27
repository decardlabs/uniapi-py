from __future__ import annotations

import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from starlette.responses import FileResponse

router = APIRouter(tags=["web"])

# Frontend build output directory (project root /webui/)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "webui")


def _serve_index() -> HTMLResponse:
    """Read and return the SPA index.html."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    try:
        with open(index_path) as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>UniAPI Python Backend</h1>")


@router.get("/")
async def index():
    return _serve_index()


@router.get("/login")
async def login_page():
    return _serve_index()


@router.get("/assets/{path:path}")
async def serve_assets(path: str):
    """Serve static assets from the frontend build."""
    asset_path = os.path.join(FRONTEND_DIR, "assets", path)
    if os.path.isfile(asset_path):
        return FileResponse(asset_path)
    return HTMLResponse("", status_code=404)


@router.get("/{path:path}")
async def spa_fallback(path: str):
    """Serve SPA for all non-API, non-v1 paths."""
    if path.startswith(("api/", "v1/")):
        from fastapi import HTTPException
        raise HTTPException(status_code=404)

    # Try serving static files directly
    file_path = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    return _serve_index()
