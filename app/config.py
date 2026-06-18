from __future__ import annotations

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    server_port: int = 8000
    debug: bool = False
    gin_mode: str = "debug"

    # Database
    sql_dsn: str = ""
    sqlite_path: str = "uniapi.db"
    log_sql_dsn: str = ""
    log_sqlite_path: str = ""

    # Session
    session_secret: str = ""
    cookie_max_age_hours: int = 168
    enable_cookie_secure: bool = False

    # Token
    token_key_prefix: str = "sk-"
    initial_root_token: str = ""
    initial_root_access_token: str = ""

    # Rate limits
    global_api_rate_limit: int = 480
    global_web_rate_limit: int = 60
    global_relay_rate_limit: int = 480
    global_channel_rate_limit: int = 5

    # Relay
    relay_timeout: int = 300
    billing_timeout: int = 30
    streaming_billing_interval: int = 10
    relay_proxy: str = ""
    idle_timeout: int = 300

    # Billing
    pre_consumed_quota: int = 500
    quota_remind_threshold: int = 500
    quota_per_unit: int = 500000
    display_in_currency_enabled: bool = False
    display_unit: str = "token"
    approximate_token_enabled: bool = True

    # DeepSeek
    deepseek_api_key: str = ""

    # Batch update
    batch_update_enabled: bool = False
    batch_update_interval: int = 30

    # Monitoring
    enable_prometheus_metrics: bool = False
    open_telemetry_enabled: bool = False
    enable_metric: bool = False

    # Channel
    channel_test_frequency: int = 0
    channel_suspend_seconds_for_5xx: int = 10
    channel_suspend_seconds_for_429: int = 5
    channel_suspend_seconds_for_auth: int = 60
    channel_disable_threshold: int = 0
    automatic_disable_channel_enabled: bool = False
    automatic_enable_channel_enabled: bool = False

    # Sticky session
    sticky_session_enabled: bool = True
    sticky_session_timeout_seconds: int = 600

    # Misc
    cache_enabled: bool = True
    sync_frequency: int = 120
    max_items_per_page: int = 50
    shutdown_timeout_sec: int = 30

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
