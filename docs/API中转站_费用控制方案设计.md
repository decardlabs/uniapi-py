# API 中转站——基于预算的模型调用方案设计

> 场景：企业给每个用户分配月度预算（如 800 元），用户可调用任意模型，总费用控制在预算范围内。预算耗尽后硬拒绝。

---

## 一、方案总览

### 1.1 一句话描述

中转站在路由层之上新增一个**预算仲裁器（Budget Arbiter）**，在每次模型调用前估算本次费用 + 已消耗费用，判断是否超出预算，超出则拒绝，未超出则放行，调用完成后扣减实际费用。

### 1.2 核心流程（30 秒版）

```
用户请求 → 认证 → 查预算余额 → 选模型 → 估费用 → 余额够？
                                                    ├── 够 → 调用模型 → 扣实费 → 返回
                                                    └── 不够 → 402 "余额不足，剩余 ¥X，请下月重试"
```

### 1.3 关键决策点

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 预算周期 | 按月，每月 1 日 0:00 自动重置 | 简单可控，防止无限透支 |
| 预算耗尽 | 硬拒绝（402） | 用户明确选择，最严格 |
| 预算粒度 | 全局预算（每人一个池子） | 管理最简 |
| 扣费时机 | 调用完成后按实际 Token 用量扣 | Token 消耗不可预测，预估不准 |
| 预估用途 | 仅用于「余额是否够」的判断 | 不依赖预估做最终扣费 |

---

## 二、数据模型设计

### 2.1 核心表结构

```sql
-- 预算表：每人一条记录
CREATE TABLE budgets (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL UNIQUE,       -- 用户 ID
    monthly_budget  DECIMAL(10, 4) NOT NULL DEFAULT 800.0000,  -- 月度预算（元）
    consumed        DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,    -- 当月已消费（元）
    frozen          DECIMAL(10, 4) NOT NULL DEFAULT 0.0000,    -- 冻结金额（正在执行的调用）
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 费用记录表：每次 API 调用一条
CREATE TABLE cost_records (
    id              BIGSERIAL PRIMARY KEY,
    request_id      VARCHAR(64) NOT NULL UNIQUE,       -- 请求唯一 ID
    user_id         VARCHAR(64) NOT NULL,              -- 用户 ID
    model           VARCHAR(64) NOT NULL,               -- 使用的模型
    input_tokens    INTEGER NOT NULL,                   -- 实际输入 Token
    output_tokens   INTEGER NOT NULL,                   -- 实际输出 Token
    cache_hit_tokens INTEGER DEFAULT 0,                 -- 缓存命中 Token
    cost            DECIMAL(10, 6) NOT NULL,            -- 实际费用（元）
    estimated_cost  DECIMAL(10, 6),                     -- 预估费用（元）
    protocol        VARCHAR(32),                        -- 协议类型
    agent_type      VARCHAR(64),                        -- 智能体类型
    status          VARCHAR(16) NOT NULL,                -- 'success' | 'rejected' | 'error'
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    
    INDEX idx_cost_user_month (user_id, created_at),
    INDEX idx_cost_request_id (request_id)
);

-- 预算重置日志：每月生成一条
CREATE TABLE budget_reset_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         VARCHAR(64) NOT NULL,
    period          VARCHAR(7) NOT NULL,                -- '2026-06'
    total_consumed  DECIMAL(10, 4) NOT NULL,            -- 该月总消费
    total_requests  INTEGER NOT NULL,                   -- 总请求数
    reset_at        TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 2.2 预算状态在 Redis 中的缓存

```python
# Redis Key 设计
{
    # 当月已消费
    f"budget:consumed:{user_id}:{period}" -> "523.4560"
    
    # 冻结金额（正在执行的并发调用）
    f"budget:frozen:{user_id}:{period}" -> "12.3400"
    
    # 每月 1 日自动过期（TTL = 下月 1 日 - 当前时间）
}
```

为什么需要 Redis：
- PostgreSQL 在高并发扣减时有行锁瓶颈
- Redis `DECRBY` 是原子的，适合高频余额扣减
- PostgreSQL 作为最终数据源，定时（如每 5 分钟）或实时异步同步

---

## 三、费用计算模型

### 3.1 定价数据（从 Review 文档提取）

```python
# 完整定价表（元/百万 Tokens）
MODEL_PRICING = {
    # DeepSeek（V4 仅两个模型：V4-Pro 和 V4-Flash）
    "deepseek-v4-pro":      {"input": 3.0,   "output": 6.0,   "cache_hit": 0.025},
    "deepseek-v4-flash":    {"input": 1.0,   "output": 2.0,   "cache_hit": 0.02},
    
    # Qwen（阿里云百炼）
    "qwen3.7-max":          {"input": 12.0,  "output": 36.0,  "cache_hit": 3.0},
    "qwen3.7-plus":         {"input": 2.0,   "output": 8.0,   "cache_hit": 0.5},
    "qwen3.6-flash":        {"input": 0.5,   "output": 2.0,   "cache_hit": 0.125},
    "qwen3-coder-plus":     {"input": 4.0,   "output": 16.0,  "cache_hit": 1.0},
    "qwen3-coder-flash":    {"input": 0.5,   "output": 2.0,   "cache_hit": 0.125},
    
    # GLM（智谱AI）
    "glm-5.2":              {"input": 0.0,   "output": 0.0,   "cache_hit": 0.0},    # 当前限免
    "glm-5.1":              {"input": 10.1,  "output": 31.7,  "cache_hit": 2.5},
    "glm-5":                {"input": 7.2,   "output": 23.0,  "cache_hit": 1.8},
    "glm-5-turbo":          {"input": 8.6,   "output": 28.8,  "cache_hit": 2.15},
    "glm-4.7":              {"input": 4.3,   "output": 15.8,  "cache_hit": 1.0},
    "glm-4.6":              {"input": 4.3,   "output": 15.8,  "cache_hit": 1.0},
    "glm-4-flash":          {"input": 0.0,   "output": 0.0,   "cache_hit": 0.0},    # 免费
    "glm-4.5-air":          {"input": 1.4,   "output": 7.9,   "cache_hit": 0.35},
    
    # Kimi（Moonshot）
    "kimi-k2.7-code":       {"input": 6.5,   "output": 27.0,  "cache_hit": 1.30},
    "kimi-k2.7-code-hs":    {"input": 13.0,  "output": 54.0,  "cache_hit": 2.60},
    "kimi-k2.6":            {"input": 6.5,   "output": 27.0,  "cache_hit": 1.10},
    "kimi-k2.5":            {"input": 4.0,   "output": 21.0,  "cache_hit": 0.70},
    
    # MiniMax
    "minimax-m3":           {"input": 2.16,  "output": 8.64,  "cache_hit": 0.54},
    "minimax-m2.5":         {"input": 2.16,  "output": 8.64,  "cache_hit": 0.54},
}
```

### 3.2 费用计算公式

```python
def calculate_cost(model: str, input_tokens: int, output_tokens: int, cache_hit_tokens: int = 0) -> float:
    """
    计算实际费用
    
    Args:
        model: 模型名称
        input_tokens: 实际输入 Token 数（不含缓存命中）
        output_tokens: 实际输出 Token 数
        cache_hit_tokens: 缓存命中的 Token 数
    
    Returns:
        费用（元）
    """
    pricing = MODEL_PRICING[model]
    
    cost = (
        (input_tokens / 1_000_000) * pricing["input"] +
        (output_tokens / 1_000_000) * pricing["output"] +
        (cache_hit_tokens / 1_000_000) * pricing["cache_hit"]
    )
    
    return round(cost, 6)


def estimate_cost(model: str, estimated_input_tokens: int, estimated_output_tokens: int = 1000) -> float:
    """
    预估费用（调用前使用）
    
    保守策略：按最大可能输出预估（避免估计不准导致扣费时超预算）
    """
    # 保守预估：输出按请求的 max_tokens 估算
    # 如果 max_tokens 未设，按经验值 4096
    pricing = MODEL_PRICING[model]
    
    est_cost = (
        (estimated_input_tokens / 1_000_000) * pricing["input"] +
        (estimated_output_tokens / 1_000_000) * pricing["output"]
    )
    
    return round(est_cost * 1.2, 6)  # 上浮 20%，保守估计
```

### 3.3 典型场景费用估算

按 800 元/月预算，用 V4-Pro 能走多远：

| 场景 | 输入 Token | 输出 Token | 单次费用 | 800 元可调用 |
|------|-----------|-----------|---------|------------|
| 简单对话（"写个排序函数"） | ~1,000 | ~500 | ¥0.006 | ~133,000 次 |
| 中等任务（"重构这个模块"） | ~10,000 | ~3,000 | ¥0.048 | ~16,600 次 |
| 复杂任务（"审查整个项目"） | ~50,000 | ~10,000 | ¥0.21 | ~3,800 次 |
| 超长上下文（"分析整个代码库"） | ~100,000 | ~20,000 | ¥0.42 | ~1,900 次 |

**结论**：800 元/月 在 V4-Pro 下，足够一个重度编程用户每天 60 次中等任务或 120 次简单任务。如果用 V4-Flash（1/3 价格），数量翻三倍。

---

## 四、预算仲裁流程

### 4.1 请求前：预检阶段

```python
class BudgetArbiter:
    """预算仲裁器——请求到达时的第一道闸门"""
    
    def pre_check(self, request: IncomingRequest, user_id: str) -> BudgetDecision:
        """
        请求前预检
        
        Returns:
            BudgetDecision:
                - 'approved': 预算充足，放行
                - 'rejected': 预算不足，拒绝（402）
                - 'degraded': 预算紧张，降级到更便宜的模型
        """
        
        # Step 1: 获取用户预算状态
        budget = self.get_budget(user_id)  # Redis 原子读取
        # budget = {"monthly": 800.0, "consumed": 523.456, "frozen": 12.34, "period": "2026-06"}
        
        available = budget["monthly"] - budget["consumed"] - budget["frozen"]
        
        # Step 2: 估算本次调用费用
        estimated_cost = self.estimate_cost(request)
        
        # Step 3: 判断
        if available >= estimated_cost:
            # 预算充足，放行
            self.freeze_budget(user_id, estimated_cost)  # 冻结预估金额
            return BudgetDecision(
                status="approved",
                available=available,
                estimated_cost=estimated_cost,
                remaining_after=round(available - estimated_cost, 4)
            )
        
        # 预算不足，检查是否有更便宜的替代模型
        cheaper_model = self.find_cheaper_model(request, max_cost=available)
        
        if cheaper_model:
            # 有更便宜的模型可以替代
            cheaper_estimated = self.estimate_cost(request, model=cheaper_model)
            self.freeze_budget(user_id, cheaper_estimated)
            return BudgetDecision(
                status="degraded",
                available=available,
                original_model=request.model,
                degraded_model=cheaper_model,
                estimated_cost=cheaper_estimated,
                remaining_after=round(available - cheaper_estimated, 4),
                note=f"预算不足，已从 {request.model} 降级到 {cheaper_model}"
            )
        
        # 连最便宜的模型都调不起
        return BudgetDecision(
            status="rejected",
            available=available,
            error_code=402,
            error_message=f"月度预算已耗尽。已消费 ¥{budget['consumed']:.2f} / ¥{budget['monthly']}，\n"
                          f"剩余 ¥{available:.4f}，最便宜调用需 ¥{MIN_CALL_COST}。\n"
                          f"请等待下月 1 日重置，或联系管理员增加预算。"
        )
```

### 4.2 调用后：扣费阶段

```python
class BudgetArbiter:
    
    def post_settle(self, request_id: str, actual_usage: ActualUsage):
        """
        调用完成后结算
        
        Args:
            actual_usage: 模型返回的实际 Token 用量
                {"input_tokens": 9823, "output_tokens": 3102, "cache_hit_tokens": 4000}
        """
        
        # Step 1: 计算实际费用
        actual_cost = calculate_cost(
            actual_usage.model,
            actual_usage.input_tokens,
            actual_usage.output_tokens,
            actual_usage.cache_hit_tokens
        )
        
        # Step 2: 从 Redis 扣减（原子操作）
        frozen = self.redis.decrby(f"budget:frozen:{user_id}:{period}", frozen_amount)
        consumed = self.redis.incrbyfloat(f"budget:consumed:{user_id}:{period}", actual_cost)
        
        # Step 3: 处理特殊情况——实际费用 > 冻结金额
        if actual_cost > frozen_amount:
            # 超出预算！（预估偏低 + 没有缓存命中）
            overage = actual_cost - frozen_amount
            
            # 记录超额日志
            self.log_overage(user_id, request_id, frozen_amount, actual_cost, overage)
            
            # 宽容处理：允许本次超支，但触发告警
            self.alert(f"User {user_id} exceeded budget by ¥{overage:.4f}")
        
        # Step 4: 异步写入 PostgreSQL
        self.async_write_cost_record(
            request_id=request_id,
            user_id=user_id,
            model=actual_usage.model,
            input_tokens=actual_usage.input_tokens,
            output_tokens=actual_usage.output_tokens,
            cache_hit_tokens=actual_usage.cache_hit_tokens,
            cost=actual_cost
        )
        
        return SettlementResult(
            cost=actual_cost,
            consumed_now=consumed,
            remaining=round(monthly - consumed, 4)
        )
```

### 4.3 全额生命周期图

```
请求到达
    ↓
认证（API Key）
    ↓
查预算余额（Redis）
    ↓
    ├──── available <= 0 ──────→ 402 "预算耗尽" ← 最快路径
    │
    ↓ available > 0
选择模型 + 估费用
    ↓
    ├──── estimated > available ──→ 找更便宜模型
    │                                    ├── 找到 → 降级路由
    │                                    └── 没找到 → 402 "预算不足"
    │
    ↓ estimated <= available
冻结预估金额（Redis DECRBY available）
    ↓
协议转换 + 模型调用
    ↓
收到响应（含实际 token 用量）
    ↓
计算实际费用（不是预估值！）
    ↓
解冻预估金额 + 扣减实际金额（Redis 原子操作）
    ↓
写入 PostgreSQL 费用记录
    ↓
    ├── 实际费用 > 冻结金额 → 告警 "超预算 ¥X"
    └── 实际消耗 = 冻结金额 → 正常
    ↓
返回结果给智能体
```

### 4.4 并发安全

```python
# 预算扣减的并发安全保障

# ❌ 错误做法（读写分离，有竞态）
balance = redis.get(f"budget:{user_id}")  # 读
balance -= cost
redis.set(f"budget:{user_id}", balance)    # 写 —— 可能被另一个请求覆盖！

# ✅ 正确做法（原子操作）
# Redis INCRBYFLOAT 是原子的，无需加锁
new_consumed = redis.incrbyfloat(f"budget:consumed:{user_id}:{period}", cost)

if new_consumed > monthly_budget:
    # 超额了（可能 concurrent calls 同时超）
    # 回滚本次扣费
    redis.incrbyfloat(f"budget:consumed:{user_id}:{period}", -cost)
    return BudgetDecision(status="rejected")
```

---

## 五、降级策略

### 5.1 模型价格阶梯

```
¥12/¥36  —  Qwen3.7-Max
¥8/¥28   —  GLM-5.2, GLM-5.1, GLM-5
¥6.5/¥27 —  Kimi K2.6
¥4/¥21   —  Kimi K2.5
¥4/¥16   —  Qwen3-Coder-Plus
¥3/¥6    —  DeepSeek V4-Pro
¥2.16/¥8.64 — MiniMax M3, M2.5
¥2/¥8    —  Qwen3.7-Plus
¥1/¥2    —  DeepSeek V4-Flash
¥0.5/¥2  —  Qwen3-Coder-Flash
¥0/¥0    —  GLM-4-Flash（免费！）
```

### 5.2 降级规则

```python
# 降级链：从高到低
DEGRADATION_CHAINS = {
    "deepseek-v4-pro":  ["deepseek-v4-flash", "qwen3-coder-flash", "glm-4-flash"],
    "glm-5.2":          ["deepseek-v4-pro", "deepseek-v4-flash", "glm-4-flash"],
    "kimi-k2.6":        ["kimi-k2.5", "deepseek-v4-flash", "glm-4-flash"],
    "qwen3.7-max":      ["qwen3.7-plus", "deepseek-v4-pro", "deepseek-v4-flash"],
    # ... 其他模型类似
}
```

### 5.3 预算分阶段策略

可以将月度预算分段，越到后期越偏向便宜模型：

```python
def budget_aware_model_selection(user_id: str, request: IncomingRequest, 
                                  consumed_pct: float) -> Model:
    """
    根据预算消耗比例选择模型
    
    Args:
        consumed_pct: 已消耗预算百分比 (0-100)
    """
    
    if consumed_pct < 50:
        # 预算宽裕：用最好的模型
        return "deepseek-v4-pro"
    
    elif consumed_pct < 75:
        # 预算正常：根据任务类型选择
        if request.task_type == "code_generation":
            return "deepseek-v4-pro"
        else:
            return "deepseek-v4-flash"
    
    elif consumed_pct < 90:
        # 预算紧张：默认用便宜的
        return "deepseek-v4-flash"
    
    else:
        # 预算告急：最便宜的，或免费
        return "glm-4-flash"  # 免费
```

---

## 六、可观测性

### 6.1 预算仪表盘

| 指标 | 显示内容 | 用途 |
|------|---------|------|
| 实时余额 | "¥523.46 / ¥800.00 (已用 34.6%)" | 用户自查 |
| 今日消费 | "¥12.34（预估月消费 ¥370.20）" | 消费趋势 |
| 消费排行 | "1. V4-Pro ¥312 / 2. GLM-5.2 ¥89 / ..." | 模型偏好分析 |
| 预算预警 | "按当前速度，预算将在 6月22日耗尽" | 预警 |
| 调用次数 | "本月 1,234 次，平均 ¥0.42/次" | 使用概况 |

### 6.2 告警规则

```yaml
alerts:
  - name: "月度预算即将耗尽"
    condition: "consumed_pct >= 80"
    severity: "warning"
    action: "发送企业微信/邮件通知用户"
  
  - name: "月度预算耗尽"
    condition: "consumed_pct >= 100"
    severity: "critical"
    action: "发送告警 + 自动降级到免费模型"
  
  - name: "单日消费异常"
    condition: "daily_cost > avg_daily * 3"
    severity: "info"
    action: "发送通知（可能是正常的大项目）"
  
  - name: "超额扣费"
    condition: "actual_cost > frozen_amount"
    severity: "warning"
    action: "记录超额日志 + 通知管理员"
```

---

## 七、管理接口

### 7.1 API 设计

```yaml
# 用户侧
GET  /api/v1/budget/status
  → {"monthly": 800.00, "consumed": 523.46, "remaining": 276.54,
     "frozen": 12.34, "available": 264.20, "consumed_pct": 65.4}

GET  /api/v1/budget/history?month=2026-06
  → {"records": [{"date":"2026-06-18","cost":12.34,"model":"deepseek-v4-pro",...}, ...],
     "total_cost": 523.46, "total_requests": 1234}

# 管理员侧
GET  /api/v1/admin/budgets
  → [{"user_id":"user_001", "monthly":800, "consumed":523.46, ...}, ...]

PUT  /api/v1/admin/budgets/{user_id}
  → {"monthly_budget": 1200.00}  # 调整预算

POST /api/v1/admin/budgets/{user_id}/reset
  → {"status":"ok", "previous_period":"2026-06", "total_consumed":523.46}

GET  /api/v1/admin/cost_records?user_id=xxx&start=2026-06-01&end=2026-06-18
  → 详细费用记录列表（支持按模型、协议、智能体分组统计）
```

### 7.2 管理员功能

- **查看全员预算消耗**：表格 + 柱状图，按消费金额排序
- **调整预算**：单独调整个别用户的月度预算（如实习生 200 元，高级工程师 2000 元）
- **强制重置**：手动重置某用户的预算（紧急情况）
- **预算预警名单**：列出本月已消耗 >80% 的用户
- **消费分析**：按模型/协议/智能体/小时的消费分布

---

## 八、800 元预算的实战推演

### 8.1 一个典型重度编程用户的月度账单

| 日期 | 场景 | 模型 | 输入 | 输出 | 费用 | 累计 |
|------|------|------|------|------|------|------|
| 6/1 | 新项目架构设计 | V4-Pro | 8,000 | 3,500 | ¥0.045 | ¥0.05 |
| 6/1 | 编写 50 个单元测试 | V4-Flash | 2,000 | 1,000 | ¥0.004 | ¥0.05 |
| 6/2 | 重构 3 个模块 | V4-Pro | 15,000 | 5,000 | ¥0.075 | ¥0.13 |
| 6/3 | Code Review（3 个 PR） | GLM-5.2 | 25,000 | 8,000 | ¥0.424 | ¥0.55 |
| 6/4 | Bug 修复（10 个） | V4-Flash | 5,000 | 2,000 | ¥0.009 | ¥0.56 |
| 6/5 | 长上下文分析整个项目 | Kimi K2.6 | 80,000 | 20,000 | ¥1.06 | ¥1.62 |
| ... | ... | ... | ... | ... | ... | ... |
| 6/18 | 至今 18 天 | 混用 | 统计 | 统计 | ¥380 | ¥380 |

**推测**：
- 轻度用户（每天 10 次简单调用）：月消费约 ¥50-100
- 中度用户（每天 30 次中等任务）：月消费约 ¥250-400
- 重度用户（每天 60 次，含大量长上下文）：月消费约 ¥500-700
- **800 元对于绝大多数编程场景来说是非常充裕的**

### 8.2 预算消耗预警时间线

```
800 元预算消耗曲线（典型重度用户）：

Day 1-5:     ¥80  (10%)   —正常
Day 6-10:    ¥200 (25%)   —正常
Day 11-15:   ¥360 (45%)   —正常
Day 16-20:   ¥550 (68%)   —正常
Day 21-25:   ¥720 (90%)   —【预警】自动切换 V4-Flash
Day 26-28:   ¥780 (97.5%) —【告急】自动切换 GLM-4-Flash（免费）
Day 29-30:   ¥800 (100%)  —【耗尽】402 硬拒绝
```

---

## 九、实施清单

| 优先级 | 任务 | 说明 |
|--------|------|------|
| **P0** | 预算表 + 费用表建表 | PostgreSQL schema |
| **P0** | 预算缓存到 Redis | 高频读写的性能保障 |
| **P0** | 预检逻辑（`pre_check`） | 请求前余额检查 + 预估 + 冻结 |
| **P0** | 实际扣费逻辑（`post_settle`） | 调用后按实际 Token 扣费 |
| **P0** | 预算耗尽 402 拒绝 | 硬拒绝实现 |
| **P1** | 降级策略 | 预算不足时自动切更便宜模型 |
| **P1** | 月度自动重置 | Cron job 每月 1 日 0:00 执行 |
| **P1** | 费用记录异步写入 | 不阻塞主流程 |
| **P1** | 预算查询 API | 用户自查接口 |
| **P2** | 管理后台 | 预算管理、费用分析、调整 |
| **P2** | 告警通知 | 预算 80% / 100% 告警 |
| **P2** | 消费仪表盘 | Grafana Dashboard |
| **P3** | 多级预算（日预算上限） | 精细粒度控制 |
| **P3** | 预算分阶段自动调整模型 | 越后期越偏便宜模型 |

---

## 十、核心结论

1. **800 元/月非常充裕**。重度编程用户也很难花完，大部分用户剩一半以上。

2. **预估-冻结-实际扣费三阶段模型**是最可靠的设计：
   - 预估保守（上浮 20%），保证余额判断的安全
   - 冻结避免并发调用同时超出预算
   - 实际扣费以厂商返回的 Token 数为准

3. **Redis + PostgreSQL 双写**是工程实践的最佳平衡：
   - Redis 负责高频原子扣减（保证并发安全 + 性能）
   - PostgreSQL 负责持久化审计（对账、分析、报表）

4. **降级策略让用户体验更平滑**：预算不足时不直接 402，而是自动切到便宜的模型，用户几乎无感知。

5. **免费模型（GLM-4-Flash）是兜底利器**：即便预算耗尽，仍有零成本模型可用，不会完全断服务。

---

*设计日期：2026-06-18*  
*版本：v1.0*
