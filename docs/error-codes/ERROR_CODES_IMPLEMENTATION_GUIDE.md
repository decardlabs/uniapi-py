# 错误代码系统改进方案 - 快速实施指南

## 一图胜千言：问题与解决

```
┌─────────────────────────────────────────────────────────────┐
│ 现状：混乱的异常系统                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  dependencies.py ────→ HTTPException                       │
│  relay.py ───────────→ HTTPException                       │
│  services/user.py ───→ HTTPException                       │
│  services/token.py ──→ HTTPException                       │
│                                                             │
│  exceptions.py       ↓ (已定义但未使用！)                   │
│  ├─ AppException                                            │
│  ├─ ForbiddenException                                      │
│  ├─ UnauthorizedException                                   │
│  ├─ NotFoundException                                       │
│  └─ QuotaExceededException                                  │
│                                                             │
│  问题：                                                      │
│  ❌ 冗余定义（重复写 status_code=403 等）                     │
│  ❌ 不一致（不同位置错误格式不同）                           │
│  ❌ 无标识（无错误代码，难以客户端处理）                     │
│  ❌ 缺信息（无建议、无请求ID）                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘

               ⬇️ (实施改进)

┌─────────────────────────────────────────────────────────────┐
│ 目标：统一的异常系统                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  所有代码 ─────────→ ForbiddenException(                    │
│                      error_code="TOKEN_MODEL_NOT_ALLOWED",│
│                      message="...",                        │
│                      details={...},                        │
│                      suggestion="..."                      │
│                    )                                        │
│                      ↓                                      │
│                    app_exception_handler                   │
│                      ↓                                      │
│   统一的 JSON 响应：                                        │
│   {                                                        │
│     "error": {                                             │
│       "code": "TOKEN_MODEL_NOT_ALLOWED",                   │
│       "message": "Token not allowed...",                   │
│       "details": {                                         │
│         "allowed_models": ["glm-5.2"]                      │
│       },                                                   │
│       "suggestion": "Call GET /v1/models",                │
│       "request_id": "req_123abc",                         │
│       "timestamp": "2026-06-21T10:30:00Z"                 │
│     }                                                      │
│   }                                                        │
│                                                             │
│  收益：                                                      │
│  ✅ 代码清洁（一个异常机制）                                 │
│  ✅ 一致性（所有错误格式相同）                              │
│  ✅ 可追踪（error_code + request_id）                       │
│  ✅ 有建议（suggestion 指导用户）                            │
│  ✅ 易调试（详细的 details 和 help_url）                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 第一步：定义错误代码常量

创建或更新 `app/errors.py`：

```python
from enum import Enum

class ErrorCode(str, Enum):
    """API 错误代码"""
    
    # 认证 (401)
    NOT_LOGGED_IN = "NOT_LOGGED_IN"
    NO_TOKEN_PROVIDED = "NO_TOKEN_PROVIDED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_DISABLED = "TOKEN_DISABLED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    USER_DISABLED = "USER_DISABLED"
    
    # 权限 (403)
    ACCESS_DENIED = "ACCESS_DENIED"
    ADMIN_ACCESS_REQUIRED = "ADMIN_ACCESS_REQUIRED"
    ROOT_ACCESS_REQUIRED = "ROOT_ACCESS_REQUIRED"
    TOKEN_MODEL_NOT_ALLOWED = "TOKEN_MODEL_NOT_ALLOWED"
    USER_GROUP_NOT_ALLOWED = "USER_GROUP_NOT_ALLOWED"
    FUSION_NOT_AUTHORIZED = "FUSION_NOT_AUTHORIZED"
    
    # 业务 (400)
    MODEL_NOT_SPECIFIED = "MODEL_NOT_SPECIFIED"
    MODEL_NOT_SUPPORTED = "MODEL_NOT_SUPPORTED"
    NO_AVAILABLE_CHANNELS = "NO_AVAILABLE_CHANNELS"
    INSUFFICIENT_QUOTA = "INSUFFICIENT_QUOTA"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    
    # 其他
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"


# 错误码 → HTTP 状态码映射
ERROR_CODE_TO_STATUS = {
    ErrorCode.NOT_LOGGED_IN: 401,
    ErrorCode.NO_TOKEN_PROVIDED: 401,
    ErrorCode.INVALID_TOKEN: 401,
    ErrorCode.TOKEN_DISABLED: 401,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.USER_DISABLED: 401,
    ErrorCode.ACCESS_DENIED: 403,
    ErrorCode.ADMIN_ACCESS_REQUIRED: 403,
    ErrorCode.ROOT_ACCESS_REQUIRED: 403,
    ErrorCode.TOKEN_MODEL_NOT_ALLOWED: 403,
    ErrorCode.USER_GROUP_NOT_ALLOWED: 403,
    ErrorCode.FUSION_NOT_AUTHORIZED: 403,
    ErrorCode.MODEL_NOT_SPECIFIED: 400,
    ErrorCode.MODEL_NOT_SUPPORTED: 400,
    ErrorCode.NO_AVAILABLE_CHANNELS: 400,
    ErrorCode.INSUFFICIENT_QUOTA: 400,
    ErrorCode.QUOTA_EXHAUSTED: 402,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.PAYMENT_REQUIRED: 402,
}
```

---

## 第二步：改进异常类

更新 `app/exceptions.py`：

```python
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
from fastapi.responses import JSONResponse
from fastapi import Request
from app.errors import ErrorCode, ERROR_CODE_TO_STATUS


class AppException(Exception):
    """改进的基础异常类"""
    
    def __init__(
        self,
        error_code: ErrorCode | str,
        message: str,
        details: dict | None = None,
        suggestion: str | None = None,
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion
        self.status_code = ERROR_CODE_TO_STATUS.get(
            error_code,
            400
        ) if isinstance(error_code, (ErrorCode, str)) else 400


class UnauthorizedException(AppException):
    """401 Unauthorized"""
    def __init__(
        self,
        error_code: ErrorCode | str = ErrorCode.INVALID_TOKEN,
        message: str = "Unauthorized",
        details: dict | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )


class ForbiddenException(AppException):
    """403 Forbidden"""
    def __init__(
        self,
        error_code: ErrorCode | str = ErrorCode.ACCESS_DENIED,
        message: str = "Forbidden",
        details: dict | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            details=details,
            suggestion=suggestion,
        )


class NotFoundException(AppException):
    """404 Not Found"""
    def __init__(
        self,
        error_code: ErrorCode | str = ErrorCode.NOT_FOUND,
        message: str = "Not Found",
        details: dict | None = None,
    ):
        super().__init__(error_code, message, details)


class QuotaExceededException(AppException):
    """额度/配额异常"""
    def __init__(
        self,
        message: str = "Quota exceeded",
        details: dict | None = None,
        suggestion: str | None = None,
    ):
        super().__init__(
            error_code=ErrorCode.QUOTA_EXHAUSTED,
            message=message,
            details=details,
            suggestion=suggestion,
        )


# 改进的异常处理器
async def app_exception_handler(
    request: Request, exc: AppException
) -> JSONResponse:
    """统一的异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": str(exc.error_code),
                "message": exc.message,
                "details": exc.details,
                **({"suggestion": exc.suggestion} if exc.suggestion else {}),
                "request_id": getattr(request.state, "request_id", "unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
```

---

## 第三步：添加 RequestID 中间件

在 `app/middleware.py` 中添加：

```python
import uuid
from fastapi import Request


class RequestIDMiddleware:
    """为每个请求添加唯一的 request_id"""
    
    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        request.state.request_id = f"req_{uuid.uuid4().hex[:12]}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
```

在 `app/main.py` 中注册：

```python
from app.middleware import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
```

---

## 第四步：迁移现有代码

### 示例 1：dependencies.py 中的权限检查

**旧代码：**
```python
async def admin_auth(request: Request, db: AsyncSession):
    user = await user_auth(request, db)
    if user.role < 10:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

**新代码：**
```python
from app.errors import ErrorCode
from app.exceptions import ForbiddenException

async def admin_auth(request: Request, db: AsyncSession):
    user = await user_auth(request, db)
    if user.role < 10:
        raise ForbiddenException(
            error_code=ErrorCode.ADMIN_ACCESS_REQUIRED,
            message="Admin access required",
            suggestion="Your user role must be 10 or higher. Contact administrators for access.",
        )
    return user
```

### 示例 2：relay.py 中的模型权限检查

**旧代码：**
```python
if model_name and token_allowed_models and model_name not in token_allowed_models:
    raise HTTPException(
        status_code=403,
        detail=f"Token not allowed to use model '{model_name}'. "
               f"Allowed models: {', '.join(token_allowed_models)}. "
               f"Call GET /v1/models to list available models."
    )
```

**新代码：**
```python
from app.errors import ErrorCode
from app.exceptions import ForbiddenException

if model_name and token_allowed_models and model_name not in token_allowed_models:
    raise ForbiddenException(
        error_code=ErrorCode.TOKEN_MODEL_NOT_ALLOWED,
        message=f"Token not allowed to use model '{model_name}'",
        details={
            "requested_model": model_name,
            "allowed_models": token_allowed_models,
        },
        suggestion="Call GET /v1/models to list available models for your token",
    )
```

**新的响应：**
```json
{
  "success": false,
  "error": {
    "code": "TOKEN_MODEL_NOT_ALLOWED",
    "message": "Token not allowed to use model 'deepseek-v4-pro'",
    "details": {
      "requested_model": "deepseek-v4-pro",
      "allowed_models": ["glm-5.2"]
    },
    "suggestion": "Call GET /v1/models to list available models for your token",
    "request_id": "req_abc123def456",
    "timestamp": "2026-06-21T10:30:00.123456Z"
  }
}
```

### 示例 3：services/user.py 中的验证

**旧代码：**
```python
if len(password) < 8:
    raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
```

**新代码：**
```python
from app.exceptions import AppException
from app.errors import ErrorCode

if len(password) < 8:
    raise AppException(
        error_code=ErrorCode.INVALID_REQUEST,
        message="Password too short",
        details={
            "field": "password",
            "min_length": 8,
            "provided_length": len(password),
        },
        suggestion="Password must be at least 8 characters long",
    )
```

---

## 第五步：测试改进

创建 `tests/test_error_codes.py`：

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.errors import ErrorCode

client = TestClient(app)


def test_token_model_not_allowed():
    """测试模型权限错误响应"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "deepseek-v4-pro",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer sk-restricted-to-glm"},
    )
    
    assert response.status_code == 403
    data = response.json()
    
    # 验证错误结构
    assert not data["success"]
    error = data["error"]
    assert error["code"] == ErrorCode.TOKEN_MODEL_NOT_ALLOWED
    assert "allowed_models" in error["details"]
    assert error["suggestion"] is not None
    assert "request_id" in error
    assert error["request_id"].startswith("req_")


def test_admin_access_required():
    """测试管理员权限错误"""
    response = client.get(
        "/api/users",  # 需要管理员权限
        headers={"Authorization": "Bearer session_regular_user"},
    )
    
    assert response.status_code == 403
    data = response.json()
    error = data["error"]
    assert error["code"] == ErrorCode.ADMIN_ACCESS_REQUIRED
    assert error["suggestion"] is not None


def test_request_id_in_error():
    """测试错误响应中包含 request_id"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "invalid-model",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer valid_token"},
    )
    
    # 验证 header 中的 request_id
    request_id_header = response.headers.get("X-Request-ID")
    assert request_id_header is not None
    
    # 验证响应体中的 request_id
    data = response.json()
    assert data["error"]["request_id"] == request_id_header
```

---

## 迁移检查清单

- [ ] 创建 `app/errors.py` 并定义所有 ErrorCode
- [ ] 更新 `app/exceptions.py` 中的异常类
- [ ] 添加 RequestIDMiddleware 到 middleware
- [ ] 在 `app/main.py` 中注册异常处理器和中间件
- [ ] 迁移 `app/dependencies.py` (10 个错误)
- [ ] 迁移 `app/routers/v1/relay.py` (11 个错误)
- [ ] 迁移 `app/services/user.py` (8 个错误)
- [ ] 迁移 `app/services/token.py` (2 个错误)
- [ ] 迁移 `app/middleware.py` (1 个错误)
- [ ] 编写测试并验证
- [ ] 更新 API 文档
- [ ] 编写迁移指南

---

## 预期收益对比

| 方面 | 现状 | 改进后 |
|------|------|--------|
| **代码冗余** | 高 (重复 status_code) | 低 (单一机制) |
| **错误可追踪** | ❌ | ✅ (request_id) |
| **错误可编程处理** | ❌ | ✅ (error_code) |
| **错误消息完整性** | 50% | 100% |
| **文档化** | 低 | 高 |
| **客户端集成难度** | 高 (解析字符串) | 低 (结构化) |

---

## 时间估计

| 阶段 | 任务 | 时间 |
|------|------|------|
| 1 | 基础设施 (errors.py, exceptions.py 改进) | 2h |
| 2 | 关键路径迁移 (dependencies, relay) | 4h |
| 3 | 完整迁移 (所有文件) | 2h |
| 4 | 测试和文档 | 2h |
| **总计** | | **10h** |

---

## 相关文档

- 📖 [ERROR_CODES_REVIEW.md](ERROR_CODES_REVIEW.md) — 完整审查报告
- 🔗 [HTTP_ERROR_CODE_GUIDE.md](HTTP_ERROR_CODE_GUIDE.md) — HTTP 状态码详解
- ⚡ [HTTP_ERROR_QUICK_REFERENCE.md](HTTP_ERROR_QUICK_REFERENCE.md) — 快速参考
