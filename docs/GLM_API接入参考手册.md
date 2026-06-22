# GLM（智谱AI）API 接入参考手册

> 版本：2026-06-18 | 基于官方文档 [docs.bigmodel.cn](https://docs.bigmodel.cn/) 及 [bigmodel.cn](https://bigmodel.cn/)

---

## 一、Base URL & 端点

| 协议 | Base URL | 适用场景 |
|------|----------|---------|
| **OpenAI 兼容（通用）** | `https://open.bigmodel.cn/api/paas/v4` | Chat Completions `/chat/completions` |
| **OpenAI 兼容（Coding）** | `https://open.bigmodel.cn/api/coding/paas/v4` | 仅限 Coding Plan 订阅用户 |
| **Anthropic 兼容** | `https://open.bigmodel.cn/api/anthropic` | Messages `/v1/messages` |

### 认证方式

GLM 使用 `id.secret` 格式的 API Key。认证时需将 `id.secret` 格式的 Key 生成 JWT Token，直接设置为 Authorization 头（不添加 `Bearer` 前缀）：

```
Authorization: <JWT_TOKEN_GENERATED_FROM_ID.SECRET>
```

Anthropic 兼容端点使用：
```
x-api-key: <JWT_TOKEN_GENERATED_FROM_ID.SECRET>
```

**API Key 申请**：[https://bigmodel.cn/usercenter/proj-mgmt/apikeys](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)

---

## 二、模型清单

### 2.1 GLM-5 系列（旗舰 — 2026）

| 模型 ID | 定位 | 上下文 | 最大输出 | MCP | Thinking | 价格（输入/输出 ¥/百万tokens） |
|---------|------|--------|---------|-----|---------|--------------------------|
| **`glm-5.2`** | 🆕 最强旗舰 | 1M | 128K | ✅ | ✅ `reasoning_effort` | 🆕 新品上线，限时免费体验 |
| **`glm-5.1`** | 高智能基座 | 200K | 128K | ✅ | ✅ | ¥10.1 / ¥31.7 |
| **`glm-5`** | 强推理旗舰 | 200K | 128K | ✅ | ✅ | ¥7.2 / ¥23.0 |
| **`glm-5-turbo`** | 高速旗舰 | 200K | — | ✅ | ✅ | ¥8.6 / ¥28.8 |

> 🆕 **GLM-5.2**（2026-06-17 发布）：Code Arena 全球可用模型第一，1M 无损上下文，MIT 开源。当前**限时免费**。

### 2.2 中端模型

| 模型 ID | 上下文 | 输入 ¥ | 输出 ¥ | 说明 |
|---------|--------|--------|--------|------|
| **`glm-4.7`** | 205K | ¥4.3 | ¥15.8 | 性价比编程首选 |
| **`glm-4.6`** | 205K | ¥4.3 | ¥15.8 | 与 4.7 同价 |
| **`glm-4.5`** | 131K | ¥4.3 | ¥15.8 | 稳定通用模型 |
| **`glm-4.5-air`** | 131K | ¥1.4 | ¥7.9 | 经济之选 |

### 2.3 经济 & 免费模型

| 模型 ID | 上下文 | 输入 ¥ | 输出 ¥ | 说明 |
|---------|--------|--------|--------|------|
| **`glm-4.7-flash`** | 203K | **免费** | **免费** | 🆓 零成本编程助手 |
| **`glm-4.5-flash`** | — | **免费** | **免费** | 🆓 通用轻量模型 |
| **`glm-4.7-flashx`** | — | ¥0.5 | ¥2.9 | 高速低价 |
| **`glm-4-32b`** | 128K | ¥0.7 | ¥0.7 | 小参数开源模型 |
| **`glm-4-flash-250414`** | 128K | **免费** | **免费** | 🆓 旧版免费 Flash |
| **`glm-z1-flash`** | 128K | **免费** | **免费** | 🆓 推理模型免费版 |

### 2.4 视觉模型

| 模型 ID | 输入 ¥ | 输出 ¥ | 说明 |
|---------|--------|--------|------|
| **`glm-5v-turbo`** | ¥8.6 | ¥28.8 | 旗舰多模态 |
| **`glm-4.6v`** | ¥2.2 | ¥6.5 | 性价比视觉 |
| **`glm-4.6v-flash`** | **免费** | **免费** | 🆓 免费视觉 |

---

## 三、价格概览速查

| 模型 | 输入 | 输出 | 日 100 次中等任务估算 | 月估算 |
|------|------|------|---------------------|--------|
| `glm-5.2` | **限免** | **限免** | ¥0 | ¥0 |
| `glm-5.1` | ¥10.1 | ¥31.7 | ~¥12 | ~¥360 |
| `glm-5` | ¥7.2 | ¥23.0 | ~¥9 | ~¥270 |
| `glm-4.7` | ¥4.3 | ¥15.8 | ~¥5 | ~¥150 |
| `glm-4.5-air` | ¥1.4 | ¥7.9 | ~¥2 | ~¥60 |
| `glm-4.7-flash` | **免费** | **免费** | ¥0 | ¥0 |

> 估算基于每次任务平均输入 30K + 输出 3K tokens。

---

## 四、GLM Coding Plan（订阅制）

如果不想按量付费，智谱提供打包订阅方案：

| 套餐 | 季付原价 | Q2 优惠价 | 折合月费 | 可用模型 |
|------|---------|----------|---------|---------|
| **Lite** | $30/季 | **$27/季** | ~¥72 | GLM-5.1, 5-Turbo, 4.7, 4.6, 4.5-Air |
| **Pro** | $90/季 | **$81/季** | ~¥216 | Lite 全部 + **GLM-5** |
| **Max** | $240/季 | **$216/季** | ~¥576 | Pro 全部（更大配额） |

> 所有套餐赠送免费 MCP 工具：视觉分析、Web Search、Web Reader、Zread。

---

## 五、速率限制

智谱采用分级限速策略：

| 用户等级 | RPM（预估） | TPM（预估） | 并发 |
|---------|-----------|-----------|------|
| 免费/体验 | ~3-5 | 几千 | 1 |
| 付费用户 | ~60+ | 15万+ | 适中 |
| 企业用户 | 数百 | 数十万 | 高 |

**HTTP 响应头参考：**
```
X-RateLimit-Limit-Requests: 60
X-RateLimit-Remaining-Requests: 45
X-RateLimit-Reset-Requests: 1700000000
```

超过限制返回 HTTP 429，建议实现指数退避重试。

---

## 六、协议兼容性详情

### 6.1 Anthropic 兼容端点

```bash
export ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
export ANTHROPIC_API_KEY=<your_zhipu_api_key>
```

**推荐模型（Anthropic 端点）：**

| 模型 | 定位 | 上下文 | 输出 |
|------|------|--------|------|
| `glm-5.2` | 高智能旗舰 | 1M | 128K |
| `glm-5.1` | 高智能基座 | 200K | 128K |
| `glm-5` | 高智能基座 | 200K | 128K |

**Python 调用示例：**
```python
import anthropic

client = anthropic.Anthropic(
    api_key="your-zhipuai-api-key",
    base_url="https://open.bigmodel.cn/api/anthropic"
)

message = client.messages.create(
    model="glm-5.2",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Hello, ZHIPU"}]
)
print(message.content)
```

### 6.2 OpenAI 兼容端点

```bash
export OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
export OPENAI_API_KEY=<your_zhipu_api_key>
```

**Python 调用示例（zai-sdk，推荐）：**
```python
from zai import ZhipuAiClient

client = ZhipuAiClient(api_key="your-api-key")

response = client.chat.completions.create(
    model="glm-5.2",
    messages=[
        {"role": "system", "content": "你是一名资深的全栈软件工程师"},
        {"role": "user", "content": "帮我设计一个博客网站"}
    ],
    thinking={"type": "enabled"},
    reasoning_effort="max",
    max_tokens=65536,
    temperature=1.0
)
print(response.choices[0].message)
```

**SDK 安装：**
```bash
# 新版 SDK（推荐）
pip install zai-sdk

# 旧版 SDK（兼容）
pip install zhipuai==2.1.5.20250726
```

**cURL 示例：**
```bash
curl -X POST "https://open.bigmodel.cn/api/paas/v4/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: <JWT_TOKEN_GENERATED_FROM_ID.SECRET>" \
  -d '{
    "model": "glm-5.2",
    "messages": [{"role": "user", "content": "Hello!"}],
    "thinking": {"type": "enabled"},
    "reasoning_effort": "max",
    "max_tokens": 65536,
    "temperature": 1.0
  }'
```

### 6.3 小程序 / Coding 专用端点

```
https://open.bigmodel.cn/api/coding/paas/v4
```

仅限 Coding Plan 订阅用户，不适用于通用 API 场景。

---

## 七、主流编程智能体接入

### 7.1 Claude Code（推荐走 Anthropic 端点）

```bash
export ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic
export ANTHROPIC_AUTH_TOKEN=<your_zhipu_api_key>
export ANTHROPIC_MODEL=glm-5.2
export ANTHROPIC_DEFAULT_OPUS_MODEL=glm-5.2
export ANTHROPIC_DEFAULT_SONNET_MODEL=glm-5.1
export ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.7-flash
export CLAUDE_CODE_SUBAGENT_MODEL=glm-4.7-flash
export CLAUDE_CODE_EFFORT_LEVEL=max
```

- 主力模型用 `glm-5.2`（1M 上下文，限时免费）
- 子智能体用 `glm-4.7-flash`（免费，省配额）
- 需要 8 小时级长程任务用 `glm-5.1`

### 7.2 Cursor

```json
{
  "openaiBaseUrl": "https://open.bigmodel.cn/api/paas/v4",
  "openaiKey": "<your_api_key>",
  "model": "glm-5.2"
}
```

### 7.3 Cline（原生集成）

Cline 已原生集成智谱，直接在设置中选择 "Zhipu AI" provider 即可，无需手动配置端点。

### 7.4 其他兼容工具

已确认兼容 20+ 编程工具：Kilo Code、Continue.dev、OpenClaw、Crush、Factory 等。所有支持 OpenAI/Anthropic 协议的工具均可接入。

---

## 八、GLM-5.2 亮点速览（2026-06-17 发布）

| 特性 | 详情 |
|------|------|
| Code Arena 排名 | 🥇 全球可用模型第一 |
| 上下文 | 1M 无损（接近用满 850K+ 实测） |
| 架构 | MoE 744B 总参数 / ~40B 激活参数 |
| 开源协议 | MIT |
| 国产算力 | Day 0 适配华为昇腾等 8 大国产芯片 |
| 长程能力 | 可自主完成 85 万 token 级完整开发链路 |
| 价格 | 🆕 **限时免费** |

---

## 九、关键链接

| 项目 | 地址 |
|------|------|
| 官方文档 | [https://docs.bigmodel.cn/](https://docs.bigmodel.cn/) |
| API Key 管理 | [https://bigmodel.cn/usercenter/proj-mgmt/apikeys](https://bigmodel.cn/usercenter/proj-mgmt/apikeys) |
| Coding Plan 订阅 | [https://bigmodel.cn/claude-code](https://bigmodel.cn/claude-code) |
| 开放平台首页 | [https://bigmodel.cn/](https://bigmodel.cn/) |
| 价格页 | [https://bigmodel.cn/pricing](https://bigmodel.cn/pricing) |
| 技术博客 | [https://z.ai/blog](https://z.ai/blog) |

---

## 十、注意事项

1. **GLM-5.2 当前限免**，正式定价待官方公布，届时可能调至 ¥8-15/百万 tokens 区间
2. **Coding 端点独立**：`/api/coding/paas/v4` 仅限 Coding Plan 用户，普通 API 用户走 `/api/paas/v4`
3. **免费模型真免费**：`glm-4.7-flash` 和 `glm-4.5-flash` 是永久免费，不是试用
4. **Coding Plan 是季付**，不是月付，订阅前注意计费周期
5. **thinking 参数**：GLM-5 系列支持 `thinking: {"type": "enabled"}` + `reasoning_effort` 控制推理深度
6. **MCP 原生支持**：GLM-5.2 和 5.1 原生支持 MCP 工具调用
7. **SDK 双轨**：新版 `zai-sdk`（推荐）和旧版 `zhipuai` SDK 并存，API 不同
8. **价格以美元结算**：官方标价以美元计，支付宝/信用卡按实时汇率换算
9. **Anthropic 端点兼容性**：部分 Claude 特有参数可能被忽略，详见官方兼容性说明
10. **Batch API 五折**：大规模离线任务可走 Batch API，价格减半
11. ⚠️ **以下模型可能需要配置定价后才能使用**：`glm-5-turbo`、`glm-4.6`、`glm-4.5`、`glm-4.5-flash`、`glm-4.7-flashx`、`glm-4-32b`、`glm-4-flash-250414`、`glm-5v-turbo`、`glm-4.6v`、`glm-4.6v-flash`。这些模型已在文档中列出但尚未在 `pricing.py` 中添加定价配置，在配置完成前可能无法使用。

---

*手册基于 2026-06-18 官方文档及第三方资料综合生成。GLM-5.2 价格信息为发布初期限免政策，正式定价以 [bigmodel.cn/pricing](https://bigmodel.cn/pricing) 为准。*
