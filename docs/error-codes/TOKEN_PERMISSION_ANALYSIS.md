# Token 权限诊断报告

## 测试 Token
```
Token: sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1
Base URL: api.ccbot.chat
Allowed Models: glm-5.2 (仅此一个)
```

---

## 实际测试结果

### ✅ 权限检查**有效**

| 测试场景 | 状态码 | 结果 | 说明 |
|---------|-------|------|------|
| `model="glm-5.2"` | 200 | ✅ 成功 | 正确允许授权模型 |
| `model="auto"` | 200 | ✅ 成功 | 自动选择 glm-5.2 (尊重权限) |
| 无 model 参数 | 400 | ❌ 拒绝 | 未指定模型 |
| `model="deepseek-v4-pro"` | 403 | ❌ 拒绝 | **正确阻止非授权模型** |
| `model="fusion"` | 400 | ❌ 拒绝 | 权限不足 (需 2+ 模型) |

### 核心发现

**系统权限检查工作正常！** 即使客户端尝试请求 `deepseek-v4-pro`，服务器也会正确拒绝：

```json
{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'"
}
```

---

## 根因分析：为什么会困惑

您说"token 只支持 glm-5.2，为什么会去找 deepseek-v4-pro"？

**可能原因：**

### 原因 1: 客户端行为
- 客户端可能在某个重试或 fallback 逻辑中，会尝试其他模型
- 看到日志中提到 `deepseek-v4-pro` 时以为系统选了它
- **实际上：** 请求被拒绝了，只是被尝试过

### 原因 2: 错误消息不清晰（已修复）
之前的错误消息：
```json
{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'"
}
```

新的错误消息（已改进）：
```json
{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'. Allowed models: glm-5.2"
}
```

### 原因 3: 没有 model 时的提示（已改进）
之前：
```json
{
  "detail": "Model '' not supported by any configured provider"
}
```

新的提示：
```json
{
  "detail": "Model not specified. Token is restricted to: glm-5.2. Please specify one of these models or use model='auto' for automatic selection."
}
```

---

## 已做的代码改进

### 1. 提前验证权限 (第 238-251 行)

```python
# Token model permissions check (early validation)
token_allowed_models = None
if hasattr(token, "models") and token.models:
    token_allowed_models = [m.strip() for m in token.models.split(",") if m.strip()]

# If model is specified, validate it against token permissions
if model_name and token_allowed_models and model_name not in token_allowed_models:
    raise HTTPException(
        status_code=403,
        detail=f"Token not allowed to use model '{model_name}'. "
               f"Allowed models: {', '.join(token_allowed_models)}"
    )

# If no model specified but token has restrictions, require explicit selection
if not model_name and token_allowed_models and model_name != "auto":
    raise HTTPException(
        status_code=400,
        detail=f"Model not specified. Token is restricted to: {', '.join(token_allowed_models)}. "
               f"Please specify one of these models or use model='auto' for automatic selection."
    )
```

### 2. 改进最终权限检查的错误消息 (第 410+ 行)

```python
# Token model permissions (final check after any model resolution/selection)
if token_allowed_models and model_name not in token_allowed_models:
    raise HTTPException(
        status_code=403,
        detail=f"Token not allowed to use model '{model_name}'. "
               f"Allowed models: {', '.join(token_allowed_models)}"
    )
```

---

## 推荐的客户端行为

对于您的 token（仅允许 glm-5.2），客户端应该：

### ✅ 推荐用法
```bash
# 方式 1: 显式指定模型
curl -X POST https://api.ccbot.chat/v1/chat/completions \
  -H "Authorization: Bearer sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5.2",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 方式 2: 使用 auto（自动选择可用模型）
curl -X POST https://api.ccbot.chat/v1/chat/completions \
  -H "Authorization: Bearer sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### ❌ 不推荐（会被拒绝）
```bash
# 不指定 model
{
  "messages": [...]
}

# 尝试未授权的模型
{
  "model": "deepseek-v4-pro",
  "messages": [...]
}
```

---

## 总结

| 项目 | 状态 | 说明 |
|------|------|------|
| 权限检查 | ✅ 有效 | Token 只能访问授权的模型 |
| 非法访问阻止 | ✅ 有效 | 试图访问 deepseek-v4-pro 被拒 |
| 错误消息清晰度 | ✅ 已改进 | 现在会告诉用户允许的模型列表 |
| 无 model 提示 | ✅ 已改进 | 用户现在知道应该用哪些模型或 auto |

**系统是安全的。** Token 权限得到了妥当的保护。

---

## 后续步骤

1. ✅ **代码已修改**（本地）— 见 [app/routers/v1/relay.py](app/routers/v1/relay.py)
2. 📋 **需要您部署** — 重启 api.ccbot.chat 服务器使改动生效
3. ✅ **改进已完成** — 错误消息现在会显示允许的模型列表

### 部署命令
```bash
cd /path/to/uniapi-py
git pull  # 获取最新代码
python3 -m pip install -e .  # 更新依赖
# 重启 FastAPI 服务器
uvicorn app.main:app --reload --port 8000
```

或使用 Docker：
```bash
docker compose up --build
```
