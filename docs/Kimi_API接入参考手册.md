# Kimi（月之暗面 Moonshot AI）API 接入参考手册

> 来源：Kimi 开放平台官方文档，2026-06-18 更新
> 文档地址：https://platform.kimi.com/docs/

---

## 一、基本信息

| 项目 | 内容 |
|------|------|
| **厂商** | 月之暗面（Moonshot AI） |
| **平台名** | Kimi 开放平台 |
| **官方文档** | https://platform.kimi.com/docs/ |
| **API Key 申请** | https://platform.kimi.com/console/api-keys |
| **用量与账单** | https://platform.kimi.com/console |
| **开发工作台** | https://platform.kimi.com/playground |
| **费用控制** | 免费额度 + 按量付费，需充值 |

---

## 二、Base URL（双协议端点）

### 2.1 OpenAI 兼容端点

```
https://api.moonshot.cn/v1
```

- 完全兼容 OpenAI Chat Completions API（`/v1/chat/completions`）
- 认证方式：`Authorization: Bearer <MOONSHOT_API_KEY>`
- 支持流式（SSE）、Function Calling、JSON Mode、Partial Mode

### 2.2 Anthropic 兼容端点

```
https://api.moonshot.cn/anthropic
```

- 兼容 Anthropic Messages API（`/v1/messages`）
- 认证方式：`x-api-key: <MOONSHOT_API_KEY>` + `anthropic-version: 2023-06-01`（或 `Authorization: Bearer <KEY>`）
- 支持流式（SSE）、Tool Use、Thinking

> ⚠️ **注意**：两个端点的认证头格式略有差异。
> - OpenAI 端：Header `Authorization: Bearer <KEY>`，Base `api.moonshot.cn/v1`
> - Anthropic 端：Header `x-api-key: <KEY>`（也兼容 `Authorization: Bearer`），Base `api.moonshot.cn/anthropic`

### 2.3 环境变量配置速查

```bash
# OpenAI 兼容
export MOONSHOT_API_KEY="sk-xxxxxxxxxxxxxxxx"
export OPENAI_API_KEY="$MOONSHOT_API_KEY"
export OPENAI_BASE_URL="https://api.moonshot.cn/v1"

# Anthropic 兼容（Claude Code / Codex 等）
export ANTHROPIC_API_KEY="$MOONSHOT_API_KEY"
export ANTHROPIC_BASE_URL="https://api.moonshot.cn/anthropic"
export ANTHROPIC_MODEL="kimi-k2.7-code"
export ANTHROPIC_SMALL_FAST_MODEL="kimi-k2.6"
```

---

## 三、模型列表

### 3.1 主力模型

| 模型 ID | 定位 | 上下文 | 多模态 | 思考 | Function Call | JSON Mode |
|---------|------|--------|:---:|:---:|:---:|:---:|
| `kimi-k2.7-code` | 🔴 最强编码 | 256K | 图/视频 | ✅ 始终开启 | ✅ | ✅ |
| `kimi-k2.7-code-highspeed` | 🔴 编码高速版 | 256K | 图/视频 | ✅ 始终开启 | ✅ | ✅ |
| `kimi-k2.6` | 🔴 最新旗舰 | 256K | 图/视频 | ✅ 可控 | ✅ | ✅ |
| `kimi-k2.5` | 🟡 均衡多模态 | 256K | 图/视频 | ✅ 可控 | ✅ | ✅ |
| `kimi-k2` | 🟡 上代旗舰 | 256K | 图/视频 | ✅ | ✅ | ✅ |

### 3.2 模型定位速览

| 模型 | 核心优势 | 适用场景 |
|------|---------|---------|
| `kimi-k2.7-code` | 最强代码能力，长程指令遵循 | Claude Code / Codex 主力，复杂编程任务 |
| `kimi-k2.7-code-highspeed` | 同 k2.7-code，输出 180-260 TPS | 对速度敏感的编程场景 |
| `kimi-k2.6` | 多模态 + 高性能推理 | 需要图片/视频理解的编程任务 |
| `kimi-k2.5` | 性价比最高 | 日常编程，成本敏感场景 |

### 3.3 模型能力矩阵

| 能力 | k2.7-code | k2.7-code-hs | k2.6 | k2.5 |
|------|:---:|:---:|:---:|:---:|
| 文本生成 | ✅ | ✅ | ✅ | ✅ |
| 图片输入 | ✅ | ✅ | ✅ | ✅ |
| 视频输入 | ✅ | ✅ | ✅ | ✅ |
| 思考模式 | 始终开启 | 始终开启 | 可控 | 可控 |
| Tool Calling | ✅ | ✅ | ✅ | ✅ |
| JSON Mode | ✅ | ✅ | ✅ | ✅ |
| Partial Mode | ✅ | ✅ | ✅ | ✅ |
| 联网搜索 | ✅ | ✅ | ✅ | ✅ |
| 上下文缓存 | ✅ | ✅ | ✅ | ✅ |

> ⚠️ **k2.7-code 的思考模式注意**：始终开启，不支持 `"type": "disabled"`。这与 k2.6 不同——k2.6 可以通过 `thinking` 参数关闭思考。

---

## 四、定价表（元/百万 Tokens）

### 4.1 完整定价

| 模型 ID | 输入（缓存命中） | 输入（缓存未命中） | 输出 |
|---------|:---:|:---:|:---:|
| `kimi-k2.7-code` | ¥1.30 | ¥6.50 | ¥27.00 |
| `kimi-k2.7-code-highspeed` | ¥2.60 | ¥13.00 | ¥54.00 |
| `kimi-k2.6` | ¥1.10 | ¥6.50 | ¥27.00 |
| `kimi-k2.5` | ¥0.70 | ¥4.00 | ¥21.00 |

### 4.2 上下文缓存说明

Kimi 自动启用上下文缓存，无需显式配置 `cache_control`。缓存对编程智能体极其有效——长时间会话中，大部分输入 Token 都会命中缓存。

对于 Claude Code / Codex 等编程工具，建议使用 `prompt_cache_key` 参数指定会话 ID，提高缓存命中率。

### 4.3 费用示例

| 场景 | 模型 | 输入 Token | 输出 Token | 缓存命中占比 | 预估费用 |
|------|------|-----------|-----------|:---:|------|
| Claude Code 单次对话 | `kimi-k2.7-code` | 30K | 5K | 80% | ¥0.05 + ¥0.14 = **¥0.19** |
| Claude Code 长对话 | `kimi-k2.7-code` | 80K | 10K | 90% | ¥0.08 + ¥0.27 = **¥0.35** |
| Codex 重度编码 | `kimi-k2.7-code` | 150K | 30K | 70% | ¥0.43 + ¥0.81 = **¥1.24** |
| 日常编码（省钱） | `kimi-k2.5` | 50K | 8K | 80% | ¥0.10 + ¥0.17 = **¥0.27** |
| 图片理解 | `kimi-k2.6` | 100K | 5K | 50% | ¥0.37 + ¥0.14 = **¥0.51** |

### 4.4 每月用量推演（k2.7-code 主力）

| 用户类型 | 日均调用 | 月费用 |
|---------|---------|--------|
| 轻度编程（偶尔用） | 10 次 | ~¥60 |
| 中度编程（日常工作） | 40 次 | ~¥240 |
| 重度编程（整天用） | 80 次 | ~¥480 |
| 极限编程（不停歇） | 150 次 | ~¥900 |

> 💡 **省钱策略**：日常简单任务用 `kimi-k2.5`，复杂编码任务切 `kimi-k2.7-code`。缓存命中可节省 80%+ 输入成本。

---

## 五、速率限制

> Kimi 速率限制信息详见控制台：https://platform.kimi.com/console/access

| 等级 | 说明 |
|------|------|
| **新用户** | 有限速率，需充值提升 |
| **已充值用户** | RPM/TPM 随充值金额提升 |
| **高消费用户** | 可联系商务提升限流 |

> ⚠️ Kimi 对并发较敏感。高频调用建议客户端实现重试机制（指数退避 + jitter）。

---

## 六、协议兼容性细节

### 6.1 OpenAI Chat Completions 兼容

| 特性 | 支持状态 | 说明 |
|------|:---:|------|
| `messages` | ✅ | 标准格式。`content` 支持 string 或 `[{type: "text/image_url/video_url"}]` |
| `stream` (SSE) | ✅ | `data: [DONE]` 结尾 |
| `temperature` | ✅ | 支持 |
| `max_completion_tokens` | ✅ | 推荐使用，替代已弃用的 `max_tokens` |
| `stop` | ✅ | 最多 5 个，每个 ≤ 32 字节 |
| `tools` / `tool_choice` | ✅ | 最多 128 个工具 |
| `response_format` | ✅ | `json_object` / `json_schema` |
| `thinking` | ✅ | `{"type": "enabled/disabled", "keep": "all"}` |
| `prompt_cache_key` | ✅ | Kimi 特有，强烈推荐设置以提升缓存命中率 |
| `safety_identifier` | ✅ | 用户标识哈希，用于内容安全 |
| `partial` | ✅ | Kimi 特有的 Partial Mode |
| `seed` | ❌ | 不支持 |
| `n` | ❌ | 不支持 |

### 6.2 Anthropic Messages 兼容

| 特性 | 支持状态 | 说明 |
|------|:---:|------|
| `messages` | ✅ | 标准 Anthropic 格式 |
| `stream` (SSE) | ✅ | 完整流式支持 |
| `system` | ✅ | 系统提示词 |
| `tools` / `tool_choice` | ✅ | Tool Use |
| `temperature` | ✅ | 支持 |
| `top_p` | ✅ | 支持 |
| `max_tokens` | ✅ | 最大输出 |
| `stop_sequences` | ✅ | 停用序列 |
| `thinking` | ✅ | k2.6/k2.5 可控；k2.7-code 始终开启 |
| `cache_control` | ✅ | 显式缓存 |
| MCP 协议 | ✅ | 通过工具调用 |
| 多模态输入 | ✅ | 支持图片/视频（通过 Anthropic 多模态格式） |

### 6.3 k2.7-code thinking 行为差异

```
k2.7-code:
  thinking: {"type": "enabled"}   // ✅ 仅支持 enabled，传 disabled 报错
  thinking: {"keep": "all"}        // ✅ 始终保留所有轮次的 reasoning_content

k2.6 / k2.5:
  thinking: {"type": "enabled"}    // ✅ 支持
  thinking: {"type": "disabled"}   // ✅ 支持关闭思考
  thinking: {"keep": "all"}        // ✅ 保留 reasoning_content
```

### 6.4 编程智能体接入速查

| 工具 | 协议端点 | Base URL | 模型名 |
|------|---------|---------|--------|
| **Claude Code** | Anthropic | `api.moonshot.cn/anthropic` | `kimi-k2.7-code` / `kimi-k2.6` |
| **Codex CLI** | OpenAI | `api.moonshot.cn/v1` | `kimi-k2.7-code` / `kimi-k2.6` |
| **Cursor** | OpenAI | `api.moonshot.cn/v1` | `kimi-k2.7-code` |
| **Windsurf** | OpenAI | `api.moonshot.cn/v1` | `kimi-k2.7-code` |

### 6.5 Claude Code 配置示例

```json
// ~/.claude/settings.json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-xxxxxxxxxxxxxxxx",
    "ANTHROPIC_BASE_URL": "https://api.moonshot.cn/anthropic",
    "ANTHROPIC_MODEL": "kimi-k2.7-code",
    "ANTHROPIC_SMALL_FAST_MODEL": "kimi-k2.6"
  }
}
```

### 6.6 Codex CLI 配置示例

```toml
# ~/.codex/config.toml
[model_providers.kimi]
name = "Kimi"
base_url = "https://api.moonshot.cn/v1"
api_key = "sk-xxxxxxxxxxxxxxxx"

[model_providers.kimi.models.default]
id = "kimi-k2.7-code"

[model_providers.kimi.models.small]
id = "kimi-k2.6"
```

---

## 七、调用注意事项

1. **双域名双认证**：OpenAI 端（`api.moonshot.cn`）和 Anthropic 端（`api.kimi.com`）使用不同的域名和认证头格式——中转站需要分别处理。
2. **k2.7-code 始终开启思考**：`thinking: {type: "disabled"}` 会直接报错。如果不需要思考模式，用 `kimi-k2.6`。
3. **缓存优化至关重要**：`prompt_cache_key` 参数对编程工具极有价值——设置为会话 ID，缓存命中率可达 80-90%，成本降 80%。
4. **思考 Token 包含在输出中**：开启 thinking 时，输出 Token 包含 `reasoning_content` + 回答内容，两者都按输出价计费。
5. **多模态真的能用**：Kimi 是少数支持图片/视频输入且编程能力强的国产模型，适合需要分析截图、UI 稿的编程场景。
6. **highspeed 版慎用**：价格是标准版的 2 倍，仅在对延迟极度敏感时使用。
7. **Partial Mode**：Kimi 特有的半增量输出模式，适合流式交互场景。传统对话不需要关心。
8. **max_tokens 已弃用**：Kimi 推荐使用 `max_completion_tokens`，`max_tokens` 已标记弃用。

---

## 八、特色能力

### 8.1 联网搜索

Kimi 内置联网搜索工具，可通过 Tool Calling 调用。适合需要实时信息的编程场景。

### 8.2 多模态输入

```python
# 图片 + 文本输入示例
from openai import OpenAI

client = OpenAI(
    api_key="sk-xxx",
    base_url="https://api.moonshot.cn/v1",
)

response = client.chat.completions.create(
    model="kimi-k2.7-code",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "分析这个 UI 截图中的布局问题"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        ]
    }]
)
```

### 8.3 Preserved Thinking（k2.7-code）

k2.7-code 在多轮对话中保留所有历史轮次的 `reasoning_content`，让模型能"回忆"之前的思考链。这对长程编程任务的理解一致性极其重要。

---

## 九、选模建议

| 场景 | 推荐模型 | 预估单价 |
|------|---------|---------|
| **编程智能体主力** | `kimi-k2.7-code` | ~¥0.19-0.35/次 |
| **需要多模态的编程** | `kimi-k2.6` | ~¥0.30-0.50/次 |
| **日常编码（省钱）** | `kimi-k2.5` | ~¥0.15-0.27/次 |
| **高速编码（不差钱）** | `kimi-k2.7-code-highspeed` | ~¥0.38-0.70/次 |
| **极限省钱（仍可靠）** | `kimi-k2.5` + 缓存优化 | ~¥0.10/次 |

> 💡 **主推策略**：`kimi-k2.7-code` 作为默认编码模型。它是目前 Kimi 最强的编程模型，k2.5 作为省钱备选。

---

## 十、促销活动

> 详见：https://platform.kimi.com/docs/pricing/promotion

Kimi 不定期推出充值优惠活动，新用户首充常有额外赠送。建议关注控制台公告。

---

*手册生成日期：2026-06-18*
*数据来源：Kimi 开放平台官方文档 https://platform.kimi.com/docs/*
*价格可能随时调整，请以官网为准*
