"""Email service for verification codes and password reset."""

from __future__ import annotations

import random
import smtplib
import time
from email.mime.text import MIMEText
from typing import Optional

from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.option import Option

# In-memory verification code store
# {email: {"code": str, "expires": int}}
_verification_codes: dict[str, dict] = {}

# Per-email rate limiting for verification code sending
# {email: [list of timestamps]}
_email_send_limits: dict[str, list[float]] = {}


def check_email_rate_limit(
    email: str,
    max_per_minute: int | None = None,
) -> tuple[bool, int]:
    """Check if this email has exceeded the send rate limit.

    Returns (is_allowed, remaining_attempts_in_window).
    """
    now = time.time()
    window = 60.0
    limit = max_per_minute if max_per_minute is not None else settings.verification_email_max_per_minute

    # Clean old entries
    timestamps = _email_send_limits.get(email, [])
    timestamps = [t for t in timestamps if now - t < window]

    remaining = max(0, limit - len(timestamps))

    if remaining <= 0:
        _email_send_limits[email] = timestamps
        return False, 0

    # Record this attempt
    timestamps.append(now)
    _email_send_limits[email] = timestamps
    return True, remaining - 1

# Reset token serializer (same library as session management)
_reset_serializer: Optional[URLSafeTimedSerializer] = None

RESET_TOKEN_MAX_AGE = 1800  # 30 minutes


def _get_reset_serializer() -> URLSafeTimedSerializer:
    global _reset_serializer
    if _reset_serializer is None:
        _reset_serializer = URLSafeTimedSerializer(
            settings.session_secret_key, salt="password-reset"
        )
    return _reset_serializer


def generate_verification_code(length: int = 6) -> str:
    """Generate a numeric verification code."""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


async def load_smtp_config(db: AsyncSession) -> dict:
    """Load SMTP configuration from DB options table."""
    result = await db.execute(
        select(Option).where(Option.key.in_(["SMTPServer", "SMTPPort", "SMTPAccount", "SMTPFrom"]))
    )
    opts = {row.key: row.value for row in result.scalars().all()}
    return {
        "host": opts.get("SMTPServer", ""),
        "port": int(opts.get("SMTPPort", "587")),
        "user": opts.get("SMTPAccount", ""),
        "password": settings.smtp_token,
        "from_addr": opts.get("SMTPFrom", ""),
    }


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    smtp_config: dict,
) -> bool:
    """Send an email via SMTP.

    Uses synchronous smtplib in a thread to avoid adding aiosmtplib dependency.
    """
    if not smtp_config["host"] or not smtp_config["user"] or not smtp_config["password"]:
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_config["from_addr"] or smtp_config["user"]
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_config["host"], smtp_config["port"], timeout=10) as server:
            server.starttls()
            server.login(smtp_config["user"], smtp_config["password"])
            server.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"Email send failed: {e}")
        return False


async def send_verification_code(
    db: AsyncSession,
    to_email: str,
) -> tuple[bool, str]:
    """Generate and send a verification code to the given email.

    Returns (success, message).
    """
    # Rate limit check — must be first
    allowed, _remaining = check_email_rate_limit(to_email)
    if not allowed:
        return False, "发送验证码过于频繁，请稍后再试"

    code = generate_verification_code()
    smtp_config = await load_smtp_config(db)

    if not smtp_config["host"]:
        # SMTP not configured: store code anyway for testing/dev
        _store_code(to_email, code)
        return False, "SMTP not configured"

    sent = await send_email(
        to_email,
        subject="邮箱验证码",
        body=f"您的验证码是：{code}，有效期 10 分钟。",
        smtp_config=smtp_config,
    )

    if sent:
        _store_code(to_email, code)
        return True, "验证码已发送到邮箱"
    else:
        return False, "发送验证码失败，请稍后重试"


def _store_code(email: str, code: str) -> None:
    """Store verification code with 10-minute TTL."""
    _verification_codes[email] = {
        "code": code,
        "expires": int(time.time()) + 600,
    }


def get_stored_code(email: str) -> str | None:
    """Return the stored verification code for an email, or None if not found.

    Used by E2E tests via the debug endpoint. Returns the code without consuming it.
    """
    record = _verification_codes.get(email)
    if not record:
        return None
    if int(time.time()) > record["expires"]:
        _verification_codes.pop(email, None)
        return None
    return record["code"]


def verify_code(email: str, code: str) -> bool:
    """Verify a verification code. Returns True if valid.

    Consumes the code on success (one-time use).
    """
    record = _verification_codes.get(email)
    if not record:
        return False
    if int(time.time()) > record["expires"]:
        _verification_codes.pop(email, None)
        return False
    if record["code"] != code:
        return False
    # Consume the code (one-time use)
    _verification_codes.pop(email, None)
    return True


def generate_reset_token(email: str) -> str:
    """Generate a signed password reset token."""
    s = _get_reset_serializer()
    return s.dumps(email)


def verify_reset_token(token: str) -> Optional[str]:
    """Verify a reset token and return the email.

    Returns None if token is invalid or expired.
    """
    s = _get_reset_serializer()
    try:
        email = s.loads(token, max_age=RESET_TOKEN_MAX_AGE)
        return email
    except Exception:
        return None
