"""
Middleware: authentication, rate limiting, audit logging.

Inspired by agentfw's wire-tap + detect pipeline:
  - Auth: verify relay API key
  - Rate limit: per-key request limits
  - PII mask: redact sensitive data before forwarding to upstream
  - Audit: log all requests/responses
"""

import logging
import time
import json
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Verify relay API key from Authorization header."""

    def __init__(self, app, relay_api_key: str, public_paths: list[str] | None = None):
        super().__init__(app)
        self.relay_api_key = relay_api_key
        self.public_paths = public_paths or ["/health", "/docs", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if any(request.url.path.startswith(p) for p in self.public_paths):
            return await call_next(request)

        # Check Authorization header
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return Response(
                content=json.dumps({"error": {"message": "Missing API key", "type": "auth_error"}}),
                status_code=401,
                media_type="application/json",
            )

        token = auth[7:]
        if token != self.relay_api_key:
            return Response(
                content=json.dumps({"error": {"message": "Invalid API key", "type": "auth_error"}}),
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter (per IP)."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Clean old hits
        self._hits[client_ip] = [
            t for t in self._hits.get(client_ip, []) if now - t < 60
        ]

        if len(self._hits[client_ip]) >= self.rpm:
            return Response(
                content=json.dumps({"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}),
                status_code=429,
                media_type="application/json",
            )

        self._hits[client_ip].append(now)
        return await call_next(request)


class AuditMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses for audit trail."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()

        # Read request body
        body = b""
        if request.method == "POST":
            body = await request.body()
            # Re-create request body for downstream
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            request._receive = receive

        response = await call_next(request)

        latency_ms = int((time.time() - start) * 1000)

        # Audit log
        logger.info(
            "AUDIT | %s %s | %d | %dms | body_size=%d",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            len(body),
        )

        return response


class PIIMaskMiddleware(BaseHTTPMiddleware):
    """
    Mask PII (phone, email, API keys) in request before forwarding.

    Inspired by agentfw's MASK pipeline.
    """

    import re
    _patterns = {
        "phone": (re.compile(r"1[3-9]\d{9}"), "[PHONE]"),
        "email": (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "[EMAIL]"),
        "api_key": (re.compile(r"sk-[a-zA-Z0-9]{40,}"), "[API_KEY]"),
        "id_card": (re.compile(r"\d{17}[\dXx]"), "[ID_CARD]"),
    }

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and "/v1/chat/completions" in request.url.path:
            body = await request.body()
            if body:
                import json
                try:
                    data = json.loads(body)
                    masked = self._mask_pii(data)
                    new_body = json.dumps(masked).encode()
                    async def receive():
                        return {"type": "http.request", "body": new_body, "more_body": False}
                    request._receive = receive
                except (json.JSONDecodeError, KeyError):
                    pass

        return await call_next(request)

    def _mask_pii(self, data: Any) -> Any:
        """Recursively mask PII in request data."""
        if isinstance(data, str):
            for name, (pattern, replacement) in self._patterns.items():
                data = pattern.sub(replacement, data)
            return data
        elif isinstance(data, dict):
            return {k: self._mask_pii(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._mask_pii(item) for item in data]
        return data
