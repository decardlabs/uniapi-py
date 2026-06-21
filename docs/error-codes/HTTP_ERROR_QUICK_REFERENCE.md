# 403 错误码定义 - 速查表

## 简化回答

**403 错误码在代码中是这样定义的：**

```python
from fastapi import HTTPException

raise HTTPException(
    status_code=403,                    # ← HTTP 标准中的状态码数字
    detail="Token not allowed to use..."  # ← 错误消息文本
)
```

### 工作流程图

```
代码抛出异常
    │
    ├─ status_code=403  
    │   └─ 来自 HTTP 1.1 标准规范
    │   └─ 表示 "Forbidden" (禁止访问)
    │
    ├─ detail="..."
    │   └─ 人类可读的错误消息
    │   └─ 包含具体原因和建议
    │
    ▼
FastAPI 框架
    │
    ├─ 捕获 HTTPException
    ├─ 读取 status_code 和 detail
    ├─ 生成 HTTP 响应
    │
    ▼
HTTP 响应
{
  "detail": "Token not allowed to use model 'xxx'..."
}

HTTP/1.1 403 Forbidden
```

---

## 系统中的所有 403 定义

### 位置 1：模型权限检查（最常见）

**文件：** `app/routers/v1/relay.py` 第 248 行

```python
if model_name and token_allowed_models and model_name not in token_allowed_models:
    raise HTTPException(
        status_code=403,
        detail=f"Token not allowed to use model '{model_name}'. "
               f"Allowed models: {', '.join(token_allowed_models)}. "
               f"Call GET /v1/models to list available models."
    )
```

### 位置 2：最终权限再次检查

**文件：** `app/routers/v1/relay.py` 第 414 行

```python
if token_allowed_models and model_name not in token_allowed_models:
    raise HTTPException(
        status_code=403,
        detail=f"Token not allowed to use model '{model_name}'. "
               f"Allowed models: {', '.join(token_allowed_models)}. "
               f"Call GET /v1/models to list available models."
    )
```

### 位置 3：Fusion 权限不足

**文件：** `app/routers/v1/relay.py` 第 281 行

```python
if not panel:
    raise HTTPException(
        status_code=403, 
        detail="No fusion-authorized models available for this token"
    )
```

### 位置 4：用户组权限

**文件：** `app/routers/v1/relay.py` 第 424 行

```python
raise HTTPException(
    status_code=403, 
    detail=f"User group '{user_group}' not allowed to access channel group '{channel.group}'"
)
```

### 位置 5-7：管理权限

**文件：** `app/dependencies.py` 第 35, 47, 58 行

```python
# 第 35 行：一般权限拒绝
raise HTTPException(status_code=403, detail="Access denied")

# 第 47 行：管理员权限要求
raise HTTPException(status_code=403, detail="Admin access required")

# 第 58 行：Root 权限要求
raise HTTPException(status_code=403, detail="Root access required")
```

---

## 关键技术细节

### 为什么用 403 而不是 401？

```
401 Unauthorized
├─ 意思：您没有身份（Token 无效/不存在）
├─ 客户端应该：重新认证
└─ 我们的场景：❌ 不适用（Token 是有效的）

403 Forbidden  
├─ 意思：您有身份，但权限不足
├─ 客户端应该：使用有权限的资源
└─ 我们的场景：✅ 完全适用（Token 有效，但无权用某模型）
```

### 403 在 HTTP 标准中的定义

```
RFC 7231 - HTTP Semantics and Content
Section 6.5.3 - 403 Forbidden

The 403 (Forbidden) status code indicates that the server 
understood the request but refuses to authorize it.
```

---

## 三种异常机制

### 机制 1️⃣ : FastAPI HTTPException（当前使用）

```python
from fastapi import HTTPException

raise HTTPException(status_code=403, detail="...")
```

✅ 优点：
- 简单直接
- FastAPI 自动处理
- 用于 API 立即响应

### 机制 2️⃣ : 自定义 AppException

**定义位置：** `app/exceptions.py`

```python
class AppException(Exception):
    def __init__(self, status_code: int = 400, message: str = "..."):
        self.status_code = status_code
        self.message = message

class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(status_code=403, message=message)
```

✅ 优点：
- 类型安全
- 可复用
- 易于维护

### 机制 3️⃣ : 自定义异常处理器

```python
@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc)}
    )
```

✅ 优点：
- 统一处理
- 支持自定义格式
- 集中管理

---

## 客户端收到 403 的样子

### HTTP 响应头

```
HTTP/1.1 403 Forbidden
Content-Type: application/json
Content-Length: 150
```

### 响应体

```json
{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'. Allowed models: glm-5.2. Call GET /v1/models to list available models."
}
```

### cURL 测试

```bash
curl -v -X POST "https://api.ccbot.chat/v1/chat/completions" \
  -H "Authorization: Bearer sk-989ef..." \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-pro", "messages":[...]}'
  
# 响应：
# < HTTP/1.1 403 Forbidden
# {"detail":"Token not allowed to use model 'deepseek-v4-pro'..."}
```

---

## 如何修改 403 错误消息

### 场景：想要更详细的错误响应

**当前响应：**
```json
{"detail": "Token not allowed to use model 'xxx'..."}
```

**改进为结构化响应：**

```python
# app/routers/v1/relay.py
raise HTTPException(
    status_code=403,
    detail={
        "error": "ModelNotAllowed",
        "message": f"Token cannot use model '{model_name}'",
        "allowed_models": token_allowed_models,
        "help_url": "/v1/models",
        "timestamp": datetime.now().isoformat()
    }
)
```

**新的响应：**
```json
{
  "detail": {
    "error": "ModelNotAllowed",
    "message": "Token cannot use model 'deepseek-v4-pro'",
    "allowed_models": ["glm-5.2"],
    "help_url": "/v1/models",
    "timestamp": "2026-06-21T10:30:00.123456"
  }
}
```

---

## 总结对比

| 特性 | FastAPI HTTPException | AppException | 自定义处理器 |
|------|----------------------|--------------|-------------|
| 定义方式 | `raise HTTPException(...)` | `raise ForbiddenException(...)` | 装饰器注册 |
| 使用难度 | ⭐ 简单 | ⭐⭐ 中等 | ⭐⭐⭐ 复杂 |
| 灵活性 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 推荐场景 | 快速开发 | 重用代码 | 统一格式 |
| 我们用的 | ✅ 现在用 | 📋 可选 | ❌ 未使用 |

---

## 快速链接

- 📖 详细文档：[HTTP_ERROR_CODE_GUIDE.md](HTTP_ERROR_CODE_GUIDE.md)
- 💻 代码位置：
  - [app/routers/v1/relay.py](app/routers/v1/relay.py#L248) (model check)
  - [app/dependencies.py](app/dependencies.py#L35) (auth check)
  - [app/exceptions.py](app/exceptions.py) (exception definitions)
  - [app/main.py](app/main.py) (exception handler setup)
- 🧪 测试脚本：[test_token_permissions.py](tests/test_token_permissions.py)
