# uniapi-py

**UniAPI** 的 Python 后端实现 — 一个聚合多供应商 LLM 的统一 API 网关。

> 这是 [uniapi](https://github.com/decardlabs/uniapi) (Go) 的 Python 重写版，前端复用原项目的 React/TypeScript 实现。
>
> **为什么用 Python 重写？** 原 Go 版的适配器模式和路由逻辑适合静态类型语言，但在快速迭代供应商适配器和动态协议转换场景下，Python 的类型系统和元编程能力（ABC + 注册表模式）能显著降低新增供应商的开发成本。Python 版不追求替换 Go 版，而是作为轻量级替代方案，聚焦于快速接入新供应商和实验性功能验证。

## Status

🚧 **All phases complete** — 604 tests, all GREEN (11 skipped)

| Phase | 内容 | 状态 | 测试数 |
|-------|------|------|--------|
| 1 | Auth, Status, DeepSeek Chat Completions | ✅ | 28 |
| 2 | Management API CRUD, Billing | ✅ | 148 |
| 3 | Multi-format: NATIVE_FORMATS routing | ✅ | 7 |
| 4 | Extensibility + Budget Pool Management | ✅ | 46 |
| 5 | Upstream 429 retry + failover | ✅ | 273 |
| 6 | Recharge & Redemption codes | ✅ | 48 |

### 已接入供应商（5 家）

> DeepSeek/Qwen/Kimi/MiniMax 支持 OpenAI Chat 和 Anthropic Claude Messages 双协议直通；GLM（智谱）Claude Messages 走转换路径。

| Provider | NATIVE_FORMATS | 模型数 |
|----------|---------------|--------|
| **DeepSeek** | `chat_completions`, `claude_messages` | 2 |
| **GLM (智谱)** | `chat_completions` | 7 |
| **Qwen (百炼)** | `chat_completions`, `claude_messages` | 9 |
| **Kimi (Moonshot)** | `chat_completions`, `claude_messages` | 5 |
| **MiniMax** | `chat_completions`, `claude_messages` | 8 |

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
    NATIVE_FORMATS = {"chat_completions"}

    def _get_path_for_mode(self, relay_mode: int) -> str:
        if relay_mode == CLAUDE_MESSAGES:
            return "https://open.bigmodel.cn/api/anthropic/v1/messages"
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
│   ├── exceptions.py        # 统一异常处理 + handler
│   ├── error_codes.py       # 错误码定义 (UNIAPI_ 前缀)
│   ├── middleware.py         # Audit, PIIMask, RateLimit, RequestTiming, RequestID
│   ├── version.py           # 自动生成版本号 (git describe)
│   ├── models/              # SQLAlchemy ORM
│   │   ├── user.py, token.py, channel.py, ability.py
│   │   ├── log.py, option.py, budget.py
│   │   ├── recharge.py, redemption.py, passkey.py
│   │   └── base.py
│   ├── schemas/             # Pydantic v2 validation
│   │   ├── common.py, user.py, relay.py, error.py
│   │   └── recharge.py, redemption.py
│   ├── services/            # 业务逻辑
│   │   ├── auth.py, user.py, token.py
│   │   ├── recharge.py, redemption.py
│   │   ├── email.py, totp.py, webauthn.py
│   ├── budget/              # 预算系统
│   │   ├── arbiter.py, pricing.py, redis.py
│   ├── routers/
│   │   ├── api/             # 管理 API (/api/*)
│   │   └── v1/              # 中继 API (/v1/*)
│   ├── relay/               # 上游供应商中继
│   │   ├── adaptor.py       # BaseAdaptor ABC
│   │   ├── registry.py      # 供应商注册表
│   │   ├── mode.py          # RelayMode enum
│   │   ├── meta.py          # RelayMeta dataclass
│   │   ├── converter.py     # anthropic_to_chat(), responses_to_chat()
│   │   ├── sse_converter.py # SSE 格式转换
│   │   ├── channeltype.py   # 渠道类型常量
│   │   ├── upstream_errors.py # 上游错误映射
│   │   ├── openai_compatible.py  # SSE streaming + shared relay
│   │   └── adaptors/
│   │       ├── deepseek/    # DeepSeek adaptor
│   │       ├── glm/         # GLM (Zhipu/智谱) adaptor
│   │       ├── qwen/        # Qwen (百炼) adaptor
│   │       ├── kimi/        # Kimi (Moonshot) adaptor
│   │       └── minimax/     # MiniMax adaptor
│   └── fusion/              # 多模型融合引擎
│       ├── schemas.py
│       ├── adapters/        # Provider adapters (5 providers)
│       └── core/            # FusionEngine, Judge, Synthesizer
└── tests/
    ├── conftest.py                  # 测试 fixtures + FakeRedisClient
    ├── test_api.py                  # Phase 1: API 集成 (5 tests)
    ├── test_deepseek_normalize.py   # Phase 1: DeepSeek 归一化 (23 tests)
    ├── test_channeltype.py          # 渠道类型测试 (15 tests)
    ├── test_relay_comparison.py     # Relay 对比测试 (3 tests)
    ├── phase2/                      # Phase 2: 管理 API (128 tests)
    ├── phase3/                      # Phase 3: 多格式 (7 tests)
    ├── phase4/                      # Phase 4: 可扩展性 (14 tests)
    ├── phase5/                      # Phase 5: 429重试与退路 (273 tests)
    ├── phase6/                      # Phase 6: 充值 & 兑换码 (48 tests)
    ├── glm/                         # GLM adaptor (13 tests)
    ├── test_cache_analytics.py     # Cache analytics (8 tests)
    ├── manual/                      # 手动测试工具
    └── live/                        # 实时测试框架
        ├── live_test.py             # 入口
        ├── config.py                # 环境变量配置
        ├── client.py                # HTTP 客户端 (含重试+SSE流式)
        ├── runner.py                # 运行器 + 报告
        ├── test_token_accuracy.py   # Token 精度测试
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
| `POST /v1/chat/completions` | OpenAI Chat | Direct | `/api/paas/v4/...` | Direct | Direct | Direct | 支持 `model="auto"`（价格最优选模型）和 `model="fusion"`（多模型融合） |
| `POST /v1/messages` | Claude Messages | Direct (`/anthropic`) | `open.bigmodel.cn/api/anthropic` | Direct | Direct | Direct |
| `POST /v1/responses` | OpenAI Response | Converted to Chat | Converted to Chat | Converted | Converted | Converted |
| `GET /v1/models` | OpenAI | Model list | Model list | Model list | Model list | Model list |
| `GET /v1/models/{model_id}` | OpenAI | Model detail | Model detail | Model detail | Model detail | Model detail |

### Auth

- **管理 API**: Session cookie (`itsdangerous URLSafeTimedSerializer`)，也支持 `Authorization: Bearer <access_token>` 回退
- **中继 API**: Bearer token (`Authorization: Bearer <key>`)，支持 `token_key:channel_id` 格式锚定渠道
- **响应格式**: `{"success": bool, "message"?: str, "data"?: T, "total"?: int}`

#### 认证扩展

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/verification?email=x&turnstile=x` | Public | 发送邮箱验证码 |
| `GET /api/reset_password?email=x&turnstile=x` | Public | 发送密码重置邮件 |
| `POST /api/user/reset` | Public | 确认密码重置 |
| `GET /api/oauth/state` | Public | OAuth CSRF state |
| `GET /api/oauth/github` | Public | GitHub OAuth 回调 |
| `GET /api/user/totp/status` | UserAuth | TOTP 状态查询 |
| `GET /api/user/totp/setup` | UserAuth | TOTP 设置信息 |
| `POST /api/user/totp/confirm` | UserAuth | 确认启用 TOTP |
| `POST /api/user/totp/disable` | UserAuth | 禁用 TOTP |
| `GET /api/user/passkey` | UserAuth | Passkey 列表 |
| `POST /api/user/passkey/register/begin` | UserAuth | Passkey 注册开始 |
| `POST /api/user/passkey/register/finish` | UserAuth | Passkey 注册完成 |
| `POST /api/user/passkey/login/begin` | Public | Passkey 登录开始 |
| `POST /api/user/passkey/login/finish` | Public | Passkey 登录完成 |
| `DELETE /api/user/passkey/{passkey_id}` | UserAuth | 删除 Passkey |
| `GET /api/user/cache-analytics` | UserAuth | 缓存命中分析 |

#### MCP 服务器管理 (Admin)

| Endpoint | Auth | 描述 |
|----------|------|------|
| `GET /api/mcp_servers/` | UserAuth | 列出 MCP 服务器 |
| `GET /api/mcp_servers/{server_id}` | UserAuth | 获取 MCP 服务器详情 |
| `POST /api/mcp_servers/` | UserAuth | 创建 MCP 服务器 |
| `PUT /api/mcp_servers/{server_id}` | UserAuth | 更新 MCP 服务器 |
| `DELETE /api/mcp_servers/{server_id}` | UserAuth | 删除 MCP 服务器 |
| `POST /api/mcp_servers/{server_id}/sync` | UserAuth | 同步 MCP 工具 |
| `POST /api/mcp_servers/{server_id}/test` | UserAuth | 测试 MCP 连接 |
| `GET /api/mcp_servers/{server_id}/tools` | UserAuth | 获取 MCP 工具列表 |

## 配置

| Env Var | 默认值 | 说明 |
|---------|--------|------|
| `SERVER_PORT` | 8000 | 服务端口 |
| `DEBUG` | false | 调试模式 |
| `SQLITE_PATH` | uniapi.db | SQLite 数据库路径 |
| `SQL_DSN` | — | MySQL/PostgreSQL DSN |
| `SESSION_SECRET` | auto (随机生成，重启后所有会话失效) | Session cookie 签名密钥 |
| `TOKEN_KEY_PREFIX` | sk- | Token 密钥前缀 |
| `API_RATE_LIMIT` | 480 | 管理 API 每分钟请求上限 |
| `RELAY_RATE_LIMIT` | 480 | 中继 API 每分钟请求上限 |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |
| `GLM_API_KEY` | — | GLM (智谱) API key |
| `QWEN_API_KEY` | — | Qwen (百炼) API key |
| `KIMI_API_KEY` | — | Kimi (Moonshot) API key |
| `MINIMAX_API_KEY` | — | MiniMax API key |
| `UPSTREAM_RETRY_MAX` | 4 | 上游重试次数（429/5xx） |
| `UPSTREAM_RETRY_BACKOFF_BASE` | 1.0 | 重试退避基数（秒） |
| `TURNSTILE_SECRET_KEY` | — | Cloudflare Turnstile Secret Key |
| `SMTP_TOKEN` | — | SMTP 密码（邮箱验证） |
| `GITHUB_CLIENT_SECRET` | — | GitHub OAuth Client Secret |
| `COOKIE_MAX_AGE_HOURS` | 168 | Session Cookie 有效期（小时） |
| `BUDGET_REDIS_URL` | — | Redis 地址 (留空且 BUDGET_ENABLED=false 禁用) |
| `BUDGET_ENABLED` | true | 启用预算系统 |
| `DEFAULT_MONTHLY_BUDGET` | 800.0 | 默认月预算 |

## 测试

### 单元测试 (604 tests, 11 skipped)

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

## 版本历史

### v0.11.x — 负载均衡 & 计费货币化

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.11.1** | 2026-06-23 | 修复 429 fallback 请求未实际执行（`continue` 退出循环）的 bug；修复 root 用户 balance=0 问题；收紧 `except Exception` 为具体 httpx 异常类型；`_record_channel_failure` 死 SELECT 清理；文档同步；修复流式日志 prompt_tokens/completion_tokens 为 0 的问题；Dashboard 余额卡片 CNY 显示 |

### v0.10.x — Bugfix & 功能迭代

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.10.20** | 2026-06-23 | 新增充值 & 兑换码完整子系统（RechargeRequest/RedemptionCode model + schema + service + CRUD endpoint + 48 tests）；MCP 服务器管理后端 CRUD；预算池管理系统 |
| **v0.10.19** | 2026-06-23 | 修复 relay.py `except Exception` 缺少 `as exc` 导致上游超时后 UnboundLocalError 连环崩溃；修复前端 TS 类型错误（lazy import、recharge 类型对齐） |
| **v0.10.18** | 2026-06-23 | （版本跳号） |
| **v0.10.17** | 2026-06-22 | 修复 GLM Coding Plan 特殊错误处理；MiniMax `prompt_tokens=0` 时 `cached_tokens` 解析错误；流式请求配额计算 bug 修复 |
| **v0.10.16** | 2026-06-22 | 429 exponential backoff retry（同渠道）；新增 `upstream_retry_max` / `upstream_retry_backoff_base` 配置项 |
| **v0.10.15** | 2026-06-22 | 修复流式中继请求中急切检查上游 HTTP 状态（streaming relay fix） |
| **v0.10.14** | 2026-06-22 | 实现真实缓存分析查询（替换占位符）；修复版本号正则匹配；流式 SSE 添加 usage 字段防止 Claude Code CLI 崩溃 |
| **v0.10.12** | 2026-06-22 | 修复 Claude Code 中转 GLM 时 metadata 字段导致 400 错误返回登录状态 |
| **v0.10.11** | 2026-06-22 | 修复原生 Claude 流式(raw_passthrough)不记录实际 token 用量；GLM 适配器注释说明 Coding Plan 限制 |
| **v0.10.10** | 2026-06-21 | 错误码体系 + Claude Messages SSE 直通修复 + 文档对齐 |
| **v0.10.9** | 2026-06-21 | 修复 MiniMax/Kimi/Qwen Claude Messages URL 缺少 `/v1/messages` 路径 |
| **v0.10.8** | 2026-06-21 | 修复流式 callback 未读取 `input_tokens`/`output_tokens` |
| **v0.10.7** | 2026-06-21 | SQLite WAL 模式 + 30s busy timeout，解决并发写锁 |
| **v0.10.6** | 2026-06-21 | 捕获 Anthropic SSE `message_delta` 中的 usage |
| **v0.10.5** | 2026-06-21 | Claude Messages `input_tokens`/`output_tokens` 兼容；channel metadata 动态读取；版本号统一为 `app.version`；Git tag 驱动版本 |

### v0.10.0 — 渠道修复

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.10.3** | 2026-06-20 | 模型名称归一化（创建/更新渠道时去别名） |
| **v0.10.0** | 2026-06-19 | Token 创建时间修复；MiniMax 模型名小写化；渠道自动禁用；模型别名 |

### v0.9.x — 流式与中间件

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.9.6** | 2026-06-18 | 流式 usage 录制；reasoning_content 缓存优化；前端超时 300s |
| **v0.9.4** | 2026-06-17 | 缓存感知成本计算（DeepSeek）；Python >=3.11 |

### v0.8.x — 前端独立

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.8.0** | 2026-06-16 | 前端 Fork 原 Go 仓库，自包含项目 |

### v0.7.x — 渠道管理

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.7.0** | 2026-06-15 | Channel CRUD API，前端兼容 |

### v0.5.x–v0.6.x — 协议转换与预算

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.6.0** | 2026-06-15 | Admin 预算管理 API |
| **v0.5.0** | 2026-06-14 | SSE 流式格式转换（Chat→Anthropic） |
| **v0.4.0** | 2026-06-13 | Anthropic ↔ Chat 协议互转 |

### v0.2.x–v0.3.x — 基础设施

| 版本 | 日期 | 变更 |
|------|------|------|
| **v0.3.0** | 2026-06-12 | Redis 预算验证 + 月度自动重置 |
| **v0.2.0** | 2026-06-11 | Phase 1 预算系统，5 供应商接入，对比测试 |

## 发布流程

版本号由 Git tag 驱动，`deploy.sh` 自动烘焙到 `app/version.py`。

```bash
# 1. 提交代码
git add ... && git commit -m "fix: description"

# 2. 打 tag（版本号唯一来源）
git tag -a v0.11.x -m "v0.11.x — release notes"

# 3. 推送
git push origin main && git push origin v0.11.x

# 4. 部署（自动读取 tag 生成版本号）
bash deploy.sh
```

版本号在 `pyproject.toml` 中维护，`deploy.sh` 自动读取并写入 `app/version.py`。Git tag 应与 `pyproject.toml` 中的版本号保持一致。`/health` 和 `/api/status` 均从 `app/version.py` 读取。

### 版本检查

```bash
curl https://api.ccbot.chat/health      # → {"status":"healthy","version":"0.11.x"}
curl https://api.ccbot.chat/api/status  # → {"success":true,"data":{"version":"0.11.x",...}}
```

### 部署文件

| 文件 | 说明 |
|------|------|
| `deploy.sh` | 一键部署：构建前端 → 生成版本号 → rsync 代码 → 重启服务 |
| `app/version.py` | 自动生成（gitignore），`VERSION = "0.11.x"` |
| `/etc/systemd/system/uniapi-py.service` | systemd 服务定义 |
| `/www/server/panel/vhost/nginx/extension/api.ccbot.chat/proxy_sse.conf` | Nginx SSE 优化参数 |

### 服务器运维信息

> 服务器: `api.ccbot.chat` (OpenCloudOS 9) · 项目目录: `/www/wwwroot/api.ccbot.chat` · SSH: `root@api.ccbot.chat`

| 路径 | 说明 |
|------|------|
| **`/www/wwwroot/api.ccbot.chat/uniapi.db`** | **SQLite 数据库文件（主数据库）** |
| `/www/wwwroot/api.ccbot.chat/uniapi.db-wal` | SQLite WAL 日志（写入缓冲，崩溃恢复用） |
| `/www/wwwroot/api.ccbot.chat/uniapi.db-shm` | SQLite 共享内存索引（WAL 索引） |
| `/www/wwwroot/api.ccbot.chat/logs/access.log` | 应用访问日志（stdout） |
| `/www/wwwroot/api.ccbot.chat/logs/error.log` | 应用错误日志（stderr） |
| `/www/wwwroot/api.ccbot.chat/.env` | 环境变量配置（首次部署生成，后续不覆盖） |

**数据库备份**（手动执行）：

```bash
# 在服务器上备份（WAL 模式下安全复制）
ssh root@api.ccbot.chat "cd /www/wwwroot/api.ccbot.chat && sqlite3 uniapi.db '.backup /www/wwwroot/api.ccbot.chat/backups/uniapi-$(date +%Y%m%d).db'"

# 拉取到本地
scp root@api.ccbot.chat:/www/wwwroot/api.ccbot.chat/uniapi.db ./uniapi-backup.db
```

**rsync 保护**: `deploy.sh` 的 `--exclude 'uniapi.db'` 确保部署时不会覆盖生产数据库。

## 技术栈

- **Python 3.11+** / **FastAPI** — Web framework
- **SQLAlchemy 2.0** (async) — ORM
- **Alembic** — Database migrations
- **Pydantic v2** — Validation
- **httpx** — Async HTTP client
- **pytest-asyncio** — Async testing

## License

MIT
