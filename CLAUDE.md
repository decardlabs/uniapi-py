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

## File Organization

```
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
├── phase3-6/             # Feature phases
├── security/             # RBAC + input validation
├── glm/                  # GLM adaptor tests
└── live/                 # Live probe framework
```

## Testing Conventions

- SQLite at `/tmp/uniapi_test.db`, fresh tables per fixture
- `client` fixture: `httpx.AsyncClient` via ASGITransport
- Budget tests use `FakeRedisClient` (in-memory dict)
- CI enforces ≥70% coverage
