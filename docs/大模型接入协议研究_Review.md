# 大模型接入协议研究 — Review

> 对《大模型接入协议研究.md》的补充审查，重点补充**接口端点细节、协议兼容性矩阵、官方文档地址、API 申请链接**四部分。

---

## 一、总体结论

原文结论正确——5 家头部国产模型均已原生支持 **OpenAI + Anthropic 双协议**。但原文缺失了**编程调用最关键的信息**：具体的 Base URL、协议兼容性差异、以及各厂商接口文档的直达链接。下面逐个厂商补充。

---

## 二、各厂商协议兼容端点 & 调用注意事项

### 2.1 DeepSeek（深度求索）

| 项目 | 内容 |
|------|------|
| **OpenAI 兼容 Base URL** | `https://api.deepseek.com`（也可用 `https://api.deepseek.com/v1`，注：v1 与模型版本无关） |
| **Anthropic 兼容 Base URL** | `https://api.deepseek.com/anthropic` |
| **认证方式** | `Authorization: Bearer <API_KEY>` |
| **推荐模型** | `deepseek-v4-pro`（深度推理）、`deepseek-v4-flash`（高速推理） |
| **API 申请** | https://platform.deepseek.com/api_keys |
| **接口文档** | https://api-docs.deepseek.com/zh-cn/guides/anthropic_api |

**⚠️ 协议兼容性重点关注：**

| 特性 | 兼容状态 |
|------|----------|
| `temperature` | ✅ 支持，范围 [0.0 ~ 2.0] |
| `top_p` | ✅ 支持 |
| `top_k` | ❌ 忽略 |
| `stream` | ✅ 支持 |
| `stop_sequences` | ✅ 支持 |
| `tools` / `tool_choice` | ✅ 支持（`disable_parallel_tool_use` 忽略） |
| `thinking` | ✅ 支持（`budget_tokens` 忽略） |
| 图片输入 (type="image") | ❌ 不支持 |
| 文档输入 (type="document") | ❌ 不支持 |
| `cache_control` | ❌ 忽略 |
| `mcp_servers` | ❌ 忽略 |

**🔧 调用注意事项：**
- **模型映射机制**：传入 `claude-opus-*` 自动映射到 `deepseek-v4-pro`；`claude-haiku-*` / `claude-sonnet-*` 自动映射到 `deepseek-v4-flash`。利用此特性可在 Claude Desktop APP developer 模式下绕过模型名限制。
- **模型弃用提醒**：`deepseek-chat` / `deepseek-reasoner` 将于 **2026/07/24 弃用**，需迁移至 `deepseek-v4-flash`。
- **Claude Code 配置示例**：
  ```bash
  export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
  export ANTHROPIC_API_KEY="<YOUR_KEY>"
  export ANTHROPIC_MODEL="deepseek-v4-pro"
  ```
- **Cursor / Codex 配置**：直接用 OpenAI 兼容端点 `https://api.deepseek.com`。

---

### 2.2 Qwen（阿里通义千问 / 百炼平台）

| 项目 | 内容 |
|------|------|
| **OpenAI 兼容 Base URL** | 北京：`https://dashscope.aliyuncs.com/compatible-mode/v1` |
|  | 新加坡：`https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1` |
| **Anthropic 兼容 Base URL** | 北京：`https://dashscope.aliyuncs.com/apps/anthropic` |
|  | 新加坡：`https://dashscope-intl.aliyuncs.com/apps/anthropic` |
|  | 新加坡专属（推荐）：`https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/apps/anthropic` |
| **认证方式** | `Authorization: Bearer <API_KEY>` 或 `x-api-key: <API_KEY>` |
| **推荐模型** | `qwen3.7-max`（旗舰）、`qwen3-coder-plus`（编程专用）、`qwen3-coder-flash`（轻量编程） |
| **API 申请** | https://bailian.console.aliyun.com/（需开通百炼服务后获取 API Key） |
| **接口文档** | OpenAI 兼容：https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope |
|  | Anthropic 兼容：https://help.aliyun.com/zh/model-studio/anthropic-api-messages |

**⚠️ 协议兼容性重点关注：**

- **新加坡专属域名（推荐）**：`https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/apps/anthropic`，性能更稳定，适合生产环境。`{WorkspaceId}` 在百炼控制台「业务空间详情」页面查看。
- **Anthropic 端点支持的模型范围极广**，除 Qwen 全系外，还支持 DeepSeek V4、Kimi K2.5/K2.6、GLM-5/4.6/4.7、MiniMax-M2.5/M2.1 等第三方模型，一处 Key 可调用多家模型。
- **API Key 分地域**：北京和新加坡的 API Key 不同，需分别申请。
- **Coding Plan**：百炼提供专属 Coding Plan 订阅套餐，适合高频编程场景。
- **Claude Code 配置示例**：
  ```bash
  export ANTHROPIC_BASE_URL="https://dashscope.aliyuncs.com/apps/anthropic"
  export ANTHROPIC_AUTH_TOKEN="<DASHSCOPE_API_KEY>"
  export ANTHROPIC_MODEL="qwen3.7-max"
  ```
- **Cursor 配置**：使用 OpenAI 端点 `https://dashscope.aliyuncs.com/compatible-mode/v1`。

---

### 2.3 GLM（智谱 AI）

| 项目 | 内容 |
|------|------|
| **OpenAI 兼容 Base URL** | 通用：`https://open.bigmodel.cn/api/paas/v4` |
|  | Coding 套餐专属：`https://open.bigmodel.cn/api/coding/paas/v4` |
| **Anthropic 兼容 Base URL** | `https://open.bigmodel.cn/api/anthropic` |
| **认证方式** | `Authorization: Bearer <API_KEY>` |
| **推荐模型** | `glm-5.2`（最新旗舰）、`glm-5.1`（长程任务专长） |
| **API 申请** | https://bigmodel.cn/usercenter/proj-mgmt/apikeys |
| **接口文档** | 通用 API：https://docs.bigmodel.cn/cn/api/introduction |
|  | Anthropic/Claude 兼容：https://docs.bigmodel.cn/cn/guide/develop/claude/introduction |
|  | 接入工具（Cline 等）：https://docs.bigmodel.cn/cn/coding-plan/tool/others |

**⚠️ 调用注意事项：**
- **Coding 套餐与通用 API 的端点不同**：Coding 套餐必须使用 `https://open.bigmodel.cn/api/coding/paas/v4`，不可混用。
- **Anthropic 兼容端点路径**：完整 Messages 端点为 `https://open.bigmodel.cn/api/anthropic/v1/messages`。
- **GLM Coding Plan**：适合复杂工程化重构与本地化部署场景，原生支持 MCP 协议。
- **Claude Code 配置示例**：
  ```bash
  export ANTHROPIC_BASE_URL="https://open.bigmodel.cn/api/anthropic"
  export ANTHROPIC_API_KEY="<YOUR_KEY>"
  export ANTHROPIC_MODEL="glm-5.2"
  ```

---

### 2.4 Kimi（月之暗面 / Moonshot）

| 项目 | 内容 |
|------|------|
| **OpenAI 兼容 Base URL** | `https://api.moonshot.cn/v1`（中国）/ `https://api.moonshot.ai/v1`（全球） |
| **Anthropic 兼容 Base URL** | `https://api.moonshot.cn/anthropic`（中国）/ `https://api.moonshot.ai/anthropic`（全球） |
| **认证方式** | `Authorization: Bearer $MOONSHOT_API_KEY` |
| **推荐模型** | `kimi-k2.5`（当前主力） |
| **API 申请** | https://platform.kimi.com/console/api-keys |
| **接口文档** | 通用 API：https://platform.kimi.com/docs/api/overview |
|  | Kimi Code CLI：https://moonshotai.github.io/kimi-cli/zh/ |

**⚠️ 调用注意事项：**
- **两套域名**：中国网络用 `api.moonshot.cn`，海外用 `api.moonshot.ai`。国内用户务必用 `.cn` 域名。
- **Anthropic 端点格式**：完整路径为 `https://api.moonshot.cn/anthropic/v1/messages`。
- **环境变量配置**（Claude Code）：
  ```bash
  export ANTHROPIC_BASE_URL="https://api.moonshot.cn/anthropic"
  export ANTHROPIC_AUTH_TOKEN="<YOUR_KEY>"
  export ANTHROPIC_MODEL="kimi-k2.5"
  export ANTHROPIC_SMALL_FAST_MODEL="kimi-k2.5"
  export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
  export API_TIMEOUT_MS=600000
  ```
- **超时处理**：建议将 `API_TIMEOUT_MS` 设置为 600000ms（10分钟），避免长任务中途断开。
- **OpenAI 兼容端点**也支持 Tool Calling，详见 `platform.kimi.com/docs/api/tool-use`。
- **`thinking` 参数**：通过 SDK 的 `extra_body` 传递，是 Kimi 专有扩展。

---

### 2.5 MiniMax

| 项目 | 内容 |
|------|------|
| **OpenAI 兼容 Base URL** | `https://api.minimax.io/v1` |
| **Anthropic 兼容 Base URL** | `https://api.minimax.io/anthropic` |
| **认证方式** | `Authorization: Bearer <API_KEY>` |
| **推荐模型** | `MiniMax-M3`（最新，100万上下文）、`MiniMax-M2.5`（编码优异） |
| **API 申请** | https://platform.minimax.io/（注册后在控制台创建 API Key） |
| **接口文档** | OpenAI SDK：https://platform.minimax.io/docs/api-reference/text-openai-api |
|  | Anthropic SDK：https://platform.minimax.io/docs/api-reference/text-anthropic-api |
|  | Chat Completions（原生）：https://platform.minimax.io/docs/api-reference/text-chat-openai |

**⚠️ 协议兼容性重点关注（Anthropic 端点）：**

| 特性 | 兼容状态 |
|------|----------|
| `temperature` | ✅ [0, 2] |
| `top_p` | ✅ [0, 1] |
| `top_k` | ❌ 忽略 |
| `stop_sequences` | ❌ 忽略 |
| `thinking` | ✅ M3 默认关闭，可 `adaptive` 开启；M2.x 始终开启 |
| `stream` | ✅ |
| `tools` / `tool_choice` | ✅ |
| 图片/视频输入 | ✅ M3 支持；M2.x 仅文本+工具调用 |
| `mcp_servers` | ❌ 忽略 |
| `context_management` | ❌ 忽略 |

**🔧 调用注意事项：**
- **Thinking 控制行为不同**：M3 默认 thinking **关闭**（需手动 `adaptive` 开启）；M2.x 默认 thinking **开启**（不可关闭）。
- **多轮函数调用**：完整的 assistant 消息（含 tool_calls）必须追加回对话历史，否则推理链会断裂。
- **`service_tier`**：支持 `standard` 和 `priority` 两级，priority 价格 1.5x，但优先调度、延迟更低。
- **OpenAI 兼容端点注意事项**：`presence_penalty`、`frequency_penalty`、`logit_bias` 等参数会被忽略；`n` 仅支持 1。
- **Claude Code 配置示例**：
  ```bash
  export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
  export ANTHROPIC_API_KEY="<YOUR_KEY>"
  export ANTHROPIC_MODEL="MiniMax-M3"
  ```

---

## 三、一图纵览：5 家厂商双协议端点速查

| 厂商 | OpenAI 兼容 Base URL | Anthropic 兼容 Base URL |
|------|---------------------|-------------------------|
| **DeepSeek** | `https://api.deepseek.com` | `https://api.deepseek.com/anthropic` |
| **Qwen（百炼）** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `https://dashscope.aliyuncs.com/apps/anthropic` |
| **GLM（智谱）** | `https://open.bigmodel.cn/api/paas/v4` | `https://open.bigmodel.cn/api/anthropic` |
| **Kimi** | `https://api.moonshot.cn/v1` | `https://api.moonshot.cn/anthropic` |
| **MiniMax** | `https://api.minimax.io/v1` | `https://api.minimax.io/anthropic` |

---

## 四、API 申请一键入口 & 接口文档直达

| 厂商 | API 申请入口 | 接口文档首页 |
|------|------------|-------------|
| **DeepSeek** | https://platform.deepseek.com/api_keys | https://api-docs.deepseek.com/ |
| **Qwen（百炼）** | https://bailian.console.aliyun.com/ | https://help.aliyun.com/zh/model-studio/ |
| **GLM（智谱）** | https://bigmodel.cn/usercenter/proj-mgmt/apikeys | https://docs.bigmodel.cn/ |
| **Kimi** | https://platform.kimi.com/console/api-keys | https://platform.kimi.com/docs/ |
| **MiniMax** | https://platform.minimax.io/ | https://platform.minimax.io/docs/ |

---

## 五、编程接入决策建议

### 按接入工具选择协议

| 工具 | 推荐协议 | 原因 |
|------|---------|------|
| **Claude Code** | Anthropic 兼容端点 | 原生 Messages API，协议适配最完整 |
| **Cursor** | OpenAI 兼容端点 | Cursor 基于 OpenAI 协议构建 |
| **Codex / Cline / RooCode** | OpenAI 兼容端点 | 均原生支持 OpenAI Chat Completions |
| **OpenAI SDK** | OpenAI 兼容端点 | 直接替换 `base_url` 即可 |
| **Anthropic SDK** | Anthropic 兼容端点 | 直接替换 `base_url` 即可 |
| **LangChain / Dify / Coze** | OpenAI 兼容端点 | 生态广泛支持 |

### 按场景选择厂商

| 场景 | 推荐厂商 | 理由 |
|------|---------|------|
| 高性价比编程 | DeepSeek V4 | 价格最低，V4 能力均衡 |
| 企业级稳定性 | Qwen（百炼） | 多地域部署，专属 Coding Plan |
| 复杂工程重构 | GLM（智谱） | 原生 MCP，8 小时长程任务 |
| 长程自主编程 | Kimi K2.5 | Agent 自主执行能力最强 |
| 高性能 Bug 排查 | MiniMax M2.5 | SWE-Bench 表现优异 |

---

---

## 六、各厂商最新模型清单 & API 定价

> 价格单位：**元/百万 Tokens**，数据截至 2026-06-18，以各厂商官网最新公布为准。

### 6.1 DeepSeek（深度求索）

| 模型 ID | 定位 | 上下文 | 最大输出 | 缓存命中 | 缓存未命中 | 输出 | 并发 |
|---------|------|--------|----------|----------|-----------|------|------|
| `deepseek-v4-pro` | 🔴 旗舰推理 | 1M | 384K | ¥0.025 | ¥3.00 | ¥6.00 | 500 |
| `deepseek-v4-flash` | 🟢 高速通用 | 1M | 384K | ¥0.02 | ¥1.00 | ¥2.00 | 2500 |

**说明：**
- V4 目前仅两个模型，均支持思考/非思考双模式，通过 `thinking` 参数切换
- **永久降价**（2026/05 起）原 2.5 折优惠转为永久定价
- ⚠️ `deepseek-chat` / `deepseek-reasoner` 于 **2026/07/24 弃用**
- V4-Flash 是全球性价比之王：缓存命中仅 ¥0.02/百万 tokens
- 价格文档：https://api-docs.deepseek.com/zh-cn/quick_start/pricing

### 6.2 Qwen（阿里通义千问 / 百炼平台）

| 模型 ID | 定位 | 上下文 | 最大输出 | 输入 (≤1M) | 输出 | 缓存 |
|---------|------|--------|----------|-----------|------|------|
| `qwen3.7-max` | 🔴 旗舰 Max | 1M | 64K | ¥12.00 | ¥36.00 | 有折扣 |
| `qwen3.7-plus` | 🟡 均衡 Plus | 1M | 64K | ¥2.00 (≤256K) / ¥6.00 | ¥8.00 | 有折扣 |
| `qwen3.6-flash` | 🟢 高速轻量 | 1M | 64K | 阶梯计费（低至 ¥0.01/K） | 阶梯 | — |
| `qwen3-max` | 🟡 经典旗舰 | 256K | 64K | ¥2.50 (≤32K) | ¥10.00 | 有折扣 |
| `qwen3-coder-plus` | 🔵 编程旗舰 | 256K | 64K | ¥7.34 | ¥36.70 | — |

> **注**：百炼官方定价页（https://help.aliyun.com/zh/model-studio/model-pricing）对 Qwen3-Coder 系列采用独立阶梯定价，上表为参考价，建议以百炼控制台实时为准。

**说明：**
- qwen3.7-max / plus 为最新旗舰系列，2026 年 5-6 月发布
- **阶梯计费**：部分模型（qwen3.6-flash / qwen3.7-plus）输入 Token 量越大单价越高
- **上下文缓存**：命中缓存的输入按 20%（隐式）或 10%（显式）折扣计费
- **Batch 调用**：非实时任务享 5 折
- **Coding Plan Pro**：¥200/月（首月 ¥39.9），适合高频编程
- qwen3.7-max **当前 5 折优惠**（输入 6 元 / 输出 18 元？需核实）

### 6.3 GLM（智谱 AI）

| 模型 ID | 定位 | 上下文 | 最大输出 | 输入 | 输出 |
|---------|------|--------|----------|------|------|
| `glm-5.2` | 🔴 最新旗舰 | 1M | 128K | ¥8.00 | ¥28.00 |
| `glm-5.1` | 🟡 长程旗舰 | 200K | 128K | ¥6.00 (≤32K) / ¥8.00 (32K+) | ¥24.00 |
| `glm-5` | 🟡 基座模型 | 200K | 128K | ~¥10.80 | ~¥32.40 |
| `glm-5-Turbo` | 🟢 高速版 | 128K | — | ¥5.00 (≤32K) | — |
| `glm-4.7` | 🔵 编程专长 | 128K | — | 阶梯定价 | 阶梯定价 |

**说明：**
- GLM-5.2 于 2026 年 6 月发布，全球首个**真正可用 1M 无损上下文**的开源模型，FrontierSWE 开源第一
- GLM-5.2 **限时免费体验额度**：2 元/百万 tokens（限时优惠价）
- GLM-5.1 限时免费：1.3 元（≤32K）/ 2 元（32K+）输入
- **分段计费**：输入长度超过 32K tokens 后单价提高
- Coding Plan：¥49/月起（含 MCP 工具支持），模型全系已升级至 GLM-5.1/5-Turbo/4.7
- 自从 GLM-5 发布以来，智谱已多轮涨价（整体涨幅 >30%）
- 价格文档：https://bigmodel.cn/pricing

### 6.4 Kimi（月之暗面 / Moonshot）

| 模型 ID | 定位 | 上下文 | 最大输出 | 缓存命中 | 缓存未命中 | 输出 |
|---------|------|--------|----------|----------|-----------|------|
| `kimi-k2.6` | 🔴 最新旗舰 | 262K | — | ¥1.10 | ¥6.50 | ¥27.00 |
| `kimi-k2.5` | 🟡 主力模型 | 262K | — | ¥0.70 | ¥4.00 | ¥21.00 |

> 通过阿里云百炼还可调用 `kimi-k2.7-code`（256K 上下文，编程优化版）。

**说明：**
- K2.6 于 2026 年 4 月发布，Agent 自主编码能力显著提升（可 13 小时持续编码，4000+ 行）
- K2.5 支持文本、图片、视频多模态输入
- 均支持自动上下文缓存、Tool Calling、JSON Mode
- K2.6 较 K2.5 涨价约 58%
- 海外对应模型定价（USD）：K2.6 缓存 $0.16 / 未命中 $0.95 / 输出 $4.00
- **超时建议**：长任务设置 `API_TIMEOUT_MS=600000`（10 分钟）
- 价格文档：https://platform.kimi.com/docs/pricing/chat-k25

### 6.5 MiniMax

| 模型 ID | 定位 | 上下文 | 输入 (标准) | 输出 (标准) | 缓存命中 | 输入 (Priority) | 输出 (Priority) |
|---------|------|--------|-----------|-----------|---------|---------------|---------------|
| `MiniMax-M3` | 🔴 最新旗舰 | 1M | $0.30 (≤512K) ¥2.16 | $1.20 ¥8.64 | $0.06 ¥0.43 | $0.45 ¥3.24 | $1.80 ¥12.96 |
| `MiniMax-M2.7` | 🟡 高速推理 | 204.8K | $0.30 ¥2.16 | $1.20 ¥8.64 | $0.06 ¥0.43 | — | — |
| `MiniMax-M2.7-highspeed` | 🟢 高速版 | 204.8K | $0.60 ¥4.32 | $2.40 ¥17.28 | $0.06 ¥0.43 | — | — |
| `MiniMax-M2.5` | 🔵 编码专长 | 204.8K | $0.30 ¥2.16 | $1.20 ¥8.64 | $0.03 ¥0.22 | — | — |
| `MiniMax-M2.1` | 🟢 多语言编程 | 204.8K | $0.30 ¥2.16 | $1.20 ¥8.64 | $0.03 ¥0.22 | — | — |

> 价格单位为 USD，¥ 为按 ~7.2 汇率换算参考值，以官网实时汇率为准。
> M3 当前 **永久 5 折**活动，上表已为折后价。

**说明：**
- M3 于 2026 年 6 月 1 日正式发布并开源，万亿参数 MoE 全模态旗舰
- 100 万上下文窗口，支持图像/视频输入
- M3 在 SWE-Bench 等编码基准表现顶级
- `standard` vs `priority`：Priority 价格 1.5x，优先调度、延迟更低
- OpenAI 兼容端 `presence_penalty` / `frequency_penalty` / `logit_bias` 忽略；`n` 仅支持 1
- 价格文档：https://platform.minimax.io/docs/guides/pricing-paygo

---

## 七、五家厂商模型-价格速览总表

| 厂商 | 最新旗舰 | 旗舰价（输入/输出） | 主力编码 | 编码价（输入/输出） | 性价比之王 | 最低价（输入/输出） |
|------|---------|-------------------|---------|-------------------|----------|-------------------|
| **DeepSeek** | V4-Pro | ¥3 / ¥6 | V4-Pro | ¥3 / ¥6 | V4-Flash | ¥1 / ¥2 |
| **Qwen** | 3.7-Max | ¥12 / ¥36 | 3.7-Plus | ¥2 / ¥8 | 3.6-Flash | 阶梯低至 ¥0.01/K |
| **GLM** | 5.2 | ¥8 / ¥28 | 5.2 | ¥8 / ¥28 | GLM-4-Flash | 免费 |
| **Kimi** | K2.6 | ¥6.5 / ¥27 | K2.5 | ¥4 / ¥21 | K2.5 | ¥0.7(cache) / ¥4 / ¥21 |
| **MiniMax** | M3 | ¥2.16 / ¥8.64 | M2.5 | ¥2.16 / ¥8.64 | M2.5 | ¥2.16 / ¥8.64 |

> ⚠️ 注意：以上价格为编程智能体场景常用模型的**公开 API 按量付费标价**，Coding Plan 订阅套餐价格更低，具体参看各厂商官网。

---

## 八、价格趋势洞察

1. **DeepSeek 价格最低**：V4-Flash 输出仅 ¥2/百万 tokens，只有 Claude Opus 的 ~2%
2. **GLM 提供免费模型**：GLM-4-Flash / GLM-Z1-Flash 完全免费，适合低频开发调试
3. **智谱持续涨价**：GLM-5 系列价格较 GLM-4 上涨明显，6 月 5.2 发布后 Coding Plan 再涨 30%+
4. **Kimi 跟随涨价**：K2.6 较 K2.5 涨价约 58%，但 Agent 能力显著提升
5. **MiniMax M3 首发半价**：M3 永久 5 折，折后价格极具竞争力
6. **百炼平台最灵活**：同时可调用千问 + DeepSeek + Kimi + GLM + MiniMax，一处 Key 通吃
7. **建议策略**：日常用 DeepSeek V4-Flash 或 GLM-4-Flash（最低成本），复杂任务切 DeepSeek V4-Pro 或 GLM-5.2

---

## 九、主流编程智能体接入注意事项

> 本章聚焦 **Claude Code / Codex / Cursor / Windsurf** 四大编程工具接入国产大模型 API 的实战配置、协议差异、常见陷阱和优化建议。

### 9.1 工具-协议适配速查

| 编程工具 | 原生协议 | 接入国产模型方式 | 关键门槛 |
|---------|---------|----------------|---------|
| **Claude Code** | Anthropic Messages | 环境变量直连 Anthropic 兼容端点 | 需 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` |
| **Codex CLI** | OpenAI Responses（v0.81+）| 需中转工具（codex-bridge/CC-Switch）| **协议不兼容**：国产模型无 Responses API |
| **Codex CLI**（v0.80 及以下）| OpenAI Chat Completions | 直连 OpenAI 兼容端点 | 旧版本，功能受限 |
| **Cursor** | OpenAI Chat Completions | 设置页填 Base URL + API Key | 手动添加模型名，不自带国产模型 |
| **Windsurf** | OpenAI Compatible | AI Providers 面板配置 | 支持自定义端点 |
| **Continue.dev** | OpenAI Compatible | `config.json` 配置 | 支持多模型、Tab补全独立模型 |

### 9.2 Claude Code 接入详解

#### 9.2.1 两种配置方式

**方式一：环境变量（临时/Shell RC）**

```bash
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_AUTH_TOKEN="sk-你的API_KEY"
export ANTHROPIC_MODEL="deepseek-v4-pro"
export ANTHROPIC_SMALL_FAST_MODEL="deepseek-v4-flash"
export API_TIMEOUT_MS="600000"
```

**方式二：`~/.claude/settings.json`（推荐，持久化）**

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "sk-你的API_KEY",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-flash",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-v4-flash",
    "API_TIMEOUT_MS": "600000",
    "BASH_DEFAULT_TIMEOUT_MS": "300000",
    "DISABLE_AUTOUPDATER": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
```

#### 9.2.2 关键环境变量说明

| 变量 | 作用 | 推荐值 |
|------|------|--------|
| `ANTHROPIC_BASE_URL` | API 端点地址 | 见 [第二节](#二各厂商协议兼容端点--调用注意事项) |
| `ANTHROPIC_AUTH_TOKEN` | API 认证密钥 | 各厂商 API Key |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | Opus 级别模型（重任务） | `deepseek-v4-pro` / `glm-5.2` |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | Sonnet 级别（日常主力） | `deepseek-v4-flash` / `kimi-k2.5` |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | Haiku 级别（轻量任务） | `deepseek-v4-flash` |
| `CLAUDE_CODE_SUBAGENT_MODEL` | 子代理模型 | 同上（便宜快速即可） |
| `API_TIMEOUT_MS` | API 超时（毫秒） | `600000`（10 分钟），长任务必备 |
| `BASH_DEFAULT_TIMEOUT_MS` | Shell 命令默认超时 | `300000`（5 分钟） |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 关闭非必要网络请求 | `1`（避免向 Anthropic 官方发请求） |
| `DISABLE_AUTOUPDATER` | 禁用自动更新 | `1`（避免版本变动致配置失效） |

#### 9.2.3 Claude Code 专属注意事项

1. **跳过官方登录**：创建 `~/.claude/config.json` 写入 `{"primaryApiKey": "任意字符串"}` 即可。实际认证由国产模型 API Key 完成，完全不接触 Anthropic 官方服务器。
2. **Base URL 末尾不要加斜杠**：`https://api.deepseek.com/anthropic` ✅，`https://api.deepseek.com/anthropic/` ❌（会导致双斜杠错误）。
3. **切换模型需重开 Session**：Claude Code 在启动时读取配置，中途修改 `settings.json` 对当前 Session 无效，需关闭重开。
4. **多套配置快速切换**：
   ```bash
   # 命令行指定配置文件启动
   claude --settings ~/.claude/settings-deepseek.json
   # Shell alias
   alias claude-ds="claude --settings ~/.claude/settings-deepseek.json"
   alias claude-glm="claude --settings ~/.claude/settings-glm.json"
   ```
5. **⚠️ 防封核心原则**：不登录 Anthropic 官方账号 + 不走官方 API = 不会被封。所有请求发往国产模型端点。
6. **子代理模型**：务必设为便宜快速的模型，子代理跑的是轻量任务，主力模型留给自己用。

---

### 9.3 Codex CLI 接入详解

#### 9.3.1 核心矛盾：协议代际不兼容

Codex CLI 从 **v0.81.0** 起强制使用 OpenAI 的 **Responses API**，而国产模型（DeepSeek、Kimi、MiniMax 等）只支持 **Chat Completions API**。唯一的例外是**阿里云百炼 Qwen3.6 以上版本**原生支持 Responses。

| 版本 | 所需 API 协议 | 国产模型兼容性 |
|------|-------------|-------------|
| v0.80.0 及以下 | Chat Completions | ✅ 直连可用 |
| v0.81.0 及以上 | Responses | ❌ 需中转工具 |
| 最新版 | Responses | ❌ 需中转工具（CC-Switch / codex-bridge） |

#### 9.3.2 接入方案对比

| 方案 | 难度 | 适用场景 | 关键步骤 |
|------|------|---------|---------|
| **降级 v0.80.0** | ⭐ 极简 | 仅需基本 Codex 功能 | `npm install -g @openai/codex@0.80.0` |
| **CC-Switch** | ⭐ 零难度 | 想用最新版 Codex + GUI | 图形化添加 Provider，一键启用 |
| **codex-bridge** | ⭐⭐ 中等 | Codex 桌面版 + DeepSeek | 配置本地代理 `localhost:4001` |
| **百炼直连** | ⭐ 低 | 阿里云用户，追求极简 | Qwen3.6 原生支持 Responses |
| **LiteLLM** | ⭐⭐⭐ 高 | 企业级路由 + 审计 | 部署 LiteLLM 代理 |

#### 9.3.3 Codex 配置文件：`~/.codex/config.toml`

```toml
model_provider = "deepseek"
model = "deepseek-v4-pro"
review_model = "deepseek-v4-flash"
model_reasoning_effort = "xhigh"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com/v1"
wire_api = "chat"             # 关键！v0.80及以下用 "chat"
requires_openai_auth = true

# 如果走本地代理：
[model_providers.local_proxy]
name = "local_proxy"
base_url = "http://127.0.0.1:4001/v1"
wire_api = "responses"        # 代理做了协议转换
api_key = "与代理的PROXY_AUTH_KEY一致"
```

#### 9.3.4 Codex 认证文件：`~/.codex/auth.json`

```json
{
  "OPENAI_API_KEY": "sk-或任意字符串（走代理时）"
}
```

> ⚠️ **字段名必须是 `OPENAI_API_KEY`**，这是 Codex 的硬约定，不可改为其他名称。

#### 9.3.5 Codex 常见报错

| 报错 | 原因 | 解决 |
|------|------|------|
| `wire_api = chat is no longer supported` | 版本与协议不匹配 | 降级 v0.80.0 或使用 CC-Switch |
| `502 Bad Gateway`（DeepSeek） | Key 错或网络不通 | curl 测试 `https://api.deepseek.com/v1/models` |
| 桌面版仍要求登录 ChatGPT | 桌面版独立认证逻辑 | 通过 CC-Switch 或 codex-bridge 绕过 |
| 端口 4001 被占用 | 代理端口冲突 | 修改 `.env` 中 `PROXY_PORT` 为其他端口 |
| 模型切换后无响应 | 链路不通 | 对话中输入 `/model` 确认当前模型 |

---

### 9.4 Cursor 接入详解

#### 9.4.1 配置步骤

1. `Cmd+,` 打开设置 → 搜索 **Models** 或 **OpenAI API Key**
2. 填入：
   - **API Key**：各厂商 API Key
   - **Override OpenAI Base URL**：`https://api.deepseek.com/v1`（以 DeepSeek 为例）
3. 手动添加模型：点击 **"+ Add Model"** → 输入模型名（如 `deepseek-v4-pro`）
4. 在 Chat 面板或 Cmd+K 中选择该模型发一条测试消息

#### 9.4.2 Cursor 专属注意事项

1. **仅支持 OpenAI 兼容端点**：不能填 Anthropic 端点（`/anthropic`），必须用 `/v1`。
2. **模型名必须手动添加**：Cursor 不会自动发现自定义端点的模型列表，需手动输入。
3. **Apply 功能需额外配置**：Cursor 的 Apply 使用单独的模型调用，需在 Models 设置里也配上同端点的 Apply 专用模型。
4. **Base URL 不要包含接口路径**：`https://api.deepseek.com/v1` ✅，`https://api.deepseek.com/v1/chat/completions` ❌。
5. **流式响应问题**：如回复一次性出现而非逐字输出，检查系统代理是否干扰 SSE 长连接——国产 API 直连不需要代理。
6. **代理干扰排查**：如果开着全局代理但国产 API 报 403/503，先关掉代理再试。

#### 9.4.3 适合 Cursor 的模型速配

| 场景 | 模型 | Base URL |
|------|------|----------|
| 日常编码 | `deepseek-v4-flash` | `https://api.deepseek.com/v1` |
| 复杂架构 | `deepseek-v4-pro` | `https://api.deepseek.com/v1` |
| 代码审查 | `kimi-k2.6` | `https://api.moonshot.cn/v1` |
| 成本敏感 | `glm-4-flash`（免费） | `https://open.bigmodel.cn/api/paas/v4` |
| 长上下文 | `qwen3.7-max` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

---

### 9.5 Windsurf / Continue.dev 接入

#### Windsurf

打开 Settings → **AI Providers** → **OpenAI Compatible**：

```
Base URL: https://api.deepseek.com/v1
API Key: sk-...
Model: deepseek-v4-pro
```

Windsurf 的 Cascade（多步骤任务模式）和 Autocomplete 都支持自定义端点，配置一次全部生效。

#### Continue.dev

编辑 `~/.continue/config.json`：

```json
{
  "models": [
    {
      "title": "DeepSeek V4 Pro",
      "provider": "openai",
      "model": "deepseek-v4-pro",
      "apiKey": "sk-...",
      "apiBase": "https://api.deepseek.com/v1"
    }
  ],
  "tabAutocompleteModel": {
    "title": "DeepSeek V3 (快速补全)",
    "provider": "openai",
    "model": "deepseek-chat",
    "apiKey": "sk-...",
    "apiBase": "https://api.deepseek.com/v1"
  }
}
```

> 💡 **省钱技巧**：Tab 补全用便宜模型（DeepSeek V4-Flash），Chat 和复杂任务用旗舰模型。补全请求量大，差价显著。

---

### 9.6 CC-Switch：多工具统一管理神器

[CC-Switch](https://github.com/farion1231/cc-switch) 是一个开源桌面工具（14.5K Star），统一管理 Claude Code / Codex / Gemini CLI / OpenCode 的供应商配置。

**核心价值**：
- 内置 50+ 供应商模板（含 DeepSeek、GLM、Kimi、Qwen、MiniMax）
- 图形化一键切换，无需手动改配置文件
- 可视化管理 MCP、Skills、系统提示词
- Token 用量统计，按模型/供应商分类
- 会话历史浏览和自动备份

**安装**：
```bash
brew tap farion1231/ccswitch && brew install --cask cc-switch  # macOS Homebrew
# 或从 https://github.com/farion1231/cc-switch/releases 下载
```

**避坑**：
- Base URL 末尾不要加 `/`
- 切换 Claude Code 后需重开 Session
- 中文 Windows 用户名可能报错，建议便携版

---

### 9.7 通用注意事项（跨工具）

#### 9.7.1 上下文截断与 Token 消耗

| 工具 | 默认上下文行为 | 优化建议 |
|------|-------------|---------|
| Claude Code | 自动加载相关文件 | 显式 `@` 引用文件，避免全项目扫描 |
| Codex | 自动 compact | 设置 `model_auto_compact_token_limit` 阈值 |
| Cursor | 默认发送整个文件 | 设置中限制发送行数，手动 `@` 引用 |

**通用原则**：
- 不要让工具自动加载全项目——控制上下文长度 = 控制 Token 消耗
- 长对话中定期 `/compact` 或新建 Session，避免上下文累积
- 子代理/补全任务用便宜模型，主力任务用旗舰模型

#### 9.7.2 并发限制 & Rate Limit

| 厂商 | 默认并发 | 注意事项 |
|------|---------|---------|
| DeepSeek | V4-Pro 500；V4-Flash 2500 | 高并发下优先用 V4-Flash |
| Qwen（百炼） | 按 API Key 配额 | 可申请提额 |
| GLM（智谱） | 按套餐 | Coding Plan 有专属并发配额 |
| Kimi | 未公开 | 长任务并发较低 |
| MiniMax | Priority 优先调度 | 高并发建议用 Priority 级别 |

**应对策略**：
- 批量任务错峰执行
- Codex 异步模式天然解决并发问题（并行提交任务）
- 对重试逻辑做指数退避（exponential backoff）

#### 9.7.3 Tool Calling 兼容性差异

编程智能体重度依赖 Tool Calling（函数调用），各厂商对此的兼容性存在差异：

| 厂商 | Tool Calling 支持 | 注意事项 |
|------|------------------|---------|
| DeepSeek | ✅ 完整 | `disable_parallel_tool_use` 被忽略 |
| Qwen | ✅ 完整 | 通过 Anthropic 端点调用更稳定 |
| GLM | ✅ 完整 | Coding Plan 原生支持 MCP |
| Kimi | ✅ 完整 | 有专用 `/tool-use` 文档 |
| MiniMax | ✅ 支持 | 多轮对话需把 tool_calls 追加回历史 |

**⚠️ Codex 特有问题**：Codex 的内建 `image_generation` 工具在 Responses API 里没有 `name` 字段，DeepSeek 校验严格会拒绝。这是导致 Codex 无法直连国产模型的根因之一。

#### 9.7.4 网络与超时

| 工具 | 超时配置 | 推荐值 |
|------|---------|--------|
| Claude Code | `API_TIMEOUT_MS` | `600000`（10 分钟） |
| Codex | config.toml 中无直接配置 | 依赖代理工具配置 |
| Cursor | IDE 内置超时 | 约 30-60 秒，长任务可能超时 |

> **长推理任务（DeepSeek V4-Pro / Kimi K2.6）** 可能单次推理耗时 2-5 分钟。务必调大超时配置，否则任务中断。

#### 9.7.5 常见 HTTP 错误诊断

| 错误码 | 可能原因 | 排查步骤 |
|--------|---------|---------|
| 401 | API Key 错、失效 | curl 测试 `/v1/models` 验证 Key |
| 403 | Key 无权限、IP 限制 | 检查控制台 IP 白名单、Key 是否过期 |
| 404 | Base URL 错、路径拼错 | 不要把接口路径（`/chat/completions`）塞进 Base URL |
| 429 | 并发超限 | 降低并发、等待冷却、升级套餐 |
| 502/503 | 上游繁忙 | 换轻量模型、降低上下文、稍后重试 |
| 超时 | 任务太重、网络不稳 | 调大 `API_TIMEOUT_MS`、检查代理 |

#### 9.7.6 费用优化黄金法则

1. **补全/子代理 → 便宜模型**：Tab 补全用 V4-Flash / GLM-4-Flash，每百万 tokens 仅 ¥1-2
2. **Chat/复杂任务 → 旗舰模型**：按需切到 V4-Pro / GLM-5.2
3. **缓存命中充分利用**：保持长 Session，重复上下文命中缓存可降费 90%+
4. **CC-Switch 用量面板**：实时看 Token 消耗，心中有数
5. **百炼 Coding Plan ¥200/月**：如果月用量超 ¥200，订阅比按量便宜

---

## 十、工具-厂商最佳组合速查

| 需求场景 | 工具 | 推荐厂商/模型 | 理由 |
|---------|------|-------------|------|
| 🏃 日常编码（补全+内联编辑） | Cursor | DeepSeek V4-Flash | Tab 补全体验最佳 + 价格最低 |
| 🔧 大型重构（跨文件+上下文） | Claude Code | DeepSeek V4-Pro 或 GLM-5.2 | 200K+ 上下文 + 文件系统直操能力 |
| 📦 批量修改+自动PR | Codex | DeepSeek V4-Flash（通过CC-Switch） | 异步多任务并行 |
| 🔍 代码审查 | Claude Code | GLM-5.2 或 Kimi K2.6 | MCP 连接 Git 系统 + 深度上下文理解 |
| 🚀 CI/CD 集成 | Claude Code | 按需选用 | Terminal-native，Hooks 系统 |
| 💰 极致省钱 | Cursor+Continue.dev | GLM-4-Flash（免费） | Tab补全零成本 |
| ⚖️ 均衡之选 | Cursor Pro + Claude Code Max | DeepSeek 全家桶 | 覆盖 90% 场景，$120/月组合 |

---

*Review 日期：2026-06-18*
*数据来源：各厂商官方文档、社区最佳实践、实测配置，价格可能随时调整*
