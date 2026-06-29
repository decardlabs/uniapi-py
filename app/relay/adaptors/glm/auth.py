"""GLM JWT token generation.

GLM uses a JWT-based authentication where the API key format is "id.secret".
The token is cached in memory for 24 hours.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

_GLM_TOKEN_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 24 * 3600  # 24 hours


def generate_glm_token(api_key: str) -> str:
    """Generate a JWT token from a GLM API key (format: 'id.secret').

    The token is cached for 24 hours to avoid regenerating on every request.
    """
    # Check cache
    cached = _GLM_TOKEN_CACHE.get(api_key)
    if cached:
        token, expiry = cached
        if time.time() < expiry:
            return token

    parts = api_key.split(".", 1)
    if len(parts) != 2:
        raise ValueError("Invalid GLM API key format: expected 'id.secret'")

    _id, secret = parts[0], parts[1]

    now = int(time.time() * 1000)  # milliseconds
    exp = now + _CACHE_TTL * 1000

    # JWT header
    header = {"alg": "HS256", "sign_type": "SIGN"}
    # JWT payload
    payload = {"api_key": _id, "exp": exp, "timestamp": now}

    # Base64url encode
    import base64

    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    # Sign
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)

    token = f"{signing_input}.{sig_b64}"

    # Cache
    _GLM_TOKEN_CACHE[api_key] = (token, time.time() + _CACHE_TTL)

    return token
