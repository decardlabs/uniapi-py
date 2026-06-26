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
const RECHARGE_REMARK = 'E2E test recharge';

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
      // 创建一个测试池子
      const createResp = await apiPost(request, '/api/pool/', {
        name: 'E2E Test Pool',
        total_funded: 10000.0,
        period_type: 'monthly',
        period_key: '2026-06',
      });
      const createData = await createResp.json();
      g_poolId = createData.data.id;
    }

    // 2. 记录初始状态
    const userResp = await apiGet(request, '/api/user/self');
    g_initialUserBalance = (await userResp.json()).data.balance;

    const poolDetailResp = await apiGet(request, `/api/pool/${g_poolId}`);
    const poolData = (await poolDetailResp.json()).data;
    g_initialPoolAvailable = poolData.total_funded - poolData.total_consumed;

    console.log(`[Setup] Pool ID: ${g_poolId}`);
    console.log(`[Setup] Initial user balance: ¥${(g_initialUserBalance / 1_000_000).toFixed(2)}`);
    console.log(`[Setup] Initial pool available: ¥${g_initialPoolAvailable.toFixed(2)}`);
  });

  // ── UC1: 用户提交充值申请 ──────────────────────────────

  test('UC1: 用户提交充值申请', async ({ page }) => {
    // 导航到充值管理页面
    await page.goto('/recharges');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/recharge/i).first()).toBeVisible({ timeout: 10000 });

    // 点击「新建充值申请」按钮
    const newRequestBtn = page.getByRole('button', { name: /new request|new recharge|新建/i });
    if (await newRequestBtn.isVisible()) {
      await newRequestBtn.click();
    }

    // 填写金额和备注
    const amountInput = page.getByPlaceholder(/amount/i).first();
    const remarkInput = page.getByPlaceholder(/remark/i).first();
    const submitBtn = page.getByRole('button', { name: /submit|提交/i });

    await amountInput.fill(String(RECHARGE_AMOUNT));
    if (await remarkInput.isVisible()) {
      await remarkInput.fill(RECHARGE_REMARK);
    }
    await submitBtn.click();

    // 等待提交成功（提示或列表更新）
    await page.waitForTimeout(2000);
    await page.waitForLoadState('networkidle');

    // 验证申请出现在列表中（最新的第一条）
    const firstRowAmount = page.locator('table tbody tr').first();
    await expect(firstRowAmount).toBeVisible({ timeout: 5000 });

    // 通过 API 获取刚创建的 recharge ID
    const rechargesResp = await apiGet(request, '/api/recharge/self?p=0&size=5');
    const recharges = (await rechargesResp.json()).data || [];
    expect(recharges.length).toBeGreaterThan(0);
    g_rechargeId = recharges[0].id;
    expect(recharges[0].status).toBe(1); // pending

    console.log(`[UC1] Recharge #${g_rechargeId} created, status=pending`);
  });

  // ── UC2: 管理员审批通过 ──────────────────────────────

  test('UC2: 管理员审批通过', async ({ page }) => {
    expect(g_rechargeId).toBeGreaterThan(0);

    // 管理员导航到充值管理页
    await page.goto('/recharges');
    await page.waitForLoadState('networkidle');

    // 找到对应的申请行，点击「审批/Approve」
    // 查找包含 recharge ID 的行
    const targetRow = page.locator('table tbody tr').filter({ hasText: String(g_rechargeId) }).first();
    await expect(targetRow).toBeVisible({ timeout: 5000 });

    // 点击「通过/Approve」按钮
    const approveBtn = targetRow.getByRole('button', { name: /approve|通过/i });
    if (await approveBtn.isVisible()) {
      await approveBtn.click();
    } else {
      // 可能行上有「审批」展开按钮
      const reviewBtn = targetRow.getByRole('button', { name: /review|审批|审核/i });
      if (await reviewBtn.isVisible()) {
        await reviewBtn.click();
        await page.waitForTimeout(500);
        // 在弹出的审批面板中点击「通过」
        const confirmApprove = page.getByRole('button', { name: /approve|通过|确认/i });
        await confirmApprove.click();
      }
    }

    // 等待审批完成
    await page.waitForTimeout(2000);
    await page.waitForLoadState('networkidle');

    // 验证状态变为「已通过」
    const statusBadge = targetRow.locator('.badge, [class*="badge"], [class*="status"]');
    // 或者刷新列表看最新状态
    await page.reload();
    await page.waitForLoadState('networkidle');

    // 通过 API 验证状态
    const rechargesResp = await apiGet(request, `/api/recharge/self?p=0&size=5`);
    const recharges = (await rechargesResp.json()).data || [];
    const approved = recharges.find((r: any) => r.id === g_rechargeId);
    expect(approved).toBeDefined();
    expect(approved.status).toBe(2); // approved

    console.log(`[UC2] Recharge #${g_rechargeId} approved, status=approved`);
  });

  // ── UC3: 数据验证 ──────────────────────────────────────

  test('UC3: 验证用户余额和预算池扣减', async ({ request }) => {
    // 1. 验证用户余额增加了 RECHARGE_AMOUNT 元
    const userResp = await apiGet(request, '/api/user/self');
    const newBalance = (await userResp.json()).data.balance;
    const expectedBalance = g_initialUserBalance + RECHARGE_AMOUNT * 1_000_000;
    const balanceDiff = newBalance - g_initialUserBalance;

    expect(Math.abs(balanceDiff - RECHARGE_AMOUNT * 1_000_000)).toBeLessThan(10);
    console.log(`[UC3] User balance: ¥${(g_initialUserBalance / 1_000_000).toFixed(2)} → ¥${(newBalance / 1_000_000).toFixed(2)} (expected +¥${RECHARGE_AMOUNT})`);

    // 2. 验证池子可用余额减少了 RECHARGE_AMOUNT 元
    const poolResp = await apiGet(request, `/api/pool/${g_poolId}`);
    const poolData = (await poolResp.json()).data;
    const newPoolAvailable = poolData.total_funded - poolData.total_consumed;
    const poolDiff = g_initialPoolAvailable - newPoolAvailable;

    expect(Math.abs(poolDiff - RECHARGE_AMOUNT)).toBeLessThan(0.01);
    console.log(`[UC3] Pool available: ¥${g_initialPoolAvailable.toFixed(2)} → ¥${newPoolAvailable.toFixed(2)} (decreased by ¥${poolDiff.toFixed(2)})`);

    // 3. 验证有对应的 PoolTransaction 记录
    const txResp = await apiGet(request, `/api/pool/${g_poolId}/transactions?p=0&size=50`);
    const txs = (await txResp.json()).data || [];
    const rechargeTx = txs.find((t: any) =>
      t.type === 'consume' &&
      t.remark?.includes('Recharge approval')
    );
    expect(rechargeTx).toBeDefined();
    expect(Math.abs(rechargeTx.amount - RECHARGE_AMOUNT)).toBeLessThan(0.01);
    console.log(`[UC3] PoolTransaction #${rechargeTx.id}: ${rechargeTx.type} ¥${rechargeTx.amount}`);

    // 4. 验证对账 API 的数据一致
    const reconfResp = await apiGet(request, `/api/pool/${g_poolId}/reconciliation`);
    const reconf = (await reconfResp.json()).data.pool;
    expect(reconf.total_consumed).toBe(poolData.total_consumed);
    expect(reconf.available).toBeCloseTo(newPoolAvailable, 2);
    console.log(`[UC3] Reconciliation agrees: consumed=¥${reconf.total_consumed}, available=¥${reconf.available}`);

    console.log('\n✅ 全部验证通过！');
  });
});
