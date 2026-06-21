# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run backend (dev)
uvicorn app.main:app --reload --port 8000

# Run all tests
python3 -m pytest tests/ -v --no-header

# Run a single test file
python3 -m pytest tests/phase2/test_channel_crud.py -v

# Run a single test
python3 -m pytest tests/phase2/test_channel_crud.py::test_create_channel -v

# Run tests matching keyword
python3 -m pytest tests/ -k "deepseek" -v

# Install deps
pip install -e ".[dev]"

# Database migration
alembic revision --autogenerate -m "description"
alembic upgrade head

# Frontend (in web/)
cd web && yarn dev     # dev server
cd web && yarn build   # production build
cd web && yarn lint    # eslint
cd web && yarn type-check  # TypeScript check

# Docker
docker compose up --build

# Live tests (requires real API keys and running instance)
python -m tests.live.live_test --quick
UNIAPI_PROVIDER=glm GLM_API_KEY=id.secret python -m tests.live.live_test
```

## Project Architecture

### Overview

UniAPI is an **AI API gateway** — aggregates multiple LLM providers (DeepSeek, GLM, Qwen, Kimi, MiniMax) behind a unified OpenAI-compatible API. Clients send requests in OpenAI Chat or Claude Messages format; the gateway routes to the appropriate provider, converting formats only when necessary.

### Key Pattern: Provider Adaptor + Registry

The extensibility mechanism is the `BaseAdaptor` ABC ([app/relay/adaptor.py](app/relay/adaptor.py)). Each provider implements:
- `get_request_url()` / `setup_request_headers()` — upstream connection
- `convert_request()` — transform incoming request to provider-native format
- `get_supported_models()` — model names and pricing ratios (returns `dict[str, ModelConfig]`)
- `NATIVE_FORMATS` — declares which API formats this provider supports natively (avoids unnecessary conversion)

Adaptors register themselves in the global registry ([app/relay/registry.py](app/relay/registry.py)). Each adaptor is keyed by a **channel type integer** (see [app/relay/channeltype.py](app/relay/channeltype.py)): `39=DeepSeek`, `41=GLM`, `50=Qwen`, `25=Kimi`, `27=MiniMax`.

**To add a new provider**: create `app/relay/adaptors/<name>/` with adaptor.py + pricing.py, subclass `BaseAdaptor`, and register in registry.py.

### Relay Pipeline ([app/routers/v1/relay.py](app/routers/v1/relay.py))

1. Authenticate via Bearer token (supports `key:channel_id` pinning)
2. Parse relay mode from URL path (chat_completions, claude_messages, responses)
3. Resolve provider by model name → channel type
4. Weighted-random channel selection with group access control
5. Estimate cost + pre-consume token/user quota
6. Check `NATIVE_FORMATS`: if native → proxy directly; if not → convert request format
7. Relay upstream via `relay_chat_completion()` with SSE streaming support
8. Post-settle: reconcile actual token usage, refund over-consumed quota
9. Channel failover: auto-retry with fallback model on 429/5xx, auto-disable after 3 consecutive failures

### SSE Streaming & Usage Capture

Streaming responses go through `_capture_stream_usage()` ([app/relay/openai_compatible.py](app/relay/openai_compatible.py)), which intercepts the final SSE chunk carrying `usage`. That triggers an async callback (`_make_stream_usage_callback`) that patches the provisional log entry with real token counts after the stream completes — in a *new* DB session, since the request's session is already closed.

Claude Messages→Chat conversion during streaming also requires SSE format conversion (`needs_sse_conversion` flag).

### Auth System

- **Management API** (`/api/*`): Session cookie via `itsdangerous.URLSafeTimedSerializer`, with `Authorization: Bearer <access_token>` fallback
- **Relay API** (`/v1/*`): Bearer token with optional `token_key:channel_id` pinning syntax
- Role hierarchy: `user_auth` (role>=1) → `admin_auth` (role>=10) → `root_auth` (role>=100)
- Token-level: `remain_quota`, `expired_time`, `status`, per-token model allowlist

### Budget/Quota System

- **SQL-based**: `User.quota`/`used_quota` and `Token.remain_quota`
- **Optional Redis budget arbiter**: Two-phase freeze-and-settle — `pre_check` freezes estimated cost, `post_settle` reconciles with actual token usage. Monthly budget periods via `Budget` model.
- Tests use `FakeRedisClient` in-memory mock ([tests/conftest.py](tests/conftest.py))

### Fusion Engine ([app/fusion/](app/fusion/))

Multi-model ensemble that sends the same prompt to multiple providers in parallel, then synthesizes responses using a judge+synthesizer model pair. Triggered by `model="fusion"` in the request. Requires provider API keys configured in `_build_fusion_registry()` in [app/main.py](app/main.py).

### Cache-Aware Cost Calculation

DeepSeek's prefix caching is handled via three fields in `ModelConfig`: `cached_input_ratio` (default 0.1), `input_ratio`, `output_ratio`. The relay normalizes cache-token formats from both DeepSeek (`prompt_cache_hit_tokens`) and OpenAI (`prompt_tokens_details.cached_tokens`) into a unified calculation. Body normalization (`_normalize_deepseek_body`) strips `reasoning_content` from non-tool assistant turns to keep prefix caching warm.

### Model Name Normalization

Each adaptor can override `resolve_model_name()` for case-insensitive lookups or aliases. The relay calls this during routing and updates `body["model"]` to the canonical form. Notably: MiniMax model names are lowercased during validation, and DeepSeek has its own normalization in `normalize_request()`.

### Middleware Stack (applied in order)

1. `AuditMiddleware` — log all requests
2. `RateLimitMiddleware` — per-route RPM (api=480, relay=480 default)
3. `PIIMaskMiddleware` — mask sensitive fields in logs
4. `RequestTimingMiddleware` — timing headers
5. `RequestIDMiddleware` — unique request ID per request

### Project Structure

```
app/
├── main.py                 # FastAPI create_app, lifespan (DB init, budget, fusion seed)
├── config.py               # Pydantic-Settings (all env vars)
├── database.py             # SQLAlchemy async engine + session factory
├── dependencies.py         # Auth DI: user_auth, admin_auth, root_auth, token_auth
├── exceptions.py           # AppException + handler
├── middleware.py            # Audit, PIIMask, RateLimit, RequestTiming, RequestID
├── models/                 # SQLAlchemy ORM: user, token, channel, log, option, ability, budget
├── schemas/                # Pydantic v2: common, user, relay, etc.
├── services/               # auth.py (session, password), user.py, token.py
├── routers/
│   ├── api/                # Management: auth, status, user, token, log, channel,
│   │                       #   options, topup, redemption, dashboard, budget, MCP, cache
│   └── v1/                 # Relay: /v1/chat/completions, /v1/messages, /v1/responses, /v1/models
├── relay/                  # Provider relay system
│   ├── adaptor.py          # BaseAdaptor ABC + ModelConfig
│   ├── registry.py         # Global AdaptorRegistry singleton
│   ├── mode.py             # RelayMode enum + relay_mode_from_path()
│   ├── meta.py             # RelayMeta dataclass (holds per-request channel/user context)
│   ├── converter.py        # anthropic_to_chat(), responses_to_chat()
│   ├── openai_compatible.py # relay_chat_completion(), SSE streaming, usage capture
│   └── adaptors/           # deepseek/, glm/, qwen/, kimi/, minimax/
└── fusion/                 # Multi-model ensemble engine
    ├── adapters/           # Provider adapters for fusion
    └── core/               # FusionEngine, FusionConfig, orchestration

tests/
├── conftest.py             # Fixtures + FakeRedisClient
├── test_api.py             # Phase 1 API integration (5 tests)
├── test_deepseek_normalize.py  # DeepSeek normalization (21 tests)
├── phase2/                 # Management API CRUD (35 tests)
├── phase3/                 # Multi-format routing (6 tests)
├── phase4/                 # Extensibility tests (6 tests)
├── glm/                    # GLM adaptor tests (9 tests)
└── live/                   # Live probe framework (real API keys)
```

### Testing Conventions

- Tests use SQLite at `/tmp/uniapi_test.db` with fresh tables per fixture
- The `client` fixture provides an `httpx.AsyncClient` connected via ASGITransport
- Budget tests use `FakeRedisClient` (in-memory dict) instead of real Redis
- Live tests in `tests/live/` connect to a running instance with real provider API keys
- All `ModelConfig` pricing ratios are tested against known values from each adaptor's `pricing.py`

### Config

All configuration via env vars ([app/config.py](app/config.py)): `SERVER_PORT`, `SQLITE_PATH`, `SQL_DSN` (for MySQL/PostgreSQL), `SESSION_SECRET`, provider API keys, `TOKEN_KEY_PREFIX`, `API_RATE_LIMIT`/`RELAY_RATE_LIMIT`, optional `BUDGET_REDIS_URL` + `BUDGET_ENABLED`.
