# CLAUDE.md — Guide for Claude Code

## Commands

```bash
# Backend (dev)
python3 -m uvicorn app.main:app --port 8000 --reload

# Run all tests
python3 -m pytest tests/ -v --no-header

# Single test file / test
python3 -m pytest tests/phase2/test_channel_crud.py -v
python3 -m pytest tests/phase2/test_channel_crud.py::test_create_channel -v

# Tests by keyword / coverage
python3 -m pytest tests/ -k "deepseek" -v
python3 -m pytest tests/ --cov=app --cov-report=term

# Install / db migration
pip install -e ".[dev]"
alembic revision --autogenerate -m "description"
alembic upgrade head

# Frontend (in web/)
cd web && yarn dev          # dev server (port 3001)
cd web && yarn build        # production build
cd web && yarn lint         # eslint
cd web && yarn type-check   # TypeScript check
cd web && yarn test         # vitest

# E2E tests
cd web && yarn test:e2e                     # all browsers
cd web && yarn test:e2e:chromium            # Chromium only

# Live tests
python -m tests.live.live_test --quick
```

## Key Architecture

### Relay Pipeline
1. Bearer token auth (supports `key:channel_id` pinning)
2. Resolve channel type via model → adaptor → weighted-random channel
3. Check `NATIVE_FORMATS`: if native → proxy directly; if not → convert format
4. Relay upstream via SSE streaming; post-settle reconcile usage
5. Channel failover on 429/5xx, auto-disable after 3 consecutive failures

### Provider Adaptor Pattern
- `BaseAdaptor` ABC at [app/relay/adaptor.py](app/relay/adaptor.py)
- Register in [app/relay/registry.py](app/relay/registry.py) with channel type integer
- Each adaptor: `convert_request()`, `get_supported_models()`, `NATIVE_FORMATS`

### Auth
- **Management API** (`/api/*`): Session cookie (`itsdangerous URLSafeTimedSerializer`)
- **Relay API** (`/v1/*`): Bearer token; roles: user(≥1) → admin(≥10) → root(≥100)
- Login: username + password only. No TOTP/Passkey support.

### Middleware Stack (order matters)
`CORSMiddleware` → `AuditMiddleware` → `RateLimitMiddleware` → `PIIMaskMiddleware` → `RequestTimingMiddleware` → `RequestIDMiddleware`

### Budget/Quota
- SQL-based: `User.balance` in micro-yuan (¥1 = 1_000_000), ¥1 overdraft
- Optional Redis arbiter: two-phase freeze-and-settle

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

- **Management API** (`/api/*`): Session cookie via `itsdangerous.URLSafeTimedSerializer`, with `Authorization: Bearer <access_token>` fallback; sessions are rotated on password change via `session_version` field ([app/models/user.py](app/models/user.py))
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

### Middleware Stack (add_middleware order; request execution is reversed)

1. `CORSMiddleware` — CORS headers
2. `AuditMiddleware` — log all requests
3. `RateLimitMiddleware` — per-route RPM (api=480, relay=480 default)
4. `PIIMaskMiddleware` — mask sensitive fields in logs
5. `RequestTimingMiddleware` — timing headers
6. `RequestIDMiddleware` — unique request ID per request (innermost, adds request ID)

### CI Pipeline ([.github/workflows/test.yml](.github/workflows/test.yml))

Four-job GitHub Actions workflow:
- **backend** — pytest + coverage (≥60%) + ruff lint
- **frontend** — yarn type-check + vitest + eslint
- **e2e** (depends on both, continue-on-error) — seed DB → start backend + frontend → playwright test
- **deploy** (depends on backend+frontend, only on `v*` tags) — build frontend → SCP to server → SSH deploy

### Project Structure

```
.github/workflows/
└── test.yml                # GitHub Actions CI (4 jobs: backend, frontend, e2e, deploy)
app/
├── main.py               # FastAPI create_app, lifespan (DB init, seeding)
├── config.py             # Pydantic-Settings (all env vars)
├── database.py           # SQLAlchemy async engine
├── dependencies.py       # Auth DI: user_auth, admin_auth, root_auth, token_auth
├── middleware.py          # Audit, PIIMask, RateLimit, RequestTiming, RequestID
├── models/               # SQLAlchemy ORM (user, token, channel, log, option, budget, ...)
├── schemas/              # Pydantic v2
├── services/             # auth.py, user.py, token.py
├── routers/
│   ├── api/              # Management API
│   └── v1/               # Relay API
├── relay/                # Provider relay system + adaptors/
├── budget/               # Budget arbiter + pricing
└── fusion/               # Multi-model ensemble engine

tests/
├── conftest.py           # Fixtures + FakeRedisClient
├── phase2/               # Management API CRUD
├── phase3/               # Feature phases (multi-format)
├── phase4/               # Feature phases (concurrent billing, SSE disconnect)
├── phase5/               # Feature phases
├── phase6/               # Feature phases
├── security/             # RBAC + input validation
├── glm/                  # GLM adaptor tests
└── live/                 # Live probe framework
```

## Testing Conventions

- Tests use SQLite at `/tmp/uniapi_test.db` with fresh tables per fixture
- The `client` fixture provides an `httpx.AsyncClient` connected via ASGITransport
- Budget tests use `FakeRedisClient` (in-memory dict) instead of real Redis
- Live tests in `tests/live/` connect to a running instance with real provider API keys
- All pricing data (yuan/1M tokens) is tested in `test_channeltype.py` and `tests/phase2/test_budget_pricing.py`
- Security tests in `tests/security/` cover RBAC isolation, SQL injection, and path traversal
- Coverage collected via `pytest-cov` and uploaded to Codecov (no hard threshold)
- Concurrent billing is tested in `tests/phase4/test_concurrent_billing.py`
- SSE disconnect cleanup is tested in `tests/phase4/test_sse_disconnect.py`
- Token expiry enforcement is tested in `tests/phase4/test_token_expiry.py`
- MCP server input validation is tested in `tests/phase2/test_mcp_servers.py`
- Adaptor contract tests live in `tests/phase4/test_adaptor_contracts.py`

### Config

All configuration via env vars ([app/config.py](app/config.py)): `SERVER_PORT`, `SQLITE_PATH`, `SQL_DSN` (for MySQL/PostgreSQL), `SESSION_SECRET`, `CORS_ORIGINS`, `session_cookie_secure`, `cookie_max_age_hours`, `password_min_length`, `password_require_uppercase`, `password_require_digit`, `password_require_special`, `login_max_attempts`, `login_lockout_minutes`, provider API keys, `TOKEN_KEY_PREFIX`, `API_RATE_LIMIT`/`RELAY_RATE_LIMIT`, optional `BUDGET_REDIS_URL` + `budget_enabled`, `debug`, `upstream_retry_max`, `upstream_retry_backoff_base`, `default_monthly_budget`, `turnstile_secret_key`, `smtp_token`, `github_client_secret`. Root password is configured via `UNIAPI_ROOT_PASSWORD` env var at seed time ([app/main.py](app/main.py)).
