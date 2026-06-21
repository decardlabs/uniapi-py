"""TOTP (Time-based One-Time Password) service for two-factor authentication."""

from __future__ import annotations

from io import BytesIO

import pyotp
import qrcode


def generate_totp_secret() -> str:
    """Generate a new TOTP secret (base32)."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "UniAPI") -> str:
    """Generate otpauth:// URI for QR code provisioning."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code with 1-step valid window."""
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
