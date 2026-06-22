# UniAPI-Py 错误代码系统全面审查报告

> ⚠️ 本文档编写于错误码体系迁移之前，描述的代码状态已过时。
> 当前代码（v0.10.16+）已完成迁移：
> - `AppException` 体系已全面使用，非"零使用"
> - `relay.py` 和 `dependencies.py` 已改用结构化异常类
> - `RequestIDMiddleware` 已实现
> 
> 保留此文档作为历史参考。

## 📋 执行摘要

UniAPI-Py 当前采用**混合异常系统**：
- **FastAPI HTTPException** — 用于大多数 API 端点（直接、快速）
- **AppException 体系** — 自定义异常基类及 5 种具体异常（灵活、可扩展）

**总体评分：** ⭐⭐⭐ (良好基础，有改进空间)

| 维度 | 评分 | 评语 |
|------|------|------|
| 一致性 | ⭐⭐ | 混用两种机制，标准不统一 |
| 可维护性 | ⭐⭐⭐ | 异常体系清晰，但使用不全面 |
| 可扩展性 | ⭐⭐⭐ | 能支持自定义异常，但未充分利用 |
| 信息完整性 | ⭐⭐ | 缺少错误代码、时间戳、请求ID |
| 文档化 | ⭐⭐ | 错误消息不够详细，缺少建议 |

---

## 📊 现状分析

### 1. 错误定义的分布

#### 按文件统计

```
app/dependencies.py         → 10 个错误 (401/403)
app/routers/v1/relay.py     → 11 个错误 (400/403/402/500)
app/services/user.py        → 8 个错误 (400/401/404)
app/services/token.py       → 2 个错误 (404)
app/middleware.py           → 1 个错误 (429)
app/exceptions.py           → 5 个异常类定义
───────────────────────────────────────────
总计                        → 37 个错误点
```

#### 按状态码统计

```
400 Bad Request           → 8 个 (21%)
401 Unauthorized          → 15 个 (40%) ← 最常见
402 Payment Required      → 1 个  (3%) ← 预算/额度
403 Forbidden             → 10 个 (27%)
404 Not Found             → 2 个  (5%)
429 Too Many Requests     → 1 个  (3%)
500 Internal Server Error → 1 个  (1%)
```

#### 按异常类型统计

```
HTTPException (FastAPI)    → 大部分已迁移
AppException (自定义)      → 已全面使用 (RelayException/ForbiddenException/UnauthorizedException 等)
───────────────────────────────────────────
总计                      → 统一使用 AppException 体系
```

---

## 🚨 识别的问题

### 问题 1️⃣ : 异常体系迁移已完成

**现状：** `AppException` 体系已全面使用（`RelayException`/`ForbiddenException`/`UnauthorizedException` 等）

**位置：** `app/exceptions.py` 定义了 5 个异常类：
- `NotFoundException`
- `UnauthorizedException`
- `ForbiddenException`
- `QuotaExceededException`
- `NotImplementedException`

**现实：** 所有代码都直接用 `HTTPException`，从不用自定义异常

```python
# ❌ 当前做法（多个位置）
raise HTTPException(status_code=403, detail="Admin access required")

# ✅ 应该用
raise ForbiddenException("Admin access required")
```

**后果：**
- 代码冗余：重复写 `status_code=403` 等
- 难以维护：改错误消息要改多个位置
- 类型不安全：无法在 IDE 中检查异常类型
- 处理器浪费：`app_exception_handler` 从未被调用

### 问题 2️⃣ : 错误消息格式不统一

**症状：** 不同位置的错误消息格式和详细程度不同

```python
# 类型 A：极简
raise HTTPException(status_code=401, detail="Not logged in")

# 类型 B：中等详细
raise HTTPException(status_code=401, detail="Invalid username or password")

# 类型 C：详细（含建议）
raise HTTPException(
    status_code=403,
    detail=f"Token not allowed to use model '{model}'. "
           f"Allowed models: {models}. "
           f"Call GET /v1/models to list available models."
)
```

**问题：**
- 类型 A 和 B 给客户端的信息不足，难以调试
- 类型 C 更好但不一致应用
- 缺少统一的错误响应结构

### 问题 3️⃣ : 缺少错误代码标识符

**症状：** 错误只通过状态码和文本区分，无唯一标识

```python
# 多个地方都是 401，但原因完全不同
raise HTTPException(status_code=401, detail="Not logged in")
raise HTTPException(status_code=401, detail="Invalid token")
raise HTTPException(status_code=401, detail="Token quota exhausted")
raise HTTPException(status_code=401, detail="User is disabled")
```

**问题：**
- 前端无法编程式区分错误类型
- 日志中难以搜索特定错误
- 无法为不同错误设置不同处理策略

### 问题 4️⃣ : 缺少上下文信息

**症状：** 错误响应中缺少诊断信息

```python
# 现有响应格式
{
  "detail": "Token not allowed to use model 'xxx'"
}

# 缺失的上下文
{
  "error_code": "TOKEN_MODEL_NOT_ALLOWED",
  "detail": "Token not allowed to use model 'xxx'",
  "requested_model": "deepseek-v4-pro",
  "allowed_models": ["glm-5.2"],
  "timestamp": "2026-06-21T10:30:00Z",
  "request_id": "req_12345",
  "help_url": "/docs?error=TOKEN_MODEL_NOT_ALLOWED"
}
```

**问题：**
- 调试困难：无法关联日志
- 无用户体验：前端无法定位问题
- 无可追溯性：无法追踪请求生命周期

### 问题 5️⃣ : 缺少错误恢复建议

**症状：** 大多数错误消息是"报告问题"而非"引导解决"

```python
# ❌ 只说问题
raise HTTPException(status_code=403, detail="Access denied")

# ✅ 引导解决
raise ForbiddenException(
    message="Access denied",
    suggestion="Check your user role. Admin role (10+) required for this operation.",
    help_url="https://docs.example.com/roles"
)
```

### 问题 6️⃣ : 缺少错误分类

**症状：** 没有有序的错误目录

当前：37 个错误散落在 5 个文件中
- 无法系统地了解所有可能的错误
- 无法确保新增错误符合标准
- 文档无法跟上代码

---

## 📍 详细错误点地图

### 认证层（15 个 401 错误）

**文件：** `app/dependencies.py`

| 行号 | 条件 | 错误消息 | 问题 |
|------|------|---------|------|
| 33 | 无登录用户 | "Not logged in" | 信息足够 ✅ |
| 69 | Bearer token 缺失 | "No token provided" | 信息足够 ✅ |
| 86 | Token 不存在 | "Invalid token" | 含糊（可能是格式错误） |
| 89 | Token 已禁用或过期 | "Token is disabled or expired" | 太模糊（两个不同原因） |
| 92 | Token 时间戳过期 | "Token has expired" | 冗余（重复第89行逻辑） |
| 95 | Token 额度用尽 | "Token quota exhausted" | 应用 402，不是 401 |
| 100 | 用户被禁用 | "User is disabled" | 信息足够 ✅ |

**推荐：**
- 第 89 行和 92 行合并：避免重复逻辑
- 第 95 行改 402 Payment Required

### 权限层（10 个 403 错误）

**文件：** `app/dependencies.py` (3) + `app/routers/v1/relay.py` (7)

| 位置 | 条件 | 错误消息 | 改进 |
|------|------|---------|------|
| dependencies.py:35 | 用户角色 < 1 | "Access denied" | 太宽泛，应细化 |
| dependencies.py:47 | 用户角色 < 10 | "Admin access required" | ✅ 具体 |
| dependencies.py:58 | 用户角色 < 100 | "Root access required" | ✅ 具体 |
| relay.py:248 | 模型权限 | 包含模型列表 + 建议 | ✅ 最佳实践 |
| relay.py:281 | Fusion 权限 | "No fusion-authorized models..." | ✅ 具体 |
| relay.py:371 | Fusion 自动选择 | "Token has no authorized model..." | ✅ 具体 |
| relay.py:414 | 模型权限（再检查） | 同第 248 行 | ✅ 一致 |
| relay.py:424 | 用户组权限 | "User group not allowed..." | ✅ 具体 |

**模式观察：**
- relay.py 中的错误消息质量更高
- dependencies.py 中的通用性不足

### 业务逻辑层（8 个 400 错误）

**文件：** `app/services/user.py` + `app/routers/v1/relay.py`

| 位置 | 条件 | 错误消息 | 问题 |
|------|------|---------|------|
| user.py:30 | 用户名已占用 | "Username already taken" | ✅ 清晰 |
| user.py:33 | 密码过短 | "Password must be at least 8 characters" | ✅ 含建议 |
| relay.py:254 | 模型未指定 | 含限制模型列表 + 建议 | ✅ 最佳实践 |
| relay.py:268 | 无 Fusion 配置 | "Fusion engine not available..." | ✅ 具体 |
| relay.py:281 | 无可用模型 | "No enabled channels available..." | ✅ 具体 |
| relay.py:402 | 无权限的自动选择 | 含允许模型列表 | ✅ 具体 |
| relay.py:407 | 模型不支持 | "Model not supported by any provider" | ✅ 具体 |
| relay.py:429 | 无可用通道 | "No enabled channels available..." | ✅ 具体 |

### 资源不存在层（2 个 404 错误）

**文件：** `app/services/token.py` + `app/services/user.py`

| 位置 | 条件 | 错误消息 | 问题 |
|------|------|---------|------|
| token.py:103 | Token 不存在 | "Token not found" | ✅ 清晰 |
| user.py:165 | 用户不存在 | "User not found" | ✅ 清晰 |

### 限流层（1 个 429 错误）

**文件：** `app/middleware.py:59`

```python
raise HTTPException(
    status_code=429,
    detail=f"Rate limit exceeded: {limit} requests per minute"
)
```

✅ 包含限制信息，良好

### 预算层（1 个 402 错误）

**文件：** `app/routers/v1/relay.py:440`

```python
raise HTTPException(status_code=402, detail=decision.error_message)
```

✅ 正确使用 402，但错误消息来自 budget_arbiter

---

## ✅ 做得好的方面

### 1. 模型权限错误（relay.py:248）

```python
raise HTTPException(
    status_code=403,
    detail=f"Token not allowed to use model '{model_name}'. "
           f"Allowed models: {', '.join(token_allowed_models)}. "
           f"Call GET /v1/models to list available models."
)
```

✅ 优点：
- 包含具体的禁用模型名
- 列出允许的模型
- 提供解决建议（调用 /v1/models）

### 2. 业务级错误消息（relay.py 中的自动选择）

✅ 缺少权限的型号明确指出：
- 允许的模型有哪些
- 为什么选择失败

### 3. 异常基类设计（exceptions.py）

```python
class AppException(Exception):
    def __init__(self, status_code: int, message: str, data: Any = None):
        self.status_code = status_code
        self.message = message
        self.data = data
```

✅ 支持：
- 自定义状态码
- 自定义消息
- 可选的数据载荷

### 4. 异常处理器（exceptions.py）

```python
async def app_exception_handler(request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "data": exc.data,
        },
    )
```

✅ 统一的响应格式

---

## 💡 改进建议

### 建议 1️⃣ : 统一使用 AppException 体系

**目标：** 用一种机制替代 HTTPException 直接使用

**第 1 步：扩展异常类**

```python
# app/exceptions.py

class ErrorCode:
    """错误代码常量定义"""
    # 认证类 (401)
    NOT_LOGGED_IN = "NOT_LOGGED_IN"
    NO_TOKEN_PROVIDED = "NO_TOKEN_PROVIDED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_DISABLED = "TOKEN_DISABLED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_QUOTA_EXHAUSTED = "TOKEN_QUOTA_EXHAUSTED"
    USER_DISABLED = "USER_DISABLED"
    
    # 权限类 (403)
    ACCESS_DENIED = "ACCESS_DENIED"
    ADMIN_ACCESS_REQUIRED = "ADMIN_ACCESS_REQUIRED"
    ROOT_ACCESS_REQUIRED = "ROOT_ACCESS_REQUIRED"
    TOKEN_MODEL_NOT_ALLOWED = "TOKEN_MODEL_NOT_ALLOWED"
    USER_GROUP_NOT_ALLOWED = "USER_GROUP_NOT_ALLOWED"
    FUSION_NOT_AUTHORIZED = "FUSION_NOT_AUTHORIZED"
    
    # 业务类 (400)
    INVALID_REQUEST = "INVALID_REQUEST"
    MODEL_NOT_SPECIFIED = "MODEL_NOT_SPECIFIED"
    MODEL_NOT_SUPPORTED = "MODEL_NOT_SUPPORTED"
    NO_AVAILABLE_CHANNELS = "NO_AVAILABLE_CHANNELS"
    INSUFFICIENT_QUOTA = "INSUFFICIENT_QUOTA"
    
    # 限流 (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # 预算 (402)
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"


class AppException(Exception):
    """改进的异常基类"""
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: dict | None = None,
        suggestion: str | None = None,
        request_id: str | None = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion
        self.request_id = request_id


class UnauthorizedException(AppException):
    def __init__(
        self,
        error_code: str,
        message: str,
        details: dict | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            status_code=401,
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )


class ForbiddenException(AppException):
    def __init__(
        self,
        error_code: str,
        message: str,
        details: dict | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            status_code=403,
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )


# ... 其他异常类
```

**第 2 步：改进异常处理器**

```python
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "suggestion": exc.suggestion,
                "request_id": exc.request_id or request.state.request_id,
                "timestamp": datetime.now().isoformat(),
            },
        },
    )
```

**第 3 步：迁移现有代码**

```python
# 旧代码
raise HTTPException(status_code=403, detail="Admin access required")

# 新代码
raise ForbiddenException(
    error_code=ErrorCode.ADMIN_ACCESS_REQUIRED,
    message="Admin access required",
    suggestion="Your user role must be 10 or higher. Contact administrators.",
)
```

**优点：**
- ✅ 唯一的异常机制
- ✅ 每个错误都有唯一的错误代码
- ✅ 支持建议和上下文信息
- ✅ 便于类型检查和 IDE 支持
- ✅ 易于客户端处理

---

### 建议 2️⃣ : 创建统一的错误代码目录

**创建文件：** `app/error_codes.md`

```markdown
# UniAPI-Py 错误代码参考

## 认证错误 (401)

### NOT_LOGGED_IN
- **场景：** 用户未登录
- **原因：** 缺少有效的会话 cookie 或 Bearer token
- **解决：** 登录或提供有效的 token
- **HTTP：** 401 Unauthorized

### NO_TOKEN_PROVIDED
- **场景：** 中继端点缺少 Bearer token
- **原因：** Authorization 头未包含 "Bearer " 前缀
- **解决：** 添加 "Authorization: Bearer {token}" 头
- **HTTP：** 401 Unauthorized

### INVALID_TOKEN
- **场景：** Token 不存在或格式错误
- **原因：** Token 密钥未在数据库中找到
- **解决：** 检查 token 是否正确
- **HTTP：** 401 Unauthorized

### TOKEN_DISABLED
- **场景：** Token 已被禁用
- **原因：** Token.status != 1
- **解决：** 联系管理员启用 token
- **HTTP：** 401 Unauthorized

### TOKEN_EXPIRED
- **场景：** Token 时间戳已过期
- **原因：** 当前时间 > token.expired_time
- **解决：** 申请新 token
- **HTTP：** 401 Unauthorized

### TOKEN_QUOTA_EXHAUSTED
- **场景：** Token 的额度用尽
- **原因：** token.remain_quota <= 0
- **解决：** 充值或申请新 token
- **HTTP：** 401 Unauthorized ← 应改 402

### USER_DISABLED
- **场景：** Token 对应的用户被禁用
- **原因：** user.status != 1
- **解决：** 联系管理员启用用户
- **HTTP：** 401 Unauthorized

## 权限错误 (403)

### ADMIN_ACCESS_REQUIRED
- **场景：** 需要管理员权限
- **原因：** user.role < 10
- **解决：** 使用管理员账户或请求提权
- **HTTP：** 403 Forbidden

### ROOT_ACCESS_REQUIRED
- **场景：** 需要 root 权限
- **原因：** user.role < 100
- **解决：** 使用 root 账户
- **HTTP：** 403 Forbidden

### TOKEN_MODEL_NOT_ALLOWED
- **场景：** Token 无权使用该模型
- **原因：** model_name 不在 token.models 列表中
- **解决：** 使用 GET /v1/models 查询允许的模型
- **HTTP：** 403 Forbidden

### USER_GROUP_NOT_ALLOWED
- **场景：** 用户组无权访问通道
- **原因：** user.group != channel.group
- **解决：** 请求加入相应的用户组
- **HTTP：** 403 Forbidden

### FUSION_NOT_AUTHORIZED
- **场景：** Token 无权使用 Fusion
- **原因：** 无任何 token 允许的模型在 Fusion 面板中
- **解决：** 请求 Fusion 权限或查看允许的模型
- **HTTP：** 403 Forbidden

## 业务错误 (400)

### MODEL_NOT_SPECIFIED
- **场景：** Token 有权限限制但未指定模型
- **原因：** model="" 且 token.models 非空
- **解决：** 指定模型或调用 GET /v1/models
- **HTTP：** 400 Bad Request

### MODEL_NOT_SUPPORTED
- **场景：** 指定的模型无任何提供商支持
- **原因：** model_name 未在任何注册的提供商中找到
- **解决：** 查看支持的模型列表
- **HTTP：** 400 Bad Request

### NO_AVAILABLE_CHANNELS
- **场景：** 该模型没有可用的通道
- **原因：** 所有通道已禁用或不支持该模型
- **解决：** 稍后重试或使用其他模型
- **HTTP：** 400 Bad Request

### INSUFFICIENT_QUOTA
- **场景：** Token 或用户额度不足
- **原因：** estimated_cost > remaining_quota
- **解决：** 减小请求规模或充值
- **HTTP：** 400 Bad Request

## 限流错误 (429)

### RATE_LIMIT_EXCEEDED
- **场景：** 请求速率超过限制
- **原因：** 在时间窗口内发送过多请求
- **解决：** 降低请求频率或等待
- **HTTP：** 429 Too Many Requests

## 预算错误 (402)

### PAYMENT_REQUIRED
- **场景：** 预算不足（由预算仲裁器）
- **原因：** 月度预算已用尽
- **解决：** 充值或等待下个月
- **HTTP：** 402 Payment Required

---

## 按状态码分类

### 400 Bad Request
- MODEL_NOT_SPECIFIED
- MODEL_NOT_SUPPORTED
- NO_AVAILABLE_CHANNELS
- INSUFFICIENT_QUOTA

### 401 Unauthorized
- NOT_LOGGED_IN
- NO_TOKEN_PROVIDED
- INVALID_TOKEN
- TOKEN_DISABLED
- TOKEN_EXPIRED
- TOKEN_QUOTA_EXHAUSTED（应改 402）
- USER_DISABLED

### 402 Payment Required
- PAYMENT_REQUIRED
- TOKEN_QUOTA_EXHAUSTED（应改用）

### 403 Forbidden
- ACCESS_DENIED
- ADMIN_ACCESS_REQUIRED
- ROOT_ACCESS_REQUIRED
- TOKEN_MODEL_NOT_ALLOWED
- USER_GROUP_NOT_ALLOWED
- FUSION_NOT_AUTHORIZED

### 429 Too Many Requests
- RATE_LIMIT_EXCEEDED

---

## 客户端集成指南

### Python
\`\`\`python
import httpx

try:
    response = httpx.post("...", ...)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    error_data = e.response.json()
    error_code = error_data["error"]["code"]
    
    if error_code == "TOKEN_MODEL_NOT_ALLOWED":
        # 处理模型权限错误
        models = error_data["error"]["details"]["allowed_models"]
        print(f"允许的模型: {models}")
    elif error_code == "TOKEN_EXPIRED":
        # 刷新 token
        refresh_token()
    else:
        # 通用错误处理
        print(error_data["error"]["message"])
\`\`\`

### JavaScript
\`\`\`javascript
fetch("...", ...)
  .then(r => {
    if (!r.ok) throw r;
    return r.json();
  })
  .catch(async (error) => {
    if (error instanceof Response) {
      const data = await error.json();
      const errorCode = data.error.code;
      
      switch (errorCode) {
        case "TOKEN_MODEL_NOT_ALLOWED":
          showAvailableModels(data.error.details.allowed_models);
          break;
        case "TOKEN_EXPIRED":
          redirectToLogin();
          break;
        default:
          alert(data.error.message);
      }
    }
  });
\`\`\`
```

**优点：**
- ✅ 所有错误的单一事实来源
- ✅ 易于搜索和引用
- ✅ 便于文档和客户端集成
- ✅ 便于代码审查和维护

---

### 建议 3️⃣ : 改进错误响应结构

**当前：**
```json
{
  "detail": "Token not allowed to use model 'xxx'"
}
```

**改进后：**
```json
{
  "success": false,
  "error": {
    "code": "TOKEN_MODEL_NOT_ALLOWED",
    "message": "Token not allowed to use model 'deepseek-v4-pro'",
    "details": {
      "requested_model": "deepseek-v4-pro",
      "allowed_models": ["glm-5.2"],
      "token_id": "last_4_chars_of_token"
    },
    "suggestion": "Call GET /v1/models to list available models",
    "request_id": "req_abc123def456",
    "timestamp": "2026-06-21T10:30:00.123456Z",
    "help_url": "https://docs.example.com/errors#TOKEN_MODEL_NOT_ALLOWED"
  }
}
```

**实现：**

```python
# app/exceptions.py - 改进异常处理器

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
                "suggestion": exc.suggestion,
                "request_id": request.state.get("request_id", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "help_url": f"https://docs.example.com/errors#{exc.error_code.lower()}",
            },
        },
    )
```

**优点：**
- ✅ 结构化错误信息便于客户端处理
- ✅ `request_id` 便于追踪
- ✅ `suggestion` 指导用户解决
- ✅ `details` 包含上下文信息
- ✅ `help_url` 便于获取帮助

---

### 建议 4️⃣ : 修复状态码误用

**问题 1：** TOKEN_QUOTA_EXHAUSTED 用 401（应改 402）

```python
# 旧代码（dependencies.py:95）
raise HTTPException(status_code=401, detail="Token quota exhausted")

# 新代码
raise UnauthorizedException(
    error_code=ErrorCode.TOKEN_QUOTA_EXHAUSTED,
    message="Token quota exhausted",
    suggestion="Purchase additional quota or wait for renewal",
)

# 改为 402：
raise AppException(
    status_code=402,  # ← 改这里
    error_code=ErrorCode.TOKEN_QUOTA_EXHAUSTED,
    message="Token quota exhausted",
    details={"remaining_quota": token.remain_quota},
    suggestion="Purchase additional quota or wait for renewal",
)
```

**问题 2：** 避免冗余的 401 错误

```python
# 旧代码（dependencies.py:89-92）
if token.status != 1:
    raise HTTPException(status_code=401, detail="Token is disabled or expired")

if token.expired_time > 0 and token.expired_time < time.time():
    raise HTTPException(status_code=401, detail="Token has expired")

# 新代码：合并并明确区分
if token.status != 1:
    raise UnauthorizedException(
        error_code=ErrorCode.TOKEN_DISABLED,
        message="Token has been disabled",
        suggestion="Contact administrators to enable your token",
    )

if token.expired_time > 0 and token.expired_time < time.time():
    raise UnauthorizedException(
        error_code=ErrorCode.TOKEN_EXPIRED,
        message="Token has expired",
        suggestion="Apply for a new token",
    )
```

---

### 建议 5️⃣ : 统一的验证异常

**当前问题：** 验证错误混在各个地方

```python
# 分散的验证：
raise HTTPException(status_code=400, detail="Username already taken")
raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
raise HTTPException(status_code=400, detail="Model not specified")
```

**改进：创建验证异常类**

```python
# app/exceptions.py

class ValidationError(AppException):
    """验证失败异常"""
    def __init__(
        self,
        field: str,
        message: str,
        allowed_values: list | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
    ):
        super().__init__(
            status_code=400,
            error_code="VALIDATION_ERROR",
            message=message,
            details={
                "field": field,
                "allowed_values": allowed_values,
                "min_length": min_length,
                "max_length": max_length,
            },
        )

# 使用
raise ValidationError(
    field="password",
    message="Password too short",
    min_length=8,
)

# 响应
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Password too short",
    "details": {
      "field": "password",
      "min_length": 8
    }
  }
}
```

---

### 建议 6️⃣ : 创建错误追踪系统

**添加到 middleware.py：**

```python
import uuid
from fastapi import Request
from fastapi.responses import Response

class RequestIDMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next) -> Response:
        request.state.request_id = f"req_{uuid.uuid4().hex[:12]}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

# 日志集成
import logging

logger = logging.getLogger(__name__)

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = request.state.get("request_id", "unknown")
    
    # 记录到结构化日志
    logger.error(
        "API Error",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "request_id": request_id,
                # ...
            },
        },
    )
```

**优点：**
- ✅ 所有错误都可追踪
- ✅ 便于调试和支持
- ✅ 客户端可用 request_id 查询日志

---

## 📋 实施计划

### 阶段 1：基础设施（1-2 天）
- [ ] 扩展 `AppException` 类（加入 error_code、suggestion 等）
- [ ] 定义 `ErrorCode` 常量类
- [ ] 创建 `error_codes.md` 文档
- [ ] 改进异常处理器

### 阶段 2：关键路径迁移（2-3 天）
- [ ] 迁移 `dependencies.py`（10 个错误）
- [ ] 迁移 `relay.py` 的权限检查（7 个错误）
- [ ] 迁移 `services/user.py` 的认证（5 个错误）

### 阶段 3：完整迁移（1-2 天）
- [ ] 迁移其他服务
- [ ] 迁移中间件
- [ ] 写测试

### 阶段 4：文档和工具（1 天）
- [ ] 生成 OpenAPI 文档补充（错误说明）
- [ ] 创建客户端示例代码
- [ ] 更新 README 和开发指南

---

## 📈 预期收益

| 指标 | 当前 | 改进后 |
|------|------|--------|
| 唯一的异常机制 | ❌ | ✅ |
| 错误代码一致性 | 0% | 100% |
| 错误恢复建议 | 30% | 100% |
| 包含 request_id | ❌ | ✅ |
| 包含建议 | 20% | 100% |
| 文档化程度 | 30% | 100% |
| 客户端可集成性 | 50% | 100% |

---

## 🔍 快速对比：现在 vs 未来

### 现在的错误响应

```
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'. Allowed models: glm-5.2. Call GET /v1/models to list available models."
}
```

### 未来的错误响应

```
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "success": false,
  "error": {
    "code": "TOKEN_MODEL_NOT_ALLOWED",
    "message": "Token not allowed to use model 'deepseek-v4-pro'",
    "details": {
      "requested_model": "deepseek-v4-pro",
      "allowed_models": ["glm-5.2"],
      "token_id": "sk_xxxxx"
    },
    "suggestion": "Call GET /v1/models to list all available models for your token",
    "request_id": "req_abc123def456",
    "timestamp": "2026-06-21T10:30:00.123456Z",
    "help_url": "https://docs.example.com/errors#TOKEN_MODEL_NOT_ALLOWED"
  }
}
```

### 客户端处理对比

**现在：**
```python
# 不知道是哪种错误，只能解析字符串
if "not allowed" in error:
    # 模型权限？
    pass
```

**未来：**
```python
# 明确的错误代码，易于处理
if error_code == "TOKEN_MODEL_NOT_ALLOWED":
    models = error["details"]["allowed_models"]
    # 处理模型权限错误
```

---

## 📚 参考资源

- **HTTP 状态码标准**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
- **REST API 最佳实践**: https://restfulapi.net/http-status-codes/
- **FastAPI 错误处理**: https://fastapi.tiangolo.com/tutorial/handling-errors/
- **JSON:API 错误规范**: https://jsonapi.org/examples/#error-objects

---

## ✨ 总结

**问题根源：** 
- 混用两种异常机制（HTTPException + AppException）
- 缺少错误代码标准化
- 错误消息不一致
- 缺少诊断上下文

**解决方案：**
1. 统一使用 AppException 体系
2. 定义标准的错误代码常量
3. 建立统一的错误响应格式
4. 加入错误恢复建议
5. 实现错误追踪系统

**预期效果：**
- ✅ 代码更清晰，更易维护
- ✅ 错误更易理解和调试
- ✅ 客户端集成更简单
- ✅ 生产支持更高效

