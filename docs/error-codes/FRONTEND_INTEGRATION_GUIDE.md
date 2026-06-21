# 前端智能体集成指南

## 概述

当 token 的权限受限（仅允许特定模型）时，前端智能体应该通过**查询模型列表**来确定可用的模型，而不是盲目尝试。

---

## 推荐的前端工作流程

### 1️⃣ **初始化：获取该 token 可用的模型列表**

```bash
GET /v1/models
Authorization: Bearer {token}
```

**响应示例：**
```json
{
  "object": "list",
  "data": [
    {
      "id": "glm-5.2",
      "object": "model",
      "created": 1718894400,
      "owned_by": "glm"
    }
  ]
}
```

**前端应该：**
- 在初始化时调用此端点
- 将返回的模型列表保存
- 在 UI 中仅显示这些模型供用户选择

### 2️⃣ **发送请求：使用获取到的模型**

```bash
POST /v1/chat/completions
Authorization: Bearer {token}
Content-Type: application/json

{
  "model": "glm-5.2",    # 从 /v1/models 获取的模型
  "messages": [
    {"role": "user", "content": "Hello"}
  ]
}
```

### 3️⃣ **处理错误：查看详细信息**

如果请求被拒绝（403），错误消息会告诉你：
- 不允许的模型名称
- **允许的模型列表**
- **调用 `/v1/models` 的建议**

```json
{
  "detail": "Token not allowed to use model 'deepseek-v4-pro'. Allowed models: glm-5.2. Call GET /v1/models to list available models."
}
```

---

## 代码示例

### TypeScript / JavaScript

```typescript
// 初始化：获取可用模型
async function initializeModels(baseUrl: string, token: string): Promise<string[]> {
  const response = await fetch(`${baseUrl}/v1/models`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  
  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.statusText}`);
  }
  
  const data = await response.json();
  const models = data.data.map((m: any) => m.id);
  
  console.log("Available models:", models);
  return models;
}

// 发送聊天请求
async function chatCompletion(
  baseUrl: string,
  token: string,
  model: string,
  messages: any[]
) {
  const response = await fetch(`${baseUrl}/v1/chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      messages,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    console.error("Error:", error.detail);
    
    // 如果是模型不允许的错误，建议重新获取模型列表
    if (response.status === 403) {
      console.log("Model not allowed. Getting available models...");
      await initializeModels(baseUrl, token);
    }
    
    throw new Error(error.detail);
  }
  
  return await response.json();
}

// 使用示例
async function main() {
  const baseUrl = "https://api.ccbot.chat";
  const token = "sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1";
  
  try {
    // 1. 初始化：获取可用模型
    const models = await initializeModels(baseUrl, token);
    
    if (models.length === 0) {
      console.error("No models available for this token!");
      return;
    }
    
    // 2. 使用第一个可用模型
    const model = models[0];
    
    // 3. 发送请求
    const response = await chatCompletion(baseUrl, token, model, [
      { role: "user", content: "Hello!" },
    ]);
    
    console.log("Response:", response);
  } catch (error) {
    console.error("Error:", error);
  }
}

main();
```

### Python

```python
import httpx
import json

def get_available_models(base_url: str, token: str) -> list[str]:
    """Get models available for this token."""
    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.get(f"{base_url}/v1/models", headers=headers)
    response.raise_for_status()
    data = response.json()
    return [m["id"] for m in data["data"]]

def chat_completion(
    base_url: str,
    token: str,
    model: str,
    messages: list[dict]
) -> dict:
    """Send a chat completion request."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    response = httpx.post(
        f"{base_url}/v1/chat/completions",
        json={"model": model, "messages": messages},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()

# Usage example
if __name__ == "__main__":
    base_url = "https://api.ccbot.chat"
    token = "sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1"
    
    try:
        # 1. Get available models
        models = get_available_models(base_url, token)
        print(f"Available models: {models}")
        
        if not models:
            print("No models available for this token!")
            exit(1)
        
        # 2. Use the first available model
        model = models[0]
        
        # 3. Send chat request
        response = chat_completion(
            base_url,
            token,
            model,
            [{"role": "user", "content": "Hello!"}],
        )
        
        print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Error: {e}")
```

### cURL

```bash
# 1. Get available models
curl -X GET "https://api.ccbot.chat/v1/models" \
  -H "Authorization: Bearer sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1"

# 2. Extract model name and send chat request
curl -X POST "https://api.ccbot.chat/v1/chat/completions" \
  -H "Authorization: Bearer sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5.2",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

---

## 关键要点

### ✅ 应该做

1. **初始化时调用 `/v1/models`**
   - 获取该 token 允许的完整模型列表
   - 缓存这个列表以供后续使用

2. **在 UI 中仅显示允许的模型**
   - 不要硬编码模型列表
   - 动态使用 `/v1/models` 的返回值

3. **处理 403 错误**
   - 如果收到"不允许的模型"错误，提示用户
   - 建议用户调用 `/v1/models` 查看允许的模型

### ❌ 不应该做

1. **盲目尝试所有已知模型**
   - 这会产生大量 403 错误
   - 降低用户体验

2. **硬编码模型列表**
   - 模型列表可能变更
   - 不同 token 的权限不同

3. **忽略权限限制**
   - Token 权限是有意设置的
   - 应该尊重这些限制

---

## 权限检查流程

```
前端请求
    ↓
[Token 有效性检查]
    ↓
[Token 模型权限检查]
    ├─ ✅ 模型在允许列表中 → 处理请求
    ├─ ❌ 模型不在允许列表中 → 403 Forbidden
    │                        (返回允许的模型列表)
    └─ ❌ 无 model 参数 → 400 Bad Request
                        (建议调用 /v1/models)
```

---

## 测试 Token 权限

```python
import httpx

def test_token_permissions(base_url: str, token: str):
    """Test what models are available for a token."""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get available models
    response = httpx.get(f"{base_url}/v1/models", headers=headers)
    models = [m["id"] for m in response.json()["data"]]
    print(f"Available models: {models}")
    
    # Try unauthorized model
    try:
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            json={"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "test"}]},
            headers=headers,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"Unauthorized model error: {e.response.json()['detail']}")

# Test
test_token_permissions("https://api.ccbot.chat", "sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1")
```

---

## 常见问题

### Q: 为什么我的 token 只能使用一个模型？
**A:** Token 的权限由管理员在后端配置。不同的 token 可能有不同的权限限制。调用 `/v1/models` 可以查看该 token 的确切权限。

### Q: 如何请求增加 token 的模型权限？
**A:** 联系系统管理员。他们可以编辑 token 的 `models` 字段来添加更多模型。

### Q: 如果 `/v1/models` 返回空列表怎么办？
**A:** 这表示该 token 没有被授予任何模型的访问权限。联系管理员为 token 配置权限。

### Q: 可以使用 `model="auto"` 吗？
**A:** 可以，`model="auto"` 会自动选择最便宜的允许模型。但建议前端先调用 `/v1/models` 让用户选择。

---

## 总结

```
前端智能体的正确姿势：
1. 初始化时 → GET /v1/models 获取可用模型
2. 显示模型列表 → 仅显示获取到的模型
3. 发送请求 → 使用用户选择的模型
4. 处理错误 → 看错误消息中的提示重新获取模型列表

这样既能避免权限错误，也能给用户最好的体验！
```
