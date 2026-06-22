# UniAPI 管理员配置手册

> 版本：0.10.16 | 适用：uniapi-py Python 后端

---

## 目录

1. [部署](#一部署)
2. [环境变量参考](#二环境变量参考)
3. [应用模式](#三应用模式)
4. [频道管理](#四频道管理)
5. [负载均衡](#五负载均衡)
6. [中间件配置](#六中间件配置)
7. [管理 API 参考](#七管理-api-参考)
8. [模型定价配置](#八模型定价配置)
9. [Fusion 融合模式](#九fusion-融合模式)
10. [故障排查](#十故障排查)

---

## 一、部署

### 1.1 Docker 部署（推荐）

```bash
# 构建并启动
docker compose up --build -d

# 查看日志
docker compose logs -f
```

### 1.2 手动部署

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 启动
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 开发模式（热重载）
uvicorn app.main:app --reload --port 8000
```

### 1.3 生产部署建议

- 使用 `--workers N` 启动多进程（N = CPU 核心数）
- 前置 nginx/Caddy 反向代理处理 TLS 和静态资源
- 数据库切换为 MySQL/PostgreSQL（设置 `SQL_DSN`）
- 配置 `SESSION_SECRET` 为随机字符串

---

## 二、环境变量参考

### 2.1 基础配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SERVER_PORT` | 8000 | 服务端口 |
| `DEBUG` | false | 调试模式（SQL 日志等） |

### 2.2 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SQLITE_PATH` | uniapi.db | SQLite 数据库路径 |
| `SQL_DSN` | — | MySQL/PostgreSQL DSN，设置后自动切换 |

### 2.3 认证与会话

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SESSION_SECRET` | 随机生成 | Session cookie 签名密钥（生产务必设置固定值） |
| `COOKIE_MAX_AGE_HOURS` | 168 | 登录会话有效期（小时） |
| `TOKEN_KEY_PREFIX` | sk- | API Token 密钥前缀 |

### 2.4 速率限制

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_RATE_LIMIT` | 480 | 管理 API 每分钟请求上限 |
| `RELAY_RATE_LIMIT` | 480 | 中继 API 每分钟请求上限 |

### 2.5 供应商 API Key

每个接入的供应商需要在环境变量中配置 API key：

| 变量 | 供应商 |
|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek |
| `GLM_API_KEY` | 智谱 GLM（格式：`id.secret`） |
| `QWEN_API_KEY` | 阿里百炼 Qwen |
| `KIMI_API_KEY` | Moonshot Kimi |
| `MINIMAX_API_KEY` | MiniMax |

**注意**：如果使用频道管理（推荐），可以在 Channel 表中逐频道配置 API key，此时环境变量作为全局默认值。详见[频道管理](#四频道管理)。

### 2.6 预算控制

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BUDGET_ENABLED` | true | 启用预算管控 |
| `BUDGET_REDIS_URL` | — | Redis 连接地址（预算管控需要 Redis） |
| `DEFAULT_MONTHLY_BUDGET` | 800.0 | 每月默认预算（元） |

---

## 三、应用模式

uniapi-py 支持四种请求模式，通过请求体中的 `model` 字段切换。

### 3.1 直通模式（Normal Passthrough）

指定具体模型名，请求直接转发到对应供应商：

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**路由流程**：
```
model="deepseek-v4-pro"
  → registry.resolve_channel_type("deepseek-v4-pro") → 39 (DeepSeek)
  → _select_channel(db, "deepseek-v4-pro", 39) → 按 weight 加权随机选 channel
  → 使用 channel 的 API key 和 base_url → 转发到上游
```

### 3.2 自动模式（Auto）

`model="auto"` 时，系统在所有已启用渠道中按价格从低到高选择模型：

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**路由流程**：
```
model="auto"
  → SELECT * FROM channels WHERE status=1
  → 遍历所有 channel 的模型列表
  → 过滤出 Token 有权限的模型
  → 按价格 (input_ratio + output_ratio) 升序排序
  → 取最便宜的模型
  → 使用该 channel 的 API key 和 base_url 转发到上游
```

**使用场景**：前端不关心具体模型，系统自动选性价比最高的渠道。Token 的 `models` 字段控制可用范围。

### 3.3 融合模式（Fusion）

`model="fusion"` 时，请求同时发给多个模型，经 Judge（裁判）交叉分析后由 Synthesizer（汇编器）生成融合答案：

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "fusion",
    "messages": [{"role": "user", "content": "设计微服务拆分方案"}]
  }'
```

**流水线**：
```
                   ┌─ DeepSeek V4 Pro ─┐
请求 → Panel 并发 → ├─ MiniMax M3     ─┤→ Judge(交叉分析) → Synthesizer(融合) → 最终答案
                   └─ GLM-4-Plus    ─┘
```

**返回结果**包含 `fusion_meta` 字段：
```json
{
  "id": "fuse-705256",
  "model": "fusion",
  "choices": [{"message": {"content": "融合后的答案..."}}],
  "usage": {
    "fusion_breakdown": {
      "panel": {
        "deepseek-v4-pro": {"prompt_tokens": 5, "completion_tokens": 51},
        "MiniMax-M3": {"prompt_tokens": 177, "completion_tokens": 37},
        "glm-4-plus": {"prompt_tokens": 10, "completion_tokens": 12}
      },
      "judge_model": "MiniMax-M3",
      "synthesizer_model": "deepseek-v4-pro"
    }
  },
  "fusion_meta": {
    "judge_confidence": 0.85,
    "latency_ms": 16441,
    "fallback_triggered": false
  }
}
```

**特点**：
- 质量更高（多模型交叉验证），但延迟增加（~3-5× 单模型）
- 消耗更多 token（panel × N + judge + synthesizer）
- 不支持流式（所有模型完成后才输出）
- 面板默认组合：DeepSeek V4 Pro + MiniMax M3 + GLM-4-Plus

**前提条件**：环境变量中至少配置了 DeepSeek、MiniMax、GLM 三个 API key 中的两个。

### 3.4 协议自动适配

系统自动识别入站协议（OpenAI Chat / Anthropic Messages / OpenAI Responses），并根据供应商的原生支持情况决定是直通还是转换：

```
入站协议          供应商原生支持        动作
──────────────────────────────────────────────────
/v1/chat/completions  → 支持 Chat     → 直通，零转换
/v1/messages          → 支持 Claude   → 直通，零转换
/v1/chat/completions  → 仅支持 Claude → 自动转换为 Claude 格式再转发
/v1/messages          → 仅支持 Chat   → 自动转换为 Chat 格式再转发
/v1/responses         → 统一转为 Chat → 转换为 Chat 后转发
```

所有适配器（Adaptor）通过 `NATIVE_FORMATS` 声明自己的原生支持格式，路由层自动选择最优路径。详见 `app/relay/adaptor.py`。

---

## 四、频道管理

频道（Channel）是数据库中的一条记录，代表一个供应商 + API key + 模型配置的组合。

### 4.1 Channel 表字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | int | 供应商类型编码，见下方说明 |
| `key` | text | 该频道的 API key（优先于环境变量） |
| `status` | int | 1=启用, 0=禁用 |
| `name` | string | 频道名称（标识用） |
| `models` | text | 支持的模型名，逗号分隔，如 `"deepseek-v4-pro,deepseek-v4-flash"` |
| `base_url` | text | 自定义 API 端点（覆盖 adaptor 默认值） |
| `weight` | int | 负载均衡权重，越大被选中概率越高 |
| `priority` | int | 优先级（auto 模式用），越大越优先 |
| `group` | string | 用户组限制，`"default"` 为所有用户可用 |

**供应商类型编码**：

| 编码 | 供应商 |
|------|--------|
| 39 | DeepSeek |
| 41 | GLM（智谱） |
| 50 | Qwen（百炼） |
| 25 | Kimi（Moonshot） |
| 27 | MiniMax |

### 4.2 CRUD 操作

所有频道管理通过管理 API 操作，需要 Admin 权限：

```bash
# 列出频道
curl -H "Authorization: Bearer sk-xxx" http://localhost:8000/api/channel/

# 创建频道（DeepSeek，v4-pro，weight=10，priority=100）
curl -X POST http://localhost:8000/api/channel/ \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "type": 39,
    "name": "主力 DeepSeek",
    "key": "sk-real-api-key-here",
    "models": "deepseek-v4-pro",
    "base_url": "",
    "weight": 10,
    "priority": 100,
    "status": 1,
    "group": "default"
  }'

# 更新频道
curl -X PUT http://localhost:8000/api/channel/ \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{"id": 1, "weight": 20, "priority": 200}'

# 删除频道
curl -X DELETE http://localhost:8000/api/channel/1 \
  -H "Authorization: Bearer sk-xxx"

# 搜索频道
curl "http://localhost:8000/api/channel/search?keyword=deepseek" \
  -H "Authorization: Bearer sk-xxx"

# 测试频道连通性
curl http://localhost:8000/api/channel/test/1 \
  -H "Authorization: Bearer sk-xxx"

# 查看频道类型列表
curl http://localhost:8000/api/channel/types

# 查看默认定价
curl "http://localhost:8000/api/channel/default-pricing?type=39"
```

### 4.3 配置示例

单供应商多频道（负载均衡）：
```
Channel A: type=39, name="DeepSeek 主力", models="deepseek-v4-pro",  weight=10, key=key1
Channel B: type=39, name="DeepSeek 备用", models="deepseek-v4-pro",  weight=5,  key=key2
Channel C: type=39, name="DeepSeek 便宜", models="deepseek-v4-flash", weight=3,  key=key3
```
→ 请求 `deepseek-v4-pro` 时，A:B 被概率 ≈ 2:1 分发。

多供应商：
```
Channel A: type=39, name="DeepSeek", models="deepseek-v4-pro"
Channel B: type=41, name="GLM",      models="glm-5.2"
```
→ 请求 `deepseek-v4-pro` 走 A，请求 `glm-5.2` 走 B。

---

## 五、负载均衡

### 5.1 加权随机分发

当多个频道支持同一模型时，系统按 `weight` 字段加权随机选择：

```
概率 = channel.weight / sum(all matching channels.weight)

Channel A: weight=10  → 10/16 ≈ 62.5%
Channel B: weight=5   →  5/16 ≈ 31.25%
Channel C: weight=1   →  1/16 ≈  6.25%
```

**实现位置**：`app/routers/v1/relay.py`, `_select_channel()`

### 5.2 故障降级

当上游返回 429/500/502/503 时，自动查找备选频道：

1. 查询同 `type` 的已启用频道
2. 选一个支持不同模型的频道
3. 自动重试（最多一次降级）
4. 连续 3 次失败自动禁用该频道

**切换前后 API key 不同**（如果频道配置了自己的 key），因此 429 降级有效。

### 5.3 自动禁用

频道连续 3 次失败（429/5xx）后自动 `status=0`，不再接收流量。进程重启后重置（内存计数器）。

---

## 六、中间件配置

以下中间件在 `app/middleware.py` 中实现，默认全部启用：

### 6.1 速率限制

- 中继 API（`/v1/*`）：`RELAY_RATE_LIMIT`（默认 480 rpm）
- 管理 API（`/api/*`）：`API_RATE_LIMIT`（默认 480 rpm）
- 按客户端 IP 计数，窗口 60 秒
- 超过限制返回 429 + `Retry-After: 60` 头

**注意**：单进程内存计数器，多 worker 部署下实际限额 = 配置值 × worker 数。

### 6.2 PII 脱敏

自动替换请求体中的敏感信息：
- 手机号（`1[3-9]\d{9}`）→ `[PHONE]`
- 邮箱 → `[EMAIL]`
- API Key（`sk-` 开头 40+ 字符）→ `[API_KEY]`
- 身份证号 → `[ID_CARD]`

### 6.3 审计日志

每次 API 调用记录到日志：
```
AUDIT | POST /v1/chat/completions | 200 | 1234ms | 512B
```

---

## 七、管理 API 参考

### 7.1 认证体系

| 级别 | 条件 | 适用端点 |
|------|------|----------|
| Public | 无需认证 | 状态、模型列表、登录、注册 |
| UserAuth | role >= 1，session cookie | 个人信息、Token、日志、Dashboard |
| AdminAuth | role >= 10，session cookie | 用户管理、频道管理、全部日志 |
| RootAuth | role >= 100，session cookie | 系统配置 |
| TokenAuth | Bearer token | 中继 API（`/v1/*`） |

中继 API 的 Token 支持频道锚定：
```bash
# 使用频道 ID=5 的配置转发
Authorization: Bearer sk-your-token-key:5
```

### 7.2 端点速查

```bash
# ── 公共 ──
GET  /api/status                          # 系统状态
GET  /api/models/display                  # 模型列表含定价
GET  /api/channel/types                   # 可用供应商类型
GET  /health                              # 健康检查

# ── 认证 ──
POST /api/user/login                      # 登录
POST /api/user/register                   # 注册
GET  /api/user/logout                     # 登出
GET  /api/user/self                       # 当前用户信息
PUT  /api/user/self                       # 更新个人信息

# ── 频道管理（Admin）──
GET  /api/channel/                        # 列出频道
POST /api/channel/                        # 创建频道
PUT  /api/channel/                        # 更新频道
DELETE /api/channel/{id}                  # 删除频道
GET  /api/channel/search                  # 搜索频道
GET  /api/channel/test                    # 测试所有频道
GET  /api/channel/test/{id}               # 测试单个频道

# ── 用户管理（Admin）──
GET  /api/user/                           # 列出用户
POST /api/user/                           # 创建用户
GET  /api/user/{id}                       # 用户详情
PUT  /api/user/                           # 更新用户
DELETE /api/user/{id}                     # 删除用户
GET  /api/group/                          # 用户组列表

# ── Token 管理 ──
GET  /api/token/                          # 列出 Token
POST /api/token/                          # 创建 Token
PUT  /api/token/                          # 更新 Token
DELETE /api/token/{id}                    # 删除 Token
POST /api/token/consume                   # 消耗配额
GET  /api/token/balance                   # 查询余额

# ── 日志 ──
GET  /api/log/self                        # 个人日志
GET  /api/log/                            # 全部日志（Admin）
DELETE /api/log/                           # 删除旧日志

# ── 系统配置（Root）──
GET  /api/option/                         # 查看配置
PUT  /api/option/                          # 更新配置

# ── 预算 ──
GET  /api/v1/budget/status                # 预算状态
GET  /api/v1/budget/history               # 预算历史
GET  /api/v1/admin/budgets                # 全部预算（Admin）
PUT  /api/v1/admin/budgets/{user_id}      # 更新用户预算

# ── 中继 API ──
POST /v1/chat/completions                 # OpenAI Chat（支持 auto/fusion）
POST /v1/messages                         # Anthropic Messages
POST /v1/responses                        # OpenAI Responses
GET  /v1/models                           # 列出所有模型
GET  /v1/models/{model_id}                # 模型详情
```

### 7.3 响应格式

所有管理 API 统一响应格式：

```json
// 成功
{"success": true, "data": {...}, "message": null}

// 列表
{"success": true, "data": [...], "total": 42}

// 错误
{"detail": "错误描述"}
```

---

## 八、模型定价配置

各供应商的定价在 `app/relay/adaptors/<provider>/pricing.py` 中配置。

### 8.1 定价模型

```python
# app/relay/adaptors/deepseek/pricing.py
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "deepseek-v4-pro": ModelConfig(
        input_ratio=3.0,          # ¥/M tokens 输入价格
        output_ratio=6.0,         # ¥/M tokens 输出价格
        cached_input_ratio=0.025, # ¥/M tokens 缓存命中价格
        max_tokens=384000,        # 最大输出 token 数
    ),
}
```

`input_ratio` / `output_ratio` 的值直接对应 ¥/M tokens 价格。系统用这些值做配额扣费和预算控制。

### 8.2 当前已配置供应商定价

| 供应商 | 模型 | 输入 ¥/M | 输出 ¥/M | 缓存 ¥/M |
|--------|------|---------|---------|---------|
| **DeepSeek** | v4-pro | 3.00 | 6.00 | 0.025 |
| | v4-flash | 1.00 | 2.00 | 0.02 |
| **GLM** | glm-5.2 | 0 | 0 | 0 |
| | glm-5.1 | 10.10 | 31.70 | 2.00 |
| | glm-5 | 7.20 | 23.00 | 1.44 |
| | glm-4.7 | 4.30 | 15.80 | 0.86 |
| | glm-4.5-air | 1.40 | 7.90 | 0.28 |
| | glm-4.7-flash | 0 | 0 | 0 |
| | glm-z1-flash | 0 | 0 | 0 |
| **Qwen** | qwen3.7-max | 12.00 | 36.00 | 2.40 |
| | qwen3.7-plus | 2.00 | 8.00 | 0.40 |
| | qwen3.6-plus | 2.00 | 12.00 | 0.40 |
| | qwen3.6-flash | 0.50 | 2.00 | 0.10 |
| | qwen3.5-plus | 0.80 | 4.80 | 0.16 |
| | qwen3.5-flash | 0.35 | 1.40 | 0.07 |
| | qwen3-coder-plus | 7.34 | 36.70 | 1.47 |
| | qwen3-coder-flash | 2.00 | 8.00 | 0.40 |
| | qwen-turbo | 0.30 | 1.20 | 0.06 |
| **Kimi** | kimi-k2.7-code | 6.50 | 27.00 | 1.30 |
| | kimi-k2.7-code-highspeed | 13.00 | 54.00 | 2.60 |
| | kimi-k2.6 | 6.50 | 27.00 | 1.10 |
| | kimi-k2.5 | 4.00 | 21.00 | 0.70 |
| | kimi-k2 | 2.00 | 10.00 | 0.40 |
| **MiniMax** | MiniMax-M3 | 2.16 | 8.64 | 0.43 |
| | MiniMax-M2.7 | 2.16 | 8.64 | 0.43 |
| | MiniMax-M2.7-highspeed | 4.32 | 17.28 | 0.43 |
| | MiniMax-M2.5 | 2.16 | 8.64 | 0.22 |
| | MiniMax-M2.5-highspeed | 4.32 | 17.28 | 0.22 |
| | MiniMax-M2.1 | 2.16 | 8.64 | 0.22 |
| | MiniMax-M2.1-highspeed | 4.32 | 17.28 | 0.22 |
| | MiniMax-M2 | 2.16 | 8.64 | 0.22 |

---

## 九、Fusion 融合模式

### 9.1 工作原理

Fusion 将请求并发发给多个模型（Panel），由 Judge 模型做交叉分析（找出共识、矛盾和遗漏），最后由 Synthesizer 模型综合所有信息生成最终答案。

```
                    ┌──────────────────────┐
                    │  用户请求             │
                    │  model="fusion"       │
                    └──────────┬───────────┘
                               ▼
                    ┌──────────────────────┐
                    │  Panel 并发分发       │
                    │  asyncio.gather       │
                    └──────┬───────┬───────┘
                           ▼       ▼
              ┌─────────────────┐ ┌─────────────────┐
              │ DeepSeek V4 Pro │ │  MiniMax M3     │
              │ (推理/综合)      │ │ (代码/中文)      │
              └────────┬────────┘ └────────┬────────┘
                       ▼                   ▼
              ┌────────────────────────────────────┐
              │  Judge (MiniMax M3)                │
              │  交叉分析：共识/矛盾/盲区/置信度    │
              └────────────────┬───────────────────┘
                               ▼
              ┌────────────────────────────────────┐
              │  Synthesizer (DeepSeek V4 Pro)     │
              │  融合各模型回答 → 最终答案          │
              └────────────────┬───────────────────┘
                               ▼
                    ┌──────────────────────┐
                    │  最终答案（含融合元数据）│
                    └──────────────────────┘
```

### 9.2 前提条件

Fusion 引擎启动需要至少两个供应商的 API key 已配置（在环境变量中）：

```bash
DEEPSEEK_API_KEY=sk-xxx        # 必须：Panel + Synthesizer
MINIMAX_API_KEY=xxx            # 建议：Panel + Judge
GLM_API_KEY=id.secret          # 建议：Panel
```

缺少 API key 的模型会被自动跳过。如果所有 Panel 模型都不可用，返回 fallback 错误。

**Panel 模型选择**：从 Token 授权的模型中，与 Fusion 注册表可用模型取交集。不足 2 个时自动降级为单模型直通。Judge 和 Synthesizer 取 Panel 中能力最强的模型。

### 9.3 默认策略

在 `app/main.py` 的 `_build_fusion_registry()` 中配置：

```python
FusionConfig(
    panel=["deepseek-v4-pro", "MiniMax-M3", "glm-4-plus"],
    judge="MiniMax-M3",
    synthesizer="deepseek-v4-pro",
    timeout_seconds=30,
    retry_count=2,
    fallback_model="deepseek-v4-pro",
)
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `panel` | `[deepseek-v4-pro, MiniMax-M3, glm-4-plus]` | 参与评审的模型列表 |
| `judge` | `MiniMax-M3` | 交叉分析的裁判模型 |
| `synthesizer` | `deepseek-v4-pro` | 生成最终答案的汇编模型 |
| `timeout_seconds` | 30 | 单个模型调用超时 |
| `retry_count` | 2 | 失败重试次数 |
| `fallback_model` | `deepseek-v4-pro` | 全部失败后的降级模型 |
| `max_tokens` | 8192 | 单模型最大输出 token 数 |
| `temperature` | 0.7 | 推理温度（0-1） |

---

## 十、故障排查

### 10.1 常见问题

| 现象 | 原因 | 解决 |
|------|------|------|
| `curl /health` 返回 200 但 `<h1>UniAPI...</h1>` | web 路由拦截 health | 检查路由注册顺序，health 必须在 web router 之前 |
| `model="auto"` 返回"无可用频道" | 未创建任何频道或频道 status≠1 | 通过 `/api/channel/` 创建频道 |
| `model="fusion"` 返回"Fusion engine not available" | 未配置任何供应商 API key | 检查 `DEEPSEEK_API_KEY` 等环境变量 |
| 上游 429 限流 | API key 达到供应商并发上限 | 创建多个频道分配不同 API key，设 `weight` 做负载均衡 |
| 上游 401 认证失败 | API key 无效或过期 | 检查频道配置的 `key` 和环境变量 `*_API_KEY` |
| 配额不足拒绝请求 | Token 配额用完 | admin 调整用户配额或充值 |
| SSE 流式响应卡顿 | 响应全量缓冲后转换 | 检查 `openai_compatible.py` 是否仍有 `list()` 调用 |
| 多 worker 下限流不准 | 内存计数器不共享 | 考虑部署 Redis 共享限流状态 |

### 10.2 日志查看

```bash
# 审计日志（中间件自动记录）
AUDIT | POST /v1/chat/completions | 200 | 1234ms | 512B

# 频道故障降级
FALLBACK | 429 -> model=deepseek-v4-flash | channel_type=39

# 频道自动禁用
Auto-disabling channel 3 after 3 consecutive failures

# Fusion 流程
Fusion started | id=fuse-705256 | panel=[deepseek-v4-pro, ...]
Judge analysis complete | confidence=0.85
Synthesis complete | model=deepseek-v4-pro | tokens=642
```

### 10.3 调试端点

```bash
# 健康检查
curl http://localhost:8000/health
# → {"status":"healthy","service":"uniapi-py","version":"0.10.16"}

# 管理统计
curl http://localhost:8000/api/admin/stats
# → {"total_requests":0,"models_count":32,...}
```
