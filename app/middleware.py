"""Middleware: request timing, request ID, rate limiting, PII masking, audit logging."""
from __future__ import annotations

import json
import logging
import re
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Add request timing info for logging."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.time()
        response = await call_next(request)
        elapsed = int((time.time() - start) * 1000)
        response.headers["X-Request-Time"] = str(elapsed)
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to every response and store it in request.state.

    The request ID is made available to exception handlers via
    ``request.state.request_id`` so error responses always carry a trace ID.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-Id", uuid.uuid4().hex)
        # Store in request.state for exception handlers and downstream code
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory rate limiter per IP, with separate limits for API and relay paths."""

    def __init__(self, app, api_rpm: int = 480, relay_rpm: int = 480):
        super().__init__(app)
        self.api_rpm = api_rpm
        self.relay_rpm = relay_rpm
        self._hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )
        now = time.time()

        # Determine RPM based on path
        rpm = self.relay_rpm if request.url.path.startswith("/v1/") else self.api_rpm

        # Clean old entries
        self._hits[client_ip] = [t for t in self._hits.get(client_ip, []) if now - t < 60]

        if len(self._hits[client_ip]) >= rpm:
            request_id = getattr(request.state, "request_id", None)
            from app.schemas.error import build_error_response

            error_resp = build_error_response(
                code="UNIAPI_RATE_LIMITED",
                message="Rate limit exceeded",
                request_id=request_id,
            )
            return Response(
                content=json.dumps(error_resp),
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        self._hits[client_ip].append(now)
        return await call_next(request)


class PIIMaskMiddleware(BaseHTTPMiddleware):
    """Mask PII (phone, email, API keys) in request body for audit logging.

    Stores the masked body in ``request.state.masked_body`` so downstream
    middleware (e.g. audit loggers) can record it without exposing secrets.
    """

    # Ordered by specificity — higher-specificity patterns first to avoid
    # false partial matches (e.g. phone pattern swallowing ID card numbers).
    _patterns = [
        ("id_card", re.compile(r"\b\d{17}[\dXx]\b"), "[ID_CARD]"),
        ("phone", re.compile(r"\b1[3-9]\d{9}\b"), "[PHONE]"),
        ("email", re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "[EMAIL]"),
        ("api_key", re.compile(r"\bsk-[a-zA-Z0-9]{40,}\b"), "[API_KEY]"),
    ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.json()
                request.state.masked_body = self._mask_pii(body)
            except Exception:
                request.state.masked_body = None
        response = await call_next(request)
        return response

    def _mask_pii(self, data):
        if isinstance(data, str):
            for _name, pattern, replacement in self._patterns:
                data = pattern.sub(replacement, data)
            return data
        elif isinstance(data, dict):
            return {k: self._mask_pii(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._mask_pii(item) for item in data]
        return data


class AuditMiddleware(BaseHTTPMiddleware):
    """Log all API requests with timing, user, and path info."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.time()
        body_size = request.headers.get("content-length", 0)
        response = await call_next(request)
        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "AUDIT | %s %s | %d | %dms | %sB",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            body_size,
        )
        return response
