# 测试用例 - Token权限验证

此目录包含错误代码系统改进方案的测试用例参考。

## 📋 包含的文件

### test_token_permissions.py
**位置：** `/Users/macairm5/Documents/uniapi-py/docs/error-codes/tests/test_token_permissions.py`

**内容：** 完整的 Token 权限验证测试套件

**用途：**
- 验证 Token 权限检查是否正常工作
- 验证错误响应格式和内容
- 验证新的改进是否有效
- 提供测试最佳实践的参考

**测试场景：**

| 测试 | 描述 | 预期结果 |
|------|------|---------|
| ✅ test_no_token | 无 token 请求 | 401 Unauthorized |
| ✅ test_invalid_token | 无效 token | 401 Invalid token |
| ✅ test_glm_model_allowed | 允许的模型 | 200 OK (或模型不存在) |
| ✅ test_deepseek_model_forbidden | 禁止的模型 | 403 Forbidden |
| ✅ test_auto_selection | 自动选择 | 200 OK (使用允许的模型) |
| ✅ test_get_models_endpoint | 获取模型列表 | 200 OK (仅返回允许的模型) |
| ✅ test_fusion_forbidden | Fusion 权限检查 | 400 或 403 |
| ✅ test_error_contains_suggestion | 错误包含建议 | 错误消息含 /v1/models 提示 |

---

## 🚀 如何运行测试

### 前置条件
```bash
# 确保环境已配置
cd /Users/macairm5/Documents/uniapi-py

# 激活虚拟环境
source .venv/bin/activate

# 确保依赖已安装
pip install httpx pytest
```

### 运行所有测试
```bash
# 使用 pytest
pytest test_token_permissions.py -v

# 或者直接用 Python 运行
python3 test_token_permissions.py https://api.ccbot.chat sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1
```

### 运行特定测试
```bash
# 只测试模型权限
pytest test_token_permissions.py::test_deepseek_model_forbidden -v

# 只测试获取模型列表
pytest test_token_permissions.py::test_get_models_endpoint -v
```

---

## 📊 测试用例详情

### 1. 无 Token 请求
```python
def test_no_token():
    """应该返回 401 - No token provided"""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "glm-5.2", "messages": [...]},
    )
    assert response.status_code == 401
    data = response.json()
    assert "No token provided" in data.get("detail", "")
```

**预期：**
- 状态码：401
- 错误信息：No token provided

---

### 2. 无效 Token
```python
def test_invalid_token():
    """应该返回 401 - Invalid token"""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "glm-5.2", "messages": [...]},
        headers={"Authorization": "Bearer invalid-token-12345"},
    )
    assert response.status_code == 401
    data = response.json()
    assert "Invalid token" in data.get("detail", "")
```

**预期：**
- 状态码：401
- 错误信息：Invalid token

---

### 3. 允许的模型
```python
def test_glm_model_allowed():
    """Token 允许使用 glm-5.2"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "glm-5.2",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer sk-989ef..."},
    )
    # 应该被接受（可能因为模型不存在而失败，但不是 403 权限错误）
    assert response.status_code != 403
```

**预期：**
- 状态码：不是 403（2xx 或其他 4xx，但不是权限错误）

---

### 4. 禁止的模型 ⭐ **最重要**
```python
def test_deepseek_model_forbidden():
    """Token 不允许使用 deepseek-v4-pro，应返回 403"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "deepseek-v4-pro",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer sk-989ef..."},
    )
    assert response.status_code == 403
    data = response.json()
    
    # 验证错误内容
    detail = data.get("detail", "")
    assert "deepseek-v4-pro" in detail  # 包含请求的模型
    assert "glm-5.2" in detail  # 包含允许的模型
    assert "/v1/models" in detail  # 包含建议
```

**预期：**
- 状态码：403 Forbidden
- 错误消息应包含：
  - 请求的模型名 (deepseek-v4-pro)
  - 允许的模型列表 (glm-5.2)
  - 解决建议 (/v1/models)

---

### 5. 自动选择模型
```python
def test_auto_selection():
    """model='auto' 应选择允许的最便宜模型"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "auto",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer sk-989ef..."},
    )
    # 应该成功（或因为消息处理失败，但不是权限/模型错误）
    assert response.status_code not in [400, 403]
```

**预期：**
- 自动选择应该是允许的模型之一

---

### 6. 获取模型列表 ⭐ **最重要**
```python
def test_get_models_endpoint():
    """GET /v1/models 应返回 Token 允许的模型"""
    response = client.get(
        "/v1/models",
        headers={"Authorization": "Bearer sk-989ef..."},
    )
    assert response.status_code == 200
    data = response.json()
    
    # 验证返回的模型列表
    models = [m["id"] for m in data.get("data", [])]
    assert "glm-5.2" in models  # 应包含允许的模型
    assert "deepseek-v4-pro" not in models  # 不应包含禁止的模型
```

**预期：**
- 状态码：200 OK
- 返回模型列表中只有允许的模型
- 不包含禁止的模型

---

### 7. Fusion 权限检查
```python
def test_fusion_authorization():
    """Fusion 权限检查"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "fusion",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer sk-989ef..."},
    )
    # 应该失败（无权限或配置问题）
    assert response.status_code in [400, 403]
```

**预期：**
- 400（无 Fusion 配置）或 403（权限不足）

---

### 8. 错误消息包含建议 ⭐ **改进后的新测试**
```python
def test_error_contains_suggestion():
    """错误消息应包含解决建议"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "deepseek-v4-pro",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer sk-989ef..."},
    )
    assert response.status_code == 403
    data = response.json()
    
    # 验证改进后的结构
    error_detail = data.get("detail", "")
    assert "Call GET /v1/models" in error_detail
    # 或者（改进后）
    if "error" in data:
        error = data["error"]
        assert "suggestion" in error
        assert "/v1/models" in error["suggestion"]
```

**预期：**
- 错误消息应包含 `/v1/models` 提示
- 改进后应有专门的 `suggestion` 字段

---

## 🔍 如何验证改进

### 改进前的错误响应
```json
{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'. Allowed models: glm-5.2. Call GET /v1/models to list available models."
}
```

### 改进后的错误响应（目标）
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

### 验证测试
```python
def test_improved_error_format():
    """验证改进后的错误响应格式"""
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "deepseek-v4-pro",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Authorization": "Bearer sk-989ef..."},
    )
    
    assert response.status_code == 403
    data = response.json()
    
    # 检查新的结构
    assert "error" in data
    error = data["error"]
    assert error["code"] == "TOKEN_MODEL_NOT_ALLOWED"
    assert "suggestion" in error
    assert "request_id" in error
    assert "timestamp" in error
    assert "details" in error
    assert error["details"]["allowed_models"] == ["glm-5.2"]
```

---

## 🧪 为新的错误系统编写测试

### 示例：测试新的 ErrorCode 枚举
```python
# tests/test_errors.py

from app.errors import ErrorCode, ERROR_CODE_TO_STATUS

def test_error_code_to_status_mapping():
    """验证错误代码到状态码的映射"""
    assert ERROR_CODE_TO_STATUS[ErrorCode.ADMIN_ACCESS_REQUIRED] == 403
    assert ERROR_CODE_TO_STATUS[ErrorCode.INVALID_TOKEN] == 401
    assert ERROR_CODE_TO_STATUS[ErrorCode.TOKEN_MODEL_NOT_ALLOWED] == 403

def test_all_error_codes_have_status():
    """验证每个错误代码都有状态码映射"""
    for error_code in ErrorCode:
        assert error_code in ERROR_CODE_TO_STATUS
```

### 示例：测试新的异常处理器
```python
# tests/test_exceptions.py

from app.exceptions import ForbiddenException
from app.errors import ErrorCode

def test_forbidden_exception_response():
    """验证改进后的异常处理器响应格式"""
    exc = ForbiddenException(
        error_code=ErrorCode.TOKEN_MODEL_NOT_ALLOWED,
        message="Test message",
        details={"model": "test-model"},
    )
    
    assert exc.error_code == ErrorCode.TOKEN_MODEL_NOT_ALLOWED.value
    assert exc.status_code == 403
    assert exc.message == "Test message"
    assert exc.details["model"] == "test-model"
    assert exc.suggestion is not None  # 自动查询
```

---

## 📈 测试覆盖率

### 现有测试
- ✅ Token 认证
- ✅ 模型权限
- ✅ 获取模型列表
- ✅ 自动选择

### 改进后应添加的测试
- ❌ 错误代码格式
- ❌ 请求 ID 追踪
- ❌ 时间戳
- ❌ 详细信息结构
- ❌ 建议文本

---

## 🔗 相关文档

- 📖 [ERROR_CODES_REVIEW.md](../ERROR_CODES_REVIEW.md) - 为什么需要改进
- ⚡ [ERROR_CODES_IMPLEMENTATION_GUIDE.md](../ERROR_CODES_IMPLEMENTATION_GUIDE.md) - 测试部分
- 💻 [../examples/README.md](../examples/README.md) - 代码示例

---

## 📝 最佳实践

### 1. 测试所有错误路径
```python
def test_all_error_scenarios():
    """测试所有可能导致权限错误的场景"""
    scenarios = [
        (401, "no_token"),
        (401, "invalid_token"),
        (403, "model_not_allowed"),
        (403, "admin_access_required"),
        (403, "user_group_not_allowed"),
    ]
    # 对每个场景验证...
```

---

### 2. 验证错误消息的可用性
```python
def test_error_message_helpful():
    """验证错误消息对用户有帮助"""
    response = client.post(...)
    
    if response.status_code == 403:
        data = response.json()
        detail = data.get("detail", "")
        # 应该包含：
        assert any(hint in detail for hint in [
            "allowed",
            "Call",
            "GET /v1/models",
            "list",
        ])
```

---

### 3. 定期运行测试
```bash
# 每次部署前
pytest test_token_permissions.py -v

# 开发时持续测试
pytest test_token_permissions.py -v --watch

# CI/CD 集成
# (在 .github/workflows/ 或 .gitlab-ci.yml 中配置)
```

---

## 💡 调试技巧

### 1. 打印完整响应
```python
def test_debug_response():
    response = client.post("/v1/chat/completions", ...)
    print(f"Status: {response.status_code}")
    print(f"Body: {response.json()}")
    print(f"Headers: {response.headers}")
```

### 2. 使用实际的 API 端点
```bash
# 实时测试（使用真实的 Token）
python3 test_token_permissions.py https://api.ccbot.chat sk-xxxx
```

### 3. 启用详细日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📞 常见问题

**Q: 测试失败是什么原因？**
A: 检查：
1. Token 是否有效
2. API 端点是否可达
3. Token 的权限配置

**Q: 如何添加自己的测试？**
A: 复制现有的测试并修改场景。

**Q: 测试可以在 CI/CD 中运行吗？**
A: 是的，建议集成到 CI/CD 流程。

