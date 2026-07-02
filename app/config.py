from __future__ import annotations

import secrets
import sys
import warnings

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    server_port: int = 8000
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # Database
    sql_dsn: str = ""
    sqlite_path: str = "uniapi.db"

    # Session
    session_secret: str = ""
    session_cookie_secure: bool = True  # 生产环境必须为 True
    cookie_max_age_hours: int = 168

    # Password policy
    password_min_length: int = 8
    password_require_uppercase: bool = True
    password_require_digit: bool = True
    password_require_special: bool = False

    # Token
    token_key_prefix: str = "sk-"

    # Rate limits
    api_rate_limit: int = 480
    relay_rate_limit: int = 480

    # Upstream retry
    upstream_retry_max: int = 4
    upstream_retry_backoff_base: float = 1.0

    # DeepSeek
    deepseek_api_key: str = ""

    # GLM
    glm_api_key: str = ""

    # Qwen (百炼)
    qwen_api_key: str = ""

    # Kimi (Moonshot)
    kimi_api_key: str = ""

    # MiniMax
    minimax_api_key: str = ""

    # Redis / Budget
    budget_redis_url: str = ""
    budget_enabled: bool = True
    default_monthly_budget: float = 800.0

    # Login lockout
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # Verification code rate limit
    verification_email_max_per_minute: int = 3

    # Turnstile (Cloudflare anti-bot)
    turnstile_secret_key: str = ""

    # SMTP (email verification)
    smtp_token: str = ""

    # GitHub OAuth
    github_client_secret: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def validate_secret(self):
        if not self.session_secret:
            if not any("pytest" in a for a in sys.argv):
                warnings.warn("SESSION_SECRET not set. Using auto-generated key. Sessions invalidated on restart!")
        return self

    @property
    def db_url(self) -> str:
        if self.sql_dsn:
            return self.sql_dsn
        return f"sqlite+aiosqlite:///{self.sqlite_path}"

    @property
    def session_secret_key(self) -> str:
        if self.session_secret:
            return self.session_secret
        return secrets.token_hex(32)


settings = Settings()
