# 企业级 API 中转站优化架构设计
## 支持多编程智能体与自动模型分配

> 基于《大模型接入协议研究_Review.md》和《API中转站协议转换架构讨论.md》，设计完整的企业级API中转站架构，重点优化：多智能体支持、自动模型分配、高可用、可观测性。

---

## 文档版本

| 版本 | 日期 | 说明 |
|------|------|------|
| v2.0 | 2026-06-18 | 初始版本，完整架构设计 |

---

## 一、架构设计目标

### 1.1 核心目标

| 目标 | 说明 | 衡量指标 |
|------|------|----------|
| **多协议支持** | 同时支持 Anthropic Messages、OpenAI Chat Completions、OpenAI Responses 三种入站协议 | 协议覆盖率 100% |
| **多模型接入** | 接入 DeepSeek、Qwen、GLM、Kimi、MiniMax 5 家厂商，每家双协议端点 | 模型可用率 >99.9% |
| **自动模型分配** | 基于任务特征、成本、性能、可用性自动选择最优模型 | 分配准确率 >85% |
| **多智能体隔离** | 支持 Claude Code、Codex、Cursor、Windsurf 等智能体并发调用 | 智能体数量无上限 |
| **高可用** | 故障自动降级、多副本部署、健康检查 | SLA >99.95% |
| **可观测性** | 全链路追踪、实时指标、告警 | 故障发现 <30s |

### 1.2 设计原则

1. **协议中立**：智能体不知道后端模型，模型不知道前端智能体
2. **零信任安全**：所有调用需认证、授权、审计
3. **成本透明**：每个智能体、每个用户的调用成本可追踪
4. **渐进式演进**：先支持同协议透传，再支持跨协议转换
5. **故障隔离**：单模型故障不影响其他模型，单智能体故障不影响其他智能体

---

## 二、整体架构设计

### 2.1 架构全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          企业级 API 中转站                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      接入层 (Ingress Layer)                           │  │
│  │                                                                      │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │  │
│  │  │ Anthropic    │  │ OpenAI Chat  │  │ OpenAI       │           │  │
│  │  │ Messages     │  │ Completions  │  │ Responses    │           │  │
│  │  │ /v1/messages │  │ /v1/chat/   │  │ /v1/responses│           │  │
│  │  └──────────────┘  │ completions  │  └──────────────┘           │  │
│  │                    └──────────────┘                              │  │
│  │                                                                      │  │
│  │ 智能体识别 → API Key 验证 → 速率限制 → 请求日志                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      协议适配层 (Protocol Adapter Layer)               │  │
│  │                                                                      │  │
│  │  ┌────────────────────────────────────────────────────────────┐    │  │
│  │  │               协议转换矩阵                                    │    │  │
│  │  ├────────────────────────────────────────────────────────────┤    │  │
│  │  │ Anthropic → Anthropic  │ 透传（仅 auth + 路由）          │    │  │
│  │  │ Chat → Chat              │ 透传（参数过滤）                 │    │  │
│  │  │ Responses → Responses    │ 透传（仅百炼）                  │    │  │
│  │  │ Anthropic → Chat         │ 格式转换 + SSE 流转换           │    │  │
│  │  │ Chat → Anthropic         │ 格式转换 + SSE 流转换           │    │  │
│  │  │ Responses → Chat         │ 状态机转换（复杂，V2 支持）      │    │  │
│  │  └────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │ 语义沟处理：thinking 块、cache_control、tool_choice 映射               │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      智能路由层 (Intelligent Routing Layer)            │  │
│  │                                                                      │  │
│  │  ┌────────────────────────────────────────────────────────────┐    │  │
│  │  │                  自动模型分配引擎                              │    │  │
│  │  ├────────────────────────────────────────────────────────────┤    │  │
│  │  │ 任务感知路由                                                │    │  │
│  │  │   ├── 代码生成 → DeepSeek V4-Pro / Qwen3-Coder-Plus      │    │  │
│  │  │   ├── 代码审查 → GLM-5.2 / Kimi K2.6                   │    │  │
│  │  │   ├── Bug 修复 → DeepSeek V4-Flash / GLM-4-Flash        │    │  │
│  │  │   └── 长上下文 → Kimi K2.6 / Qwen3.7-Max               │    │  │
│  │  │                                                              │    │  │
│  │  │ 成本感知路由                                                │    │  │
│  │  │   ├── 预算充足 → V4-Pro / GLM-5.2                       │    │  │
│  │  │   ├── 预算紧张 → V4-Flash / GLM-4-Flash                 │    │  │
│  │  │   └── 批量任务 → Kimi K2.5 / MiniMax M2.5              │    │  │
│  │  │                                                              │    │  │
│  │  │ 性能感知路由                                                │    │  │
│  │  │   ├── 低延迟要求 → DeepSeek V4-Flash (600+ TPS)          │    │  │
│  │  │   ├── 高质量要求 → DeepSeek V4-Pro / GLM-5.2             │    │  │
│  │  │   └── 均衡要求 → Qwen3.7-Plus                            │    │  │
│  │  │                                                              │    │  │
│  │  │ 可用性感知路由                                              │    │  │
│  │  │   ├── 主模型健康 → 直接使用                                │    │  │
│  │  │   ├── 主模型降级 → 自动切换到备用模型                      │    │  │
│  │  │   └── 全部降级 → 返回 503 + 降级模型列表                  │    │  │
│  │  └────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │ 路由策略配置：智能体级、用户级、会话级、请求级                        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      模型管理層 (Model Management Layer)               │  │
│  │                                                                      │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │  │
│  │  │ DeepSeek     │  │ Qwen (百炼)  │  │ GLM (智谱)   │           │  │
│  │  │ ├── V4-Pro   │  │ ├── 3.7-Max  │  │ ├── GLM-5.2  │           │  │
│  │  │ └── V4-Flash │  │ ├── 3.7-Plus │  │ ├── GLM-5.1  │           │  │
│  │  │              │  │ └── 3.6-Flash│  │ └── 4.7-Flash│           │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │  │
│  │                                                                      │  │
│  │  ┌──────────────┐  ┌──────────────┐                              │  │
│  │  │ Kimi         │  │ MiniMax      │                              │  │
│  │  │ ├── K2.7-Code│  │ ├── M3       │                              │  │
│  │  │ ├── K2.6     │  │ ├── M2.5     │                              │  │
│  │  │ └── K2.5     │  │ └── M2.1     │                              │  │
│  │  └──────────────┘  └──────────────┘                              │  │
│  │                                                                      │  │
│  │ 健康检查 │ 负载均衡 │ 故障降级 │ 模型版本管理                          │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      出站层 (Egress Layer)                            │  │
│  │                                                                      │  │
│  │  ┌────────────────────────────────────────────────────────────┐    │  │
│  │  │               协议端点选择                                    │    │  │
│  │  ├────────────────────────────────────────────────────────────┤    │  │
│  │  │ DeepSeek                                                    │    │  │
│  │  │   ├── Anthropic: api.deepseek.com/anthropic              │    │  │
│  │  │   └── OpenAI: api.deepseek.com/v1                        │    │  │
│  │  │                                                              │    │  │
│  │  │ Qwen (百炼)                                                  │    │  │
│  │  │   ├── Anthropic: dashscope.aliyuncs.com/apps/anthropic  │    │  │
│  │  │   └── OpenAI: dashscope.aliyuncs.com/compatible-mode/v1 │    │  │
│  │  │                                                              │    │  │
│  │  │ GLM (智谱)                                                   │    │  │
│  │  │   ├── Anthropic: open.bigmodel.cn/api/anthropic          │    │  │
│  │  │   └── OpenAI: open.bigmodel.cn/api/paas/v4              │    │  │
│  │  │                                                              │    │  │
│  │  │ Kimi                                                         │    │  │
│  │  │   ├── Anthropic: api.moonshot.cn/anthropic               │    │  │
│  │  │   └── OpenAI: api.moonshot.cn/v1                         │    │  │
│  │  │                                                              │    │  │
│  │  │ MiniMax                                                      │    │  │
│  │  │   ├── Anthropic: api.minimax.io/anthropic                │    │  │
│  │  │   └── OpenAI: api.minimax.io/v1                          │    │  │
│  │  └────────────────────────────────────────────────────────────┘    │  │
│  │                                                                      │  │
│  │ 请求签名 │ TLS 双向认证 │ 重试策略 │ 超时控制                      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      治理层 (Governance Layer)                        │  │
│  │                                                                      │  │
│  │  多租户管理 │ Token 计量计费 │ 审计日志 │ 敏感信息脱敏 │ 合规检查       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                    ↓                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      可观测层 (Observability Layer)                    │  │
│  │                                                                      │  │
│  │  指标监控 │ 链路追踪 │ 日志聚合 │ 告警通知 │ 仪表盘 │ 性能分析       │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 分层说明

| 层级 | 名称 | 核心职责 | 技术选型建议 |
|------|------|----------|--------------|
| L1 | 接入层 | 协议识别、认证、限流、日志 | Envoy/Nginx (API Gateway) |
| L2 | 协议适配层 | 协议转换、SSE 流转换、语义沟处理 | 自研 Adapter (Go/Python) |
| L3 | 智能路由层 | 自动模型分配、路由策略执行 | 自研 Router (Go/Python) |
| L4 | 模型管理层 | 模型注册、健康检查、负载均衡 | 自研 Manager + Redis |
| L5 | 出站层 | 请求签名、重试、超时控制 | 自研 Egress (Go/Python) |
| L6 | 治理层 | 多租户、计费、审计、合规 | 自研 Governance + PostgreSQL |
| L7 | 可观测层 | 监控、追踪、日志、告警 | Prometheus + Grafana + Jaeger |

---

## 三、智能路由层详细设计

### 3.1 自动模型分配引擎

这是优化架构的核心。分配引擎基于多维度决策：

```python
class IntelligentRouter:
    """智能路由引擎"""
    
    def route(self, request: IncomingRequest) -> RoutingDecision:
        """
        基于多维度决策选择最优模型
        
        决策维度：
        1. 任务类型（从请求内容、工具调用、system prompt 推断）
        2. 成本约束（用户/租户的预算限制）
        3. 性能要求（延迟、吞吐量）
        4. 模型可用性（实时健康状态）
        5. 历史表现（模型在该任务类型上的历史成功率）
        """
        
        # Step 1: 提取请求特征
        features = self.extract_features(request)
        # features = {
        #   "agent_type": "claude-code",
        #   "task_type": "code_generation",  # 推断得出
        #   "context_length": 15000,
        #   "tool_calls_count": 3,
        #   "has_images": False,
        #   "urgency": "normal",  # normal, high, low
        #   "user_id": "user_123",
        #   "session_id": "sess_456"
        # }
        
        # Step 2: 应用路由规则（优先级：请求级 > 会话级 > 用户级 > 智能体级 > 全局默认）
        routing_rules = self.get_routing_rules(request, features)
        
        # Step 3: 过滤可用模型（基于协议兼容性、模型能力）
        compatible_models = self.filter_compatible_models(
            request_protocol=request.protocol,
            required_capabilities=features["required_capabilities"]
        )
        
        # Step 4: 评分与排序
        scored_models = []
        for model in compatible_models:
            score = self.score_model(model, features, routing_rules)
            scored_models.append((model, score))
        
        scored_models.sort(key=lambda x: x[1], reverse=True)
        
        # Step 5: 选择最优模型 + 备用模型
        primary_model = scored_models[0][0]
        fallback_models = [m for m, _ in scored_models[1:3]]  # 取前 2 个备用
        
        return RoutingDecision(
            primary=primary_model,
            fallbacks=fallback_models,
            reason=self.explain_decision(primary_model, features, routing_rules)
        )
    
    def score_model(self, model: Model, features: dict, rules: RoutingRules) -> float:
        """多维度评分"""
        score = 0.0
        
        # 维度 1: 任务匹配度 (权重 0.3)
        task_score = self.calculate_task_match(model, features["task_type"])
        score += 0.3 * task_score
        
        # 维度 2: 成本效率 (权重 0.25)
        cost_score = self.calculate_cost_efficiency(model, features["context_length"])
        score += 0.25 * cost_score
        
        # 维度 3: 性能指标 (权重 0.2)
        perf_score = self.calculate_performance(model, features["urgency"])
        score += 0.2 * perf_score
        
        # 维度 4: 可用性 (权重 0.15)
        avail_score = self.calculate_availability(model)
        score += 0.15 * avail_score
        
        # 维度 5: 历史表现 (权重 0.1)
        history_score = self.calculate_history_performance(model, features["task_type"])
        score += 0.1 * history_score
        
        return score
```

### 3.2 任务类型识别

| 任务类型 | 识别特征 | 推荐模型 | 优先级 |
|---------|---------|---------|--------|
| **代码生成** | system prompt 含 "code" "implement" "write"，工具调用含 `write_file` `create_file` | DeepSeek V4-Pro / Qwen3-Coder-Plus | P0 |
| **代码审查** | system prompt 含 "review" "refactor"，工具调用含 `read_file` | GLM-5.2 / Kimi K2.6 | P0 |
| **Bug 修复** | system prompt 含 "fix" "debug" "error"，工具调用含 `run_terminal_cmd` | DeepSeek V4-Flash / GLM-4-Flash | P0 |
| **长上下文理解** | `context_length` > 32K | Kimi K2.6 (128K) / Qwen3.7-Max (128K) | P1 |
| **多工具编排** | `tool_calls_count` > 5 | DeepSeek V4-Pro (tool calling 强) | P1 |
| **图像理解** | `has_images` = True | MiniMax M3 / Qwen3.7-Max | P2 |
| **批量任务** | `urgency` = "low"，请求来自批量脚本 | Kimi K2.5 / MiniMax M2.5 | P2 |

### 3.3 成本感知路由

```python
class CostAwareRouter:
    """成本感知路由"""
    
    # 模型成本表（元/百万 Tokens）
    PRICING = {
        "deepseek-v4-pro": {"input": 3.0,   "output": 6.0,   "cache_hit": 0.025},
        "deepseek-v4-flash": {"input": 1.0,   "output": 2.0,   "cache_hit": 0.02},
        "qwen3.7-max":      {"input": 12.0,  "output": 36.0,  "cache_hit": 2.4},
        "qwen3.7-plus":     {"input": 2.0,   "output": 8.0,   "cache_hit": 0.4},
        "qwen3-coder-plus": {"input": 7.34,  "output": 36.70, "cache_hit": 1.47},
        "qwen3-coder-flash":{"input": 0.5,   "output": 2.0,   "cache_hit": 0.10},
        "glm-5.2":          {"input": 0.0,   "output": 0.0,   "cache_hit": 0.0},     # 限免
        "glm-5.1":          {"input": 10.1,  "output": 31.7,  "cache_hit": 2.5},
        "glm-4.7-flash":    {"input": 0.0,   "output": 0.0,   "cache_hit": 0.0},     # 免费
        "kimi-k2.7-code":   {"input": 6.5,   "output": 27.0,  "cache_hit": 1.30},
        "kimi-k2.6":        {"input": 6.5,   "output": 27.0,  "cache_hit": 1.10},
        "kimi-k2.5":        {"input": 4.0,   "output": 21.0,  "cache_hit": 0.70},
        "minimax-m3":       {"input": 2.16,  "output": 8.64,  "cache_hit": 0.43},
        "minimax-m2.5":     {"input": 2.16,  "output": 8.64,  "cache_hit": 0.22},
    }
    
    def estimate_cost(self, model: str, context_length: int, expected_output_length: int = 1000) -> float:
        """估算单次调用成本（元）"""
        pricing = self.PRICING[model]
        input_cost = (context_length / 1_000_000) * pricing["input"]
        output_cost = (expected_output_length / 1_000_000) * pricing["output"]
        return input_cost + output_cost
    
    def route_with_budget(self, request: IncomingRequest, budget: float) -> Model:
        """
        在预算约束下选择最优模型
        
        Args:
            budget: 本次调用的预算上限（元）
        """
        compatible_models = self.get_compatible_models(request)
        
        # 过滤：只保留在预算内的模型
        affordable_models = []
        for model in compatible_models:
            estimated_cost = self.estimate_cost(
                model, 
                request.context_length,
                request.expected_output_length
            )
            if estimated_cost <= budget:
                affordable_models.append((model, estimated_cost))
        
        if not affordable_models:
            # 预算不足，选择最便宜的模型
            cheapest = min(compatible_models, key=lambda m: self.estimate_cost(m, request.context_length))
            return cheapest, "budget_exceeded"
        
        # 在预算内选择性能最好的
        best = max(affordable_models, key=lambda x: self.performance_score(x[0]))
        return best[0], "budget_aware"
```

### 3.4 可用性感知路由

```python
class AvailabilityAwareRouter:
    """可用性感知路由"""
    
    def __init__(self):
        self.health_checker = HealthChecker()
        self.circuit_breaker = CircuitBreaker()
    
    def route_with_availability(self, request: IncomingRequest) -> RoutingDecision:
        """基于实时可用性路由"""
        
        # Step 1: 获取所有兼容模型
        compatible_models = self.get_compatible_models(request)
        
        # Step 2: 过滤掉不健康的模型
        healthy_models = []
        for model in compatible_models:
            health = self.health_checker.get_health(model)
            if health.status == "healthy" and self.circuit_breaker.is_closed(model):
                healthy_models.append(model)
        
        if not healthy_models:
            # 所有模型都不健康，触发告警，返回最不健康的（总比没有好）
            self.alert("All models unhealthy!")
            return self.fallback_to_least_unhealthy(compatible_models)
        
        # Step 3: 检查主模型是否健康
        primary = healthy_models[0]
        if self.health_checker.get_latency(primary) > request.max_latency:
            # 主模型延迟过高，切换到备用
            return healthy_models[1], "latency_degraded"
        
        return primary, "healthy"
```

### 3.5 路由策略配置

支持多级配置，优先级从高到低：

```yaml
# 全局默认策略 (config/default_routing.yaml)
global_default:
  strategy: "cost_aware"  # cost_aware | performance_aware | availability_aware | balanced
  fallback_chain:
    - "deepseek-v4-flash"
    - "glm-4-flash"
    - "kimi-k2.5"

# 智能体级策略 (config/agent_routing.yaml)
agent_strategies:
  claude-code:
    strategy: "performance_aware"
    preferred_models:
      - "deepseek-v4-pro"
      - "glm-5.2"
    fallback_chain:
      - "deepseek-v4-flash"
      - "kimi-k2.6"
  
  cursor:
    strategy: "cost_aware"
    preferred_models:
      - "deepseek-v4-flash"
      - "qwen3-coder-flash"
    fallback_chain:
      - "glm-4-flash"
  
  codex:
    strategy: "balanced"
    preferred_models:
      - "qwen3.7-max"  # 百炼支持 Responses API
      - "deepseek-v4-pro"
    fallback_chain:
      - "deepseek-v4-flash"

# 用户级策略 (存储在数据库)
user_strategies:
  - user_id: "user_123"
    strategy: "cost_aware"
    max_cost_per_request: 0.5  # 元
    preferred_models: ["deepseek-v4-flash", "glm-4-flash"]

# 会话级策略 (存储在 Redis)
session_strategies:
  - session_id: "sess_456"
    strategy: "performance_aware"
    override_models: ["deepseek-v4-pro"]  # 强制使用 V4-Pro

# 请求级策略 (从请求头解析)
request_strategies:
  - header: "X-Routing-Strategy"
    values:
      - "cost_aware": 成本优先
      - "performance_aware": 性能优先
      - "availability_aware": 可用性优先
```

---

## 四、多智能体管理设计

### 4.1 智能体注册与识别

```python
class AgentManager:
    """智能体管理器"""
    
    def identify_agent(self, request: IncomingRequest) -> AgentProfile:
        """
        识别智能体类型
        
        识别方式（按优先级）：
        1. 请求头 `User-Agent` (最可靠)
        2. 请求头 `X-Agent-Type` (中转站自定义)
        3. 请求特征推断（协议类型 + 工具调用模式）
        """
        
        # Method 1: User-Agent
        user_agent = request.headers.get("User-Agent", "")
        if "Claude-Code" in user_agent:
            return AgentProfile(type="claude-code", protocol="anthropic")
        if "Codex" in user_agent:
            return AgentProfile(type="codex", protocol="openai-responses")
        if "Cursor" in user_agent:
            return AgentProfile(type="cursor", protocol="openai-chat")
        if "Windsurf" in user_agent:
            return AgentProfile(type="windsurf", protocol="openai-chat")
        
        # Method 2: Custom header
        agent_type = request.headers.get("X-Agent-Type")
        if agent_type:
            return self.get_agent_profile(agent_type)
        
        # Method 3: Infer from request features
        return self.infer_agent_type(request)
```

### 4.2 智能体隔离

```python
class AgentIsolationManager:
    """智能体隔离管理器"""
    
    def isolate_agent(self, agent_type: str, request: IncomingRequest):
        """
        为智能体提供隔离环境
        
        隔离维度：
        1. 连接池隔离：每个智能体使用独立的 HTTP 连接池
        2. 限流隔离：每个智能体有独立的速率限制
        3. 日志隔离：日志中标记智能体类型，便于排查
        4. 配额隔离：每个智能体/用户可以设置独立的配额
        """
        
        # 1. 连接池隔离
        connection_pool = self.get_or_create_pool(
            agent_type=agent_type,
            max_connections=1000,
            max_connections_per_host=100
        )
        
        # 2. 限流隔离
        rate_limiter = self.get_or_create_limiter(
            agent_type=agent_type,
            max_requests_per_minute=1000,
            max_tokens_per_minute=100_000
        )
        
        # 3. 配额隔离
        quota_manager = self.get_or_create_quota_manager(
            agent_type=agent_type,
            user_id=request.user_id,
            daily_quota=100_000_000  # Tokens
        )
        
        return IsolatedContext(
            connection_pool=connection_pool,
            rate_limiter=rate_limiter,
            quota_manager=quota_manager
        )
```

### 4.3 智能体配置管理

```yaml
# config/agents.yaml
agents:
  claude-code:
    display_name: "Claude Code"
    protocol: "anthropic"
    default_model: "deepseek-v4-pro"
    fallback_models: ["deepseek-v4-flash", "glm-5.2"]
    max_context_length: 128000
    supports:
      - "tool_calling"
      - "thinking_blocks"
      - "cache_control"
    rate_limit:
      requests_per_minute: 1000
      tokens_per_minute: 100000
    
  codex:
    display_name: "Codex CLI"
    protocol: "openai-responses"  # 优先，如不支持则降级到 openai-chat
    fallback_protocol: "openai-chat"
    default_model: "qwen3.7-max"  # 百炼支持 Responses API
    fallback_models: ["deepseek-v4-pro", "kimi-k2.6"]
    max_context_length: 128000
    supports:
      - "tool_calling"
      - "previous_response_id"
      - "reasoning"
    rate_limit:
      requests_per_minute: 500
      tokens_per_minute: 50000
    
  cursor:
    display_name: "Cursor IDE"
    protocol: "openai-chat"
    default_model: "deepseek-v4-flash"
    fallback_models: ["qwen3-coder-flash", "glm-4-flash"]
    max_context_length: 64000
    supports:
      - "tool_calling"
      - "apply_model"  # Cursor 专用的 Apply 模型
    rate_limit:
      requests_per_minute: 2000
      tokens_per_minute: 200000
```

---

## 五、协议适配层优化设计

### 5.1 协议转换矩阵（完整版）

| 入站协议 | 出站协议 | 转换难度 | 推荐策略 | 注意事项 |
|---------|---------|---------|---------|---------|
| Anthropic | Anthropic | ⭐ 透传 | 优先 | 仅替换 auth + 路由 |
| OpenAI Chat | OpenAI Chat | ⭐ 透传 | 优先 | 参数过滤（忽略目标模型不支持的参数） |
| OpenAI Responses | OpenAI Responses | ⭐ 透传 | 仅百炼 | 需要状态管理（previous_response_id） |
| Anthropic | OpenAI Chat | ⭐⭐⭐ 中等 | 需要时转换 | SSE 流转换复杂，需拼装 tool_calls |
| OpenAI Chat | Anthropic | ⭐⭐⭐ 中等 | 需要时转换 | system 消息提取，tool_calls 格式转换 |
| OpenAI Responses | OpenAI Chat | ⭐⭐⭐⭐⭐ 极难 | V2 支持 | 需要完整状态机，维护对话历史 |
| OpenAI Responses | Anthropic | ⭐⭐⭐⭐⭐ 极难 | 不支持 | 语义沟太大，建议避免 |

### 5.2 协议转换最佳实践

```python
class ProtocolAdapter:
    """协议适配器"""
    
    def adapt(self, request: IncomingRequest) -> OutgoingRequest:
        """
        协议转换入口
        
        策略：
        1. 同协议 → 透传
        2. 跨协议 → 转换（如无法实现则返回 400）
        3. 语义沟 → 降级（忽略不支持的字段，或返回 400）
        """
        
        inbound_protocol = request.protocol
        outbound_protocol = self.get_outbound_protocol(request.routing_decision)
        
        if inbound_protocol == outbound_protocol:
            return self.passthrough(request)
        
        # 跨协议转换
        if inbound_protocol == "anthropic" and outbound_protocol == "openai-chat":
            return self.anthropic_to_openai_chat(request)
        elif inbound_protocol == "openai-chat" and outbound_protocol == "anthropic":
            return self.openai_chat_to_anthropic(request)
        elif inbound_protocol == "openai-responses" and outbound_protocol == "openai-chat":
            return self.responses_to_openai_chat(request)
        else:
            raise UnsupportedConversionError(
                f"Cannot convert {inbound_protocol} to {outbound_protocol}"
            )
    
    def anthropic_to_openai_chat(self, request: IncomingRequest) -> OutgoingRequest:
        """Anthropic Messages → OpenAI Chat Completions"""
        
        # 1. 转换 messages
        openai_messages = []
        
        # 1.1 system 字段处理
        if request.body.get("system"):
            system_content = self.flatten_anthropic_system(request.body["system"])
            openai_messages.insert(0, {"role": "system", "content": system_content})
        
        # 1.2 普通 messages
        for msg in request.body["messages"]:
            openai_messages.append(self.convert_message(msg))
        
        # 2. 转换 tools
        openai_tools = []
        if request.body.get("tools"):
            for tool in request.body["tools"]:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {})
                    }
                })
        
        # 3. 转换 tool_choice
        tool_choice = self.convert_tool_choice(request.body.get("tool_choice"))
        
        # 4. 构建出站请求
        outbound = OutgoingRequest(
            protocol="openai-chat",
            endpoint="/v1/chat/completions",
            headers=self.build_openai_headers(request),
            body={
                "model": request.routing_decision.model,
                "messages": openai_messages,
                "tools": openai_tools if openai_tools else None,
                "tool_choice": tool_choice,
                "max_tokens": request.body.get("max_tokens"),
                "temperature": request.body.get("temperature"),
                "top_p": request.body.get("top_p"),
                "stream": request.body.get("stream", False),
                # 注意：thinking, cache_control 等字段在 OpenAI Chat 中无等价物，需忽略
            }
        )
        
        return outbound
```

### 5.3 SSE 流转换核心代码

```python
class SSEStreamConverter:
    """SSE 流转换器"""
    
    def anthropic_to_openai_chat_sse(self, anthropic_stream: Iterator[str]) -> Iterator[str]:
        """
        Anthropic SSE 流 → OpenAI Chat Completions SSE 流
        
        核心挑战：
        1. Anthropic 的 content_block 需要转换为 OpenAI 的 delta
        2. Anthropic 的 tool_use 需要拼装为 OpenAI 的 tool_calls
        3. 事件顺序不同，需要缓冲和重组
        """
        
        # 状态变量
        current_tool_call_id = None
        current_tool_name = None
        current_tool_arguments = ""
        
        for event in anthropic_stream:
            event_type, event_data = self.parse_anthropic_event(event)
            
            if event_type == "message_start":
                # OpenAI 无对应事件，跳过或生成 chatcmpl 起始事件
                yield self.openai_chunk(
                    id=event_data["message"]["id"],
                    delta={"role": "assistant"}
                )
            
            elif event_type == "content_block_start":
                block = event_data["content_block"]
                if block["type"] == "tool_use":
                    current_tool_call_id = block["id"]
                    current_tool_name = block["name"]
                    current_tool_arguments = ""
                    
                    yield self.openai_chunk(
                        delta={
                            "tool_calls": [{
                                "index": event_data["index"],
                                "id": current_tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": current_tool_name,
                                    "arguments": ""
                                }
                            }]
                        }
                    )
            
            elif event_type == "content_block_delta":
                delta = event_data["delta"]
                if delta["type"] == "text_delta":
                    yield self.openai_chunk(
                        delta={"content": delta["text"]}
                    )
                elif delta["type"] == "input_json_delta":
                    current_tool_arguments += delta["partial_json"]
                    yield self.openai_chunk(
                        delta={
                            "tool_calls": [{
                                "index": event_data["index"],
                                "function": {
                                    "arguments": delta["partial_json"]
                                }
                            }]
                        }
                    )
            
            elif event_type == "content_block_stop":
                # 一个 content block 结束，无需特殊处理
                pass
            
            elif event_type == "message_delta":
                # 提取 stop_reason 和 usage
                stop_reason = self.map_stop_reason(event_data["delta"]["stop_reason"])
                usage = event_data.get("usage", {})
                
                yield self.openai_chunk(
                    delta={},
                    finish_reason=stop_reason,
                    usage={
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0)
                    }
                )
            
            elif event_type == "message_stop":
                yield "data: [DONE]\n\n"
    
    def openai_chat_to_anthropic_sse(self, openai_stream: Iterator[str]) -> Iterator[str]:
        """OpenAI Chat Completions SSE 流 → Anthropic Messages SSE 流"""
        
        # 状态变量
        content_index = 0
        tool_index = 1
        current_content = ""
        
        for chunk in openai_stream:
            chunk_data = self.parse_openai_chunk(chunk)
            
            if chunk_data["choices"][0]["delta"].get("role"):
                # 起始事件
                yield self.anthropic_event(
                    "message_start",
                    {"type": "message_start", "message": {"id": chunk_data["id"], ...}}
                )
            
            if chunk_data["choices"][0]["delta"].get("content"):
                content = chunk_data["choices"][0]["delta"]["content"]
                current_content += content
                
                yield self.anthropic_event(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": content_index,
                        "delta": {"type": "text_delta", "text": content}
                    }
                )
            
            if chunk_data["choices"][0]["delta"].get("tool_calls"):
                tool_call = chunk_data["choices"][0]["delta"]["tool_calls"][0]
                
                if "function" in tool_call and "name" in tool_call["function"]:
                    # 新的 tool call 开始
                    yield self.anthropic_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": tool_index,
                            "content_block": {
                                "type": "tool_use",
                                "id": tool_call["id"],
                                "name": tool_call["function"]["name"],
                                "input": {}
                            }
                        }
                    )
                
                if "function" in tool_call and "arguments" in tool_call["function"]:
                    # tool call arguments 增量
                    yield self.anthropic_event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": tool_index,
                            "delta": {
                                "type": "input_json_delta",
                                "partial_json": tool_call["function"]["arguments"]
                            }
                        }
                    )
            
            if chunk_data["choices"][0].get("finish_reason"):
                yield self.anthropic_event(
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": self.reverse_map_stop_reason(
                                chunk_data["choices"][0]["finish_reason"]
                            )
                        },
                        "usage": chunk_data.get("usage", {})
                    }
                )
                yield self.anthropic_event("message_stop", {"type": "message_stop"})
                yield "event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n"
```

---

## 六、高可用设计

### 6.1 故障降级链

```
主模型 (Primary)
    ↓ 429 / 503 / 超时
备用模型 1 (Fallback 1)
    ↓ 同样故障
备用模型 2 (Fallback 2)
    ↓ 同样故障
返回 503 + 可用模型列表
```

**配置示例：**

```yaml
# config/fallback_chains.yaml
fallback_chains:
  deepseek-v4-pro:
    - "glm-5.2"
    - "kimi-k2.6"
    - "deepseek-v4-flash"
  
  deepseek-v4-flash:
    - "glm-4-flash"
    - "qwen3-coder-flash"
    - "kimi-k2.5"
  
  glm-5.2:
    - "deepseek-v4-pro"
    - "kimi-k2.6"
    - "qwen3.7-plus"
  
  kimi-k2.6:
    - "deepseek-v4-pro"
    - "glm-5.2"
    - "qwen3.7-max"
```

### 6.2 健康检查

```python
class HealthChecker:
    """健康检查器"""
    
    def __init__(self):
        self.models = {...}  # 所有注册的模型
        self.health_status = {}  # 缓存健康状态
        self.check_interval = 30  # 秒
    
    async def start_health_check_loop(self):
        """启动健康检查循环"""
        while True:
            for model in self.models:
                try:
                    health = await self.check_model_health(model)
                    self.health_status[model.id] = health
                except Exception as e:
                    self.health_status[model.id] = HealthStatus(
                        status="unhealthy",
                        error=str(e)
                    )
            
            await asyncio.sleep(self.check_interval)
    
    async def check_model_health(self, model: Model) -> HealthStatus:
        """检查单个模型的健康状态"""
        
        # 1. 发送轻量级探针请求
        probe_request = {
            "model": model.default_model_name,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 10,
            "stream": False
        }
        
        start_time = time.time()
        try:
            response = await self.send_request(model, probe_request, timeout=5)
            latency = (time.time() - start_time) * 1000  # ms
            
            return HealthStatus(
                status="healthy",
                latency_ms=latency,
                last_check=time.time(),
                error=None
            )
        except TimeoutError:
            return HealthStatus(
                status="degraded",
                latency_ms=5000,
                last_check=time.time(),
                error="Timeout"
            )
        except Exception as e:
            return HealthStatus(
                status="unhealthy",
                latency_ms=-1,
                last_check=time.time(),
                error=str(e)
            )
```

### 6.3 熔断器模式

```python
class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = {}
        self.last_failure_time = {}
        self.state = {}  # "closed" | "open" | "half-open"
    
    def is_closed(self, model: str) -> bool:
        """检查熔断器是否关闭（允许请求）"""
        
        if model not in self.state:
            self.state[model] = "closed"
        
        if self.state[model] == "closed":
            return True
        
        if self.state[model] == "open":
            # 检查是否进入 half-open 状态
            if time.time() - self.last_failure_time[model] > self.recovery_timeout:
                self.state[model] = "half-open"
                return True
            return False
        
        if self.state[model] == "half-open":
            return True
        
        return False
    
    def record_success(self, model: str):
        """记录成功请求"""
        self.failure_count[model] = 0
        self.state[model] = "closed"
    
    def record_failure(self, model: str):
        """记录失败请求"""
        self.failure_count[model] = self.failure_count.get(model, 0) + 1
        self.last_failure_time[model] = time.time()
        
        if self.failure_count[model] >= self.failure_threshold:
            self.state[model] = "open"
```

---

## 七、可观测性设计

### 7.1 指标监控

| 指标类型 | 指标名称 | 说明 | 告警阈值 |
|---------|---------|------|---------|
| **流量指标** | `requests_total` | 总请求数 | - |
|  | `requests_per_second` | 每秒请求数 | >1000 告警 |
|  | `errors_total` | 总错误数 | error_rate >5% 告警 |
| **延迟指标** | `latency_p50` | P50 延迟 | >2s 告警 |
|  | `latency_p95` | P95 延迟 | >5s 告警 |
|  | `latency_p99` | P99 延迟 | >10s 告警 |
| **模型指标** | `model_requests_total{model="xxx"}` | 各模型请求数 | - |
|  | `model_latency_p95{model="xxx"}` | 各模型 P95 延迟 | >8s 告警 |
|  | `model_error_rate{model="xxx"}` | 各模型错误率 | >10% 告警 |
| **成本指标** | `cost_total{user="xxx"}` | 用户总成本 | 超预算 80% 告警 |
|  | `cost_per_request{model="xxx"}` | 各模型单请求成本 | - |
| **智能体指标** | `agent_requests_total{agent="xxx"}` | 各智能体请求数 | - |
|  | `agent_error_rate{agent="xxx"}` | 各智能体错误率 | >10% 告警 |

### 7.2 链路追踪

```python
class TracingMiddleware:
    """链路追踪中间件"""
    
    def __init__(self, tracer: Tracer):
        self.tracer = tracer
    
    async def __call__(self, request: IncomingRequest, call_next):
        # 创建根 span
        with self.tracer.start_span("api_request") as span:
            span.set_attribute("agent.type", request.agent_type)
            span.set_attribute("request.protocol", request.protocol)
            span.set_attribute("request.size", len(request.body))
            
            # 路由决策 span
            with self.tracer.start_span("routing_decision") as routing_span:
                routing_decision = self.router.route(request)
                routing_span.set_attribute("model.primary", routing_decision.primary)
                routing_span.set_attribute("model.fallback", routing_decision.fallback)
            
            # 协议转换 span
            if request.protocol != routing_decision.outbound_protocol:
                with self.tracer.start_span("protocol_conversion") as convert_span:
                    outbound_request = self.adapter.adapt(request, routing_decision)
                    convert_span.set_attribute("conversion.type", 
                        f"{request.protocol}_to_{routing_decision.outbound_protocol}")
            
            # 模型调用 span
            with self.tracer.start_span("model_call") as model_span:
                response = await self.call_model(outbound_request, routing_decision)
                model_span.set_attribute("response.latency", response.latency)
                model_span.set_attribute("response.status", response.status_code)
            
            return response
```

### 7.3 日志聚合

```yaml
# logging configuration
logging:
  format: "json"  # 结构化日志，便于 ELK 解析
  level: "INFO"
  
  # 日志字段
  fields:
    - "timestamp"
    - "level"
    - "request_id"       # 全链路追踪 ID
    - "agent_type"        # 智能体类型
    - "user_id"           # 用户 ID
    - "session_id"        # 会话 ID
    - "model"             # 使用的模型
    - "protocol.inbound"  # 入站协议
    - "protocol.outbound" # 出站协议
    - "latency_ms"        # 延迟
    - "cost_yuan"         # 成本
    - "error"             # 错误信息
  
  # 敏感信息脱敏
  redact:
    - "api_key"
    - "authorization"
    - "password"
    - "token"
```

---

## 八、安全与治理设计

### 8.1 认证与授权

```python
class AuthManager:
    """认证与授权管理器"""
    
    def authenticate(self, request: IncomingRequest) -> AuthResult:
        """
        认证方式：
        1. API Key（最简单，推荐）
        2. JWT Token（支持细粒度权限）
        3. OAuth 2.0（企业级，支持 SSO）
        """
        
        # Method 1: API Key
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        if api_key:
            return self.authenticate_api_key(api_key)
        
        # Method 2: JWT Token
        jwt_token = request.headers.get("X-JWT-Token")
        if jwt_token:
            return self.authenticate_jwt(jwt_token)
        
        raise AuthenticationError("No valid authentication found")
    
    def authorize(self, auth_result: AuthResult, request: IncomingRequest) -> bool:
        """
        授权检查：
        
        权限模型：
        1. 用户级权限：用户可以调用哪些模型
        2. 智能体级权限：智能体可以调用哪些模型
        3. 速率限制：用户/智能体的 QPS、Token 限制
        4. 成本限制：用户/智能体的成本预算
        """
        
        # 检查模型权限
        if not self.has_model_permission(auth_result.user_id, request.routing_decision.model):
            raise AuthorizationError(f"User {auth_result.user_id} not allowed to use model {request.routing_decision.model}")
        
        # 检查速率限制
        if not self.check_rate_limit(auth_result.user_id, request.agent_type):
            raise RateLimitError("Rate limit exceeded")
        
        # 检查成本预算
        if not self.check_cost_budget(auth_result.user_id, request.estimated_cost):
            raise BudgetExceededError("Cost budget exceeded")
        
        return True
```

### 8.2 审计日志

```python
class AuditLogger:
    """审计日志器"""
    
    def log_request(self, request: IncomingRequest, auth_result: AuthResult):
        """记录请求审计日志"""
        
        audit_log = {
            "timestamp": time.time(),
            "request_id": request.request_id,
            "user_id": auth_result.user_id,
            "agent_type": request.agent_type,
            "model": request.routing_decision.model,
            "protocol": request.protocol,
            "request_size": len(request.body),
            "estimated_cost": request.estimated_cost,
            "action": "model_call"
        }
        
        # 写入审计日志存储（不可篡改）
        self.audit_store.append(audit_log)
        
        # 同时写入普通日志（用于排查）
        self.logger.info("Audit log", extra=audit_log)
```

### 8.3 敏感信息脱敏

```python
class SensitiveDataRedactor:
    """敏感信息脱敏器"""
    
    def redact(self, text: str) -> str:
        """
        脱敏规则：
        1. API Key / Token → 替换为 ***
        2. 密码 → 替换为 ***
        3. 身份证号 → 替换为 ***
        4. 手机号 → 替换为 ***
        5. 邮箱 → 替换为 ***
        """
        
        # 规则 1: API Key (sk-xxxxxxxxxxxxxxxx)
        text = re.sub(r'sk-[a-zA-Z0-9]{32,}', '***', text)
        
        # 规则 2: JWT Token
        text = re.sub(r'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}', '***', text)
        
        # 规则 3: 身份证号
        text = re.sub(r'\d{17}[\dXx]', '***', text)
        
        # 规则 4: 手机号
        text = re.sub(r'1[3-9]\d{9}', '***', text)
        
        # 规则 5: 邮箱
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***@***.***', text)
        
        return text
```

---

## 九、部署架构设计

### 9.1 推荐部署拓扑

```
┌────────────────────────────────────────────────────────────────┐
│                          DNS (域名解析)                          │
│                    api-proxy.your-company.com                   │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                      CDN (内容分发网络)                          │
│                  缓存静态资源、减轻源站压力                         │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                   负载均衡器 (Load Balancer)                      │
│                  Nginx / HAProxy / AWS ALB                     │
│                   SSL 终止、负载分发、健康检查                      │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                    API 网关集群 (API Gateway)                    │
│                  3 个实例（多 AZ 部署）                           │
│                                                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ Instance 1 │  │ Instance 2 │  │ Instance 3 │             │
│  └────────────┘  └────────────┘  └────────────┘             │
│                                                                │
│  职责：                                                        │
│  • 认证 / 授权                                                 │
│  • 速率限制                                                     │
│  • 请求日志                                                     │
│  • 协议识别                                                     │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                 协议适配层集群 (Protocol Adapter)                 │
│                  5 个实例（多 AZ 部署）                           │
│                                                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ Instance 1 │  │ Instance 2 │  │ Instance 3 │  ...        │
│  └────────────┘  └────────────┘  └────────────┘             │
│                                                                │
│  职责：                                                        │
│  • 协议转换                                                     │
│  • SSE 流转换                                                  │
│  • 语义沟处理                                                   │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                 智能路由层集群 (Intelligent Router)               │
│                  3 个实例（多 AZ 部署）                           │
│                                                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ Instance 1 │  │ Instance 2 │  │ Instance 3 │             │
│  └────────────┘  └────────────┘  └────────────┘             │
│                                                                │
│  职责：                                                        │
│  • 自动模型分配                                                 │
│  • 路由策略执行                                                 │
│  • 故障降级                                                     │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                  模型管理层 (Model Manager)                       │
│                  2 个实例（主备）                                │
│                                                                │
│  职责：                                                        │
│  • 模型注册与管理                                               │
│  • 健康检查                                                     │
│  • 负载均衡                                                     │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                  出站层 (Egress)                                │
│                  3 个实例                                       │
│                                                                │
│  职责：                                                        │
│  • 请求签名                                                     │
│  • 重试策略                                                     │
│  • 超时控制                                                     │
└───────────────────────────┬────────────────────────────────────┘
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                  后端模型 API                                    │
│  DeepSeek / Qwen / GLM / Kimi / MiniMax                        │
└────────────────────────────────────────────────────────────────┘
```

### 9.2 数据存储设计

| 存储类型 | 技术选型 | 用途 | 数据保留 |
|---------|---------|------|---------|
| **关系型数据库** | PostgreSQL | 用户、智能体、模型、路由规则、审计日志 | 永久 |
| **缓存** | Redis | 会话状态、模型健康状态、路由缓存 | 1 小时 |
| **时序数据库** | InfluxDB / TimescaleDB | 指标数据、性能指标 | 30 天 |
| **日志存储** | Elasticsearch | 审计日志、应用日志 | 90 天 |
| **对象存储** | S3 / OSS | 请求/响应存档（可选，用于调试） | 7 天 |

---

## 十、实施路线图

### 10.1 Phase 1: MVP（最小可行产品）

**目标**：支持同协议透传，基本路由功能

**交付物**：
- [ ] 接入层：支持 Anthropic Messages 和 OpenAI Chat Completions 两种协议
- [ ] 协议适配层：同协议透传
- [ ] 智能路由层：基本路由（基于配置文件）
- [ ] 模型管理层：接入 DeepSeek 和 Qwen，双协议端点
- [ ] 出站层：请求转发、重试
- [ ] 治理层：API Key 认证、简单审计日志
- [ ] 可观测层：基本指标（Prometheus + Grafana）

**时间估算**：4-6 周

### 10.2 Phase 2: 协议转换

**目标**：支持跨协议转换，SSE 流转换

**交付物**：
- [ ] 协议适配层：Anthropic ↔ OpenAI Chat 双向转换
- [ ] SSE 流转换器
- [ ] 语义沟处理（thinking 块、cache_control）
- [ ] 智能路由层：成本感知路由、可用性感知路由

**时间估算**：6-8 周

### 10.3 Phase 3: 智能路由

**目标**：自动模型分配，多维度决策

**交付物**：
- [ ] 任务类型识别
- [ ] 多维度评分引擎
- [ ] 路由策略配置（智能体级、用户级、会话级）
- [ ] 模型健康管理（健康检查、熔断器）
- [ ] 故障自动降级

**时间估算**：4-6 周

### 10.4 Phase 4: 多智能体支持

**目标**：完善多智能体管理，隔离，配置

**交付物**：
- [ ] 智能体注册与识别
- [ ] 智能体隔离（连接池、限流、配额）
- [ ] 智能体配置管理
- [ ] Codex Responses API 支持（百炼直通）

**时间估算**：4-6 周

### 10.5 Phase 5: 企业级治理

**目标**：安全、审计、合规

**交付物**：
- [ ] JWT / OAuth 2.0 认证
- [ ] 细粒度授权（模型权限、速率限制、成本预算）
- [ ] 完整审计日志
- [ ] 敏感信息脱敏
- [ ] 合规检查（数据不出境、敏感数据加密）

**时间估算**：6-8 周

### 10.6 Phase 6: 优化与规模化

**目标**：性能优化，支持大规模调用

**交付物**：
- [ ] 性能优化（连接池、缓存、异步）
- [ ] 水平扩展（无状态设计，支持自动扩缩容）
- [ ] 多 region 部署（异地容灾）
- [ ] 全链路压测

**时间估算**：8-12 周

---

## 十一、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **协议转换 bug** | 智能体调用失败，影响开发效率 | 充分测试，先支持同协议透传，跨协议转换作为可选功能 |
| **模型故障** | 服务不可用 | 健康检查 + 自动降级 + 多模型备份 |
| **成本失控** | 预算超支 | 成本预算限制 + 实时成本监控 + 告警 |
| **性能瓶颈** | 延迟过高，影响用户体验 | 性能测试 + 缓存优化 + 异步处理 |
| **安全风险** | 数据泄露、未授权访问 | 认证授权 + 审计日志 + 敏感信息脱敏 + 定期安全审计 |
| **供应商锁定** | 依赖单一模型厂商 | 多模型接入 + 标准化协议（OpenAI Chat Completions） |

---

## 十二、总结

本架构设计的核心价值：

1. **协议中立**：智能体不知道后端模型，模型不知道前端智能体，真正实现解耦
2. **自动分配**：基于任务、成本、性能、可用性多维度自动选择最优模型
3. **高可用**：健康检查、故障自动降级、熔断器、多副本部署
4. **可观测**：全链路追踪、实时指标、告警、审计日志
5. **安全合规**：认证授权、敏感信息脱敏、审计日志、合规检查

**关键技术决策**：

- **优先同协议透传**：Anthropic ↔ Anthropic，Chat ↔ Chat，避免不必要的协议转换
- **Responses API 谨慎支持**：仅百炼直通，不做完整的状态机转换（复杂度太高）
- **路由策略多级配置**：全局默认 → 智能体级 → 用户级 → 会话级 → 请求级，灵活性最大化
- **成本透明**：每个请求、每个用户、每个智能体的成本可追踪、可控制

---

*设计日期：2026-06-18*  
*作者：砖家*  
*版本：v2.0*
