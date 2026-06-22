# MiniMax API 接入参考手册

> 版本：2026-06-18 | 来源：platform.minimax.io 官方文档

---

## 一、快速开始

### 1.1 API 平台入口

| 项目 | 链接 |
|------|------|
| **控制台** | https://platform.minimax.io |
| **API Key 申请** | https://platform.minimax.io/user-center/basic-information/interface-key |
| **充值中心** | https://platform.minimax.io/user-center/payment/balance |
| **Token Plan** | https://platform.minimax.io/user-center/payment/token-plan |
| **文档中心** | https://platform.minimax.io/docs |
| **速率限制** | https://platform.minimax.io/docs/guides/rate-limits |

### 1.2 Base URL

两种协议兼容端点：

```bash
# OpenAI 兼容端点
export OPENAI_BASE_URL="https://api.minimaxi.com/v1"
export OPENAI_API_KEY="你的API_Key"

# Anthropic 兼容端点
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
export ANTHROPIC_API_KEY="你的API_Key"
```

**三种编程智能体配置方式：**

```bash
# Claude Code（Anthropic 协议）
export ANTHROPIC_BASE_URL="https://api.minimaxi.com/anthropic"
export ANTHROPIC_API_KEY="sk-xxx"

# Cursor / Windsurf（OpenAI 协议）
# 在 Cursor 设置中添加：
# Base URL: https://api.minimaxi.com/v1
# API Key: 你的API_Key

# Codex CLI（OpenAI 协议）
export OPENAI_BASE_URL="https://api.minimaxi.com/v1"
export OPENAI_API_KEY="你的API_Key"
```

---

## 二、文本模型清单

### 2.1 当前主力模型

| 模型 ID | 上下文窗口 | TPS | 说明 |
|---------|-----------|-----|------|
| **MiniMax-M3** | 1,000,000 | ~80 tps | **最新旗舰**，支持思考（thinking）、工具调用、多模态（图片/视频），适合编程、Agent、长上下文任务 |
| MiniMax-M2.7 | 204,800 | ~60 tps | 递归自改进系列 |
| MiniMax-M2.7-highspeed | 204,800 | ~100 tps | M2.7 高速版，性能相同但更快 |
| MiniMax-M2.5 | 204,800 | ~60 tps | 巅峰性能，极致性价比 |
| MiniMax-M2.5-highspeed | 204,800 | ~100 tps | M2.5 高速版 |
| MiniMax-M2.1 | 204,800 | ~60 tps | 多语言编程增强 |
| MiniMax-M2.1-highspeed | 204,800 | ~100 tps | M2.1 高速版 |
| MiniMax-M2 | 204,800 | ~60 tps | Agent 能力，高级推理 |

### 2.2 模型能力矩阵

| 能力 | M3 | M2.7 | M2.5 | M2.1 | M2 |
|------|:--:|:----:|:----:|:----:|:--:|
| 思考（Thinking） | ✅ 可控 | ✅ 不可关闭 | ✅ 不可关闭 | ✅ 不可关闭 | ✅ 不可关闭 |
| 工具调用 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 图片输入 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 视频输入 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 流式输出 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Priority 优先通道 | ✅ | ✅ | ✅ | ✅ | ✅ |

### 2.3 Thinking 控制说明

| 模型 | 默认 Thinking | 是否可关闭 | 控制参数 |
|------|:--:|:--:|------|
| **MiniMax-M3** | Anthropic: 关 / OpenAI: 开 | ✅ 可关闭 | `thinking: {"type": "disabled" \| "adaptive"}` |
| **M2.x 系列** | 开 | ❌ 不可关闭 | `thinking: {"type": "disabled"}` 会被接受但不生效 |

OpenAI 兼容端点额外支持 `reasoning_split: true` 参数，将思考内容分离到 `reasoning_details` 字段。

---

## 三、完整价格表

> MiniMax 按美元计费，以下同时列出美元和人民币参考价（汇率 1 USD ≈ 7.2 CNY）。

### 3.1 MiniMax-M3（旗舰）

#### Standard 通道（当前 Permanent 50% Off 促销）

| Token 区间 | 计费项 | 原价 (USD) | 促销价 (USD) | 促销价 (CNY) |
|-----------|--------|-----------|-------------|-------------|
| ≤512K 输入 | Input | $0.60/M | **$0.30/M** | **¥2.16** |
| ≤512K 输入 | Output | $2.40/M | **$1.20/M** | **¥8.64** |
| ≤512K 输入 | Cache Read | $0.12/M | **$0.06/M** | **¥0.43** |
| >512K 输入 | Input | $1.20/M | **$0.60/M** | **¥4.32** |
| >512K 输入 | Output | $4.80/M | **$2.40/M** | **¥17.28** |
| >512K 输入 | Cache Read | $0.24/M | **$0.12/M** | **¥0.86** |

> **Priority 通道**（1.5x Standard）：响应更快、更可靠。设置 `service_tier: "priority"` 启用。

| Priority Token 区间 | 促销价 (USD) | 促销价 (CNY) |
|--------------------|-------------|-------------|
| ≤512K Input | $0.45/M | ¥3.24 |
| ≤512K Output | $1.80/M | ¥12.96 |
| ≤512K Cache Read | $0.09/M | ¥0.65 |

### 3.2 M2.x 系列

| 模型 | Input (USD/M) | Output (USD/M) | Cache Read (USD/M) | Cache Write (USD/M) | Input (¥/M) | Output (¥/M) |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| **M2.7** | $0.30 | $1.20 | $0.06 | $0.375 | ¥2.16 | ¥8.64 |
| **M2.7-highspeed** | $0.60 | $2.40 | $0.06 | $0.375 | ¥4.32 | ¥17.28 |
| **M2.5** | $0.30 | $1.20 | $0.03 | $0.375 | ¥2.16 | ¥8.64 |
| **M2.5-highspeed** | $0.60 | $2.40 | $0.03 | $0.375 | ¥4.32 | ¥17.28 |
| **M2.1** | $0.30 | $1.20 | $0.03 | $0.375 | ¥2.16 | ¥8.64 |
| **M2.1-highspeed** | $0.60 | $2.40 | $0.03 | $0.375 | ¥4.32 | ¥17.28 |
| **M2** | $0.30 | $1.20 | $0.03 | $0.375 | ¥2.16 | ¥8.64 |

> 比较：M3 Standard（促销后）输入价格和 M2.7 完全相同（¥2.16），但 M3 输出更贵（¥8.64 vs ¥8.64，相同）。建议直接上 M3。

### 3.3 五家厂商横向价格对比

| 模型 | Input (¥/M) | Output (¥/M) | 性价比评级 |
|------|:---:|:---:|:---:|
| DeepSeek V4-Pro | ¥3.00 | ¥6.00 | ⭐⭐⭐⭐⭐ |
| DeepSeek V4-Flash | ¥1.00 | ¥2.00 | ⭐⭐⭐⭐⭐ |
| MiniMax M3 (促销) | ¥2.16 | ¥8.64 | ⭐⭐⭐⭐ |
| MiniMax M2.7 | ¥2.16 | ¥8.64 | ⭐⭐⭐⭐ |
| GLM-5.2 | ¥8.00 | ¥28.00 | ⭐⭐⭐ |
| Kimi K2.6 | ¥6.50 | ¥27.00 | ⭐⭐⭐ |
| Qwen3.7-Max | ¥12.00 | ¥36.00 | ⭐⭐ |

> MiniMax M3 促销后价格极具竞争力——输入价格接近 V4-Pro，且是唯一支持 1M 上下文窗口 + 多模态的国产模型。

---

## 四、速率限制

### 4.1 按模型的并发限制

| 模型 | RPM | TPM | 同厂商横向对比 |
|------|:---:|:---:|------|
| **MiniMax-M3** | 200 | 10,000,000 | 比 M2.x 低，因 M3 推理资源更大 |
| M2.7 / highspeed | 500 | 20,000,000 | 标准限制 |
| M2.5 / highspeed | 500 | 20,000,000 | |
| M2.1 / highspeed | 500 | 20,000,000 | |
| M2 | 500 | 20,000,000 | |

### 4.2 独特的固定 5 小时窗口（重要！）

MiniMax 使用**固定时间窗口**而非 OpenAI/Anthropic 的滚动窗口：

```
┌───────────┬──────────────┬──────────────────────┐
│   窗口    │     时间      │      备注            │
├───────────┼──────────────┼──────────────────────┤
│  Window 1 │  00:00-05:00 │  5:00 AM 重置        │
│  Window 2 │  05:00-10:00 │  10:00 AM 重置 ← 最有用│
│  Window 3 │  10:00-15:00 │  3:00 PM 重置         │
│  Window 4 │  15:00-20:00 │  8:00 PM 重置         │
│  Window 5 │  20:00-24:00 │  午夜重置（仅4小时）     │
└───────────┴──────────────┴──────────────────────┘
```

**工作原理：**
- 9:45 AM 触发限流 → 只需等到 10:00 AM（15分钟），不是 5 小时
- 2:45 PM 触发限流 → 只需等到 3:00 PM（15分钟）

**最佳实践：** 把重度 API 调用安排在重置时间点后立即开始（10:00 AM / 3:00 PM / 8:00 PM），而非窗口末尾。

**注意：** 还存在总计费周期限制（Token Plan 模式），5 小时窗口 + 周限制双重约束。

---

## 五、协议兼容性详细说明

### 5.1 OpenAI 兼容端点

```
Base URL:  https://api.minimaxi.com/v1
认证方式:  Bearer Token（API Key）
适用模型:  全部 M 系列
```

**支持参数：**

| 参数 | 状态 |
|------|:--:|
| `model` | ✅ |
| `messages` | ✅ M3 支持 text/image/video；M2.x 仅 text |
| `max_tokens` / `max_completion_tokens` | ✅ |
| `temperature` [0,2] | ✅ |
| `top_p` [0,1] | ✅ M3 默认0.95；M2.x 默认0.9 |
| `stream` | ✅ |
| `tools` | ✅ |
| `tool_choice` | ✅ |
| `thinking` (extra_body) | ✅ M3 可控；M2.x 不可关闭 |
| `reasoning_split` (extra_body) | ✅ 分离思考内容 |
| `service_tier` (extra_body) | ✅ `standard` \| `priority` |
| `stream_options.include_usage` | ✅ |
| `presence_penalty` | ❌ 忽略 |
| `frequency_penalty` | ❌ 忽略 |
| `logit_bias` | ❌ 忽略 |
| `n` | ❌ 仅支持 1 |

### 5.2 Anthropic 兼容端点

```
Base URL:  https://api.minimaxi.com/anthropic
认证方式:  x-api-key Header
适用模型:  全部 M 系列
```

**支持参数：**

| 参数 | 状态 |
|------|:--:|
| `model` | ✅ |
| `messages` | ✅ M3 支持 text/image/video/thinking/tool_use/tool_result |
| `max_tokens` | ✅ |
| `system` | ✅ |
| `stream` | ✅ |
| `temperature` [0,2] | ✅ |
| `top_p` [0,1] | ✅ |
| `tool_choice` | ✅ |
| `tools` | ✅ |
| `thinking` | ✅ M3 可开关；M2.x 不可关闭 |
| `metadata` | ✅ |
| `service_tier` | ✅ `standard` \| `priority` |
| `top_k` | ❌ 忽略 |
| `stop_sequences` | ❌ 忽略 |
| `mcp_servers` | ❌ 忽略 |
| `context_management` | ❌ 忽略 |
| `container` | ❌ 忽略 |

### 5.3 Claude Code 接入注意事项

1. **Thinking 差异**：M3 Anthropic 端点的 thinking **默认关闭**（与原生 Claude 默认开启相反），需显式设置 `thinking: {"type": "adaptive"}`
2. **stop_sequences 忽略**：不要依赖 stop_sequences 做输出控制
3. **cache_control 不支持**：`cache_control` 相关参数会被忽略
4. **mcp_servers 不支持**：MCP 工具需通过 `tools` 参数传入

---

## 六、5 家厂商速查对比

| | DeepSeek | Qwen | GLM | Kimi | **MiniMax** |
|------|:---:|:---:|:---:|:---:|:---:|
| OpenAI 端点 | `/v1` | `/compatible-mode/v1` | `/api/paas/v4` | `/v1` | **`/v1`** |
| Anthropic 端点 | `/anthropic` | `/apps/anthropic` | `/api/anthropic` | `/anthropic` | **`/anthropic`** |
| 旗舰模型 | V4-Pro | 3.7-Max | GLM-5.2 | K2.7-Code | **M3** |
| 旗舰输入 ¥/M | ¥3.00 | ¥12.00 | ¥8.00 | ¥6.50 | **¥2.16** |
| 旗舰输出 ¥/M | ¥6.00 | ¥36.00 | ¥28.00 | ¥27.00 | **¥8.64** |
| 最大上下文 | 1M | 1M | 1M | 256K | **1M** |
| 多模态 | 文本 | 文本 | 文本/图片 | 图片/视频 | **图片/视频** |
| RPM M3 级别 | - | - | - | - | **200** |
| Thinking 控制 | ✅ | ❌ | ❌ | ❌ | ✅ **M3 可关闭** |

---

## 七、故障排查

### 7.1 常见错误码

| HTTP 状态 | 含义 | 处理 |
|-----------|------|------|
| 200 | 成功 | - |
| 400 | 参数错误 | 检查 temperature 范围 [0,2]、model 名称拼写 |
| 401 | API Key 无效 | 检查 Key 是否正确，是否已过期 |
| 429 | 速率限制 | 等下一个 5 小时窗口重置（见上文时间表） |
| 500 | 服务端错误 | 重试 |
| 503 | 服务不可用 | 降级到其他模型 |

### 7.2 429 速率限制特殊处理

由于 MiniMax 使用固定 5 小时窗口，429 的最佳处理方式是**查询重置时间**而非重试：

```python
import datetime

def get_minimax_reset_time():
    """计算 MiniMax 下一个速率限制重置时间"""
    now = datetime.datetime.now()
    hour = now.hour
    
    # 5 小时窗口
    windows = [0, 5, 10, 15, 20]
    
    for w in windows:
        if hour < w or (hour == w and now.minute == 0):
            # 当前在 w-5 到 w 之间，下个重置在 w:00
            return now.replace(hour=w, minute=0, second=0, microsecond=0)
    
    # 20:00-24:00 窗口
    return now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)

# 用法：收到 429 后，等待 reset_time 再重试
reset_time = get_minimax_reset_time()
wait_seconds = (reset_time - datetime.datetime.now()).total_seconds()
print(f"将在 {reset_time.strftime('%H:%M')} 重置，等待 {wait_seconds:.0f} 秒")
```

### 7.3 Claude Code 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|------|
| Thinking 不显示 | M3 Anthropic 默认 thinking=off | 显式传入 `thinking: {"type": "adaptive"}` |
| stop_sequences 不生效 | MiniMax 忽略该参数 | 改用其他方式控制输出 |
| cache_control 不生效 | M2.x 不支持缓存控制 | M3 支持 Prompt Caching |
| 工具调用失败 | 函数名/参数格式问题 | 确保 tool_choice 格式正确 |

---

## 八、快速上手示例

### 8.1 Python + OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.minimaxi.com/v1",
    api_key="你的API_Key"
)

# 基础调用
response = client.chat.completions.create(
    model="MiniMax-M3",
    messages=[
        {"role": "system", "content": "你是一个编程助手。"},
        {"role": "user", "content": "用 Python 写一个快速排序函数。"}
    ],
    temperature=1.0,
    max_tokens=2048,
    extra_body={"reasoning_split": True}  # 分离思考内容
)

print(response.choices[0].message.content)
```

### 8.2 Python + Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="https://api.minimaxi.com/anthropic",
    api_key="你的API_Key"
)

message = client.messages.create(
    model="MiniMax-M3",
    max_tokens=1000,
    system="你是一个编程助手。",
    messages=[
        {"role": "user", "content": [{"type": "text", "text": "你好"}]}
    ],
    thinking={"type": "adaptive"},  # M3 需显式启用 thinking
    temperature=1.0
)

for block in message.content:
    if block.type == "thinking":
        print(f"思考: {block.thinking}")
    elif block.type == "text":
        print(f"回答: {block.text}")
```

### 8.3 Claude Code 配置

```bash
# settings.json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    "ANTHROPIC_API_KEY": "你的API_Key"
  }
}
```

---

*生成日期：2026-06-18*
*数据来源：https://platform.minimax.io/docs*
