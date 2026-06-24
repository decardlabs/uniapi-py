# CCBot API 中转站接入参考手册

> 版本：2026-06-24 | 基于 [uniapi-py](https://github.com/sunm15/uniapi-py) 网关部署实例

---

## 一、概述

CCBot 是一个 **统一 AI API 中转站**，聚合多家主流 LLM 提供商，对外暴露标准的 OpenAI / Anthropic 兼容接口。只需一个 API Token，即可在多种智能体工具间切换使用不同提供商的模型。

### 支持的提供商

| 提供商 | 渠道 | 协议支持 |
|--------|------|---------|
| **DeepSeek** | `deepseek` | OpenAI Chat / Anthropic Messages |
| **GLM（智谱）** | `glm` | OpenAI Chat |
| **Qwen（阿里百炼）** | `qwen` | OpenAI Chat / Anthropic Messages |
| **Kimi（月之暗面）** | `kimi` | OpenAI Chat / Anthropic Messages |
| **MiniMax** | `minimax` | OpenAI Chat / Anthropic Messages |

### 核心特性

- **统一认证**：一个 Token 访问所有模型
- **自动格式转换**：Anthropic Messages ↔ OpenAI Chat 自动互转
- **智能路由**：加权随机 + 429 回退 + 5xx 自动容错
- **SSE 流式**：完整支持流式输出
- **用量透明**：`GET /v1/models` 实时查看可用模型
- **Token 模型白名单**：支持为 Token 限定可用的模型列表

---

## 二、Base URL & 认证

### Base URL

```
https://api.ccbot.chat/v1
```

### 认证方式

中转站使用 **Token Key** 认证，支持两种传参方式：

**方式一：OpenAI 风格（Authorization Header）**
```
Authorization: Bearer <your_token_key>
```

**方式二：Anthropic 风格（x-api-key Header）**
```
x-api-key: <your_token_key>
```

> 两种方式等价，视工具支持的配置而定。

### Token 获取

在管理员后台用户管理页面生成 Access Token，每个用户可创建多个 Token。

### 高级：Channel Pinning

如需将请求固定到特定渠道（适用于渠道级调试），Token Key 后可附加 `:channel_id`：

```
Authorization: Bearer <your_token_key>:1
```

---

## 三、Endpoints 速查

| 端点 | 方法 | 说明 | 兼容格式 |
|------|------|------|---------|
| `/v1/chat/completions` | POST | OpenAI Chat 补全 | OpenAI SDK 通用 |
| `/v1/messages` | POST | Anthropic Messages | Anthropic SDK（Claude Code 等） |
| `/v1/responses` | POST | OpenAI Responses API | OpenAI Responses |
| `/v1/models` | GET | 列出可用模型 | OpenAI 兼容格式 |

### 端点调用示例

**cURL — Chat Completions：**
```bash
curl -X POST "https://api.ccbot.chat/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token_key>" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

**cURL — 列出可用模型：**
```bash
curl -s "https://api.ccbot.chat/v1/models" \
  -H "Authorization: Bearer <your_token_key>" | jq '.data[].id'
```

**Python — OpenAI SDK：**
```python
from openai import OpenAI

client = OpenAI(
    api_key="<your_token_key>",
    base_url="https://api.ccbot.chat/v1"
)

response = client.chat.completions.create(
    model="qwen3.7-plus",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.choices[0].message.content)
```

**Python — Anthropic SDK：**
```python
import anthropic

client = anthropic.Anthropic(
    api_key="<your_token_key>",
    base_url="https://api.ccbot.chat"
)

message = client.messages.create(
    model="deepseek-v4-flash",
    max_tokens=4096,
    messages=[{"role": "user", "content": "你好"}]
)
print(message.content[0].text)
```

---

## 四、可用模型清单

所有模型 ID 统一通过 `GET /v1/models` 查询。以下为当前支持的模型汇总：

### 4.1 DeepSeek

| 模型 ID | 上下文 | 输入 ¥/百万tokens | 输出 ¥/百万tokens | 缓存输入 |
|---------|--------|-------------------|-------------------|---------|
| `deepseek-v4-pro` | 384K | ¥3.0 | ¥6.0 | ¥0.025 |
| `deepseek-v4-flash` | 384K | ¥1.0 | ¥2.0 | ¥0.020 |

DeepSeek 原生支持 Anthropic Messages 协议，推荐用于 Claude Code。

### 4.2 GLM（智谱）

| 模型 ID | 上下文 | 输入 ¥ | 输出 ¥ | 说明 |
|---------|--------|--------|--------|------|
| `glm-5.2` | 131K | **免费** | **免费** | 🆕 最强旗舰，限免 |
| `glm-5.1` | 131K | ¥10.1 | ¥31.7 | 高智能基座 |
| `glm-5` | 131K | ¥7.2 | ¥23.0 | 强推理旗舰 |
| `glm-4.7` | 131K | ¥4.3 | ¥15.8 | 性价比编程首选 |
| `glm-4.5-air` | 131K | ¥1.4 | ¥7.9 | 经济之选 |
| `glm-4.7-flash` | 131K | **免费** | **免费** | 🆓 零成本 |
| `glm-z1-flash` | 131K | **免费** | **免费** | 🆓 推理模型免费版 |

GLM 仅原生支持 OpenAI Chat 协议。走 Anthropic Messages 端点时由网关自动格式转换。

### 4.3 Qwen（阿里百炼）

| 模型 ID | 上下文 | 输入 ¥ | 输出 ¥ | 缓存输入 |
|---------|--------|--------|--------|---------|
| `qwen3.7-max` | 128K | ¥12.0 | ¥36.0 | ¥2.4 |
| `qwen3.7-plus` | 128K | ¥2.0 | ¥8.0 | ¥0.4 |
| `qwen3.6-plus` | 128K | ¥2.0 | ¥12.0 | ¥0.4 |
| `qwen3.6-flash` | 128K | ¥0.5 | ¥2.0 | ¥0.1 |
| `qwen3.5-plus` | 128K | ¥0.8 | ¥4.8 | ¥0.16 |
| `qwen3.5-flash` | 128K | ¥0.35 | ¥1.4 | ¥0.07 |
| `qwen3-coder-plus` | 128K | ¥7.34 | ¥36.7 | ¥1.47 |
| `qwen3-coder-flash` | 128K | ¥2.0 | ¥8.0 | ¥0.4 |
| `qwen-turbo` | 128K | ¥0.3 | ¥1.2 | ¥0.06 |

### 4.4 Kimi（月之暗面）

| 模型 ID | 上下文 | 输入 ¥ | 输出 ¥ | 缓存输入 |
|---------|--------|--------|--------|---------|
| `kimi-k2.7-code` | 256K | ¥6.5 | ¥27.0 | ¥1.3 |
| `kimi-k2.7-code-highspeed` | 256K | ¥13.0 | ¥54.0 | ¥2.6 |
| `kimi-k2.6` | 256K | ¥6.5 | ¥27.0 | ¥1.1 |
| `kimi-k2.5` | 256K | ¥4.0 | ¥21.0 | ¥0.7 |
| `kimi-k2` | 256K | ¥2.0 | ¥10.0 | ¥0.4 |

### 4.5 MiniMax

| 模型 ID | 上下文 | 输入 ¥ | 输出 ¥ | 缓存输入 |
|---------|--------|--------|--------|---------|
| `MiniMax-M3` | 128K | ¥2.16 | ¥8.64 | ¥0.43 |
| `MiniMax-M2.7` | 128K | ¥2.16 | ¥8.64 | ¥0.43 |
| `MiniMax-M2.7-highspeed` | 128K | ¥4.32 | ¥17.28 | ¥0.43 |
| `MiniMax-M2.5` | 128K | ¥2.16 | ¥8.64 | ¥0.22 |
| `MiniMax-M2.5-highspeed` | 128K | ¥4.32 | ¥17.28 | ¥0.22 |
| `MiniMax-M2.1` | 128K | ¥2.16 | ¥8.64 | ¥0.22 |
| `MiniMax-M2.1-highspeed` | 128K | ¥4.32 | ¥17.28 | ¥0.22 |
| `MiniMax-M2` | 128K | ¥2.16 | ¥8.64 | ¥0.22 |

> **注意**：MiniMax 模型 ID 区分大小写（PascalCase），如 `MiniMax-M3`。网关会做大小写不敏感匹配，但建议使用准确的模型 ID。

### 4.6 价格速览概算

| 模型 | 输入 ¥ | 输出 ¥ | 日 100 次中等任务估算 | 月估算 |
|------|--------|--------|---------------------|--------|
| `deepseek-v4-flash` | ¥1.0 | ¥2.0 | ~¥1 | ~¥30 |
| `glm-5.2` | **免费** | **免费** | ¥0 | ¥0 |
| `glm-4.7-flash` | **免费** | **免费** | ¥0 | ¥0 |
| `qwen3.5-flash` | ¥0.35 | ¥1.4 | ~¥0.5 | ~¥15 |
| `kimi-k2` | ¥2.0 | ¥10.0 | ~¥3 | ~¥90 |
| `MiniMax-M2.5` | ¥2.16 | ¥8.64 | ~¥3 | ~¥90 |

> 估算基于每次任务平均输入 30K + 输出 3K tokens。

---

## 五、编程 IDE / 智能体工具配置

### 5.1 Claude Code

Claude Code 使用 Anthropic Messages 协议。中转站中支持该协议的有：DeepSeek、Qwen、Kimi、MiniMax。GLM 会由网关自动转换。

```bash
# 方式一：环境变量
export ANTHROPIC_BASE_URL=https://api.ccbot.chat
export ANTHROPIC_API_KEY=<your_token_key>
export ANTHROPIC_MODEL=deepseek-v4-flash
```

**模型推荐方案：**

```bash
# 主力模型用 deepseek 或 qwen
export ANTHROPIC_MODEL=deepseek-v4-pro

# 子智能体用低成本模型
export CLAUDE_CODE_SUBAGENT_MODEL=qwen3.5-flash

# 各层级映射
export ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro
export ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-flash
export ANTHROPIC_DEFAULT_HAIKU_MODEL=qwen3.5-flash
```

### 5.2 Cursor

Cursor 支持自定义 OpenAI 兼容 API。在 Cursor Settings → Models 中配置。

```json
{
  "openaiBaseUrl": "https://api.ccbot.chat/v1",
  "openaiKey": "<your_token_key>",
  "model": "deepseek-v4-flash"
}
```

**配置步骤：**
1. 打开 Cursor → Settings → Models
2. 关闭所有默认的 OpenAI/Anthropic 模型开关
3. 在 "API Key" 填入 Token Key
4. 在 "Override Base URL" 填入 `https://api.ccbot.chat/v1`
5. 在 "Model" 填入要使用的模型 ID（如 `deepseek-v4-flash`）
6. 点击 "Verify" 验证连接

### 5.3 Cline / Roo Code

Cline 默认支持自定义 API Provider。

**配置步骤：**
1. 打开 Cline → Settings → API Provider
2. 选择 "OpenAI Compatible"
3. 填入：
   - **Base URL**: `https://api.ccbot.chat/v1`
   - **API Key**: `<your_token_key>`
   - **Model ID**: `deepseek-v4-flash`（或其他模型）

### 5.4 Continue.dev

VS Code 插件 Continue.dev 支持自定义 OpenAI 兼容端点。

编辑 `~/.continue/config.json`：

```json
{
  "models": [
    {
      "title": "CCBot DeepSeek",
      "provider": "openai",
      "model": "deepseek-v4-flash",
      "apiBase": "https://api.ccbot.chat/v1",
      "apiKey": "<your_token_key>"
    },
    {
      "title": "CCBot Qwen",
      "provider": "openai",
      "model": "qwen3.7-plus",
      "apiBase": "https://api.ccbot.chat/v1",
      "apiKey": "<your_token_key>"
    },
    {
      "title": "CCBot GLM",
      "provider": "openai",
      "model": "glm-5.2",
      "apiBase": "https://api.ccbot.chat/v1",
      "apiKey": "<your_token_key>"
    }
  ],
  "tabAutocompleteModel": {
    "title": "CCBot AutoComplete",
    "provider": "openai",
    "model": "qwen3.5-flash",
    "apiBase": "https://api.ccbot.chat/v1",
    "apiKey": "<your_token_key>"
  }
}
```

### 5.5 Windsurf

Windsurf（原 Codeium）可通过配置自定义 API 端点。

编辑 `~/.codeium/windsurf.json`：

```json
{
  "models": {
    "chat": {
      "provider": "openai",
      "model": "deepseek-v4-flash",
      "apiKey": "<your_token_key>",
      "apiBase": "https://api.ccbot.chat/v1"
    }
  }
}
```

### 5.6 Aider

Aider 是命令行 AI 编程工具，支持 OpenAI 兼容 API。

```bash
# 基本用法
export OPENAI_API_BASE=https://api.ccbot.chat/v1
export OPENAI_API_KEY=<your_token_key>

aider --model openai/deepseek-v4-flash
```

```bash
# 模型映射（.aider.models.yml）
# Aider 需要为每个模型配置价格，跳过检查
aider --model openai/deepseek-v4-flash \
  --no-show-model-warnings
```

### 5.7 GitHub Copilot（自定义 API）

GitHub Copilot 在 VS Code 中支持手动指定自定义 API 端点（预览功能）。

编辑 VS Code 设置：

```json
{
  "github.copilot.advanced": {
    "debug.chat.overrideModel": "deepseek-v4-flash",
    "debug.chat.overrideApiEndpoint": "https://api.ccbot.chat/v1/chat/completions",
    "debug.chat.overrideApiKey": "<your_token_key>"
  }
}
```

> ⚠️ 此功能为实验性，不同版本 VS Code 的配置方式可能不同。

---

## 六、聊天客户端配置

### 6.1 ChatGPT-Next-Web（LobeChat / NextChat）

```env
# .env 或 Docker 环境变量
OPENAI_API_KEY=<your_token_key>
BASE_URL=https://api.ccbot.chat

# 自定义模型列表
CUSTOM_MODELS=deepseek-v4-pro|deepseek-v4-flash|glm-5.2|glm-4.7-flash|qwen3.7-max|qwen3.7-plus|kimi-k2.5
```

**Web 界面配置：**
1. 设置 → 接口地址 → `https://api.ccbot.chat/v1`
2. API Key → 填入 Token Key
3. 自定义模型列表 → 手动添加需要的模型 ID

### 6.2 Open WebUI

Open WebUI 原生支持 OpenAI 兼容端点。

```bash
# Docker 环境变量方式
docker run -d \
  -e OPENAI_API_BASE_URL=https://api.ccbot.chat/v1 \
  -e OPENAI_API_KEY=<your_token_key> \
  -p 3000:8080 \
  ghcr.io/open-webui/open-webui:main
```

**Web 界面配置：**
1. 管理员面板 → 连接设置
2. OpenAI API URL → `https://api.ccbot.chat/v1`
3. API Key → 填入 Token Key
4. 点击刷新按钮加载模型列表

### 6.3 Jan / ChatBox

**Jan**：
1. 打开 Jan → Settings → My Models
2. 选择 "OpenAI Compatible"
3. 填入：
   - **API Key**: `<your_token_key>`
   - **API URL**: `https://api.ccbot.chat/v1/chat/completions`

**ChatBox**：
1. 设置 → AI 提供商
2. 选择 "OpenAI"
3. 自定义接口 → `https://api.ccbot.chat/v1`
4. 填入 API Key
5. 手动输入模型 ID

### 6.4 Dify

Dify 支持在模型提供商中添加自定义 OpenAI 兼容模型。

**配置步骤：**
1. Dify 管理后台 → 模型提供商 → 添加模型
2. 选择 "OpenAI API Compatible"
3. 填入：
   - **API Key**: `<your_token_key>`
   - **Endpoint URL**: `https://api.ccbot.chat/v1`
   - **模型名称**: 如 `deepseek-v4-flash`
4. 验证并保存

---

## 七、模型选择建议

| 使用场景 | 推荐模型 | 理由 |
|---------|---------|------|
| 日常代码编写 | `deepseek-v4-flash` | 性价比极高，¥1.0/¥2.0 |
| 高难度编程任务 | `deepseek-v4-pro` | 强推理能力，384K 上下文 |
| 免费方案 | `glm-5.2` / `glm-4.7-flash` | 当前限时免费/永久免费 |
| 中文长对话 | `qwen3.7-plus` | 中文本土优化，¥2.0/¥8.0 |
| 编程专用模型 | `qwen3-coder-plus` | Qwen Coder 系列 |
| 超长上下文（256K） | `kimi-k2.7-code` | 256K 上下文窗口 |
| 高速响应 | `qwen3.5-flash` | ¥0.35/¥1.4，极低成本 |
| 经济版量产 | `qwen-turbo` | ¥0.3/¥1.2，最低价 |

---

## 八、模型自动选择

中转站支持 `model="auto"` 参数，自动选择当前 Token 可用的最便宜模型：

```bash
curl -X POST "https://api.ccbot.chat/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token_key>" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

> 仅当 Token 未设置模型白名单时可用，否则从指定白名单中选择最便宜的模型。

---

## 九、流式输出（SSE）

中转站完整支持 SSE 流式输出，所有协议均兼容：

```bash
curl -X POST "https://api.ccbot.chat/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token_key>" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": "讲个笑话"}],
    "stream": true
  }'
```

**Python 流式示例：**
```python
from openai import OpenAI

client = OpenAI(
    api_key="<your_token_key>",
    base_url="https://api.ccbot.chat/v1"
)

stream = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "讲个笑话"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

---

## 十、注意事项

1. **API Key 是 Token Key**：不是提供商（DeepSeek/GLM/Qwen）的原始 API Key，而是在 CCBot 后台生成的 Access Token
2. **Auth 无需 Bearer 前缀**：Token Key 本身不包含 `Bearer`，由网关的标准 HTTP Authorization 头携带
3. **GLM 限免模型真免费**：`glm-5.2` 和 `glm-4.7-flash` 当前为免费模型，不消耗配额
4. **MiniMax 模型名大小写敏感**：虽然网关会做大小写不敏感匹配，建议使用准确 PascalCase 形式
5. **429 自动重试**：网关内置指数退避（初始 10s，最大 120s）和 5xx 自动容错，客户端通常无需自行重试
6. **Channel Pinning 调试**：Token Key 后加 `:channel_id` 可将请求固定到特定渠道
7. **Token 模型白名单**：如果 Token 设置了模型白名单，`/v1/models` 和实际请求会受其限制
8. **模型列表实时查询**：`GET /v1/models` 始终返回当前可用的最新模型列表
9. **各提供商的原始费用以官方定价为准**：以上价格为 CCBot 中转站设定的标准费率
10. **缓存优惠**：DeepSeek 等支持前缀缓存的模型，缓存命中可节省大量费用

---

## 十一、快速参考

### 一行启动 Claude Code

```bash
ANTHROPIC_BASE_URL=https://api.ccbot.chat \
ANTHROPIC_API_KEY=<your_token_key> \
ANTHROPIC_MODEL=deepseek-v4-flash \
claude
```

### 一行测试连接

```bash
# 测试 Chat Completions
curl -s https://api.ccbot.chat/v1/chat/completions \
  -H "Authorization: Bearer <your_token_key>" \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hi"}]}' \
  | jq .
```

```bash
# 测试 Anthropic Messages
curl -s https://api.ccbot.chat/v1/messages \
  -H "x-api-key: <your_token_key>" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"deepseek-v4-flash","max_tokens":100,"messages":[{"role":"user","content":"hi"}]}' \
  | jq .
```

### 查看可用模型

```bash
curl -s https://api.ccbot.chat/v1/models \
  -H "Authorization: Bearer <your_token_key>" \
  | jq -r '.data[] | "\(.id) (\(.owned_by))"'
```

---

*手册基于 uniapi-py v0.11.2 代码库分析生成。模型清单和价格以网关实际配置为准，可通过 `GET /v1/models` 实时查询。*
