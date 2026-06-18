# uniapi-py

**UniAPI** 的 Python 后端实现 — 一个聚合多供应商 LLM 的统一 API 网关。

> 这是 [uniapi](https://github.com/decardlabs/uniapi) (Go) 的 Python 重写版，前端复用原项目的 React/TypeScript 实现。
>
> **为什么用 Python 重写？** 原 Go 版的适配器模式和路由逻辑适合静态类型语言，但在快速迭代供应商适配器和动态协议转换场景下，Python 的类型系统和元编程能力（ABC + 注册表模式）能显著降低新增供应商的开发成本。Python 版不追求替换 Go 版，而是作为轻量级替代方案，聚焦于快速接入新供应商和实验性功能验证。

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

> 当前已接入 2 家，后续按需求批量接入 Qwen、Kimi、MiniMax 等（接口模式成熟的厂商可在 1-2 天内完成适配）。参见 [app/relay/adaptors/](app/relay/adaptors/) 了解适配器结构。

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

### 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `curl /api/status` 连接失败 | 服务未启动或端口不匹配 | 确认 `uvicorn` 日志正常；检查 `SERVER_PORT` 环境变量 |
| SQLite 数据库锁错误 | 并发写 SQLite 触发锁超时 | 开发环境正常现象，生产应切换为 MySQL (`SQL_DSN`) |
| `ModuleNotFoundError` | 依赖未安装或虚拟环境未激活 | 确认 `.venv/bin/activate` 已执行；`pip list` 检查依赖 |
| `401 Unauthorized` | API Key 错误或未设置 | 检查 `Authorization: Bearer` 头部和对应供应商环境变量 |
| Cursor/Claude Code 调用无响应 | Base URL 配置错误 | 参见 [大模型接入协议研究_Review.md](docs/大模型接入协议研究_Review.md#二各厂商协议兼容端点--调用注意事项) |

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

#### 公共

| Endpoint | 描述 |
|----------|------|
| `GET /api/status` | 系统状态、品牌信息 |
| `GET /api/status/channel` | 渠道状态列表 |
| `GET /api/models/display` | 模型列表含定价 |
| `GET /api/available_models` | 可用模型列表 |
| `GET /api/models` | 模型列表 |
| `GET /api/home_page_content` | 首页内容 |
| `GET /api/about` | 关于页面 |
| `GET /api/tools/display` | 工具列表 |
| `GET /api/channel/types` | 可用渠道类型 |

#### 认证 (Session)

| Endpoint | Auth | 描述 |
|----------|------|------|
| `POST /api/user/login` | Public | 登录，返回 session cookie |
| `POST /api/user/register` | Public | 注册新用户 |
| `GET /api/user/logout` | UserAuth | 登出 |
| `GET /api/user/self` | UserAuth | 当前用户信息 |
| `PUT /api/user/self` | UserAuth | 更新个人信息 |
| `GET /api/user/aff` | UserAuth | 推广信息 |
| `GET /api/user/token` | UserAuth | 获取 access token |
| `GET /api/user/get-by-token` | UserAuth | 通过 token 获取用户 |
| `GET /api/user/available_models` | UserAuth | 可用模型 |

#### 用户管理 (Admin, role >= 10)

| Endpoint | 描述 |
|----------|------|
| `GET /api/user/` | 列出用户 |
| `GET /api/user/search` | 搜索用户 |
| `POST /api/user/` | 创建用户 |
| `PUT /api/user/` | 更新用户 |
| `GET /api/user/{user_id}` | 获取用户详情 |
| `DELETE /api/user/{user_id}` | 删除用户 |
| `POST /api/user/totp/disable/{user_id}` | 禁用 TOTP |
| `GET /api/group/` | 用户组列表 |

#### Token 管理

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/token/` | UserAuth | 列出令牌 |
| `GET /api/token/search` | UserAuth | 搜索令牌 |
| `GET /api/token/{token_id}` | UserAuth | 获取令牌详情 |
| `POST /api/token/` | UserAuth | 创建令牌 |
| `PUT /api/token/` | UserAuth | 更新令牌 |
| `DELETE /api/token/{token_id}` | UserAuth | 删除令牌 |
| `POST /api/token/consume` | TokenAuth | 外部配额消费 |
| `GET /api/token/balance` | TokenAuth | 令牌余额 |
| `GET /api/token/transactions` | TokenAuth | 交易记录 |
| `GET /api/token/logs` | TokenAuth | 令牌使用日志 |

#### 日志

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/log/self` | UserAuth | 个人日志 |
| `GET /api/log/self/stat` | UserAuth | 个人日志统计 |
| `GET /api/log/self/search` | UserAuth | 搜索个人日志 |
| `GET /api/log/` | AdminAuth | 全部日志 |
| `GET /api/log/stat` | AdminAuth | 日志统计 |
| `GET /api/log/search` | AdminAuth | 搜索日志 |
| `DELETE /api/log/` | AdminAuth | 删除旧日志 |

#### 渠道管理 (Admin)

| Endpoint | 描述 |
|----------|------|
| `GET /api/channel/` | 列出渠道 |
| `GET /api/channel/search` | 搜索渠道 |
| `POST /api/channel/` | 创建渠道 |
| `PUT /api/channel/` | 更新渠道 |
| `GET /api/channel/{channel_id}` | 获取渠道详情 |
| `DELETE /api/channel/{channel_id}` | 删除渠道 |
| `GET /api/channel/test` | 测试所有渠道 |
| `GET /api/channel/test/{channel_id}` | 测试单个渠道 |
| `GET /api/channel/default-pricing` | 默认定价 |
| `GET /api/channel/metadata` | 渠道元数据 |
| `DELETE /api/channel/disabled` | 清理已禁用渠道 |

#### 系统配置 (Root, role >= 100)

| Endpoint | 描述 |
|----------|------|
| `GET /api/option/` | 系统配置列表 |
| `PUT /api/option/` | 更新系统配置 |

#### 充值 & 兑换

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/topup/` | AdminAuth | 充值记录列表 |
| `POST /api/topup/` | UserAuth | 创建充值 |
| `PUT /api/topup/` | AdminAuth | 更新充值 |
| `GET /api/recharge/self` | UserAuth | 个人充值记录 |
| `POST /api/recharge/` | UserAuth | 创建充值请求 |
| `GET /api/recharge/` | AdminAuth | 全部充值请求 |
| `POST /api/recharge/{recharge_id}/approve` | AdminAuth | 审批充值 |
| `POST /api/recharge/{recharge_id}/reject` | AdminAuth | 拒绝充值 |
| `GET /api/redemption/` | AdminAuth | 兑换码列表 |
| `GET /api/redemption/search` | AdminAuth | 搜索兑换码 |
| `GET /api/redemption/{redemption_id}` | AdminAuth | 兑换码详情 |
| `POST /api/redemption/` | AdminAuth | 创建兑换码 |
| `PUT /api/redemption/` | AdminAuth | 更新兑换码 |
| `DELETE /api/redemption/{redemption_id}` | AdminAuth | 删除兑换码 |

#### Dashboard

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/user/dashboard` | UserAuth | 使用量仪表盘（admin 可看全局） |
| `GET /api/user/dashboard/users` | AdminAuth | 用户列表（仪表盘筛选用） |

#### 预算 (Budget)

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/v1/budget/status` | UserAuth | 预算状态 |
| `GET /api/v1/budget/history` | UserAuth | 预算历史 |
| `GET /api/v1/admin/budgets` | AdminAuth | 全部预算 |
| `GET /api/v1/admin/budgets/stats` | AdminAuth | 预算统计 |
| `PUT /api/v1/admin/budgets/{user_id}` | AdminAuth | 更新用户预算 |
| `POST /api/v1/admin/budgets/reset/{user_id}` | AdminAuth | 重置用户预算 |

#### 前端页面 (Web)

| Endpoint | 描述 |
|----------|------|
| `GET /` | SPA 入口 |
| `GET /login` | 登录页 |
| `GET /assets/{path}` | 静态资源 |
| `GET /{path}` | SPA fallback |

### 中继 API (`/v1/*`)

| Endpoint | Format | DeepSeek | GLM | Qwen | Kimi | MiniMax |
|----------|--------|----------|-----|------|------|---------|
| `POST /v1/chat/completions` | OpenAI Chat | Direct | `/api/paas/v4/...` | Direct | Direct | Direct |
| `POST /v1/messages` | Claude Messages | Direct (`/anthropic`) | `open.bigmodel.cn/api/anthropic` | Direct | Direct | Direct |
| `POST /v1/responses` | OpenAI Response | Converted to Chat | Converted to Chat | Converted | Converted | Converted |
| `GET /v1/models` | OpenAI | Model list | Model list | Model list | Model list | Model list |
| `GET /v1/models/{model_id}` | OpenAI | Model detail | Model detail | Model detail | Model detail | Model detail |

### Auth

- **管理 API**: Session cookie (`itsdangerous URLSafeTimedSerializer`)，也支持 `Authorization: Bearer <access_token>` 回退
- **中继 API**: Bearer token (`Authorization: Bearer <key>`)，支持 `token_key:channel_id` 格式锚定渠道
- **响应格式**: `{"success": bool, "message"?: str, "data"?: T, "total"?: int}`

## 配置

| Env Var | 默认值 | 说明 |
|---------|--------|------|
| `SERVER_PORT` | 8000 | 服务端口 |
| `DEBUG` | false | 调试模式 |
| `SQLITE_PATH` | uniapi.db | SQLite 数据库路径 |
| `SQL_DSN` | — | MySQL/PostgreSQL DSN |
| `SESSION_SECRET` | auto | Session cookie 签名密钥 |
| `TOKEN_KEY_PREFIX` | sk- | Token 密钥前缀 |
| `API_RATE_LIMIT` | 480 | 管理 API 每分钟请求上限 |
| `RELAY_RATE_LIMIT` | 480 | 中继 API 每分钟请求上限 |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |
| `GLM_API_KEY` | — | GLM (智谱) API key |
| `QWEN_API_KEY` | — | Qwen (百炼) API key |
| `KIMI_API_KEY` | — | Kimi (Moonshot) API key |
| `MINIMAX_API_KEY` | — | MiniMax API key |
| `BUDGET_REDIS_URL` | — | Redis 地址 (留空且 BUDGET_ENABLED=false 禁用) |
| `BUDGET_ENABLED` | false | 启用预算系统 |
| `DEFAULT_MONTHLY_BUDGET` | 800.0 | 默认月预算 |

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
