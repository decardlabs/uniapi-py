# Qwen（阿里云百炼）API 接入参考手册

> 来源：阿里云百炼官方文档，2026-06-18 更新
> 文档地址：https://help.aliyun.com/zh/model-studio/

---

## 一、基本信息

| 项目 | 内容 |
|------|------|
| **厂商** | 阿里云（通义千问） |
| **平台名** | 大模型服务平台百炼（Model Studio） |
| **官方文档** | https://help.aliyun.com/zh/model-studio/ |
| **API Key 申请** | https://bailian.console.aliyun.com/（控制台 → API Key 管理） |
| **模型广场** | https://bailian.console.aliyun.com/cn-beijing?tab=model#/model-market/all |
| **新人免费额度** | 开通后 90 天内 100 万 Token（各主力模型分别赠送） |

---

## 二、Base URL（双协议端点）

### 2.1 OpenAI 兼容端点

```
https://dashscope.aliyuncs.com/compatible-mode/v1
```

- 完全兼容 OpenAI Chat Completions API（`/v1/chat/completions`）
- 认证方式：`Authorization: Bearer <DASHSCOPE_API_KEY>`
- 支持流式（SSE）、Function Calling、Structured Output

### 2.2 Anthropic 兼容端点

```
https://dashscope.aliyuncs.com/apps/anthropic
```

- 兼容 Anthropic Messages API（`/v1/messages`）
- 认证方式：`x-api-key: <DASHSCOPE_API_KEY>` + `anthropic-version: 2023-06-01`
- 支持流式（SSE）、Tool Use、Thinking

### 2.3 环境变量配置速查

```bash
# OpenAI 兼容
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxx"
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"

# Anthropic 兼容（Claude Code / Codex 等）
export ANTHROPIC_API_KEY="sk-xxxxxxxxxxxxxxxx"
export ANTHROPIC_BASE_URL="https://dashscope.aliyuncs.com/apps/anthropic"
export ANTHROPIC_MODEL="qwen3.7-plus"
export ANTHROPIC_SMALL_FAST_MODEL="qwen3.6-flash"
```

> ⚠️ 百炼默认开通**北京地域**。若需其他地域（新加坡/美国/法兰克福），需在控制台开通对应地域服务，价格有所不同。

---

## 三、模型列表

### 3.1 主力模型（推荐）

| 模型 ID | 定位 | 上下文 | 最大输出 | 思考 | Function Call | Vision | Structured Output |
|---------|------|--------|----------|------|:---:|:---:|:---:|
| `qwen3.7-max` | 🔴 旗舰 Max | 1M | 64K | ✅ | ✅ | ❌ | ❌ |
| `qwen3.7-plus` | 🟡 均衡 Plus | 1M | 64K | ✅ | ✅ | ❌ | ✅ |
| `qwen3.6-flash` | 🟢 高速 Flash | 1M | 64K | ✅ | ✅ | ❌ | ✅ |
| `qwen3.5-plus` | 🟡 上代 Plus | 1M | 64K | ✅ | ✅ | ❌ | ✅ |
| `qwen3.5-flash` | 🟢 上代 Flash | 1M | 64K | ✅ | ✅ | ❌ | ✅ |

### 3.2 Coder 系列（编程专用）

| 模型 ID | 定位 | 上下文 | 思考 | Function Call | Structured Output |
|---------|------|--------|:---:|:---:|:---:|
| `qwen3-coder-plus` | 🔴 编码旗舰 | 1M | ✅ | ✅ | ✅ |
| `qwen3-coder-flash` | 🟢 编码 Flash | 1M | ✅ | ✅ | ✅ |
| `qwen3-coder-next` | 🟡 预览版 | 256K | ✅ | ✅ | ✅ |

### 3.3 第三方模型（百炼平台托管）

| 模型 ID | 定位 | 上下文 | 思考 | Function Call |
|---------|------|--------|:---:|:---:|
| `deepseek-v4-pro` | DeepSeek 旗舰 | 1M | ✅ | ✅ |
| `deepseek-v4-flash` | DeepSeek 高速 | 1M | ✅ | ✅ |
| `glm-5.2` | 智谱最新旗舰 | 1M | ✅ | ✅ |
| `glm-5.1` | 智谱长程 | 198K | ✅ | ✅ |
| `glm-5` | 智谱基座 | 198K | ✅ | ✅ |
| `glm-4.7` | 智谱编程 | 198K | ✅ | ✅ |
| `kimi-k2.7-code` | Kimi 最强编码 | 256K | ✅ | ✅ |
| `kimi-k2.5` | Kimi 多模态 | 256K | ✅ | ✅ |
| `MiniMax-M2.5` | MiniMax 均衡 | 192K | ✅ | ✅ |
| `mimo-v2.5-pro` | 米么旗舰 | 1M | ✅ | ✅ |

### 3.4 旧版模型（保留可用，不推荐新项目）

| 模型 ID | 上下文 | 说明 |
|---------|--------|------|
| `qwen3-max` | 256K | Qwen3 系列旗舰（阶梯计费） |
| `qwen-plus` | 1M | 旧版 Plus 主线 |
| `qwen-max` | 32K | 旧版 Max |
| `qwen-flash` | 1M | 旧版 Flash |
| `qwen-turbo` | 128K | 旧版 Turbo |
| `qwq-plus` | 128K | 推理专用 |

---

## 四、定价表（中国内地，元/百万 Tokens）

### 4.1 旗舰 Max 系列

| 模型 ID | 输入 (≤1M) | 输出 |
|---------|-----------|------|
| `qwen3.7-max` | ¥12.00 | ¥36.00 |
| `qwen3.7-max-2026-06-08` | ¥12.00 | ¥36.00 |

> Batch 调用半价（输入 ¥6.00 / 输出 ¥18.00）
> 上下文缓存享有折扣（命中缓存的输入部分享折扣）

### 4.2 Plus 系列（阶梯计费）

| 模型 ID | 输入 (≤256K) | 输入 (256K-1M) | 输出 (≤256K) | 输出 (256K-1M) |
|---------|-------------|----------------|-------------|----------------|
| `qwen3.7-plus` | ¥2.00 | ¥6.00 | ¥8.00 | ¥24.00 |
| `qwen3.6-plus` | ¥2.00 | ¥8.00 | ¥12.00 | ¥48.00 |
| `qwen3.5-plus` | ¥0.80 (≤128K) | ¥2.00 (128K-256K) / ¥4.00 (256K-1M) | ¥4.80 | ¥12.00 / ¥24.00 |

> ⚠️ **思考模式**下，输出价格包含思维链 + 回答。思维链 token 和回答 token 均按输出单价计费。
> 百炼的阶梯计费：输入 token 总量落在哪个区间，**全部按该区间单价**结算。

### 4.3 Flash / Turbo 系列

| 模型 ID | 输入 (≤1M) | 输出 |
|---------|-----------|------|
| `qwen3.6-flash` | ¥0.50 | ¥2.00 |
| `qwen3.5-flash` | ¥0.35 | ¥1.40 |
| `qwen-turbo` | ¥0.30 | ¥1.20 |

### 4.4 上下文缓存折扣

部分模型支持上下文缓存，命中缓存后输入价折扣：

- **隐式缓存**（自动）：命中缓存部分输入价 × 20%
- **显式缓存**（`cache_control`）：命中缓存部分输入价 × 10%

支持缓存的模型：`qwen3.7-max`、`qwen3.7-plus`、`qwen3.6-flash` 等。

### 4.5 费用示例

| 场景 | 模型 | 输入 Token | 输出 Token | 总费用 |
|------|------|-----------|-----------|--------|
| Claude Code 单次对话（编程） | `qwen3.7-plus` | 30K (≤256K) | 5K | ¥0.06 + ¥0.04 = **¥0.10** |
| Codex 大任务（长上下文） | `qwen3.7-plus` | 500K (256K-1M) | 20K | ¥3.00 + ¥0.48 = **¥3.48** |
| 轻量问答 | `qwen3.6-flash` | 5K | 2K | ¥0.003 + ¥0.004 = **¥0.007** |
| 旗舰推理（Max） | `qwen3.7-max` | 100K | 10K | ¥1.20 + ¥0.36 = **¥1.56** |

---

## 五、速率限制

> 具体 RPM/TPM 限制需在控制台查看：https://bailian.console.aliyun.com/

| 等级 | 说明 |
|------|------|
| **免费额度用户** | 100 万 Token / 90 天，速率较低 |
| **按量付费用户** | RPM/TPM 随消费等级自动提升 |
| **月消费 > ¥1,000** | 可申请提升限流配额 |
| **企业用户** | 可签约定制限流方案 |

> ⚠️ 百炼速率限制遵循"先到先得"原则，瞬时高并发可能导致限流。建议客户端实现指数退避重试。

---

## 六、协议兼容性细节

### 6.1 OpenAI Chat Completions 兼容

| 特性 | 支持状态 | 说明 |
|------|:---:|------|
| `messages` | ✅ | 标准 OpenA I格式 |
| `stream` (SSE) | ✅ | 完整流式支持 |
| `temperature` | ✅ | 0-2 |
| `top_p` | ✅ | 0-1 |
| `max_completion_tokens` | ✅ | 推荐使用，替代 max_tokens |
| `stop` | ✅ | 最多 4 个停用词 |
| `tools` / `tool_choice` | ✅ | Function Calling |
| `response_format` | ✅ | `json_object` / `json_schema` |
| `thinking` / `enable_thinking` | ✅ | 百炼自定义参数，控制思考模式 |
| `seed` | ✅ | 确定性输出 |
| `n` | ❌ | 不支持多次采样 |
| `logprobs` | ❌ | 不支持 |
| `modalities` | ❌ | Qwen 文本模型不支持多模态输入 |

### 6.2 Anthropic Messages 兼容

| 特性 | 支持状态 | 说明 |
|------|:---:|------|
| `messages` | ✅ | 标准 Anthropic 格式 |
| `stream` (SSE) | ✅ | 完整流式支持 |
| `system` | ✅ | 系统提示词 |
| `tools` / `tool_choice` | ✅ | Tool Use |
| `temperature` | ✅ | 0-1 |
| `top_p` | ✅ | 0-1 |
| `max_tokens` | ✅ | 最大输出 |
| `stop_sequences` | ✅ | 停用序列 |
| `thinking` | ✅ | 思考模式（`enabled`/`disabled`） |
| `thinking.budget_tokens` | ✅ | 思考预算（最大 256K） |
| `cache_control` | ✅ | 显式缓存控制 |
| `disable_parallel_tool_use` | ⚠️ | 部分支持 |
| MCP 协议 | ✅ | 通过工具调用支持 |
| 多模态输入 | ❌ | 文本模型不支持 |

### 6.3 编程智能体接入速查

| 工具 | 协议端点 | Base URL | 模型名示例 |
|------|---------|---------|-----------|
| **Claude Code** | Anthropic | `dashscope.aliyuncs.com/apps/anthropic` | `qwen3.7-plus` / `qwen3.7-max` |
| **Codex CLI** | OpenAI | `dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.7-plus` / `qwen3-coder-plus` |
| **Cursor** | OpenAI | `dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.7-plus` |
| **Windsurf** | OpenAI | `dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.7-plus` |

### 6.4 Claude Code 配置示例

```json
// ~/.claude/settings.json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-xxxxxxxxxxxxxxxx",
    "ANTHROPIC_BASE_URL": "https://dashscope.aliyuncs.com/apps/anthropic",
    "ANTHROPIC_MODEL": "qwen3.7-plus",
    "ANTHROPIC_SMALL_FAST_MODEL": "qwen3.6-flash"
  }
}
```

### 6.5 Codex CLI 配置示例

```toml
# ~/.codex/config.toml
[model_providers.qwen]
name = "Qwen"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "sk-xxxxxxxxxxxxxxxx"

[model_providers.qwen.models.default]
id = "qwen3.7-plus"

[model_providers.qwen.models.small]
id = "qwen3.6-flash"
```

---

## 七、调用注意事项

1. **阶梯计费陷阱**：百炼的阶梯计费并非"分段计费"，而是落在高阶梯后**全部按高价算**。例如 `qwen3.7-plus` 输入 300K Token，全部按 ¥6.00/百万 Token 结算。
2. **思考模式的额外成本**：开启思考模式后，思维链 Token 也按输出价计费。单次可能产生数万 Token 的思考消耗。
3. **地域差异**：国际/全球/欧盟价格远高于中国内地（通常 1.5-2 倍），非必要选北京地域。
4. **上下文缓存**：仅 `qwen3.7-max`、`qwen3.7-plus`、`qwen3.6-flash` 等主力模型支持。Batch 和缓存互斥（不能同时享受两种优惠）。
5. **免费额度**：开通后 90 天有效，各主力模型分别送 100 万 Token。过期未用完作废。
6. **模型快照锁定**：带日期的版本（如 `qwen3.7-max-2026-05-20`）可用于锁定行为。主线版本随时更新。
7. **多模态缺失**：Qwen 文本模型不支持 vision/image_url 输入。如需多模态，需使用第三方托管模型（如 `kimi-k2.7-code`）或 `qwen-omni` 系列。

---

## 八、选模建议

| 场景 | 推荐模型 | 预估单价 |
|------|---------|---------|
| **编程智能体日间主力** | `qwen3.7-plus` | ~¥0.10/次 |
| **简单问答/小修改** | `qwen3.6-flash` | ~¥0.007/次 |
| **复杂度最高的任务** | `qwen3.7-max` | ~¥1.56/次 |
| **大型代码库重构** | `qwen3-coder-plus` | ~中等 |
| **省钱方案** | `qwen3.5-plus` (≤128K) | ~¥0.03/次 |
| **极限省钱** | `qwen-turbo` | ~¥0.002/次 |

> 💡 **主推策略**：`qwen3.7-plus` 作为默认模型，能力和成本均衡。简单任务降级到 `qwen3.6-flash`，复杂任务升级到 `qwen3.7-max`。

---

*手册生成日期：2026-06-18*
*数据来源：阿里云百炼官方文档 https://help.aliyun.com/zh/model-studio/*
*价格可能随时调整，请以官网为准*
