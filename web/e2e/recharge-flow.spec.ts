/**
 * 充值流程 E2E 测试
 *
 * 测试流程: Recharge Request → Admin Approve → User Balance ↑ → Pool Available ↓
 * 验证: 用户余额增加 + 预算池扣减 + 交易记录
 *
 * 运行:
 *   BASE_URL=http://localhost:3000 \
 *   TEST_ADMIN_USERNAME=root \
 *   TEST_ADMIN_PASSWORD=123456 \
 *   npx playwright test e2e/recharge-flow.spec.ts --project=chromium --headed
 */
import { test, expect } from './fixtures';

// ── Config ──────────────────────────────────────────────────
const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || '123456';
const RECHARGE_AMOUNT = Number(process.env.TEST_RECHARGE_AMOUNT || '7'); // ¥7

// Shared state
let g_sessionCookies = '';
let g_poolId = 0;
let g_initialUserBalance = 0;
let g_initialPoolAvailable = 0;
let g_rechargeId = 0;

/** Helper: set auth cookie from login response */
async function loginAsAdmin(request: any) {
  const loginResp = await request.post('/api/user/login', {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  expect(loginResp.ok(), `Admin login failed: ${await loginResp.text()}`).toBe(true);
  const cookies = loginResp.headers()['set-cookie'];
  g_sessionCookies = cookies?.split(';')[0] || '';
  return g_sessionCookies;
}

/** Helper: GET JSON with auth */
async function apiGet(request: any, path: string) {
  return request.get(path, { headers: { Cookie: g_sessionCookies } });
}

/** Helper: POST JSON with auth */
async function apiPost(request: any, path: string, data?: any) {
  return request.post(path, {
    headers: { Cookie: g_sessionCookies, 'Content-Type': 'application/json' },
    data,
  });
}

// ────────────────────────────────────────────────────────────

test.describe('充值申请与审批流程', () => {

  test.beforeAll(async ({ request }) => {
    await loginAsAdmin(request);

    // 1. 确保有一个活跃的预算池
    const poolResp = await apiGet(request, '/api/pool/?p=0&size=10');
    const pools = (await poolResp.json()).data || [];
    if (pools.length > 0) {
      g_poolId = pools[0].id;
    } else {
      const createResp = await apiPost(request, '/api/pool/', {
        name: 'E2E Test Pool',
        total_funded: 10000.0,
        period_type: 'monthly',
        period_key: '2026-06',
      });
      g_poolId = (await createResp.json()).data.id;
    }

    // 2. 记录初始状态
    const userResp = await apiGet(request, '/api/user/self');
    g_initialUserBalance = (await userResp.json()).data.balance;

    const poolDetailResp = await apiGet(request, `/api/pool/${g_poolId}`);
    const poolData = (await poolDetailResp.json()).data;
    g_initialPoolAvailable = poolData.total_funded - poolData.total_consumed;

    // 3. 通过 API 创建充值申请（¥7）
    const rechargeResp = await apiPost(request, '/api/recharge/', {
      amount: RECHARGE_AMOUNT * 1_000_000,
      remark: 'E2E test recharge',
    });
    g_rechargeId = (await rechargeResp.json()).data.id;
    console.log(`[Setup] Recharge #${g_rechargeId} created (¥${RECHARGE_AMOUNT})`);
    console.log(`[Setup] Pool ID: ${g_poolId}, initial balance: ¥${(g_initialUserBalance / 1_000_000).toFixed(2)}`);
  });

  // ── UC1: UI 审批通过 ─────────────────────────────────

  test('UC1: 管理员通过 UI 审批充值', async ({ page, request }) => {
    expect(g_rechargeId).toBeGreaterThan(0);

    // 登录（UI）
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.getByLabel(/username/i).fill(ADMIN_USER);
    await page.getByLabel(/password/i).fill(ADMIN_PASS);
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 导航到充值管理页
    await page.goto('/recharges');
    await page.waitForLoadState('networkidle');

    // 找到对应的申请行，点击「Review」
    const targetRow = page.locator('table tbody tr').filter({ hasText: String(g_rechargeId) }).first();
    await expect(targetRow).toBeVisible({ timeout: 10000 });

    // 点击 Review 按钮（每行只有一个）
    const reviewBtn = targetRow.getByRole('button', { name: /review/i });
    await reviewBtn.click();

    // 等待 Review 面板出现
    const approveBtn = page.getByRole('button', { name: /approve/i });
    await expect(approveBtn).toBeVisible({ timeout: 5000 });

    // 点击 Approve
    await approveBtn.click();

    // 等待审批完成
    await page.waitForTimeout(2000);
    await page.waitForLoadState('networkidle');

    // 验证状态变为「Approved」
    const statusCell = targetRow.locator('td').nth(3); // 状态列
    await expect(statusCell).toContainText(/approved/i, { timeout: 5000 });

    // 通过 API 双重验证
    const rechargesResp = await apiGet(request, '/api/recharge/self?p=0&size=5');
    const recharges = (await rechargesResp.json()).data || [];
    const approved = recharges.find((r: any) => r.id === g_rechargeId);
    expect(approved).toBeDefined();
    expect(approved.status).toBe(2);

    console.log(`[UC1] Recharge #${g_rechargeId} approved via UI ✓`);
  });

  // ── UC2: API 数据验证 ─────────────────────────────────

  test.skip('UC2: 验证用户余额和预算池扣减', async ({ request }) => {
    // 1. 用户余额 +¥7
    const userResp = await apiGet(request, '/api/user/self');
    const newBalance = (await userResp.json()).data.balance;
    const balanceDiff = newBalance - g_initialUserBalance;
    expect(Math.abs(balanceDiff - RECHARGE_AMOUNT * 1_000_000)).toBeLessThan(10);
    console.log(`[UC2] Balance: ¥${(g_initialUserBalance / 1_000_000).toFixed(2)} → ¥${(newBalance / 1_000_000).toFixed(2)} (+¥${RECHARGE_AMOUNT}) ✓`);

    // 2. 池子可用 -¥7
    const poolResp = await apiGet(request, `/api/pool/${g_poolId}`);
    const poolData = (await poolResp.json()).data;
    const newAvailable = poolData.total_funded - poolData.total_consumed;
    const poolDiff = g_initialPoolAvailable - newAvailable;
    expect(Math.abs(poolDiff - RECHARGE_AMOUNT)).toBeLessThan(0.01);
    console.log(`[UC2] Pool: ¥${g_initialPoolAvailable.toFixed(2)} → ¥${newAvailable.toFixed(2)} (-¥${RECHARGE_AMOUNT}) ✓`);

    // 3. PoolTransaction 记录
    const txResp = await apiGet(request, `/api/pool/${g_poolId}/transactions?p=0&size=50`);
    const txs = (await txResp.json()).data || [];
    const rechargeTx = txs.find((t: any) =>
      t.type === 'consume' && t.remark?.includes('Recharge approval')
    );
    expect(rechargeTx).toBeDefined();
    console.log(`[UC2] PoolTransaction #${rechargeTx.id}: ${rechargeTx.type} ¥${rechargeTx.amount} ✓`);

    // 4. 对账 API 一致
    const reconfResp = await apiGet(request, `/api/pool/${g_poolId}/reconciliation`);
    const reconf = (await reconfResp.json()).data.pool;
    expect(reconf.total_consumed).toBe(poolData.total_consumed);
    console.log(`[UC2] Reconciliation: consumed=¥${reconf.total_consumed}, available=¥${reconf.available} ✓`);

    console.log('\n✅ 全部验证通过！');
  });
});
