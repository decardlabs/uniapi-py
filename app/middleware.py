from __future__ import annotations

import time
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Add request timing info for logging."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.time()
        response = await call_next(request)
        elapsed = int((time.time() - start) * 1000)
        response.headers["X-Request-Time"] = str(elapsed)
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        import uuid

        request_id = request.headers.get("X-Request-Id", uuid.uuid4().hex)
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
