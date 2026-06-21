# 前端集成 - 快速参考

## 🎯 核心流程（3 步）

### 1️⃣ 获取可用模型
```bash
GET /v1/models
Header: Authorization: Bearer {token}
```
```json
{
  "data": [{"id": "glm-5.2", ...}]
}
```

### 2️⃣ 显示在 UI 中
```javascript
const models = response.data.map(m => m.id);  // ['glm-5.2']
// 在下拉菜单中显示
```

### 3️⃣ 发送请求
```bash
POST /v1/chat/completions
{
  "model": "glm-5.2",  # ← 来自第1步
  "messages": [...]
}
```

---

## 🚀 代码框架

### React + TypeScript
```tsx
function ChatInterface() {
  const [models, setModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState("");

  useEffect(() => {
    // 初始化：获取模型列表
    fetch("/v1/models", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(d => {
        const modelIds = d.data.map(m => m.id);
        setModels(modelIds);
        setSelectedModel(modelIds[0]); // 默认选第一个
      });
  }, []);

  const handleChat = async (message: string) => {
    const res = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: selectedModel,  // ← 使用获取到的模型
        messages: [{ role: "user", content: message }],
      }),
    });
    // ...
  };

  return (
    <>
      <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}>
        {models.map(m => <option key={m}>{m}</option>)}
      </select>
      {/* 聊天界面 */}
    </>
  );
}
```

### Python 智能体
```python
def init_agent(token: str):
    """初始化智能体，获取可用模型"""
    models = httpx.get(
        "https://api.ccbot.chat/v1/models",
        headers={"Authorization": f"Bearer {token}"}
    ).json()["data"]
    
    return {"models": [m["id"] for m in models]}

def send_message(token: str, model: str, message: str):
    """发送消息"""
    return httpx.post(
        "https://api.ccbot.chat/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": message}]},
        headers={"Authorization": f"Bearer {token}"}
    ).json()
```

---

## 🔍 API 参考

| 端点 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/v1/models` | GET | 列出该 token 允许的模型 | Token 鉴权 |
| `/v1/models/{model_id}` | GET | 获取单个模型详情 | Token 鉴权 |
| `/v1/chat/completions` | POST | 发送聊天请求 | Token 鉴权 + 模型权限检查 |

---

## ⚠️ 错误处理

| 状态码 | 场景 | 处理方式 |
|--------|------|---------|
| 400 | 无 model 参数 | 调用 `/v1/models` 选择模型 |
| 403 | 模型不被允许 | 错误消息会列出允许的模型 |
| 401 | Token 无效 | 检查 token 是否正确 |
| 429 | 速率限制 | 稍后重试 |

---

## 📋 检查清单

- [ ] 初始化时调用了 `/v1/models`
- [ ] UI 中仅显示返回的模型列表
- [ ] 发送请求时使用了来自 `/v1/models` 的模型名
- [ ] 处理了 403 Forbidden 错误
- [ ] Token 已正确传递到 Authorization header
- [ ] 没有硬编码模型名称

---

## 💡 最佳实践

✅ **推荐**
```javascript
// 获取模型列表，动态显示
const models = await getAvailableModels(token);
modelSelector.options = models.map(m => new Option(m, m));
```

❌ **不推荐**
```javascript
// 硬编码模型列表 - 容易过期
const MODELS = ["glm-5.2", "deepseek-v4-pro", ...];
modelSelector.options = MODELS.map(m => new Option(m, m));
```

---

## 📞 支持

如遇问题，检查：
1. Token 是否有效（能否调用 `/v1/models`）
2. 是否收到了模型权限限制的错误信息
3. 是否按照推荐流程实现

详见 [FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md)
