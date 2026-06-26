# 测试计划 v0.13.0

> 基于 `security-upgrade-login` 分支合并后的完整代码库
> 版本: v0.13.0 | 后端测试: 785 个 | 前端 E2E: 8 个 spec 文件

## 1. 现有测试覆盖

### 1.1 后端测试（pytest, 785 个）

| 阶段 | 测试数 | 覆盖内容 |
|------|:------:|----------|
| **Phase 1** (test_api + others) | 108 | 认证、状态、DeepSeek Chat Completions、渠道类型、中间件、Fusion |
| **Phase 2** | 216 | 管理 API CRUD（用户/令牌/渠道/选项/MCP）、计费、预算模型 & 仲裁器、预算池 API |
| **Phase 3** | 7 | 多格式路由（NATIVE_FORMATS） |
| **Phase 4** | 51 | 适配器契约、可扩展性、Relay 全流程 |
| **Phase 5** | 309 | 上游 429 重试与退路、认证错误、错误码/格式、异常处理器 |
| **Phase 6** | 55 | 充值（申请/审批/拒绝/管理员直充）、兑换码（CRUD） |
| **Security** | 18 | 输入校验、RBAC、XSS |
| **Live** | 8 | 真实 API 密钥集成测试（默认跳过） |
| **其他（Phase 1）** | 108 | API 基础、DeepSeek 归一化、渠道类型、中间件、Fusion 引擎等 |

### 1.2 前端 E2E（Playwright, 8 个 spec）

| 文件 | 覆盖内容 |
|------|----------|
| `smoke.spec.ts` | 首页响应、登录页渲染 |
| `login.spec.ts` | 登录流程、TOTP 两步验证 |
| `channel-crud.spec.ts` | 渠道 CRUD |
| `token-crud.spec.ts` | 令牌 CRUD |
| `dashboard.spec.ts` | 仪表盘数据展示 |
| `pool-allocate.spec.ts` | 预算池创建 → 资金注入 → 分配 → 用户余额验证 |
| `password-change.spec.ts` | 密码修改 |
| `BudgetPoolPage.ts` | 预算池页面对象（供其他测试复用） |

## 2. 测试缺口分析

### 2.1 后端测试缺口

| # | 缺口 | 优先级 | 说明 |
|---|------|:------:|------|
| G1 | **池子对账 `_reconcile_pool` 修复** | 🔴高 | 已修复 `PoolTransaction consume` 遗漏 Bug，但无对应测试 |
| G2 | **PoolTransaction 多种 type 混合场景** | 🔴高 | fund + consume + allocate + recall 混合时的 total_consumed 计算 |
| G3 | **充值审批 + 池子扣减集成** | 🔴高 | approve_recharge 同时验证用户余额 + 池子 total_consumed + 交易记录 |
| G4 | **`schemas/management.py` 23 个 Pydantic 模型** | 🟡中 | 验证每个模型字段约束、默认值、校验规则 |
| G5 | **管理员直充 (`/api/topup/` POST) 完整流程** | 🟡中 | TopUpRequest 参数 + userId/amount/poolId/remark 组合 |
| G6 | **批量操作边界** | 🟡中 | 多个用户同时充值/审批的并发场景 |
| G7 | **池子回顾 (rollover) + 结转精度** | 🟢低 | 跨周期结转后新旧池子的数据一致性 |

### 2.2 前端 E2E 测试缺口

| # | 缺口 | 优先级 | 说明 |
|---|------|:------:|------|
| F1 | **充值申请前端流程** | 🔴高 | 用户提交充值申请 → 查看申请列表 → 确认状态 |
| F2 | **充值审批前端流程** | 🔴高 | 管理员查看待审批列表 → 审批通过 → 显示结果 |
| F3 | **池子盘点页数据准确性** | 🔴高 | 对账页 total_consumed / available 与数据库一致（验证 Bug 修复） |
| F4 | **池子回顾 (Rollover) 前端操作** | 🟡中 | 创建 → 注入资金 → 分配 → 结转 → 验证 |
| F5 | **池子回收 (Recall) 前端操作** | 🟡中 | 分配 → 回收部分/全部 → 验证用户余额 |

### 2.3 集成测试缺口

| # | 缺口 | 优先级 | 说明 |
|---|------|:------:|------|
| I1 | **全流程: 创建池子 → 资金注入 → 充值申请 → 审批 → 验证** | 🔴高 | 端到端验证池子减少 + 用户增加 |
| I2 | **池子余额不足时的拒绝场景** | 🔴高 | 申请金额 > 池子可用余额 → 审批预期失败 |
| I3 | **无活跃池子时的创建/审批行为** | 🟡中 | pool_id=0 且无池子 → 预期错误信息 |
| I4 | **API 消费后对账准确性** | 🟡中 | 调用真实 relay → 产生 CostRecord → 对账同步 total_consumed |

## 3. 新增测试计划

### 3.1 后端测试（新增 15-20 个）

#### 3.1.1 池子对账修复验证 (G1, G2, G3)

**文件**: `tests/phase2/test_pool_reconciliation.py`（新建）

```python
# 测试用例:
test_reconcile_pool_no_allocations      # 无 allocation, 有 PoolTransaction → total_consumed 正确
test_reconcile_pool_with_allocations    # 有 allocation + PoolTransaction → total_consumed 累加
test_reconcile_pool_empty               # 无 allocation 无 txn → total_consumed = 0
test_reconcile_pool_mixed_types         # fund + consume + allocate + recall 混合
test_pool_api_reconciliation_endpoint   # GET /api/pool/{id}/reconciliation 返回正确值
```

#### 3.1.2 充值 + 池子集成 (G3)

**文件**: `tests/phase6/test_recharge_pool_integration.py`（新建）

```python
# 测试用例:
test_approve_recharge_deducts_pool_consumed    # 审批通过 → pool.total_consumed +N
test_approve_recharge_creates_transaction      # 审批通过 → PoolTransaction type=consume
test_approve_recharge_updates_user_balance     # 审批通过 → user.balance +N
test_recharge_reject_no_pool_change            # 拒绝 → 池子不变
test_admin_topup_deducts_pool                  # 管理员直充 → 池子扣减
```

#### 3.1.3 管理模型校验 (G4)

**文件**: `tests/phase2/test_management_schemas.py`（新建，或追加到已有文件）

```python
# 测试用例: 每个 model 至少 1 个验证
# ApproveRechargeRequest, RejectRechargeRequest, TopupActionRequest
# PoolCreateRequest, PoolFundRequest, PoolAllocateRequest ...
test_approve_recharge_request_default_pool_id  # pool_id 默认 0
test_reject_recharge_request_default_remark    # admin_remark 默认值
test_pool_create_request_validation            # name/total_funded/period_type 必填
test_pool_allocate_request_validation          # user_id/amount 必填
```

### 3.2 前端 E2E 测试（新增 10-15 个）

#### 3.2.1 充值流程 (F1, F2)

**文件**: `web/e2e/recharge-flow.spec.ts`（新建）

```
测试用例:
  ✓ 用户提交充值申请
  ✓ 用户查看自己的充值申请列表
  ✓ 管理员查看所有待审批申请
  ✓ 管理员审批通过 → 用户余额变化
  ✓ 管理员拒绝 → 状态变更为已拒绝
  ✓ 管理员直充（跳过申请流程）
```

#### 3.2.2 池子盘点验证 (F3)

**文件**: 追加到现有 `pool-allocate.spec.ts` 或新建 `reconcile.spec.ts`

```
测试用例:
  ✓ 池子总览页面显示正确的 total_funded / total_consumed / available
  ✓ 盘点页数据与数据库一致
  ✓ 盘点后 total_consumed 不丢失（验证 Bug 修复）
```

### 3.3 集成测试（新增 5 个）

**文件**: `tests/test_integration.py`（新建，或放入 phase6）

```
测试用例:
  ✓ 创建池子 → fund ¥6000 → 充值申请 ¥500 → 审批通过 → 池子可用余额 -¥500
  ✓ 创建池子 → fund ¥100 → 充值申请 ¥200 → 审批预期失败（池子不足）
  ✓ 无池子 → 充值申请 → 审批预期失败（无活跃池子）
  ✓ 多个充值 → 池子逐笔扣减 → total_consumed 累加正确
  ✓ 池子 fund ¥1000 → allocate ¥300 → recharge ¥200 → 
    reconcile 显示 allocation consumed + txn consume
```

## 4. 测试执行计划

### 阶段 1: 后端单元测试（预计 1 天）

```bash
# 1. 运行全部现有测试，确认回归通过
python3 -m pytest tests/ -v --no-header

# 2. 运行新增测试文件
python3 -m pytest tests/phase2/test_pool_reconciliation.py -v
python3 -m pytest tests/phase6/test_recharge_pool_integration.py -v
python3 -m pytest tests/phase2/test_management_schemas.py -v
```

### 阶段 2: 前端 E2E 测试（预计 1-2 天）

```bash
# 需要后端运行在 localhost:3000
cd web
BASE_URL=http://localhost:3000 \
  TEST_ADMIN_USERNAME=root \
  TEST_ADMIN_PASSWORD=123456 \
  npx playwright test e2e/ \
    --project=chromium --headed
```

### 阶段 3: 集成测试（预计 1 天）

在完成单元测试和 E2E 测试后进行，确保完整流程无误。

## 5. 测试环境要求

| 环境 | 要求 |
|------|------|
| **后端** | Python 3.11+, SQLite 测试数据库（已配置 conftest.py 自动处理） |
| **前端** | Node.js, Playwright (chromium) |
| **服务器** | 可选：api.ccbot.chat 上的实时环境用于端到端验证 |
| **配置** | 无需真实 API 密钥（单元测试 mock） |

## 6. 质量验收标准

| 指标 | 目标 |
|------|:----:|
| 后端测试总数 | ≥ 800 |
| 后端测试通过率 | 100% |
| 前端 E2E 测试数 | ≥ 12 |
| 前端 E2E 通过率 | 100% |
| 新增代码覆盖率 | ≥ 85% |
| 回归测试 | 原有 785 测试不受影响 |
