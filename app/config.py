from __future__ import annotations

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    server_port: int = 8000
    debug: bool = False

    # Database
    sql_dsn: str = ""
    sqlite_path: str = "uniapi.db"

    # Session
    session_secret: str = ""
    cookie_max_age_hours: int = 168

    # Token
    token_key_prefix: str = "sk-"

    # Rate limits
    api_rate_limit: int = 480
    relay_rate_limit: int = 480

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

    # Turnstile (Cloudflare anti-bot)
    turnstile_secret_key: str = ""

    # SMTP (email verification)
    smtp_token: str = ""

    # GitHub OAuth
    github_client_secret: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

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
