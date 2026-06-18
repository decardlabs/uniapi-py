# Fusion API Relay — 面向多智能体的模型融合中转站

> 参考 agentfw + OpenRouter Fusion，用 **DeepSeek + MiniMax + GLM** 组合在本地搭建媲美前沿单模型的 AI 基础设施。

## 架构

```
Agent / 应用
    │  POST /v1/chat/completions  (model="fusion")
    ▼
┌──────────────────────────────────────────┐
│  API Gateway (FastAPI)                    │
│  Auth · RateLimit · PII Mask · Audit     │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│  Fusion Engine                           │
│  ① Request Cloner                        │
│  ② Parallel Dispatch (asyncio.gather)    │
│  ③ Judge (MiniMax) → 共识/矛盾/盲区      │
│  ④ Synthesizer (DeepSeek) → 最终答案      │
└──────────────────┬───────────────────────┘
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
 DeepSeek       MiniMax         GLM
 Adapter        Adapter         Adapter
     │             │             │
     ▼             ▼             ▼
 DeepSeek API  MiniMax API   GLM API
```

## 快速启动

```bash
# 1. 配置
cp .env.example .env
# 编辑 .env 填入三家 API Key

# 2. Docker 一键启动
docker-compose up -d

# 3. 测试
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer fusion-relay-your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"fusion","messages":[{"role":"user","content":"比较 RAG 和 Fine-tuning"}]}'
```

## 在 Agent 中使用

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="fusion-relay-your-secret-key"
)

# Fusion 模式
response = client.chat.completions.create(
    model="fusion",
    messages=[{"role": "user", "content": "设计微服务拆分方案"}]
)

# 直连模式
response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## 模型阵容

| 模型 | 角色 | 擅长 |
|------|------|------|
| DeepSeek V4 Pro | Panel + Synthesizer | 推理、问题拆解、数学 |
| MiniMax M3 | Panel + Judge | 代码、长上下文、中文理解 |
| GLM-4-Plus | Panel | 结构化输出、多模态 |

## 配置

- `config/models.yaml` — 模型提供商与 API Key
- `config/fusion.yaml` — Fusion 策略（panel/judge/synthesizer 组合）+ 路由规则
- `config/security.yaml` — PII 脱敏、审计、限流

## 核心接口

| 路由 | 说明 |
|------|------|
| `POST /v1/chat/completions` | OpenAI 兼容（model="fusion" 触发融合）|
| `GET /v1/models` | 列出所有可用模型 |
| `GET /admin/fusion/config` | 查看 Fusion 配置 |
| `PUT /admin/fusion/config` | 热更新 Fusion 配置 |
| `GET /admin/stats` | 调用统计 |
| `GET /health` | 健康检查 |
| `GET /docs` | Swagger 文档 |
