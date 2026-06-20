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

# Integration test (requires valid token)
python3 tests/manual/relay_test.py --token sk-xxx --base-url http://localhost:8000

# Live tests (requires real API keys)
python -m tests.live.live_test --quick
python -m tests.live.live_test --stream
UNIAPI_PROVIDER=glm GLM_API_KEY=id.secret python -m tests.live.live_test

# Install deps
pip install -e ".[dev]"

# Frontend (in web/)
cd web && yarn dev     # dev server
cd web && yarn build   # production build
cd web && yarn lint    # lint with eslint
cd web && yarn type-check  # TypeScript check

# Database migration
alembic revision --autogenerate -m "description"
alembic upgrade head

# Docker
docker compose up --build
```

## Project Architecture

### Overview

UniAPI is an **AI API gateway** — it aggregates multiple LLM providers (DeepSeek, GLM, Qwen, Kimi, MiniMax) behind a unified API. Clients send requests in OpenAI Chat or Claude Messages format, and the gateway routes to the appropriate provider, converting formats only when necessary.

### Key Pattern: Provider Adaptor + Registry

The extensibility mechanism is the `BaseAdaptor` ABC ([app/relay/adaptor.py](app/relay/adaptor.py)). Each provider implements:
- `get_request_url()` / `setup_request_headers()` — upstream connection
- `convert_request()` — transform incoming request to provider-native format
- `get_supported_models()` — model names and pricing ratios
- `NATIVE_FORMATS` — declares which API formats this provider supports natively (avoids unnecessary conversion)

Adaptors register themselves in the global registry ([app/relay/registry.py](app/relay/registry.py)). The relay pipeline ([app/routers/v1/relay.py](app/routers/v1/relay.py)) resolves which adaptor handles a request, checks `supports_native_format()`, and either proxies directly or converts.

**To add a new provider**: create `app/relay/adaptors/<name>/` with adaptor.py + pricing.py, subclass `BaseAdaptor`, and register in [app/relay/registry.py](app/relay/registry.py).

### Relay Modes

Relay mode is an integer enum (see [app/relay/mode.py](app/relay/mode.py)). Key values: `1=chat_completions`, `11=response_api`, `12=claude_messages`. The `NATIVE_FORMATS` set on each adaptor determines whether a request in a given mode can be proxied as-is or must be converted.

### Auth System

Two parallel auth mechanisms:
- **Management API** (`/api/*`): Session cookie via `itsdangerous.URLSafeTimedSerializer` ([app/services/auth.py](app/services/auth.py))
- **Relay API** (`/v1/*`): Bearer token from `Authorization` header, with optional channel pinning via `token_key:channel_id` syntax ([app/dependencies.py](app/dependencies.py))

Auth dependencies provide granular role checks: `user_auth` (role >= 1), `admin_auth` (role >= 10), `root_auth` (role >= 100), `token_auth` (Bearer token for relay).

### Budget/Quota System

- SQL-based: per-user `quota`/`used_quota` columns on `User` model and token-level `remain_quota`
- Optional Redis-based budget arbiter ([app/budget/arbiter.py](app/budget/arbiter.py)) for real-time budget enforcement — freeze-and-settle pattern with configurable monthly budgets
- Tests use `FakeRedisClient` in-memory mock ([tests/conftest.py](tests/conftest.py))

### Channel System

Channels represent API key + provider + model configurations ([app/models/channel.py](app/models/channel.py)). The relay endpoint resolves the channel mapping: a channel points to a provider and stores the API key, model override, and group restrictions.

### Project Structure

```
app/
├── main.py                 # FastAPI app creation, lifespan, router registration, seed data
├── config.py               # Pydantic-Settings (env vars)
├── database.py             # SQLAlchemy async engine + session
├── dependencies.py         # Auth DI: user_auth, admin_auth, root_auth, token_auth
├── exceptions.py           # AppException, error handler
├── middleware.py            # Request timing, ID middleware
├── models/                 # SQLAlchemy ORM models (user, token, channel, log, option, etc.)
├── schemas/                # Pydantic v2 request/response schemas
├── services/               # Business logic (auth, user, token)
├── routers/
│   ├── api/                # Management API routes (/api/*)
│   └── v1/                 # Relay API routes (/v1/*) — chat, messages, responses, models
└── relay/                  # Provider relay system
    ├── adaptor.py          # BaseAdaptor ABC
    ├── registry.py          # Provider registry (global singleton)
    ├── converter.py         # Protocol conversion (Anthropic ↔ OpenAI)
    ├── openai_compatible.py # SSE streaming + generic relay logic
    └── adaptors/           # Provider implementations
        ├── deepseek/       # DeepSeek (working adaptor)
        ├── glm/            # Zhipu/GLM (working adaptor)
        ├── qwen/           # Qwen (stub)
        ├── kimi/           # Kimi (stub)
        └── minimax/        # MiniMax (stub)

tests/
├── conftest.py             # Fixtures: ASGI test client, seed data, FakeRedisClient
├── test_api.py             # Phase 1 API integration tests
├── test_deepseek_normalize.py  # DeepSeek normalization
├── phase2/                 # Management API tests (35 tests)
├── phase3/                 # Multi-format routing tests
├── phase4/                 # Extensibility tests
├── glm/                    # GLM adaptor tests
└── live/                   # Live probe framework (requires real API keys)
    ├── live_test.py        # Entry point
    ├── runner.py           # Report generation
    └── scenarios/          # Test scenarios (chat, stream, claude_messages, tools)

web/                        # React/TypeScript frontend (forked from Go repo)
└── src/                    # Vite + shadcn/ui + Radix UI
    ├── App.tsx
    └── main.tsx

fusion-relay/               # Experimental Go-style fusion relay (separate service)
```

### Testing Conventions

- Tests use SQLite at `/tmp/uniapi_test.db` (set in conftest.py) with fresh tables per fixture
- The `client` fixture provides an `httpx.AsyncClient` connected to the FastAPI app via ASGITransport
- Budget-related tests use `FakeRedisClient` (in-memory dict) instead of real Redis
- Live tests in `tests/live/` connect to a running instance with real provider API keys

### Config

All configuration via env vars ([app/config.py](app/config.py)): `SERVER_PORT`, `SQLITE_PATH`, `SQL_DSN` (for MySQL/PostgreSQL), `SESSION_SECRET`, provider API keys, optional Redis config.
