# uniapi-py

**UniAPI** 的 Python 后端实现 — 一个聚合多供应商 LLM 的统一 API 网关。

> 这是 [uniapi](https://github.com/decardlabs/uniapi) (Go) 的 Python 重写版，前端复用原项目的 React/TypeScript 实现。

## Status

🚧 **Phase 1-4 已完成，积极开发中** — `73 tests, all GREEN`

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | MVP: Auth, Status, DeepSeek Chat Completions, SSE Streaming | ✅ |
| 2 | Management API: User/Token/Log/Options CRUD, Billing | ✅ |
| 3 | Multi-format: NATIVE_FORMATS smart routing (/v1/messages, /v1/responses) | ✅ |
| 4 | Extensibility: BaseAdaptor ABC, Registry, Provider pattern | ✅ |

## Quick Start

```bash
git clone git@github.com:decardlabs/uniapi-py.git
cd uniapi-py

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Start server
uvicorn app.main:app --reload --port 8000
```

```bash
# In another terminal, test the API
curl http://localhost:8000/api/status

# Login
curl -X POST http://localhost:8000/api/user/login \
  -H "Content-Type: application/json" \
  -d '{"username":"root","password":"123456"}'
```

### Connect Frontend

The frontend is at [web/modern/](https://github.com/decardlabs/uniapi/tree/main/web/modern) in the Go repo. Configure the Vite proxy to point to the Python backend:

```js
// web/modern/vite.config.ts
proxy: {
  '/api': { target: 'http://localhost:8000' },
  '/v1':  { target: 'http://localhost:8000' },
}
```

## Architecture

```
Frontend (React/Vite) ──HTTP──> Python Backend (FastAPI)
                                    │
                                    ├─ Session Auth (cookie) → /api/*
                                    ├─ Token Auth (Bearer)    → /v1/*
                                    │
                                    ├─ SQLAlchemy (async) → SQLite/MySQL/PostgreSQL
                                    ├─ HTTTPx (async)     → DeepSeek API
                                    └─ Static files        → web/build/modern/
```

### Key Design: NATIVE_FORMATS

Each provider adaptor declares which API formats it natively supports.
When a request arrives in a natively-supported format, it is proxied
directly **without format conversion**.

| Provider | NATIVE_FORMATS | Claude Code Flow |
|----------|---------------|------------------|
| DeepSeek | `chat_completions`, `claude_messages` | Direct proxy to `/v1/messages`, zero overhead |
| OpenAI (future) | `chat_completions`, `response_api` | Requires Claude→Chat conversion |

```python
class DeepSeekAdaptor(BaseAdaptor):
    NATIVE_FORMATS = {"chat_completions", "claude_messages"}

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == CLAUDE_MESSAGES:
            return "/v1/messages"   # Direct passthrough, no conversion
        return "/v1/chat/completions"
```

## Project Structure

```
uniapi-py/
├── app/
│   ├── main.py              # FastAPI app, lifespan, router registration
│   ├── config.py            # Pydantic-Settings (env vars)
│   ├── database.py          # SQLAlchemy async engine + session
│   ├── dependencies.py      # DI (UserAuth, AdminAuth, RootAuth, TokenAuth)
│   ├── middleware.py         # Request timing, ID middleware
│   ├── exceptions.py        # Unified error handling
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── user.py, token.py, channel.py, ability.py
│   │   ├── log.py, option.py
│   │   └── base.py
│   ├── schemas/             # Pydantic v2 validation
│   │   ├── common.py, user.py, relay.py
│   ├── services/            # Business logic
│   │   ├── auth.py, user.py, token.py
│   ├── routers/
│   │   ├── api/             # Management API (/api/*)
│   │   └── v1/              # Relay API (/v1/*)
│   └── relay/               # Upstream provider relay
│       ├── adaptor.py       # BaseAdaptor ABC
│       ├── registry.py      # Provider registry
│       ├── mode.py          # RelayMode enum
│       ├── openai_compatible.py  # SSE streaming + shared relay
│       └── adaptors/
│           └── deepseek/    # DeepSeek adaptor
│               ├── adaptor.py, request.py, pricing.py
└── tests/
    ├── test_api.py              # Phase 1: API integration (5 tests)
    ├── test_deepseek_normalize.py  # Phase 1: DeepSeek normalization (21 tests)
    ├── conftest.py              # Test fixtures
    └── phase2/                  # Phase 2: Management API (35 tests)
    └── phase3/                  # Phase 3: Multi-format (6 tests)
    └── phase4/                  # Phase 4: Extensibility (6 tests)
```

## API Endpoints

### Management API (`/api/*`)

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/status` | Public | System status, branding |
| `GET /api/models/display` | Public | Model listing with pricing |
| `POST /api/user/login` | Public | Login, returns session cookie |
| `POST /api/user/register` | Public | Register new user |
| `GET /api/user/self` | UserAuth | Current user profile |
| `GET/POST /api/user/` | AdminAuth | List/create users |
| `GET/PUT/DELETE /api/user/:id` | AdminAuth | Get/update/delete user |
| `GET /api/token/` | UserAuth | List tokens |
| `POST/PUT/DELETE /api/token/` | UserAuth | Create/update/delete token |
| `GET /api/log/self` | UserAuth | Own usage logs |
| `GET /api/log/` | AdminAuth | All logs |
| `GET /api/option/` | RootAuth | System options |
| `GET /api/channel/types` | Public | Available channel types |

### Relay API (`/v1/*`)

| Endpoint | Format | DeepSeek Route |
|----------|--------|----------------|
| `POST /v1/chat/completions` | OpenAI Chat | Direct to `/v1/chat/completions` |
| `POST /v1/messages` | Claude Messages | Direct to `/v1/messages` (no conversion) |
| `POST /v1/responses` | OpenAI Response | Converted to Chat |
| `GET /v1/models` | OpenAI | Model list |

### Auth

- **Management API**: Session cookie (`itsdangerous URLSafeTimedSerializer`)
- **Relay API**: Bearer token (`Authorization: Bearer <key>`)
- **Response format**: `{"success": bool, "message"?: str, "data"?: T, "total"?: int}`

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SERVER_PORT` | 8000 | Server port |
| `SQLITE_PATH` | uniapi.db | SQLite database path |
| `SQL_DSN` | — | MySQL/PostgreSQL DSN (e.g. `mysql+aiomysql://user:pass@localhost/db`) |
| `SESSION_SECRET` | auto | Session cookie signing key |
| `DEEPSEEK_API_KEY` | — | Default DeepSeek API key |

## Running Tests

```bash
pytest tests/ -v
```

## Adding a New Provider

1. Create `app/relay/adaptors/<provider>/` directory
2. Implement `BaseAdaptor` (6 methods):
   - `get_request_url()` / `setup_request_headers()`
   - `convert_request()` / `get_supported_models()`
3. Declare `NATIVE_FORMATS` for smart routing
4. Register: `registry.register(channel_type, YourAdaptor)`

See [DeepSeek](app/relay/adaptors/deepseek/adaptor.py) for a reference implementation.

## Tech Stack

- **Python 3.12+** / **FastAPI** — Web framework
- **SQLAlchemy 2.0** (async) — ORM
- **Alembic** — Database migrations
- **Pydantic v2** — Validation
- **httpx** — Async HTTP client
- **pytest-asyncio** — Async testing

## License

MIT
