"""
FastAPI application entry point.

Starts the Fusion Relay server:
  1. Load config from config/ directory
  2. Build adapter registry from models.yaml
  3. Build fusion engine from fusion.yaml
  4. Register middleware (auth, rate limit, PII mask, audit)
  5. Serve OpenAI-compatible API on 0.0.0.0:8080
"""

import logging
import os
import yaml
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.middleware import (
    AuthMiddleware,
    RateLimitMiddleware,
    AuditMiddleware,
    PIIMaskMiddleware,
)
from src.adapters.registry import AdapterRegistry
from src.core.fusion_engine import FusionEngine, FusionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_yaml(filename: str) -> dict:
    """Load YAML config from config/ directory."""
    config_dir = Path(__file__).parent.parent / "config"
    filepath = config_dir / filename
    if not filepath.exists():
        logger.warning("Config file not found: %s", filepath)
        return {}
    with open(filepath, "r") as f:
        return yaml.safe_load(f) or {}


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Fusion API Relay",
        description="OpenAI-compatible API relay with multi-model fusion (Panel → Judge → Synthesizer)",
        version="1.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Load configs ---
    models_config = load_yaml("models.yaml")
    fusion_config_raw = load_yaml("fusion.yaml")
    security_config = load_yaml("security.yaml")

    # --- Build adapter registry ---
    registry = AdapterRegistry()
    registry.load_from_config(models_config)
    app.state.registry = registry

    # --- Build fusion engine ---
    strategies = fusion_config_raw.get("strategies", {})
    default_strategy = strategies.get("default", {})
    fusion_config = FusionConfig(
        panel=default_strategy.get("panel", []),
        judge=default_strategy.get("judge", ""),
        synthesizer=default_strategy.get("synthesizer", ""),
        timeout_seconds=default_strategy.get("timeout_seconds", 30),
        retry_count=default_strategy.get("retry_count", 2),
        fallback_model=default_strategy.get("fallback_model", ""),
    )
    app.state.fusion_engine = FusionEngine(registry, fusion_config)
    app.state.fusion_strategies = strategies
    app.state.routing_rules = fusion_config_raw.get("routing", [])

    # --- Middleware (order matters: outermost first) ---
    relay_key = os.environ.get("RELAY_API_KEY", "fusion-relay-default-key")
    rpm = security_config.get("rate_limiting", {}).get("requests_per_minute", 60)

    if security_config.get("pii_masking", {}).get("enabled", True):
        app.add_middleware(PIIMaskMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=rpm)
    app.add_middleware(AuthMiddleware, relay_api_key=relay_key)

    # --- Routes ---
    app.include_router(router)

    @app.on_event("startup")
    async def startup():
        logger.info("=" * 60)
        logger.info("Fusion API Relay starting...")
        logger.info("Models: %s", registry.list_models())
        logger.info("Fusion panel: %s", fusion_config.panel)
        logger.info("Judge: %s", fusion_config.judge)
        logger.info("Synthesizer: %s", fusion_config.synthesizer)
        logger.info("Listen: http://0.0.0.0:8080")
        logger.info("=" * 60)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
