---
name: glm-coding-plan-limitation
description: GLM Anthropic 端点需要额外 Coding Plan 套餐，转换路径绕过
metadata:
  type: project
---

**发现：** GLM 的 `/api/anthropic` 端点需要单独的 "GLM Coding Plan" 付费套餐，普通 API Key 额度不可用。返回 `429/1309` 错误 "您的GLM Coding Plan套餐已到期"。

**决策：** GLM 不走原生 Claude Messages 直通（`NATIVE_FORMATS` 不包含 `claude_messages`），而是走转换路径：`anthropic_to_chat()` → GLM Chat 端点(`/v4/chat/completions`) → `ChatToAnthropicSSE()` 转回 Anthropic 格式。见 `app/relay/adaptors/glm/adaptor.py` 注释。

**影响：** 用户用普通 GLM API Key 就能通过 Claude Code 调用，但代价是多一次协议转换的开销。GLM-5.2 的 `pricing.py` 配置 `input_ratio=0, output_ratio=0`（免费），需要注意。

**相关 memory：** [[raw-passthrough-usage-capture]]
