# Upstream 429 Backoff Retry — 设计文档

## 问题

单一 GLM channel 场景下，Claude Code 的多工具并发调用会导致多个 `/v1/messages` 请求同时到达 UniAPI。这些请求在无协调的情况下同时发送到 GLM 上游，GLM 返回 HTTP 429（Too Many Requests）。

当前代码仅对 429 做一次 fallback 到其他 channel 的尝试，单一 channel 时 fallback 必然失败，429 直接暴露给客户端。

## 方案

在 relay 的重试循环中，对 HTTP 429 增加**同通道指数退避重试**：遇到 429 时，在当前 channel 上以 1s/2s/4s 的间隔自动重试，每次带随机 jitter 防止惊群效应。

## 详细设计

### 1. 配置项

在 `app/config.py` 中新增：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `UPSTREAM_RETRY_MAX` | 4 | 最大总尝试次数（含首次，即退避最多 3 次） |
| `UPSTREAM_RETRY_BACKOFF_BASE` | 1.0 | 退避基数（秒） |

### 2. 重试循环改造

文件：`app/routers/v1/relay.py`，方法 `_handle_relay()` 中 `for attempt in range(2)` 循环段。

#### 改动点

1. **循环范围**：`range(2)` → `range(UPSTREAM_RETRY_MAX)`
2. **拆分为三条路径**：
   - **路径 A — 429 + 有退避次数**：`asyncio.sleep(delay)` 后 `continue` 重试同通道。不记故障、不退配额。
   - **路径 B — 429 + 已耗尽退避次数**：尝试 fallback 到其他 channel。仍失败则记故障、退款、抛异常。
   - **路径 C — 5xx / 非 HTTP 错误**：保留现有 fallback 逻辑不变。
3. **流式支持**：429 退避路径不对 `stream` 设条件（5xx fallback 仍保持 `not stream` 限制）。
4. **故障计数**：仅在**所有重试和 fallback 都耗尽后**才调用 `_record_channel_failure()`。

#### 退避时间序列（max=4）

| Attempt | 裸延迟 | Jitter 后范围 |
|---------|--------|--------------|
| 0 → 1   | 1.0s   | 0.5 – 1.0s |
| 1 → 2   | 2.0s   | 1.0 – 2.0s |
| 2 → 3   | 4.0s   | 2.0 – 4.0s |

Jitter 公式：`delay = BACKOFF_BASE * (2 ** attempt) * (0.5 + random.random() * 0.5)`

### 3. 配额退款时机

- 429 退避重试期间：**不退**配额（因为还在尝试，并未失败）
- 所有重试 + fallback 均失败后：**退**配额，与现有逻辑一致
- 最终成功：正常结算

### 4. 故障计数

- 429 退避期间：**不记** `_record_channel_failure`
- 429 退避耗尽后 fallback 成功：记**原通道**故障
- 429 退避耗尽 + fallback 失败：记故障
- 5xx fallback / 非 HTTP 错误 fallback：保持现有行为不变

## 边界情况

| 场景 | 行为 |
|------|------|
| 连续 3 次 429 后成功 | 第 4 次尝试成功，故障计数器清空 |
| 连续 3 次 429 后仍 429 | 尝试 fallback，失败则报错 |
| 单 channel + 429 | 退避 3 次后仍 429 → 报错 |
| 多 channel + 429 | 退避 3 次后仍 429 → fallback 到其他 channel |
| 流式 + 429 | 退避重试（流开始前完成），不移除 `not stream` 对 5xx 的限制 |
| 500 + 单 channel | 保持现有行为：尝试 fallback（找不到则直接报错） |
| 请求被取消/超时 | 保持现有行为：非 HTTP 错误走现有 fallback 逻辑 |

## 测试策略

现有 `tests/phase3/` 和 `tests/` 中的 relay 测试不变，新增：

1. **单 channel 429 退避**：模拟上游 429，验证请求被重试指定次数后最终成功
2. **退避耗尽报错**：模拟连续 4 次 429，验证最终抛出 `UpstreamException`
3. **jitter 范围**：验证延迟在 `[0.5*base*2^t, 1.0*base*2^t]` 范围内
4. **流式 429 退避**：模拟流式请求的 429，验证重试后成功响应
5. **配额不退**：验证退避重试期间配额不退款
6. **故障计数**：验证退避成功的请求不触发 `_record_channel_failure`
