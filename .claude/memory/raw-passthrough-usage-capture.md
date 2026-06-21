---
name: raw-passthrough-usage-capture
description: Native Claude 流式（raw_passthrough）不捕获 token 用量的问题与修复
metadata:
  type: project
---

**问题：** DeepSeek 等原生 Claude Messages 流式调用走 `stream_raw_passthrough`，该函数直接透传原始字节，不解析 SSE 事件 → `prompt_tokens`/`completion_tokens` 始终为 0 → quota 用预估值而非实际值。

**修复：** `app/relay/openai_compatible.py` 中 `stream_raw_passthrough` 新增 `on_usage` 回调参数，流式传输时轻量扫描 Anthropic SSE 的 `event: message_delta` 提取 usage，流结束后回调写入 DB。

**Add：** `app/routers/v1/relay.py` 的 `_make_stream_usage_callback` 补了 `cache_read_input_tokens`（DeepSeek Anthropic 端点的缓存格式）。

**如何避免重犯：** 新增 raw_passthrough 路径必须先确认用法捕获方案；添加 `on_usage` 参数不应是可选后加的，而是设计时就考虑。
