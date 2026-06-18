# 企业级 API 中转站：多智能体 × 多模型的协议转换架构讨论

> 基于《大模型接入协议研究_Review.md》，探讨企业级中转站在同时服务 Claude Code / Codex / Cursor / Windsurf 等编程智能体，并按需调度 DeepSeek / Qwen / GLM / Kimi / MiniMax 等模型时，协议转换层的核心设计考量。

---

## 一、先回答核心问题

> 多智能体调用中转站，入站出站是不是就不需要协议转换了？

**简短回答：不能一概而论。中转站存在三类路径。**

| 路径类型 | 协议转换需求 | 占比（估算） |
|---------|------------|------------|
| **零转换路径** | 入站协议 = 出站协议，纯透传 | ~30% |
| **格式级转换** | 协议不同，但语义可完整映射 | ~40% |
| **语义沟路径** | 协议不同，且存在不可完整桥接的语义差异 | ~30% |

**中转站不是避开协议转换的魔法——中转站本身就是协议转换的实现者。** 但如果设计得当，智能体客户端确实不需要感知协议差异，这是中转站的核心价值。

---

## 二、架构全景：入站 3 协议 × 出站 2 协议

### 2.1 入站侧：智能体发送的请求协议

| 智能体 | 原生协议 | 请求格式 |
|--------|---------|---------|
| **Claude Code** | Anthropic Messages | `/v1/messages` POST |
| **Codex v0.81+** | OpenAI Responses | `/v1/responses` POST |
| **Codex v0.80−** | OpenAI Chat Completions | `/v1/chat/completions` POST |
| **Cursor** | OpenAI Chat Completions | `/v1/chat/completions` POST |
| **Windsurf** | OpenAI Chat Completions | `/v1/chat/completions` POST |
| **Continue.dev** | OpenAI Chat Completions | `/v1/chat/completions` POST |
| **直接 SDK 调用** | 任意 | 取决于 SDK |

### 2.2 出站侧：模型提供的接口协议

| 模型厂商 | Anthropic Messages 端点 | OpenAI Chat Completions 端点 |
|---------|------------------------|---------------------------|
| **DeepSeek** | `api.deepseek.com/anthropic` ✅ | `api.deepseek.com/v1` ✅ |
| **Qwen（百炼）** | `dashscope.aliyuncs.com/apps/anthropic` ✅ | `dashscope.aliyuncs.com/compatible-mode/v1` ✅ |
| **GLM（智谱）** | `open.bigmodel.cn/api/anthropic` ✅ | `open.bigmodel.cn/api/paas/v4` ✅ |
| **Kimi** | `api.moonshot.cn/anthropic` ✅ | `api.moonshot.cn/v1` ✅ |
| **MiniMax** | `api.minimax.io/anthropic` ✅ | `api.minimax.io/v1` ✅ |

**关键事实：5 家厂商全部提供双协议端点。** 这意味着中转站可以选择「同协议路由」策略，大幅减少协议转换需求。

---

## 三、零转换路径（同协议透传）✅

### 3.1 Anthropic ↔ Anthropic 路径

```
Claude Code → [Anthropic Messages] → 中转站 → [Anthropic Messages] → DeepSeek/GLM/Kimi/...
```

请求体和响应体几乎不需要修改。中转站只需要做三件事：

| 操作 | 说明 |
|------|------|
| 替换 `x-api-key` / `Authorization` 头 | 用目标模型 API Key |
| 注入/改写 `anthropic-version` 头 | 确保版本号与目标模型兼容 |
| 重写 `base_url` | 路由到正确端点 |

**推荐策略**：Claude Code → 中转站 Anthropic 端点 → 厂商 Anthropic 端点，这才是最省力的路径。

### 3.2 OpenAI Chat Completions ↔ OpenAI Chat Completions 路径

```
Cursor/Windsurf/Continue.dev → [Chat Completions] → 中转站 → [Chat Completions] → 任意厂商
```

同样是透传为主，只需处理：

| 操作 | 说明 |
|------|------|
| 替换 API Key | 按路由表切换 |
| 注入 `model` 字段（如客户端未指定） | 默认为路由规则中的目标模型 |
| 过滤目标模型不支持的参数 | 如 MiniMax 忽略 `presence_penalty` |

### 3.3 OpenAI Responses ↔ OpenAI Responses 路径（百炼专属）

```
Codex v0.81+ → [Responses] → 中转站 → [Responses] → 百炼 Qwen3.6+
```

**这是 Codex 免协议转换的唯一路径。** 百炼是目前唯一原生支持 Responses API 的国产平台。路径最短，延迟最低。

---

## 四、格式级转换路径（需转换，但语义可完整映射）⚠️

### 4.1 Anthropic Messages → OpenAI Chat Completions

这是最核心的转换路径。Claude Code 只发 Anthropic 格式，但中转站可能因成本/负载原因需要将请求路由到厂商的 Chat Completions 端点。

**转换内容：**

```
# 入站（Anthropic Messages）
{
  "model": "claude-sonnet-4-20250514",
  "messages": [
    {"role": "user", "content": [{"type": "text", "text": "..."}]}
  ],
  "system": [{"type": "text", "text": "..."}],
  "tools": [{"name": "read_file", "description": "...", "input_schema": {...}}],
  "tool_choice": {"type": "auto"},
  "max_tokens": 8192,
  "temperature": 0.7,
  "stream": true,
  "thinking": {"type": "enabled", "budget_tokens": 2048}
}
```

```
# 出站（OpenAI Chat Completions）
{
  "model": "deepseek-v4-pro",
  "messages": [
    {"role": "system", "content": "..."},     ← system 从数组展平为独立字段
    {"role": "user", "content": "..."}         ← content 从数组提取文本
  ],
  "tools": [{"type": "function", "function": {"name": "read_file", ...}}],
  "tool_choice": "auto",                       ← 枚举值格式不同
  "max_tokens": 8192,
  "temperature": 0.7,
  "stream": true
  # thinking → 忽略（Chat Completions 无等价字段）
  # budget_tokens → 忽略
}
```

**可完整映射的字段：**

| Anthropic 字段 | OpenAI 字段 | 转换难度 |
|---------------|-----------|---------|
| `messages[].role` | `messages[].role` | 直通（Anthropic 的 `assistant`/`user` 与 OpenAI 一致） |
| `system` (string/array) | `messages[0].role="system"` | 展平为单条 system 消息 |
| `tools[].name` | `tools[].function.name` | 嵌套重组 |
| `tools[].description` | `tools[].function.description` | 直通 |
| `tools[].input_schema` | `tools[].function.parameters` | 字段重命名 |
| `tool_choice` | `tool_choice` | 值映射：`{"type":"auto"}` → `"auto"`, `{"type":"any"}` → `"required"` |
| `max_tokens` | `max_tokens` | 直通 |
| `temperature` | `temperature` | 直通，但 OpenAI 需同时设 `top_p=1` 或省略 |
| `top_p` | `top_p` | 直通 |
| `stop_sequences` | `stop` | 字段重命名 |
| `stream` | `stream` | 直通 |

### 4.2 响应流转换：SSE 事件映射

这是实现难度最高的部分。两种协议的 SSE 事件结构完全不同：

**Anthropic SSE 流式事件：**

```
event: message_start
data: {"type":"message_start","message":{"id":"msg_xxx","model":"...","role":"assistant",...}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"你好"}}

event: content_block_start
data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"toolu_xxx","name":"read_file","input":{}}}

event: content_block_delta
data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\"file"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":...}}

event: message_stop
data: {"type":"message_stop"}
```

**OpenAI Chat Completions SSE 流式事件：**

```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"你好"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"tool_calls":[{"id":"call_xxx","type":"function","function":{"name":"read_file","arguments":""}}]},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"tool_calls":[{"function":{"arguments":"{\"file"}}]},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"finish_reason":"stop"}],"usage":{"prompt_tokens":...,"completion_tokens":...,"total_tokens":...}}

data: [DONE]
```

**转换要点：**

| 需求 | 实现方式 |
|------|---------|
| Tool calls 流式拼装 | OpenAI 的 `tool_calls` arguments 是增量 JSON 片段，需边收边拼，直到 `finish_reason` 出现再整体转为 Anthropic 的 `tool_use` content_block |
| Content block index 分配 | Anthropic 用 `index` 区分多个内容块（文本+工具调用），需要从 OpenAI 的 delta 流中识别文本/工具的切换点，分配索引 |
| `message_start` / `message_stop` 事件 | 这两个事件在 OpenAI SSE 中没有对应。需在首/末分块自行生成 |
| `stop_reason` 映射 | `"stop"` → `"end_turn"`, `"tool_calls"` → `"tool_use"`, `"length"` → `"max_tokens"` |
| Token 用量 | `message_delta.usage.output_tokens` 的值从 OpenAI 的最后一个 chunk 的 `usage.completion_tokens` 获取 |

### 4.3 OpenAI Chat Completions → Anthropic Messages

反向转换，Cursor/Windsurf 的请求要发给厂商的 Anthropic 端点。对称但更简单（因为 Anthropic 协议更灵活）：

| 要点 | 处理方式 |
|------|---------|
| `messages[].role` | `system` → 提取到顶层 `system` 字段；其余直通 |
| `tools` 结构 | `tools[].function` → 展平为 Anthropic 格式 |
| `tool_calls` 在 history 中 | assistant 消息的 `tool_calls` → 转为 Anthropic 的 `content: [{type:"tool_use",...}]`；tool 角色消息 → `content: [{type:"tool_result",...}]` |
| `n > 1` | Anthropic 不支持并行生成，忽略/报错 |
| `seed` | Anthropic 不支持，忽略 |
| `response_format` | Anthropic 不支持 JSON mode，忽略或转 system prompt 约束 |

---

## 五、语义沟路径（OpenAI Responses ↔ 其他协议）❌

这是**最复杂**的转换场景，也是中转站实现中最容易出 bug 的地方。

### 5.1 Responses API 独有的语义概念

OpenAI Responses API 不是简单的 Chat Completions 升级版——它重新定义了整个对话模型：

| Responses 独有概念 | 含义 | Chat Completions / Anthropic 等价物 |
|-------------------|------|-----------------------------------|
| `previous_response_id` | 指向上一条 response，自动合并上下文 | ❌ 无等价。Chat Completions 需显式传全量 messages |
| `instructions` | 系统指令，比 `system` 更动态 | 勉强可映射为顶层 system 消息 |
| `input` (数组) | 支持多类型输入项混排 | 需展平为 messages 数组 |
| `tools` (带 `type` 的平铺结构) | 比 Chat Completions 的 function 概念更广 | 需按 `type` 分类映射 |
| `text.format` | 响应格式约束 | Chat Completions 无此字段 |
| `reasoning.effort` | 推理深度控制 | 无量化的等价参数 |
| `parallel_tool_calls` | 布尔值控制是否并行调用工具 | Anthropic 用 `disable_parallel_tool_use` 取反 |

### 5.2 转换为何困难

```
Codex v0.81+ → [Responses] → 中转站 → [Chat Completions] → DeepSeek
                                          ↑
                                    这里需要做状态管理
```

**核心矛盾：**

1. **`previous_response_id` 打破了无状态假设**：Codex 通过 response ID 链式引用历史上下文，中转站不再收到完整对话历史。要转换到 Chat Completions，中转站必须自己维护对话状态——把 response ID 链还原为完整的 messages 数组。

2. **工具调用循环的格式差异**：
   - Responses API：工具调用嵌入在 response 的 `output` 中，结果通过追加到 `input` 数组
   - Chat Completions：通过 `tool_calls` / `tool` role 消息循环
   - 中转站需要把这两种多轮对话形式互相转换

3. **Codex 内建工具的字段不一致**：如 `image_generation` 工具在 Responses API 中没有 `name` 字段，中转站发送给 DeepSeek 时会被严格校验拒绝。

**结论：Responses → Chat Completions 的转换，** 本质上需要实现一个完整的状态机，不是简单的请求/响应改写。

### 5.3 实际可行的妥协方案

| 方案 | 复杂度 | 可靠性 |
|------|--------|--------|
| **只支持 Responses ↔ Responses 路径**（百炼直连） | 低 | 高 |
| **强制 Codex 降级 v0.80.0**（走 Chat Completions） | 低 | 高 |
| **在中转站实现完整 Responses → Chat 状态机** | 极高 | 中（易出 bug） |
| **让中转站充当 "Chat Completions 后端" + Codex 的 CC-Switch 模式** | 中 | 高 |

**推荐策略：中转站接受 Codex 连接时，要求客户端使用 "chat" wire_api（即走 Chat Completions 模式），或者中转站仅对百炼开启 Responses 直通。**

---

## 六、更深层的语义沟：不可转换的模型行为差异

即使中转站完美完成格式级转换，以下语义差异仍然是**无法通过协议转换来解决的**：

### 6.1 Thinking / Reasoning 的行为差异

```
Anthropic thinking blocks:
  模型将思考过程以独立 content block 输出
  客户端可决定展示/隐藏

OpenAI Chat Completions:
  无 thinking block 概念
  推理模型的思考过程（如 o1/reasoning_tokens）不走标准流
```

即便中转站在 Anthropic → Chat Completions 转换中把 `thinking` 字段丢给 DeepSeek 的 OpenAI 端点，返回的思考过程要么被丢弃、要么以非标准格式返回，导致 Claude Code 的 `thinking` 展示功能失效。

**影响**：Claude Code 用户看不到模型的思考过程，调试体验降级。

### 6.2 Cache Control 的语义断层

```
Anthropic cache_control: {"type": "ephemeral"}
  标记某段内容可缓存，服务端自动管理缓存生命周期

OpenAI Chat Completions:
  无等价机制
  Prompt Caching 是自动的（DeepSeek），无法显式标记

MiniMax Anthropic 端点: 忽略 cache_control
```

中转站无法将 Anthropic 的显式缓存标记转换为 OpenAI 的自动缓存策略。最坏情况下，中转站需手工剥离 `cache_control` 块。

### 6.3 Tool Use 的并行策略差异

```
Anthropic: tool_choice.type = "any" → 强制调用任意工具
         : disable_parallel_tool_use → 禁止并行调用

OpenAI: tool_choice = "required" → 强制调用工具
      : parallel_tool_calls = false → 禁止并行

DeepSeek Anthropic 端点: disable_parallel_tool_use 被忽略
MiniMax Anthropic 端点: 支持
```

**关键问题**：即使中转站正确映射了 `disable_parallel_tool_use` ↔ `parallel_tool_calls`，DeepSeek 的 Anthropic 端点也会忽略这个字段。中转站无法强制 DeepSeek 不并行调用——这是模型端的行为差异，协议转换无法弥补。

### 6.4 图片/多模态输入

```
Anthropic: content: [{type: "image", source: {type: "base64", media_type: "image/png", data: "..."}}]
OpenAI:   content: [{type: "image_url", image_url: {url: "data:image/png;base64,..."}}]

DeepSeek Anthropic 端点: ❌ 不支持图片输入
MiniMax M3 Anthropic 端点: ✅ 支持图片/视频
```

中转站做格式转换后发送图片给 DeepSeek，DeepSeek 会直接拒绝。这是模型能力差异。

---

## 七、多智能体并发的特殊考量

中转站在多智能体场景下还有额外挑战：

### 7.1 会话状态管理

| 场景 | 挑战 |
|------|------|
| Claude Code 多轮工具调用 | 每轮 tool_use → tool_result 都需要中转站正确拼接消息历史 |
| Codex 异步并行任务 | 多个独立 response 并发，中转站需隔离上下文 |
| Cursor Apply + Chat 双流 | 两个独立会话并发访问中转站，不能串消息 |

**方案**：以 `conversation_id` 或请求头中的 `x-session-id` 为 Key，维护每会话的消息栈。

### 7.2 并发限流与智能路由

```
中转站 Rate Limiter
├── 全局并发上限（如 1000 QPS）
├── 按 API Key 限流（企业多租户）
├── 按模型限流（DeepSeek V4-Pro 500 并发上限）
└── 故障降级：A 模型 429/503 → 自动切换到 B 模型
```

**关键设计**：中转站需要维护各厂商的实时并发上限，在限流触发时自动 fallback 到其他模型。

### 7.3 模型动态选择（Agent-Aware Routing）

中转站可以比纯透传代理更智能——根据请求特征自动选择最优模型：

```python
# 中转站路由规则示例
def route(request):
    if request.headers.get("X-Agent-Type") == "claude-code":
        if is_heavy_task(request):  # 长上下文、多工具
            return "deepseek-v4-pro", "anthropic"
        else:
            return "deepseek-v4-flash", "anthropic"
    elif request.headers.get("X-Agent-Type") == "cursor":
        return "deepseek-v4-flash", "openai"
    elif is_batch_workload(request):
        return "kimi-k2.6", "anthropic"  # Kimi 长任务专长
```

**价值**：智能体不需要关心后端模型——它始终用自己的原生协议发请求，中转站负责选模型+选协议。

---

## 八、推荐的中转站分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    入口层 (Ingress)                      │
│  /v1/messages        (Anthropic 协议智能体)              │
│  /v1/chat/completions (OpenAI Chat 协议智能体)           │
│  /v1/responses        (Codex Responses 协议)             │
├─────────────────────────────────────────────────────────┤
│                  协议适配层 (Adapter)                     │
│  Anthropic ↔ Anthropic     → 透传（仅 auth/路由改写）     │
│  Chat Completions ↔ Chat   → 透传（参数过滤）            │
│  Anthropic → Chat          → 格式转换 + SSE 流转换       │
│  Chat → Anthropic          → 格式转换 + SSE 流转换       │
│  Responses → Chat          → 状态机（不推荐生产）         │
│  Responses → Responses     → 透传（仅百炼）              │
├─────────────────────────────────────────────────────────┤
│                  路由与调度层 (Router)                    │
│  • 模型-协议映射表（6 厂商 × 2 协议）                    │
│  • 智能体感知路由（Agent-Aware）                         │
│  • 故障降级链（主模型 429 → 备模型）                     │
│  • 成本最优路由（同协议优先透传）                         │
├─────────────────────────────────────────────────────────┤
│                  治理层 (Governance)                     │
│  • 多租户 API Key 管理                                   │
│  • Token 用量计量 & 计费                                 │
│  • Rate Limiting（按租户/按模型）                        │
│  • 审计日志 & 敏感信息脱敏                               │
├─────────────────────────────────────────────────────────┤
│                  出站层 (Egress)                          │
│  → DeepSeek  (openai | anthropic)                       │
│  → Qwen      (openai | anthropic)                       │
│  → GLM       (openai | anthropic)                       │
│  → Kimi      (openai | anthropic)                       │
│  → MiniMax   (openai | anthropic)                       │
└─────────────────────────────────────────────────────────┘
```

---

## 九、实施建议优先级

| 优先级 | 功能 | 理由 |
|--------|------|------|
| **P0** | Anthropic ↔ Anthropic 透传 | Claude Code 是核心用户，同协议透传成本最低 |
| **P0** | Chat Completions ↔ Chat Completions 透传 | Cursor/Windsurf/Continue.dev 刚需 |
| **P1** | 多租户 API Key 管理 + Rate Limiting | 企业级必备 |
| **P1** | 故障降级（主模型 → 备模型） | 生产可靠性 |
| **P1** | Anthropic ↔ Chat Completions 格式转换（含 SSE 流） | 扩展路由灵活性 |
| **P2** | Responses → Responses 透传（百炼专属） | Codex 用户需求，但受众较小 |
| **P2** | 智能体感知路由（Agent-Aware） | 锦上添花，自动选模型 |
| **P3** | Responses → Chat Completions 状态机转换 | 复杂度极高，投入产出比存疑 |
| **P3** | Thinking 块的双向保留（非标扩展） | 仅部分模型支持，ROI 不确定 |

---

## 十、核心结论

1. **中转站不能消除协议转换，中转站就是协议转换的实现者。** 但当入站协议 = 出站协议时，转换成本几乎为零。

2. **最大化「同协议路由」是最优策略**：Claude Code 路由到厂商 Anthropic 端点，Cursor 路由到厂商 OpenAI 端点。转换只发生在必须跨协议的场景。

3. **真正的难点不在格式，在语义沟**：`thinking` 块、`cache_control`、`disable_parallel_tool_use` 等概念在跨协议时无法完整保留——它们不是格式问题，是概念模型差异。

4. **Responses API 是最大挑战**：Codex 的 Responses 协议与其他协议的差距太大，不建议在 V1 阶段做完整转换。优先方案是限制 Codex 走 Chat Completions 模式，或仅在百炼上启用 Responses 直通。

5. **中转站的真正价值**：统一 API Key 管理、多模型故障自动降级、Token 用量计量与成本控制、智能体透明切换后端模型。——这些是单纯直连做不到的。

---

*讨论日期：2026-06-18*
*基准文档：大模型接入协议研究_Review.md*
