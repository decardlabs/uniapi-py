# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run backend (dev)
python3 -m uvicorn app.main:app --port 8000 --reload

# Run all tests
python3 -m pytest tests/ -v --no-header

# Run a single test file
python3 -m pytest tests/phase2/test_channel_crud.py -v

# Run a single test
python3 -m pytest tests/phase2/test_channel_crud.py::test_create_channel -v

# Run tests matching keyword
python3 -m pytest tests/ -k "deepseek" -v

# Run security tests
python3 -m pytest tests/security/ -v

# Coverage report
python3 -m pytest tests/ --cov=app --cov-report=term

# Install deps
pip install -e ".[dev]"

# Database migration
alembic revision --autogenerate -m "description"
alembic upgrade head

# Frontend (in web/)
cd web && yarn dev         # dev server
cd web && yarn build       # production build
cd web && yarn lint        # eslint
cd web && yarn type-check  # TypeScript check

# E2E tests (requires running backend + frontend)
cd web && yarn test:e2e                              # all browsers
cd web && yarn test:e2e:chromium                     # Chromium only
CI=true BASE_URL=http://localhost:3001 yarn test:e2e  # with running frontend
cd web && yarn test:e2e:headed                       # visual debug

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
- `convert_claude_request()` — transform Anthropic Messages format to provider-native format
- `get_supported_models()` — model names and metadata (returns `dict[str, ModelConfig]`)
- `resolve_model_name()` — case-insensitive model name lookup and alias resolution
- `normalize_request_body()` — strip `reasoning_content` from non-tool turns for cache warmth
- `NATIVE_FORMATS` — declares which API formats this provider supports natively (avoids unnecessary conversion)

Adaptors register themselves in the global registry ([app/relay/registry.py](app/relay/registry.py)). Each adaptor is keyed by a **channel type integer** (see [app/relay/channeltype.py](app/relay/channeltype.py)): `39=DeepSeek`, `41=GLM`, `50=Qwen`, `25=Kimi`, `27=MiniMax`.

**To add a new provider**: create `app/relay/adaptors/<name>/` with adaptor.py + pricing.py, subclass `BaseAdaptor`, and register in registry.py.

### Relay Pipeline ([app/routers/v1/relay.py](app/routers/v1/relay.py))

1. Authenticate via Bearer token (supports `key:channel_id` pinning)
2. Parse relay mode from URL path (chat_completions, claude_messages, responses)
3. Resolve channel type via model name → adaptor lookup → weighted-random channel selection with group access control
4. Estimate cost + pre-consume token/user quota
5. Check `NATIVE_FORMATS`: if native → proxy directly; if not → convert request format
6. Relay upstream via `relay_chat_completion()` with SSE streaming support
7. Post-settle: reconcile actual token usage, refund over-consumed quota
8. Channel failover: auto-retry with fallback model on 429/5xx, auto-disable after 3 consecutive failures

### SSE Streaming & Usage Capture

Streaming responses go through `_capture_stream_usage()` ([app/relay/openai_compatible.py](app/relay/openai_compatible.py)), which intercepts the final SSE chunk carrying `usage`. That triggers an async callback (`_make_stream_usage_callback`) that patches the provisional log entry with real token counts after the stream completes — in a *new* DB session, since the request's session is already closed.

Claude Messages→Chat conversion during streaming also requires SSE format conversion (`needs_sse_conversion` flag).

### Auth System

- **Management API** (`/api/*`): Session cookie via `itsdangerous.URLSafeTimedSerializer`, with `Authorization: Bearer <access_token>` fallback
- **Relay API** (`/v1/*`): Bearer token with optional `token_key:channel_id` pinning syntax
- Role hierarchy: `user_auth` (role>=1) → `admin_auth` (role>=10) → `root_auth` (role>=100)
- Token-level: `expired_time`, `status`, per-token model allowlist

### Budget/Quota System

- **SQL-based**: `User.balance` (micro-yuan, ¥1 = 1_000_000), with ¥1 overdraft allowance
- **Optional Redis budget arbiter** (`budget_enabled`): Two-phase freeze-and-settle — `pre_check` freezes estimated cost, `post_settle` reconciles with actual token usage. Monthly budget periods via `Budget` model.
- Tests use `FakeRedisClient` in-memory mock ([tests/conftest.py](tests/conftest.py))

### Fusion Engine ([app/fusion/](app/fusion/))

Multi-model ensemble that sends the same prompt to multiple providers in parallel, then synthesizes responses using a judge+synthesizer model pair. Triggered by `model="fusion"` in the request. Requires provider API keys configured in `_build_fusion_registry()` in [app/main.py](app/main.py).

### Cache-Aware Cost Calculation

DeepSeek's prefix caching is handled via three fields in `ModelConfig`: `cached_input_ratio` (default 0.1), `input_ratio`, `output_ratio`. The relay normalizes cache-token formats from both DeepSeek (`prompt_cache_hit_tokens`) and OpenAI (`prompt_tokens_details.cached_tokens`) into a unified calculation. Body normalization (`normalize_request_body`) strips `reasoning_content` from non-tool assistant turns to keep prefix caching warm.

### Model Name Normalization

Each adaptor can override `resolve_model_name()` for case-insensitive lookups or aliases. The relay calls this during routing and updates `body["model"]` to the canonical form. Notably: MiniMax model names are lowercased during validation, and DeepSeek has its own normalization in `normalize_request()`.

### Middleware Stack (applied in order)

1. `CORSMiddleware` — CORS headers
2. `AuditMiddleware` — log all requests
3. `RateLimitMiddleware` — per-route RPM (api=480, relay=480 default)
4. `PIIMaskMiddleware` — mask sensitive fields in logs
5. `RequestTimingMiddleware` — timing headers
6. `RequestIDMiddleware` — unique request ID per request

### CI Pipeline ([.github/workflows/test.yml](.github/workflows/test.yml))

Three-job GitHub Actions workflow:
- **backend** — pytest + coverage (≥70%) + ruff lint
- **frontend** — yarn type-check + vitest + eslint
- **e2e** (depends on both) — seed DB → start backend + frontend → playwright test

### Project Structure

```
.github/workflows/
└── test.yml                # GitHub Actions CI (3 jobs)
app/
├── main.py                 # FastAPI create_app, lifespan (DB init, budget, fusion seed)
├── config.py               # Pydantic-Settings (all env vars)
├── database.py             # SQLAlchemy async engine + session factory
├── dependencies.py         # Auth DI: user_auth, admin_auth, root_auth, token_auth
├── exceptions.py           # AppException + handler
├── middleware.py            # Audit, PIIMask, RateLimit, RequestTiming, RequestID
├── models/                 # SQLAlchemy ORM: user, token, channel, log, option, ability, budget, passkey, mcp_server, recharge, redemption, base
├── schemas/                # Pydantic v2: common, user, relay, etc.
├── services/               # auth.py (session, password), user.py, token.py
├── routers/
│   ├── api/                # Management: auth, status, user, token, log, channel,
│   │                       #   options, topup, redemption, dashboard, budget, MCP, cache,
│   │                       #   verification, oauth, totp, passkey, mcp_servers, cache_analytics,
│   │                       #   admin_budget
│   └── v1/                 # Relay: /v1/chat/completions, /v1/messages, /v1/responses, /v1/models
├── relay/                  # Provider relay system
│   ├── adaptor.py          # BaseAdaptor ABC + ModelConfig
│   ├── registry.py         # Global AdaptorRegistry singleton
│   ├── mode.py             # RelayMode enum + relay_mode_from_path()
│   ├── meta.py             # RelayMeta dataclass (holds per-request channel/user context)
│   ├── converter.py        # anthropic_to_chat(), responses_to_chat()
│   ├── openai_compatible.py # relay_chat_completion(), SSE streaming, usage capture
│   ├── upstream_errors.py  # Upstream error classification for retry/failover
│   ├── sse_converter.py    # SSE format conversion for streaming
│   └── adaptors/           # deepseek/, glm/, qwen/, kimi/, minimax/
├── budget/                 # Budget arbiter and quota management
└── fusion/                 # Multi-model ensemble engine
    ├── adapters/           # Provider adapters for fusion
    └── core/               # FusionEngine, FusionConfig, orchestration

tests/
├── conftest.py             # Fixtures + FakeRedisClient
├── test_api.py             # Phase 1 API integration (5 tests)
├── test_deepseek_normalize.py  # DeepSeek normalization (23 tests)
├── test_channeltype.py     # Channel type tests (15 tests)
├── test_relay_comparison.py # Relay comparison tests (3 tests)
├── test_cache_analytics.py # Cache analytics tests (8 tests)
├── test_fusion_engine.py   # Fusion Engine unit tests (24 tests)
├── test_middleware.py      # Middleware tests (10 tests)
├── test_xss.py             # XSS protection tests
├── test_budget_order.py    # Budget ordering tests
├── test_streaming_budget.py # Streaming budget tests
├── test_totp_rate_limit.py # TOTP rate limiting tests
├── phase2/                 # Management API CRUD (~204 tests)
├── phase3/                 # Multi-format routing (7 tests)
├── phase4/                 # Extensibility + relay E2E (~51 tests)
├── phase5/                 # Upstream 429 retry + failover + auth (~309 tests)
├── phase6/                 # Recharge & redemption (~55 tests)
├── glm/                    # GLM adaptor tests (13 tests)
├── security/               # RBAC + input validation (18 tests)
├── live/                   # Live probe framework (real API keys)
│   └── test_token_accuracy.py  # Token rate accuracy (8 tests, skipped w/o keys)
└── manual/                 # Manual test scripts
```

### Testing Conventions

- Tests use SQLite at `/tmp/uniapi_test.db` with fresh tables per fixture
- The `client` fixture provides an `httpx.AsyncClient` connected via ASGITransport
- Budget tests use `FakeRedisClient` (in-memory dict) instead of real Redis
- Live tests in `tests/live/` connect to a running instance with real provider API keys
- All pricing data (yuan/1M tokens) is tested in `test_channeltype.py` and `test_budget_pricing.py`
- Security tests in `tests/security/` cover RBAC isolation, SQL injection, and path traversal
- CI enforces ≥70% coverage via `pytest-cov`

### Config

All configuration via env vars ([app/config.py](app/config.py)): `SERVER_PORT`, `SQLITE_PATH`, `SQL_DSN` (for MySQL/PostgreSQL), `SESSION_SECRET`, `session_cookie_secure`, `cookie_max_age_hours`, `password_min_length`, `password_require_uppercase`, `password_require_digit`, `password_require_special`, `totp_pending_ttl_seconds`, `webauthn_rp_id`, provider API keys, `TOKEN_KEY_PREFIX`, `API_RATE_LIMIT`/`RELAY_RATE_LIMIT`, optional `BUDGET_REDIS_URL` + `budget_enabled`, `debug`, `upstream_retry_max`, `upstream_retry_backoff_base`, `default_monthly_budget`, `turnstile_secret_key`, `smtp_token`, `github_client_secret`.
