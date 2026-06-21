# HTTP 错误码系统详解

## 概述

系统中的 HTTP 错误码通过两种机制定义：

1. **FastAPI 内置的 `HTTPException`**（用于 API 响应）
2. **自定义的 `AppException` 体系**（用于应用层异常）

---

## 403 错误码定义

### 在代码中的位置

#### 1️⃣ FastAPI HTTPException（最常用）

**文件：** `app/routers/v1/relay.py` 第 248 行

```python
from fastapi import HTTPException

raise HTTPException(
    status_code=403,
    detail=f"Token not allowed to use model '{model_name}'. "
           f"Allowed models: {', '.join(token_allowed_models)}. "
           f"Call GET /v1/models to list available models."
)
```

**工作原理：**
```
HTTPException 被抛出
    ↓
FastAPI 框架捕获
    ↓
转换为 HTTP 403 响应
    ↓
返回给客户端：
{
  "detail": "Token not allowed to use model 'xxx'..."
}
```

#### 2️⃣ 自定义 ForbiddenException（备选）

**文件：** `app/exceptions.py` 第 32 行

```python
class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(status_code=403, message=message)
```

**使用示例：**
```python
from app.exceptions import ForbiddenException

raise ForbiddenException("Token not allowed to use this model")
```

**工作原理：**
```
ForbiddenException 被抛出
    ↓
FastAPI 的 app_exception_handler 捕获
    ↓
转换为 JSON 响应
    ↓
返回给客户端：
{
  "success": false,
  "message": "Token not allowed to use this model",
  ...
}
```

---

## 完整的异常体系

### AppException 基类

**文件：** `app/exceptions.py`

```python
class AppException(Exception):
    def __init__(
        self,
        status_code: int = 400,
        message: str = "Bad request",
        data: Any = None,
    ):
        self.status_code = status_code
        self.message = message
        self.data = data
```

### 内置的特定异常

| 异常类 | 状态码 | 用途 | 示例 |
|--------|--------|------|------|
| `NotFoundException` | 404 | 资源不存在 | Token not found |
| `UnauthorizedException` | 401 | 身份认证失败 | Invalid token |
| `ForbiddenException` | 403 | 权限不足 | Token not allowed |
| `QuotaExceededException` | 400 | 配额超出 | Quota exceeded |
| `NotImplementedException` | 501 | 未实现 | Feature not available |

### 异常处理流程

**文件：** `app/main.py`

```python
from app.exceptions import AppException, app_exception_handler

# 注册异常处理器
app.add_exception_handler(AppException, app_exception_handler)
```

**处理器实现（简化版）：** `app/exceptions.py`

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

---

## 系统中所有 403 错误的定义位置

### 1. 模型权限检查（Relay）

**文件：** `app/routers/v1/relay.py`

#### 第 248-252 行：模型不被允许
```python
if model_name and token_allowed_models and model_name not in token_allowed_models:
    raise HTTPException(
        status_code=403,
        detail=f"Token not allowed to use model '{model_name}'. "
               f"Allowed models: {', '.join(token_allowed_models)}. "
               f"Call GET /v1/models to list available models."
    )
```

#### 第 281 行：Fusion 权限不足
```python
if not panel:
    raise HTTPException(status_code=403, detail="No fusion-authorized models available for this token")
```

#### 第 371-376 行：Fusion 权限检查（重复）
```python
if allowed_models is not None and m_name not in allowed_models:
    continue
# ...如果无法找到符合权限的模型
raise HTTPException(
    status_code=403,
    detail=f"Token has no authorized model for auto selection. Allowed: {', '.join(allowed_models)}"
)
```

#### 第 414-418 行：最终权限检查
```python
if token_allowed_models and model_name not in token_allowed_models:
    raise HTTPException(
        status_code=403,
        detail=f"Token not allowed to use model '{model_name}'. "
               f"Allowed models: {', '.join(token_allowed_models)}. "
               f"Call GET /v1/models to list available models."
    )
```

#### 第 423-424 行：用户组权限
```python
if user_group != channel.group:
    raise HTTPException(status_code=403, detail=f"User group '{user_group}' not allowed to access channel group '{channel.group}'")
```

### 2. 管理权限检查（Dependencies）

**文件：** `app/dependencies.py`

#### 第 35 行：基本权限拒绝
```python
raise HTTPException(status_code=403, detail="Access denied")
```

#### 第 47 行：管理员权限要求
```python
raise HTTPException(status_code=403, detail="Admin access required")
```

#### 第 58 行：Root 权限要求
```python
raise HTTPException(status_code=403, detail="Root access required")
```

---

## HTTP 状态码的标准定义

### 关键 HTTP 状态码

| 状态码 | 含义 | 何时使用 | 示例 |
|--------|------|---------|------|
| **400** | Bad Request | 请求参数错误 | `model=""` 不指定模型 |
| **401** | Unauthorized | 身份认证失败 | Token 无效、过期 |
| **403** | Forbidden | 有身份但权限不足 | Token 无权使用某模型 |
| **404** | Not Found | 资源不存在 | 模型不存在 |
| **429** | Too Many Requests | 速率限制 | 请求过于频繁 |
| **500** | Internal Error | 服务器错误 | 内部异常 |
| **502** | Bad Gateway | 网关/上游错误 | 代理服务故障 |
| **503** | Service Unavailable | 服务不可用 | 维护中 |

### 403 vs 401 的区别

```
401 Unauthorized（未授权）
├─ 原因：身份验证失败
├─ 场景：Token 无效、过期、不存在
└─ 处理：让用户重新登录/获取 token

403 Forbidden（禁止）
├─ 原因：身份已验证，但权限不足
├─ 场景：Token 有效，但无权使用某模型
└─ 处理：让用户选择允许的资源 ← ✅ 我们的场景
```

---

## 权限检查的执行顺序

```python
async def _handle_relay(request, db):
    # 第1步：验证 token 有效性（401）
    user, token = await _resolve_token_and_channel(request, db)
    
    # 第2步：检查 token 模型权限（403）
    if model_name not in token_allowed_models:
        raise HTTPException(status_code=403, detail=...)  # ← 这里
    
    # 第3步：检查用户组权限（403）
    if user_group != channel.group:
        raise HTTPException(status_code=403, detail=...)  # ← 或这里
    
    # 第4步：执行请求
    ...
```

---

## 客户端应该如何处理 403

### 推荐的错误处理流程

```typescript
async function callAPI(endpoint, token) {
  try {
    const response = await fetch(endpoint, {
      headers: { Authorization: `Bearer ${token}` },
    });
    
    if (response.status === 401) {
      // 认证失败：重新获取 token
      console.log("Token invalid, please re-authenticate");
      redirectToLogin();
    } else if (response.status === 403) {
      // 权限不足：告知用户并建议解决方案
      const error = await response.json();
      console.error("Access denied:", error.detail);
      
      // 对于模型权限错误
      if (error.detail.includes("not allowed to use model")) {
        console.log("Getting available models...");
        const models = await fetch("/v1/models", {
          headers: { Authorization: `Bearer ${token}` },
        }).json();
        showAvailableModels(models.data);
      }
    }
  } catch (error) {
    console.error("Request failed:", error);
  }
}
```

---

## 代码对应关系速查

### 抛出 403 的所有位置

```bash
# 查找所有 status_code=403
grep -n "status_code=403" app/routers/v1/relay.py
grep -n "status_code=403" app/dependencies.py

# 查找所有 ForbiddenException
grep -rn "ForbiddenException" app/
```

### 快速查询

| 错误消息 | 代码位置 | 原因 |
|---------|---------|------|
| "Token not allowed..." | relay.py:248, 414 | 模型权限检查 |
| "No fusion-authorized..." | relay.py:281 | Fusion 权限不足 |
| "User group not allowed..." | relay.py:424 | 用户组权限 |
| "Access denied" | dependencies.py:35 | 一般权限拒绝 |
| "Admin access required" | dependencies.py:47 | 管理员权限 |
| "Root access required" | dependencies.py:58 | Root 权限 |

---

## 定制 403 错误消息的方法

### 方法 1：使用 FastAPI HTTPException（推荐）

```python
raise HTTPException(
    status_code=403,
    detail={
        "error": "ModelNotAllowed",
        "message": "Token not allowed to use model 'xxx'",
        "allowed_models": ["glm-5.2"],
        "help": "Call GET /v1/models to list available models"
    }
)
```

### 方法 2：使用自定义 ForbiddenException

```python
# 修改 app/exceptions.py
class ModelNotAllowedException(ForbiddenException):
    def __init__(self, model: str, allowed: list[str]):
        super().__init__(f"Model '{model}' not allowed. Allowed: {allowed}")

# 使用
raise ModelNotAllowedException("deepseek-v4-pro", ["glm-5.2"])
```

### 方法 3：创建自定义异常处理器

```python
# app/main.py
@app.exception_handler(ModelNotAllowedException)
async def model_not_allowed_handler(request: Request, exc: ModelNotAllowedException):
    return JSONResponse(
        status_code=403,
        content={
            "error": "ModelNotAllowed",
            "message": str(exc),
            "timestamp": datetime.now().isoformat(),
        },
    )
```

---

## 总结

| 层级 | 定义方式 | 示例 | 用途 |
|------|---------|------|------|
| **FastAPI 层** | `HTTPException(status_code=403, detail="...")` | 最直接、最常用 | API 立即响应 |
| **应用层** | `AppException` 体系 | 灵活、可扩展 | 复杂业务逻辑 |
| **HTTP 标准** | 状态码 (403) + 消息 | REST 标准 | 客户端理解 |

---

## 参考资源

- **FastAPI 官方文档**: https://fastapi.tiangolo.com/tutorial/handling-errors/
- **HTTP 状态码标准**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403
- **我们的代码**: 
  - [app/routers/v1/relay.py](app/routers/v1/relay.py) — 权限检查
  - [app/exceptions.py](app/exceptions.py) — 异常定义
  - [app/main.py](app/main.py) — 异常注册

---

## 快速答案

**Q: 403 拒绝未授权的模型，这个错误代码是如何定义的？**

**A:** 通过 FastAPI 内置的 `HTTPException` 定义：

```python
raise HTTPException(
    status_code=403,           # ← HTTP 标准状态码
    detail="..."               # ← 错误消息
)
```

- **status_code=403** 来自 HTTP 标准，表示 "Forbidden"（禁止）
- **detail** 字段可包含任何字符串或结构化数据
- FastAPI 框架自动将其转换为 JSON 响应返回给客户端

参见：[app/routers/v1/relay.py](app/routers/v1/relay.py#L248)
