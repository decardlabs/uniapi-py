# DeepSeek API 接入参考手册

> 版本：2026-06-18 | 基于官方文档 [api-docs.deepseek.com](https://api-docs.deepseek.com/)

---

## 一、Base URL & 端点

| 协议 | Base URL | 说明 |
|------|----------|------|
| **OpenAI 兼容** | `https://api.deepseek.com` | Chat Completions 端点 `/chat/completions` |
| **Anthropic 兼容** | `https://api.deepseek.com/anthropic` | Messages 端点 `/v1/messages` |

### 认证方式

```
Authorization: Bearer <YOUR_DEEPSEEK_API_KEY>
```

API Key 申请：[https://platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys)

---

## 二、模型清单

| 模型 ID | 定位 | 上下文 | 最大输出 | 思考模式 | Tool Calls | JSON Mode | FIM |
|---------|------|--------|---------|---------|-----------|-----------|-----|
| `deepseek-v4-pro` | 旗舰推理 | 1M | 384K | 支持 | ✅ | ✅ | 非思考模式 |
| `deepseek-v4-flash` | 极速低价 | 1M | 384K | 支持（默认） | ✅ | ✅ | 非思考模式 |

> ⚠️ `deepseek-chat` 与 `deepseek-reasoner` 将于 **2026/07/24** 弃用，分别对应 v4-flash 的非思考与思考模式。

---

## 三、价格表

单位：**元 / 百万 tokens**

| 模型 | 缓存命中 | 缓存未命中（输入） | 输出 |
|------|---------|-----------------|------|
| **deepseek-v4-flash** | ¥0.02 | ¥1.00 | ¥2.00 |
| **deepseek-v4-pro** | ¥0.025 | ¥3.00 | ¥6.00 |

> 扣费顺序：先扣赠送余额，再扣充值余额。

### 价格优势对比（以 ¥/百万 tokens 输入计）

| 厂商 | 旗舰模型 | 输入 | 输出 |
|------|---------|------|------|
| **DeepSeek** | V4-Pro | ¥3 | ¥6 |
| 智谱 | GLM-5.1 | ¥10.1 | ¥31.7 |
| Anthropic | Claude Opus 4.6 | ¥108 | ¥540 |
| OpenAI | GPT-4o | ¥18 | ¥72 |

DeepSeek V4-Pro 输入价格仅为 Claude Opus 的 **~3%**。

---

## 四、速率限制

| 模型 | 并发限制 |
|------|---------|
| **deepseek-v4-pro** | 500 |
| **deepseek-v4-flash** | 2500 |

- 并发以**账号**维度计，与 API Key 数量无关
- 超过并发限制返回 HTTP 429
- 需更高并发可提交[扩容工单](https://trtgsjkv6r.feishu.cn/share/base/form/shrcnda9jNKvhyYv8rBb843xLEzc)，扩容免费

### user_id 隔离（提升并发后生效）

| user_id | V4-Pro 并发 | V4-Flash 并发 |
|---------|------------|--------------|
| 每个 user_id | 500 | 2500 |

`user_id` 格式：`[a-zA-Z0-9\-_]+`，最大 512 字符。OpenAI 接口放入 `extra_body`，Anthropic 接口放入 `metadata.user_id`。

---

## 五、协议兼容性详情

### 5.1 Anthropic 兼容端点

**环境变量配置：**
```bash
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_API_KEY=<your_deepseek_api_key>
```

**模型映射（自动）：**

| 传入模型名 | 映射到 |
|-----------|--------|
| `claude-opus-*` | `deepseek-v4-pro` |
| `claude-sonnet-*` / `claude-haiku-*` | `deepseek-v4-flash` |
| 其他不支持的模型名 | `deepseek-v4-flash` |

**字段支持矩阵：**

| 字段 | 状态 | 备注 |
|------|------|------|
| `model` | ✅ 完全支持 | 使用 DeepSeek 模型名 |
| `max_tokens` | ✅ 完全支持 | |
| `temperature` | ✅ 完全支持 | 范围 [0.0 ~ 2.0] |
| `top_p` | ✅ 完全支持 | |
| `top_k` | ❌ 忽略 | |
| `stop_sequences` | ✅ 完全支持 | |
| `system` | ✅ 完全支持 | |
| `stream` | ✅ 完全支持 | |
| `thinking` | ⚠️ 部分支持 | `budget_tokens` 被忽略 |
| `tools` (name/description/input_schema) | ✅ 完全支持 | |
| `tools.cache_control` | ❌ 忽略 | |
| `tool_choice` (auto/any/tool/none) | ✅ 完全支持 | `disable_parallel_tool_use` 被忽略 |
| `metadata.user_id` | ✅ 支持 | |
| `metadata`（其他字段） | ❌ 忽略 | |
| `anthropic-beta` | ❌ 忽略 | |
| `anthropic-version` | ❌ 忽略 | |
| `mcp_servers` | ❌ 忽略 | |
| `container` | ❌ 忽略 | |
| `service_tier` | ❌ 忽略 | |

**Message Content 支持：**

| 类型 | 状态 |
|------|------|
| `text` | ✅ 完全支持 |
| `image` | ❌ 不支持 |
| `document` | ❌ 不支持 |
| `thinking` | ✅ 支持 |
| `redacted_thinking` | ❌ 不支持 |
| `tool_use` | ✅ 完全支持 |
| `tool_result` | ✅ 完全支持（`is_error` 被忽略） |
| `server_tool_use` | ✅ 支持 |
| `web_search_tool_result` | ✅ 支持 |
| `code_execution_tool_result` | ❌ 不支持 |
| `mcp_tool_use` / `mcp_tool_result` | ❌ 不支持 |
| `search_result` | ❌ 不支持 |
| `container_upload` | ❌ 不支持 |

### 5.2 OpenAI 兼容端点

```bash
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_API_KEY=<your_deepseek_api_key>
```

支持标准 Chat Completions API，`thinking` 参数通过 `extra_body` 传递：

```python
response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[...],
    extra_body={"thinking": {"type": "enabled"}}
)
```

---

## 六、主流编程智能体接入

### 6.1 Claude Code

```bash
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=<your_deepseek_api_key>
export ANTHROPIC_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
export CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash
export CLAUDE_CODE_EFFORT_LEVEL=max
```

- `[1m]` 后缀启用 1M 上下文窗口
- DeepSeek 原生支持 Claude Code 的 Web Search 功能（会产生额外 Token 费用）
- 子智能体用 v4-flash 节省成本

### 6.2 Codex CLI

Codex 使用 OpenAI Responses API，DeepSeek **尚未原生支持**。推荐方案：
- 使用 [CC-Switch](https://github.com/cc-switch/cc-switch) 中转
- 或限制 Codex 走 Chat Completions 兼容模式
- 或通过阿里云百炼 Anthropic 端点间接接入

### 6.3 Cursor

```json
{
  "openaiBaseUrl": "https://api.deepseek.com/v1",
  "openaiKey": "<your_api_key>",
  "model": "deepseek-v4-pro"
}
```

注意 Cursor 的 OpenAI 端点需加 `/v1` 后缀。

---

## 七、请求保活机制

- **非流式请求**：持续返回空行
- **流式请求**：持续返回 SSE keep-alive 注释（`: keep-alive`）
- 等待超时：**10 分钟**未开始推理则关闭连接
- 解析 HTTP 响应时需处理空行和 keep-alive 注释

---

## 八、关键链接

| 项目 | 地址 |
|------|------|
| 官方文档 | [https://api-docs.deepseek.com/](https://api-docs.deepseek.com/) |
| API Key 管理 | [https://platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) |
| 用量监控 | [https://platform.deepseek.com/usage](https://platform.deepseek.com/usage) |
| 充值 | [https://platform.deepseek.com/top_up](https://platform.deepseek.com/top_up) |
| 扩容申请 | [工单链接](https://trtgsjkv6r.feishu.cn/share/base/form/shrcnda9jNKvhyYv8rBb843xLEzc) |

---

## 九、快速调用示例

### OpenAI SDK (Python)

```python
from openai import OpenAI

client = OpenAI(
    api_key="<your_api_key>",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    extra_body={"thinking": {"type": "enabled"}},
    stream=False
)

print(response.choices[0].message.content)
```

### Anthropic SDK (Python)

```python
import anthropic

client = anthropic.Anthropic(
    api_key="<your_api_key>",
    base_url="https://api.deepseek.com/anthropic"
)

message = client.messages.create(
    model="deepseek-v4-pro",
    max_tokens=4096,
    system="You are a helpful assistant.",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(message.content[0].text)
```

### cURL

```bash
# OpenAI 格式
curl https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'

# Anthropic 格式
curl https://api.deepseek.com/anthropic/v1/messages \
  -H "x-api-key: $DEEPSEEK_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "deepseek-v4-pro",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 十、注意事项

1. **模型名即将变更**：`deepseek-chat` / `deepseek-reasoner` 于 2026/07/24 弃用，尽快迁移到 v4-flash / v4-pro
2. **不支持多模态**：图片、文档输入暂不支持，仅文本
3. **Anthropic 端点模型映射**：传入不支持的模型名会被自动映射到 v4-flash，可能造成预期外行为
4. **thinking.budget_tokens 被忽略**：无法精细化控制思考 Token 量
5. **并发限制以账号为单位**：多 Key 不增加并发，需要扩容走工单
6. **user_id 格式限制**：仅支持 `[a-zA-Z0-9\-_]+`，最大 512 字符
7. **缓存命中极便宜**：¥0.02/百万 tokens，鼓励复用上下文
8. **Web Search 额外计费**：Claude Code 中使用会产生额外 API 请求费

---

*手册基于 2026-06-18 官方文档生成，价格和功能可能变动，请以 [api-docs.deepseek.com](https://api-docs.deepseek.com/) 为准。*
