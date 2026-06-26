# UniAPI 错误码规范草案（v1.0）

## 1. 目标

本规范用于解决以下问题：

1. API 中转站自身错误与上游大模型错误语义混淆。
2. 前端无法稳定依赖不同供应商的原始错误码。
3. 监控、排障和告警无法统一聚合。

核心目标：

1. 对外只暴露稳定的 UniAPI 错误码体系。
2. 保留上游错误原文用于排障，但不作为主错误语义。
3. 保持 HTTP 状态码语义标准化。

---

## 2. 术语

1. **UniAPI 错误**：网关/中转站自身业务逻辑产生的错误。
2. **Upstream 错误**：上游模型供应商返回或请求上游时产生的错误。
3. **规范化错误**：UniAPI 对外返回的标准错误对象。

---

## 3. 总体原则

1. HTTP 状态码保留标准含义，不做私有扩展。
2. `error.code` 必须是 UniAPI 命名空间，不直接复用上游 code。
3. 上游原始错误必须放在 `error.upstream` 字段。
4. 前端逻辑仅依赖 `error.code`，不依赖 `error.upstream.code`。
5. 所有错误返回必须包含 `request_id`。

---

## 4. 命名空间设计

### 4.1 前缀约定

| 前缀 | 语义 | 示例 |
|------|------|------|
| `UNIAPI_` | 中转站自身业务错误 | `UNIAPI_INVALID_TOKEN` |
| `UPSTREAM_` | 上游调用链路错误（超时、连接失败、上游不可用） | `UPSTREAM_TIMEOUT` |
| `PROVIDER_<name>_` | 供应商专有语义（仅在必要时使用，尽量少） | `PROVIDER_DEEPSEEK_SAFETY_BLOCKED` |

### 4.2 命名风格

- `error.code` 使用大写蛇形命名（`UPPER_SNAKE_CASE`），如 `UNIAPI_INVALID_TOKEN`。
- `error.type` 使用小写蛇形命名（`lower_snake_case`），如 `authentication`。
- 两者命名风格不同是有意的：`code` 为机器可读枚举常量，`type` 为人读大类标签。

### 4.3 示例

```
UNIAPI_INVALID_TOKEN
UNIAPI_TOKEN_EXPIRED
UNIAPI_TOKEN_MODEL_NOT_ALLOWED
UNIAPI_MODEL_NOT_SUPPORTED
UNIAPI_RATE_LIMITED
UPSTREAM_TIMEOUT
UPSTREAM_CONNECTION_FAILED
UPSTREAM_BAD_RESPONSE
UPSTREAM_RATE_LIMITED
PROVIDER_DEEPSEEK_SAFETY_BLOCKED
```

---

## 5. 统一错误响应结构

```json
{
  "success": false,
  "error": {
    "code": "UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
    "message": "Token not allowed to use model 'deepseek-v4-pro'",
    "type": "authorization",
    "status_code": 403,
    "details": {
      "requested_model": "deepseek-v4-pro",
      "allowed_models": ["glm-5.2"]
    },
    "suggestion": "Call GET /v1/models to list available models.",
    "request_id": "req_abc123def456",
    "timestamp": "2026-06-21T10:30:00Z",
    "upstream": {
      "provider": "deepseek",
      "status_code": 502,
      "code": "upstream_timeout",
      "message": "Connection to upstream timed out after 300s",
      "request_id": "deepseek_req_xyz789"
    }
  }
}
```

### 5.1 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `success` | bool | 是 | 固定 `false`。保留此字段以兼容部分客户端无法读取 HTTP 状态码的场景。 |
| `error.code` | string | 是 | 客户端分支判断唯一依据。UniAPI 命名空间枚举值。 |
| `error.message` | string | 是 | 用户可读信息，可包含动态上下文（如模型名）。 |
| `error.type` | string | 是 | 大类标签，枚举见 §5.2。 |
| `error.status_code` | int | 是 | 镜像 HTTP 状态码，便于日志检索。 |
| `error.details` | object | 否 | 结构化上下文，承载 `code` 无法表达的动态参数。 |
| `error.suggestion` | string | 否 | 可执行的修复建议。 |
| `error.request_id` | string | 是 | 链路追踪 ID，来自 `RequestIDMiddleware`。 |
| `error.timestamp` | string | 是 | ISO 8601 UTC 时间戳。 |
| `error.upstream` | object | 否 | 仅上游相关错误返回，结构见 §5.3。 |

### 5.2 `error.type` 枚举

| type | 含义 | 典型 HTTP 状态码 |
|------|------|-----------------|
| `authentication` | 身份认证失败（你是谁） | 401 |
| `authorization` | 权限不足（你能做什么） | 403 |
| `validation` | 请求参数校验失败 | 400 |
| `quota` | 配额/余额不足 | 402 |
| `rate_limit` | 频率限制 | 429 |
| `upstream` | 上游调用链路错误 | 502 / 503 / 504 |
| `internal` | 系统内部错误 | 500 |
| `not_found` | 资源不存在 | 404 |

### 5.3 `error.upstream` 结构

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `provider` | string | 是 | 上游供应商名称（小写），如 `deepseek`、`glm`。 |
| `status_code` | int | 是 | 上游返回的 HTTP 状态码。 |
| `code` | string | 否 | 上游原始错误码（如有）。 |
| `message` | string | 否 | 上游原始错误消息（如有）。 |
| `request_id` | string | 否 | 上游请求 ID，用于关联上游 trace。 |

**重要约束**：

- `upstream` 字段**不包含** `raw` 字段。上游原始响应体不直接返回给客户端，而是写入服务端日志（由 `AuditMiddleware` 负责），避免：(1) 响应体膨胀；(2) 供应商内部敏感信息泄露。
- 排障时通过 `error.request_id` + `error.upstream.request_id` 关联日志。
- 如需在错误响应中保留更多上游上下文，放入 `error.details` 中经裁剪的关键字段，而非完整 raw body。

---

## 6. 状态码与错误码映射

### 6.1 认证与权限（authentication / authorization）

| HTTP | code | type |
|------|------|------|
| 401 | `UNIAPI_INVALID_TOKEN` | `authentication` |
| 401 | `UNIAPI_TOKEN_EXPIRED` | `authentication` |
| 403 | `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` | `authorization` |
| 403 | `UNIAPI_ADMIN_REQUIRED` | `authorization` |
| 403 | `UNIAPI_GROUP_ACCESS_DENIED` | `authorization` |

### 6.2 请求参数与业务（validation / not_found）

| HTTP | code | type |
|------|------|------|
| 400 | `UNIAPI_INVALID_REQUEST` | `validation` |
| 400 | `UNIAPI_MODEL_NOT_SPECIFIED` | `validation` |
| 400 | `UNIAPI_MODEL_NOT_SUPPORTED` | `validation` |
| 400 | `UNIAPI_UNSUPPORTED_PARAMETER` | `validation` |
| 404 | `UNIAPI_RESOURCE_NOT_FOUND` | `not_found` |

说明：`UNIAPI_INVALID_REQUEST` 为通用参数校验错误，具体原因由 `error.details` 和 `error.message` 承载。`UNIAPI_MODEL_NOT_SPECIFIED` / `UNIAPI_UNSUPPORTED_PARAMETER` 为高频子场景的精确码，客户端可针对性处理。

### 6.3 配额与限流（quota / rate_limit）

| HTTP | code | type |
|------|------|------|
| 402 | `UNIAPI_QUOTA_EXHAUSTED` | `quota` |
| 429 | `UNIAPI_RATE_LIMITED` | `rate_limit` |
| 429 | `UPSTREAM_RATE_LIMITED` | `upstream` |

#### 6.3.1 限流错误码区分规则

| 场景 | 错误码 | 说明 |
|------|--------|------|
| UniAPI 自身 RPM 限流（`RateLimitMiddleware` 触发） | `UNIAPI_RATE_LIMITED` | 网关层拒绝，请求未到达上游 |
| 上游供应商返回 429 | `UPSTREAM_RATE_LIMITED` | 上游拒绝，需携带 `error.upstream` |
| 预算系统拒绝（`BudgetArbiter.pre_check` 返回 False） | `UNIAPI_QUOTA_EXHAUSTED` | 配额不足，非频率问题 |

### 6.4 上游链路（upstream）

| HTTP | code | type |
|------|------|------|
| 502 | `UPSTREAM_BAD_RESPONSE` | `upstream` |
| 502 | `UPSTREAM_CONNECTION_FAILED` | `upstream` |
| 503 | `UPSTREAM_UNAVAILABLE` | `upstream` |
| 504 | `UPSTREAM_TIMEOUT` | `upstream` |

### 6.5 服务可用性

| HTTP | code | type |
|------|------|------|
| 503 | `UNIAPI_SERVICE_DISABLED` | `internal` |
| 503 | `UNIAPI_CHANNEL_UNAVAILABLE` | `upstream` |

### 6.6 系统内部（internal）

| HTTP | code | type |
|------|------|------|
| 500 | `UNIAPI_INTERNAL_ERROR` | `internal` |

---

## 7. 与上游错误的关系

### 7.1 规范化策略

1. 将上游错误分类映射到 UniAPI code。
2. 保留上游关键字段到 `error.upstream`（不含 raw body）。
3. 绝不将上游错误码直接提升为 `error.code`。

### 7.2 上游错误映射表

| 上游场景 | 上游状态码 | UniAPI code |
|----------|-----------|-------------|
| 上游返回 429 | 429 | `UPSTREAM_RATE_LIMITED` |
| 上游模型不存在 | 404 | `UNIAPI_MODEL_NOT_SUPPORTED` |
| 上游响应格式异常 | 200 但 body 非法 | `UPSTREAM_BAD_RESPONSE` |
| 上游连接失败 | N/A | `UPSTREAM_CONNECTION_FAILED` |
| 上游超时 | N/A | `UPSTREAM_TIMEOUT` |
| 上游返回 5xx | 500-599 | `UPSTREAM_UNAVAILABLE` |
| 上游内容安全拦截 | 400/403 | `PROVIDER_<name>_SAFETY_BLOCKED` |

### 7.3 示例：DeepSeek 安全拦截

上游返回：
```json
{"error": {"code": "content_filter", "message": "Content blocked by safety system"}}
```

UniAPI 规范化后：
```json
{
  "success": false,
  "error": {
    "code": "PROVIDER_DEEPSEEK_SAFETY_BLOCKED",
    "message": "Content blocked by upstream safety system",
    "type": "upstream",
    "status_code": 502,
    "request_id": "req_abc123",
    "timestamp": "2026-06-21T10:30:00Z",
    "upstream": {
      "provider": "deepseek",
      "status_code": 400,
      "code": "content_filter",
      "message": "Content blocked by safety system",
      "request_id": "deepseek_req_xyz"
    }
  }
}
```

---

## 8. 返回兼容策略

为避免一次性破坏客户端，采用两阶段：

### 阶段 A（兼容期）

1. 保留现有响应顶层的 `detail` 字段（当前 `HTTPException` 的输出格式）。
2. 同时新增标准 `error` 对象。
3. 文档声明 `detail` 即将废弃。

兼容期响应示例：
```json
{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'",
  "success": false,
  "error": {
    "code": "UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
    "message": "Token not allowed to use model 'deepseek-v4-pro'",
    "type": "authorization",
    "status_code": 403,
    "request_id": "req_abc123",
    "timestamp": "2026-06-21T10:30:00Z"
  }
}
```

### 阶段 B（收敛期）

1. 客户端统一迁移到 `error.code`。
2. 移除顶层 `detail` 字段。
3. `error.message` 作为唯一的人类可读消息。

---

## 9. 与现有异常体系的集成方案

### 9.1 现有体系分析

当前代码中存在两套错误返回：

1. **`AppException` + handler**（`app/exceptions.py`）：返回 `{"success": false, "message": ..., "data": ...}`。用于管理 API（`/api/*`）。
2. **`HTTPException`**（FastAPI 内置）：返回 `{"detail": "..."}` ，无结构化 code。用于 Relay API（`/v1/*`），约 20+ 处分散调用。
3. **`ErrorResponse` / `ErrorDetail`**（`app/schemas/common.py`）：定义了 `error.code` 字段但未被实际使用。

### 9.2 集成策略

**目标**：不引入第三套体系，而是扩展现有 `AppException` 使其覆盖 Relay API 场景。

#### 步骤 1：扩展 `AppException`

```python
class AppException(Exception):
    def __init__(
        self,
        status_code: int = 400,
        message: str = "Bad request",
        code: str = "UNIAPI_INVALID_REQUEST",   # 新增
        type: str = "validation",                # 新增
        details: dict = None,                    # 新增
        suggestion: str = None,                  # 新增
        upstream: dict = None,                   # 新增
        data: Any = None,                        # 保留兼容
    ):
        ...
```

#### 步骤 2：新增 Relay 专用子类

```python
class RelayException(AppException):
    """Relay API 专用异常，自动填充 upstream 等字段。"""
    pass

class UpstreamException(RelayException):
    """上游调用异常，强制要求 upstream 字段。"""
    def __init__(self, ..., upstream_provider: str, upstream_status: int, ...):
        ...
```

#### 步骤 3：改造 handler

更新 `app_exception_handler` 输出标准 `error` 结构。阶段 A 兼容期内同时输出 `detail` 和 `error`。

#### 步骤 4：逐步替换 relay.py 中的 `HTTPException`

将 20+ 处 `raise HTTPException(status_code=..., detail=...)` 替换为对应的 `AppException` 子类。

### 9.3 迁移路径

```
当前状态:
  /api/* → AppException → {success, message, data}
  /v1/*  → HTTPException → {detail}

阶段 A:
  /api/* → AppException → {success, message, data}          （保持不变）
  /v1/*  → RelayException → {detail, success, error}        （新增 error 对象）

阶段 B:
  /api/* → AppException → {success, error}                  （统一格式）
  /v1/*  → RelayException → {success, error}                （移除 detail）
```

---

## 10. 最小实施清单

1. **扩展 `AppException`**：增加 `code`、`type`、`details`、`suggestion`、`upstream` 字段。
2. **新增异常子类**：`RelayException`、`UpstreamException`，覆盖 relay.py 中的典型场景。
3. **改造异常处理器**：在 `app_exception_handler` 中输出标准 `error` 结构。
4. **在 relay 上游调用处增加 upstream 映射层**：将上游 HTTP 响应分类映射到 UniAPI code。
5. **给所有异常补齐 request_id**：确保 `RequestIDMiddleware` 的 ID 进入 `error.request_id`。
6. **增加测试**：
   - `error.code` 稳定性测试（见 §11）
   - upstream 映射测试（上游各状态码 → 正确的 UniAPI code）
   - 兼容响应测试（阶段 A 同时包含 `detail` 和 `error`）

---

## 11. 前端接入约定

前端必须遵循：

1. **仅使用 `error.code` 做业务分支**。
2. **将 `error.message` 用于用户提示**。
3. **将 `error.request_id` 上报日志**。
4. **不依赖 `error.upstream.code`**。

### 推荐分支示例

| error.code | 前端行为 |
|------------|---------|
| `UNIAPI_INVALID_TOKEN` | 触发重新登录 |
| `UNIAPI_TOKEN_EXPIRED` | 触发 token 刷新或重新登录 |
| `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` | 调用 `GET /v1/models` 刷新模型列表，提示用户切换模型 |
| `UNIAPI_MODEL_NOT_SUPPORTED` | 提示用户模型不可用，建议切换 |
| `UNIAPI_QUOTA_EXHAUSTED` | 展示充值/升级入口 |
| `UNIAPI_RATE_LIMITED` | 显示限流提示，按 `Retry-After` 头重试 |
| `UPSTREAM_TIMEOUT` | 自动重试（指数退避，最多 3 次） |
| `UPSTREAM_RATE_LIMITED` | 自动切换渠道或延迟重试 |
| `UPSTREAM_UNAVAILABLE` | 提示服务暂时不可用，稍后重试 |
| `UNIAPI_INTERNAL_ERROR` | 展示通用错误提示，上报 `request_id` |

---

## 12. 首批标准错误码（共 15 个）

### 认证与权限
1. `UNIAPI_INVALID_TOKEN`
2. `UNIAPI_TOKEN_EXPIRED`
3. `UNIAPI_TOKEN_MODEL_NOT_ALLOWED`
4. `UNIAPI_ADMIN_REQUIRED`
5. `UNIAPI_GROUP_ACCESS_DENIED`

### 请求参数
6. `UNIAPI_INVALID_REQUEST`
7. `UNIAPI_MODEL_NOT_SPECIFIED`
8. `UNIAPI_MODEL_NOT_SUPPORTED`
9. `UNIAPI_UNSUPPORTED_PARAMETER`
10. `UNIAPI_RESOURCE_NOT_FOUND`

### 配额与限流
11. `UNIAPI_QUOTA_EXHAUSTED`
12. `UNIAPI_RATE_LIMITED`

### 上游链路
13. `UPSTREAM_TIMEOUT`
14. `UPSTREAM_UNAVAILABLE`
15. `UPSTREAM_BAD_RESPONSE`
16. `UPSTREAM_RATE_LIMITED`
17. `UPSTREAM_CONNECTION_FAILED`

### 服务可用性
18. `UNIAPI_SERVICE_DISABLED`
19. `UNIAPI_CHANNEL_UNAVAILABLE`

### 系统内部
20. `UNIAPI_INTERNAL_ERROR`

---

## 13. 错误码稳定性承诺

### 13.1 语义版本策略

| 变更类型 | 允许 | 条件 |
|---------|------|------|
| 新增 code | ✅ 随时 | 不影响已有 code |
| 废弃 code | ✅ | 至少一个 minor 版本的废弃期，期间同时返回新旧 code |
| 重命名 code | ❌ | 视为删除旧 code + 新增新 code |
| 修改 code 语义 | ❌ | 视为重命名 |
| 修改 `error` 对象结构（增字段） | ✅ | 新增字段必须可选，不影响已有字段 |

### 13.2 稳定性测试要求

- 每个已发布的 error code 必须有对应的单元测试，验证其 JSON 结构和字段完整性。
- CI 中运行 error code 快照测试，确保已发布 code 的响应结构不被意外修改。
- 新增 code 必须同步更新本文档。

---

## 14. 结论

不建议重做 HTTP 状态码；建议重构错误语义层：

1. 对外统一 UniAPI 错误码。
2. 对内完整保留上游错误细节（日志侧，不返回客户端）。
3. 通过命名空间和结构化返回彻底避免"中转站错误"和"上游错误"冲突。
4. 基于现有 `AppException` 体系渐进式演进，避免引入第三套错误机制。
