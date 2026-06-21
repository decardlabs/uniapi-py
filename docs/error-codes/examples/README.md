# 代码示例 - 参考实现

此目录包含改进方案的参考代码实现。所有代码文件均位于项目根目录，这里提供导航。

## 📋 包含的文件

### 1. ERROR_CODES_EXAMPLE.py
**位置：** `/Users/macairm5/Documents/uniapi-py/docs/error-codes/examples/ERROR_CODES_EXAMPLE.py`

**内容：** ErrorCode 枚举定义的参考实现

**关键内容：**
- `ErrorCode` 枚举类 - 所有错误代码的定义
- `ERROR_CODE_TO_STATUS` 映射表 - 错误代码到 HTTP 状态码
- `ERROR_CODE_TO_SUGGESTION` 映射表 - 错误代码到建议文本
- `get_suggestion_for_error()` 工具函数
- `get_help_url_for_error()` 工具函数

**用途：**
- 参考 ErrorCode 枚举如何组织
- 参考映射表的结构和内容
- 复制粘贴到项目中作为 `app/errors.py`

**代码长度：** ~150 行

**创建方式：**
1. 在项目中创建 `app/errors.py`
2. 复制 `ERROR_CODES_EXAMPLE.py` 的内容
3. 根据项目需要调整错误代码和建议文本

---

### 2. EXCEPTIONS_IMPROVED_EXAMPLE.py
**位置：** `/Users/macairm5/Documents/uniapi-py/docs/error-codes/examples/EXCEPTIONS_IMPROVED_EXAMPLE.py`

**内容：** 改进的异常处理实现

**关键内容：**
- 改进的 `AppException` 基类
- 5 种具体异常类：
  - `UnauthorizedException` (401)
  - `ForbiddenException` (403)
  - `NotFoundException` (404)
  - `BadRequestException` (400)
  - `QuotaExceededException`
- 改进的异常处理器 `app_exception_handler()`
- 详细的使用示例和集成说明

**关键改进：**
- 支持 `error_code` 参数（机器可读的错误代码）
- 支持 `details` 字典（上下文信息）
- 支持 `suggestion` 参数（用户建议）
- 自动映射 HTTP 状态码
- 自动查询建议文本
- 返回结构化的错误响应

**用途：**
- 替换或改进项目中的 `app/exceptions.py`
- 参考异常处理最佳实践
- 复制异常处理器的实现

**代码长度：** ~250 行

**创建方式：**
1. 打开现有的 `app/exceptions.py`
2. 比对 `EXCEPTIONS_IMPROVED_EXAMPLE.py` 的改进
3. 选择性地应用改进
4. 或者完全替换为新的实现

---

## 🔄 如何使用这些示例

### 场景 A：从零开始创建错误系统
```
1. 创建 app/errors.py
   └─ 复制 ERROR_CODES_EXAMPLE.py 的内容

2. 创建/改进 app/exceptions.py
   └─ 参考 EXCEPTIONS_IMPROVED_EXAMPLE.py

3. 注册异常处理器
   └─ 在 app/main.py 中调用 app.add_exception_handler()

4. 迁移现有代码
   └─ 将 HTTPException 替换为 ForbiddenException 等
```

---

### 场景 B：渐进式改进现有系统
```
1. 保持现有的 app/exceptions.py
   
2. 创建新的 app/errors.py
   └─ 定义 ErrorCode 枚举（可复用）

3. 逐步迁移：
   a. 迁移 dependencies.py (10 个错误)
   b. 迁移 relay.py 权限检查 (7 个错误)
   c. 迁移 services/user.py (5 个错误)
   d. 迁移其他文件

4. 最后一步：
   └─ 彻底替换 app/exceptions.py
```

---

### 场景 C：学习最佳实践
```
1. 研究 ERROR_CODES_EXAMPLE.py
   └─ 了解如何组织错误代码

2. 研究 EXCEPTIONS_IMPROVED_EXAMPLE.py
   └─ 了解异常处理的改进

3. 对比 app/exceptions.py
   └─ 理解改进的地方

4. 应用到项目
   └─ 采用最适合的部分
```

---

## 📊 代码结构对比

### 现有实现
```python
# app/exceptions.py (当前)
class AppException(Exception):
    def __init__(self, status_code, message, data):
        self.status_code = status_code
        self.message = message
        self.data = data

# 使用
raise HTTPException(status_code=403, detail="Admin required")
```

### 改进后的实现
```python
# app/errors.py (新增)
class ErrorCode(str, Enum):
    ADMIN_ACCESS_REQUIRED = "ADMIN_ACCESS_REQUIRED"

# app/exceptions.py (改进)
class AppException(Exception):
    def __init__(self, error_code, message, details, suggestion):
        self.error_code = error_code
        self.status_code = ERROR_CODE_TO_STATUS[error_code]
        self.message = message
        self.details = details
        self.suggestion = suggestion or get_suggestion_for_error(error_code)

# 使用
raise ForbiddenException(
    error_code=ErrorCode.ADMIN_ACCESS_REQUIRED,
    message="Admin access required",
)
```

---

## 🎯 关键改进亮点

### 1. 错误代码标准化
```python
# 旧：字符串直接用
raise HTTPException(status_code=401, detail="Invalid token")

# 新：枚举常量
raise UnauthorizedException(
    error_code=ErrorCode.INVALID_TOKEN,
    message="Invalid token",
)

# 好处：
# ✅ IDE 自动补全
# ✅ 编译时检查
# ✅ 易于重构
```

---

### 2. 自动映射和查询
```python
# 旧：手动指定状态码
raise HTTPException(status_code=403, detail="...")

# 新：自动查询
raise ForbiddenException(
    error_code=ErrorCode.TOKEN_MODEL_NOT_ALLOWED,
    message="Token not allowed",
    # 自动查询：
    # - status_code 从 ERROR_CODE_TO_STATUS 查询
    # - suggestion 从 ERROR_CODE_TO_SUGGESTION 查询
)

# 好处：
# ✅ 减少重复
# ✅ 集中管理
# ✅ 易于维护
```

---

### 3. 结构化错误响应
```python
# 旧响应格式
{
  "detail": "Token not allowed to use model 'xxx'"
}

# 新响应格式
{
  "success": false,
  "error": {
    "code": "TOKEN_MODEL_NOT_ALLOWED",
    "message": "Token not allowed to use model 'deepseek-v4-pro'",
    "details": {
      "requested_model": "deepseek-v4-pro",
      "allowed_models": ["glm-5.2"]
    },
    "suggestion": "Call GET /v1/models to list available models",
    "request_id": "req_abc123",
    "timestamp": "2026-06-21T10:30:00Z"
  }
}

# 好处：
# ✅ 机器可读（error_code）
# ✅ 人类可读（message + suggestion）
# ✅ 可追踪（request_id + timestamp）
# ✅ 有上下文（details）
```

---

## 🧪 测试用例

虽然具体的测试在 `tests/` 目录中，但这些示例文件也包含了使用示例：

```python
# 在 EXCEPTIONS_IMPROVED_EXAMPLE.py 中查看：

"""
在 FastAPI 应用中使用：

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if request.model not in allowed_models:
        raise ForbiddenException(
            error_code=ErrorCode.TOKEN_MODEL_NOT_ALLOWED,
            message=f"Token not allowed to use model '{request.model}'",
            details={
                "requested_model": request.model,
                "allowed_models": list(allowed_models),
            },
        )
"""
```

---

## 📈 代码行数统计

| 文件 | 行数 | 用途 |
|------|------|------|
| ERROR_CODES_EXAMPLE.py | ~150 | ErrorCode 定义 |
| EXCEPTIONS_IMPROVED_EXAMPLE.py | ~250 | 异常类实现 |
| **总计** | **~400** | 参考代码 |

---

## 🔍 深度学习

### 如果你想理解为什么这样改进
1. 阅读 `ERROR_CODES_REVIEW.md` 中的"问题 1-6"章节
2. 查看现有的 `app/exceptions.py`
3. 对比 `EXCEPTIONS_IMPROVED_EXAMPLE.py`
4. 理解每个改进的必要性

### 如果你想快速开始应用
1. 复制 `ERROR_CODES_EXAMPLE.py` 创建 `app/errors.py`
2. 在某个路由中试用新的异常
3. 验证错误响应格式
4. 逐步扩展使用范围

---

## ❓ 常见问题

**Q: 我能同时使用新旧异常吗？**
A: 是的，可以渐进式迁移。新的异常和旧的 HTTPException 可以共存。

**Q: 这会影响客户端吗？**
A: 不会。HTTP 状态码保持不变，只是响应体格式改进。

**Q: ErrorCode 枚举可以扩展吗？**
A: 是的，非常容易。只需在 `ERROR_CODES_EXAMPLE.py` 中添加新的枚举值。

**Q: 如何添加新的错误代码？**
A: 
1. 在 `ErrorCode` 枚举中添加新的常量
2. 在 `ERROR_CODE_TO_STATUS` 中添加映射
3. 在 `ERROR_CODE_TO_SUGGESTION` 中添加建议（可选）

**Q: 这些代码生产就绪吗？**
A: 是的，这些是参考实现，可以直接用于生产。建议先在测试环境验证。

---

## 🚀 快速开始（5 分钟）

```bash
# 1. 复制 ERROR_CODES_EXAMPLE.py
cp ERROR_CODES_EXAMPLE.py app/errors.py

# 2. 在 app/main.py 中导入
from app.errors import ErrorCode

# 3. 更新 app/exceptions.py (参考 EXCEPTIONS_IMPROVED_EXAMPLE.py)
# (手动更新或全部替换)

# 4. 在某个路由中使用新异常
from app.exceptions import ForbiddenException
from app.errors import ErrorCode

@app.get("/admin")
async def admin_only(user = Depends(get_user)):
    if user.role < 10:
        raise ForbiddenException(
            error_code=ErrorCode.ADMIN_ACCESS_REQUIRED,
            message="Admin access required",
        )
    return {"admin": True}

# 5. 测试
# curl http://localhost:8000/admin -H "Authorization: Bearer user_token"
# 应该返回 403 Forbidden，包含结构化的错误信息
```

---

## 📚 相关文档

- 📖 [ERROR_CODES_REVIEW.md](../ERROR_CODES_REVIEW.md) - 为什么需要这些改进
- ⚡ [ERROR_CODES_IMPLEMENTATION_GUIDE.md](../ERROR_CODES_IMPLEMENTATION_GUIDE.md) - 如何具体实施
- 🧪 [../tests/README.md](../tests/README.md) - 测试用例说明
