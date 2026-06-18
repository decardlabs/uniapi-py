# uniapi-py

**UniAPI** 的 Python 后端实现 — 一个聚合多供应商 LLM 的统一 API 网关。

> 这是 [uniapi](https://github.com/decardlabs/uniapi) (Go) 的 Python 重写版，前端复用原项目的 React/TypeScript 实现。

## Status

🚧 **Phases 1-4 已完成** — `82 tests, all GREEN`

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | MVP: Auth, Status, DeepSeek Chat Completions, SSE | ✅ |
| 2 | Management API: User/Token/Log/Options CRUD, Billing | ✅ |
| 3 | Multi-format: NATIVE_FORMATS smart routing | ✅ |
| 4 | Extensibility: BaseAdaptor ABC, Registry, Provider pattern | ✅ |
| **GLM** | 新增供应商: GLM (Zhipu/智谱) adaptor | ✅ |
| **Live Tests** | 真实账号探测框架 (10 scenarios × 供应商) | ✅ |

### 已接入供应商

| Provider | NATIVE_FORMATS | Claude Code 体验 |
|----------|---------------|------------------|
| **DeepSeek** | `chat_completions`, `claude_messages` | 直通 `/v1/messages`，零转换损耗 |
| **GLM (智谱)** | `chat_completions`, `claude_messages` | 直通 `open.bigmodel.cn/api/anthropic` |

## Quick Start

```bash
git clone git@github.com:decardlabs/uniapi-py.git
cd uniapi-py

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

uvicorn app.main:app --reload --port 8000
```

```bash
# 验证
curl http://localhost:8000/api/status

# 登录 (默认 root / 123456)
curl -X POST http://localhost:8000/api/user/login \
  -H "Content-Type: application/json" \
  -d '{"username":"root","password":"123456"}'
```

### 连接前端

前端在 Go 仓库的 [web/modern/](https://github.com/decardlabs/uniapi/tree/main/web/modern)。配置 Vite proxy 指向 Python 后端：

```js
// web/modern/vite.config.ts
proxy: {
  '/api': { target: 'http://localhost:8000' },
  '/v1':  { target: 'http://localhost:8000' },
}
```

## 核心设计: NATIVE_FORMATS

每个供应商适配器声明自己原生支持的 API 格式。当请求以原生支持的格式到达时，**直接转发，无需格式转换**。

```python
class DeepSeekAdaptor(BaseAdaptor):
    NATIVE_FORMATS = {"chat_completions", "claude_messages"}

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == CLAUDE_MESSAGES:
            return "/v1/messages"   # Direct passthrough
        return "/v1/chat/completions"

class GLMAdaptor(BaseAdaptor):
    NATIVE_FORMATS = {"chat_completions", "claude_messages"}

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == CLAUDE_MESSAGES:
            return "https://open.bigmodel.cn/api/anthropic"
        return f"{BASE}/api/paas/v4/chat/completions"
```

### 路由逻辑

```
Claude Code → POST /v1/messages → relay_mode=CLAUDE_MESSAGES
  → adaptor.supports_native_format(12)?
  → ✅ 是 → upstream URL (如 /v1/messages 或 /api/anthropic)，body 原样转发
  → ❌ 否 → convert_request() 转 Chat 格式 → /v1/chat/completions
```

## Project Structure

```
uniapi-py/
├── app/
│   ├── main.py              # FastAPI app, lifespan, router 注册
│   ├── config.py            # Pydantic-Settings (env vars)
│   ├── database.py          # SQLAlchemy async engine + session
│   ├── dependencies.py      # DI (UserAuth, AdminAuth, RootAuth, TokenAuth)
│   ├── middleware.py         # Request timing, ID middleware
│   ├── exceptions.py        # 统一错误处理
│   ├── models/              # SQLAlchemy ORM
│   │   ├── user.py, token.py, channel.py, ability.py
│   │   ├── log.py, option.py
│   │   └── base.py
│   ├── schemas/             # Pydantic v2 validation
│   │   ├── common.py, user.py, relay.py
│   ├── services/            # 业务逻辑
│   │   ├── auth.py, user.py, token.py
│   ├── routers/
│   │   ├── api/             # 管理 API (/api/*)
│   │   └── v1/              # 中继 API (/v1/*)
│   └── relay/               # 上游供应商中继
│       ├── adaptor.py       # BaseAdaptor ABC
│       ├── registry.py      # 供应商注册表
│       ├── mode.py          # RelayMode enum
│       ├── openai_compatible.py  # SSE streaming + shared relay
│       └── adaptors/
│           ├── deepseek/    # DeepSeek adaptor
│           │   ├── adaptor.py, request.py, pricing.py
│           └── glm/         # GLM (Zhipu/智谱) adaptor
│               ├── adaptor.py, auth.py (JWT), pricing.py
└── tests/
    ├── test_api.py                  # Phase 1: API 集成 (5 tests)
    ├── test_deepseek_normalize.py   # Phase 1: DeepSeek 归一化 (21 tests)
    ├── conftest.py                  # 测试 fixtures
    ├── phase2/                      # Phase 2: 管理 API (35 tests)
    ├── phase3/                      # Phase 3: 多格式 (6 tests)
    ├── phase4/                      # Phase 4: 可扩展性 (6 tests)
    ├── glm/                         # GLM adaptor (9 tests)
    └── live/                        # 实时测试框架
        ├── live_test.py             # 入口
        ├── config.py                # 环境变量配置
        ├── client.py                # HTTP 客户端 (含重试+SSE流式)
        ├── runner.py                # 运行器 + 报告
        └── scenarios/               # 测试场景
            ├── chat.py              # Chat Completion 测试
            ├── stream.py            # 流式测试
            ├── claude_messages.py   # Claude Messages 测试
            └── tools.py             # 工具调用测试
```

## API 端点

### 管理 API (`/api/*`)

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/status` | Public | 系统状态、品牌信息 |
| `GET /api/models/display` | Public | 模型列表含定价 |
| `POST /api/user/login` | Public | 登录，返回 session cookie |
| `POST /api/user/register` | Public | 注册新用户 |
| `GET /api/user/self` | UserAuth | 当前用户信息 |
| `GET/POST /api/user/` | AdminAuth | 列出/创建用户 |
| `GET/PUT/DELETE /api/user/:id` | AdminAuth | 获取/更新/删除用户 |
| `POST /api/user/totp/disable/:id` | AdminAuth | 禁用 TOTP |
| `GET /api/token/` | UserAuth | 列出令牌 |
| `POST/PUT/DELETE /api/token/` | UserAuth | 创建/更新/删除令牌 |
| `POST /api/token/consume` | TokenAuth | 外部配额消费 |
| `GET /api/token/balance` | TokenAuth | 令牌余额 |
| `GET /api/log/self` | UserAuth | 个人日志 |
| `GET /api/log/` | AdminAuth | 全部日志 |
| `DELETE /api/log/` | AdminAuth | 删除旧日志 |
| `GET /api/option/` | RootAuth | 系统配置 |
| `PUT /api/option/` | RootAuth | 更新配置 |
| `GET /api/channel/types` | Public | 可用渠道类型 |
| `GET /api/group/` | AdminAuth | 用户组列表 |

### 中继 API (`/v1/*`)

| Endpoint | Format | DeepSeek | GLM |
|----------|--------|----------|-----|
| `POST /v1/chat/completions` | OpenAI Chat | Direct | `/api/paas/v4/...` |
| `POST /v1/messages` | Claude Messages | Direct (零转换) | `open.bigmodel.cn/api/anthropic` |
| `POST /v1/responses` | OpenAI Response | Converted to Chat | Converted to Chat |
| `GET /v1/models` | OpenAI | Model list | Model list |

### Auth

- **管理 API**: Session cookie (`itsdangerous URLSafeTimedSerializer`)
- **中继 API**: Bearer token (`Authorization: Bearer <key>`)
- **响应格式**: `{"success": bool, "message"?: str, "data"?: T, "total"?: int}`

## 配置

| Env Var | 默认值 | 说明 |
|---------|--------|------|
| `SERVER_PORT` | 8000 | 服务端口 |
| `SQLITE_PATH` | uniapi.db | SQLite 数据库路径 |
| `SQL_DSN` | — | MySQL/PostgreSQL DSN |
| `SESSION_SECRET` | auto | Session cookie 签名密钥 |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |

## 测试

### 单元测试 (82 tests)

```bash
pytest tests/ -v
```

### 实时测试 (需真实 API key)

```bash
# 启动 uniapi-py 后，另一个终端：

UNIAPI_TOKEN=sk-xxx DEEPSEEK_API_KEY=sk-xxx \
  python -m tests.live.live_test

# 快速运行
python -m tests.live.live_test --quick

# 仅流式
python -m tests.live.live_test --stream

# 指定供应商
UNIAPI_PROVIDER=glm GLM_API_KEY=id.secret \
  python -m tests.live.live_test
```

实时测试场景：

| 场景 | 端点 | 验证 |
|------|------|------|
| Chat Simple | `POST /v1/chat/completions` | 返回 200 + usage |
| Chat Multi-turn | `POST /v1/chat/completions` | 记住对话历史 |
| Chat Reasoning Replay | `POST /v1/chat/completions` | `reasoning_content` 回放 |
| Stream Chat | `POST /v1/chat/completions` | `stream:true` |
| Claude Messages | `POST /v1/messages` | 直通 Anthropic 端点 |
| Claude Messages Tool | `POST /v1/messages` | tool_use content block |
| Claude Messages Multi-turn | `POST /v1/messages` | 上下文连贯性 |
| Stream Claude Messages | `POST /v1/messages` | SSE events |
| Tool Call Basic | `POST /v1/chat/completions` | tool_calls 被调用 |
| Tool Call History | `POST /v1/chat/completions` | 带历史工具调用 |

## 添加新供应商

```python
# app/relay/adaptors/myprovider/adaptor.py
class MyProviderAdaptor(BaseAdaptor):
    provider_name = "myprovider"
    NATIVE_FORMATS = {"chat_completions"}               # 声明原生支持格式
    DEFAULT_BASE_URL = "https://api.myprovider.com/v1"

    def get_request_url(self, meta, relay_mode=1): ...   # URL 构造
    def setup_request_headers(self, api_key): ...         # 认证
    async def convert_request(self, body, meta): ...      # 请求转换
    def get_supported_models(self): ...                   # 模型定价

# app/relay/registry.py
from app.relay.adaptors.myprovider.adaptor import MyProviderAdaptor
registry.register(MY_CHANNEL_TYPE, MyProviderAdaptor)
```

参考 [DeepSeek](app/relay/adaptors/deepseek/adaptor.py) 或 [GLM](app/relay/adaptors/glm/adaptor.py) 实现。

## 技术栈

- **Python 3.12+** / **FastAPI** — Web framework
- **SQLAlchemy 2.0** (async) — ORM
- **Alembic** — Database migrations
- **Pydantic v2** — Validation
- **httpx** — Async HTTP client
- **pytest-asyncio** — Async testing

## License

MIT
