# 测试体系 Review & 改进计划

> 版本: v0.14.0
> 日期: 2026-06-27

---

## 1. 当前测试体系 Review

### 1.1 后端测试（pytest, 795 个）

| 层级 | 数量 | 覆盖范围 | 质量 |
|------|:----:|----------|:----:|
| **Phase 1** (基础) | 108 | 认证、状态、DeepSeek 归一化、中间件、Fusion 引擎 | ✅ |
| **Phase 2** (管理 API) | 221 | 用户/令牌/渠道/选项 CRUD、预算、池子、仪表盘 | ✅ |
| **Phase 3** (多格式) | 7 | NATIVE_FORMATS 路由 | ✅ |
| **Phase 4** (可扩展性) | 51 | 适配器契约、Relay 全流程 | ✅ |
| **Phase 5** (错误处理) | 309 | 429 重试、上游错误、错误码/格式、认证安全 | ✅ |
| **Phase 6** (充值) | 60 | 充值申请/审批/拒绝、池子集成、兑换码 | ✅ |
| **Security** | 18 | 输入校验、RBAC、XSS | ✅ |
| **Live** | 8 | 真实 API Key 集成（默认跳过） | ⚠️ 需要密钥 |
| **GLM 适配器** | 13 | GLM 特定测试 | ✅ |

**优点:**
- 分层清晰（Phase 1-6 + Security）
- 覆盖率较高（784/795 通过，11 因缺 API key 跳过）
- 使用 FakeRedisClient 模拟 Redis，无外部依赖

**缺点:**
- 缺少性能/压力测试
- 缺少数据库迁移回滚测试
- Live 测试需要手动配 Key

### 1.2 前端测试

#### 单元测试
- 使用 Vitest（Vite 原生测试框架）
- 覆盖：组件渲染、表单验证、hook 逻辑
- 测试文件散落在各 page 目录的 `__tests__/` 下

#### E2E 测试（Playwright, 10 个 spec, 47 tests）

| 文件 | Tests | 覆盖 |
|------|:-----:|------|
| `smoke.spec.ts` | 2 | 首页、登录页渲染 |
| `login.spec.ts` | 22 | 登录流程、TOTP、密码重置 |
| `channel-crud.spec.ts` | 4 | 渠道 CRUD |
| `token-crud.spec.ts` | 3 | 令牌 CRUD |
| `dashboard.spec.ts` | 4 | 仪表盘数据展示 |
| `pool-allocate.spec.ts` | 3 | 池子分配流程 |
| `recharge-flow.spec.ts` | 2 | 充值审批流程 |
| `password-change.spec.ts` | 2 | 密码修改 |
| `channel-pricing.spec.ts` | 3 | 渠道定价编辑 + 模型页验证 |
| `pricing-sync.spec.ts` | 2 | 同名渠道定价同步 |

**优点:**
- 覆盖了核心业务流程
- 使用 fixture 管理登录状态
- 测试可独立运行，支持环境变量配置

**缺点:**
- 只能在有后端服务的环境运行
- 缺少 CI 集成（仓库中无 Playwright CI job）
- 缺少视觉回归测试（没有截图对比）

### 1.3 CI/CD 现状

**GitHub Actions (CI):**
- ✅ 后端：Python 3.11 + ruff lint + pytest + Codecov
- ✅ 前端：TypeScript check + vitest + ESLint
- ❌ 没有 Playwright E2E 测试
- ❌ 没有 Docker 构建验证
- ❌ 没有自动部署

**部署（deploy.sh）:**
- 手动执行 `bash deploy.sh`
- 步骤：构建前端 → rsync 到服务器 → 安装依赖 → 迁移数据库 → 重启服务
- ✅ 生产验证
- ❌ 非自动化，需要手动触发
- ❌ 没有回滚机制

---

## 2. 完整测试体系设计

### 2.1 测试金字塔

```
         ╱  E2E (Playwright)  ╲       ← 10→20 个关键场景
        ╱ 集成测试 (pytest)    ╲      ← 新增池子对账/充值/同步
       ╱  后端单元测试 (pytest) ╲     ← 795→850+ 个
      ╱   前端组件测试 (Vitest)  ╲    ← 新增 UI 组件测试
     ╱    静态分析 (ruff/tsc)    ╲   ← lint + type-check
    ╱      API 契约测试          ╲   ← OpenAPI schema 验证
```

### 2.2 新增测试计划

#### 2.2.1 后端（新增 50-60 个）

| 类别 | 数量 | 说明 |
|------|:----:|------|
| 池子对账修复 | 6 | 已实现（test_pool_reconciliation） |
| 充值+池子集成 | 5 | 已实现（test_recharge_pool_integration） |
| 同名渠道同步 | 3 | 新增 |
| 渠道 pricing 多格式兼容 | 5 | 新/旧格式、边界值 |
| 数据库迁移测试 | 5 | 迁移升级/回滚 |
| API Key 安全 | 3 | 隐藏 key 不覆盖、空 key 不写入 |
| 并发充值场景 | 5 | 多用户同时申请 |
| 性能/压力基线 | 10 | 100 并发请求、500ms 阈值 |
| 预算池 rollover | 5 | 结转精度、数据一致性 |
| 错误场景覆盖 | 10 | 404/422/500 各路径 |

#### 2.2.2 前端 E2E（新增 10-15 个）

| 场景 | 说明 |
|------|------|
| 创建预算池 → fund | 补充 |
| 预算池 close + rollover | 新增 |
| 用户注册流程（含 Turnstile） | 补充 |
| 个人设置修改 | 新增 |
| 模型页筛选/搜索 | 新增 |
| MCP 服务管理 CRUD | 新增 |
| 视觉回归（截图对比） | 新增 |

### 2.3 GitHub Actions CI 改进

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # ── 1. 后端 ──
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]"
      - run: ruff check app/ tests/
      - run: python -m pytest tests/ -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  # ── 2. 前端 ──
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: cd web && yarn install --frozen-lockfile
      - run: cd web && yarn type-check
      - run: cd web && yarn lint
      - run: cd web && yarn test --run

  # ── 3. E2E（新增）──
  e2e:
    runs-on: ubuntu-latest
    services:
      # 启动测试用的 SQLite 后端
      app:
        image: python:3.11
        options: >-
          --health-cmd "curl -f http://localhost:3000/health || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - uses: actions/setup-node@v4
      - run: pip install -e ".[dev]"
      - run: cd web && yarn install --frozen-lockfile
      - name: Start backend
        run: |
          uvicorn app.main:app --host 0.0.0.0 --port 3000 &
          sleep 5
          curl -f http://localhost:3000/api/status
      - name: Run E2E
        run: |
          cd web
          npx playwright install --with-deps chromium
          BASE_URL=http://localhost:3000 \
            npx playwright test e2e/ \
            --project=chromium --reporter=html
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: web/playwright-report/
```

### 2.4 自动部署 Pipeline（新增）

```
GitHub Push → CI 通过 → 自动部署到 api.ccbot.chat
```

**方案：GitHub Actions + SSH Deploy**

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    tags: ['v*']           # 只有打 tag 才触发部署

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build frontend
        run: |
          cd web
          yarn install --frozen-lockfile
          yarn build:prod

      - name: Deploy to server
        uses: appleboy/scp-action@v0.1.7
        with:
          host: api.ccbot.chat
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          source: "./*,!./.git,!./web/node_modules,!./tests,!./.venv"
          target: /www/wwwroot/api.ccbot.chat

      - name: Restart service
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: api.ccbot.chat
          username: root
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /www/wwwroot/api.ccbot.chat
            source .venv/bin/activate
            pip install -e . -q
            alembic upgrade head
            systemctl restart uniapi-py
```

### 2.5 测试矩阵

```
              PR → CI 运行
                │
        ┌───────┼───────┐
        │       │       │
     ruff lint  │  类型检查
        │       │       │
    pytest(795) │  vitest
        │       │       │
        │   E2E(47)     │
        │               │
    Codecov 覆盖率报告
        │
    通过 → 可合并
        │
    Merge → Tag v* → 自动部署
```

### 2.6 实施路线图

| 阶段 | 内容 | 预计工时 |
|------|------|:--------:|
| **Phase 1** | 后端新增 50-60 个测试（现有模式扩展） | 2-3 天 |
| **Phase 2** | 前端 E2E 新增 10-15 个测试 | 1-2 天 |
| **Phase 3** | CI 增加 E2E job（Playwright in CI） | 1 天 |
| **Phase 4** | 自动部署 pipeline（GitHub Actions） | 1 天 |
| **Phase 5** | 性能基线 + 数据库迁移测试 | 1-2 天 |
| **Phase 6** | 文档 + 团队培训 | 0.5 天 |

### 2.7 需要补充的配置

**GitHub Secrets（在仓库 Settings → Secrets and variables → Actions 中添加）：**

| Secret | 说明 |
|--------|------|
| `SSH_PRIVATE_KEY` | 部署服务器的 SSH 私钥 |
| `SSH_HOST` | 服务器地址（api.ccbot.chat） |
| `SSH_USER` | SSH 用户名（root） |
| `TURNSTILE_SECRET_KEY` | 测试用 Turnstile 密钥（可选） |

**Playwright CI 兼容性：**
- GitHub Actions Ubuntu 镜像需要安装 `mesa-libgbm`、`libasound2` 等系统库
- 需要在 CI yml 中添加 `npx playwright install --with-deps chromium`

---

## 3. 现有问题 & 改进点

### 3.1 测试数据隔离
- ✅ 使用 `/tmp/uniapi_test.db` 独立数据库
- ✅ 每个 function 级 fixture 自动建表、销毁
- ⚠️ 但各测试之间顺序依赖（如 pool 测试依赖 login）

### 3.2 API Key 安全测试
- ✅ 已实现隐藏 key 检测
- ⚠️ 需要补充批量渠道更新的 key 安全性测试

### 3.3 定价测试
- ✅ 已实现定价覆盖测试
- ⚠️ 需要测试多格式兼容（旧 ratio 格式仍能正确解析）

### 3.4 CI 耗时
- 后端测试：约 90s（可优化并行）
- 前端测试：约 30s
- E2E 测试：约 60s
- 总 CI 时间：约 3min（可以接受）
