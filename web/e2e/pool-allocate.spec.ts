/**
 * 预算池充值流程 E2E 测试
 *
 * 测试流程: Budget Pool → Allocate → User Account
 * 验证: Pool 数据变化 + User 余额变化的准确性
 *
 * beforeAll 自动创建测试数据（用户、预算池），无需手动准备。
 *
 * 运行:
 *   BASE_URL=http://localhost:3001 \
 *   TEST_ADMIN_USERNAME=root \
 *   TEST_ADMIN_PASSWORD=sunkiller \
 *   npx playwright test e2e/pool-allocate.spec.ts --project=chromium
 */
import { test, expect } from './fixtures';
import { BudgetPoolPage } from './pages/BudgetPoolPage';

// ── Config ──────────────────────────────────────────────────
const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || 'sunkiller';
const TARGET_USER = process.env.TEST_TARGET_USERNAME || 'testuser1';
const TARGET_PASS = process.env.TEST_TARGET_PASSWORD || 'Test1234';
const ALLOCATE_AMOUNT = Number(process.env.TEST_ALLOCATE_AMOUNT || '50');
const POOL_NAME = 'E2E Auto Test Pool';

// Shared state across tests
let g_poolId = 0;
let g_targetUserId = 0;

test.describe('预算池充值流程', () => {
  let poolPage: BudgetPoolPage;

  // ── 自动初始化测试数据 ────────────────────────────────────
  test.beforeAll(async ({ request }) => {
    // 1. 管理员登录获取 session
    const loginResp = await request.post('/api/user/login', {
      data: { username: ADMIN_USER, password: ADMIN_PASS },
    });
    expect(loginResp.ok(), `管理员登录失败: ${await loginResp.text()}`).toBe(true);

    const cookies = loginResp.headers()['set-cookie'];
    const sessionCookie = cookies?.split(';')[0] || '';

    const apiHeaders = { Cookie: sessionCookie, 'Content-Type': 'application/json' };

    // 2. 确保目标用户存在
    const searchResp = await request.get(
      `/api/user/search?q=${TARGET_USER}`,
      { headers: apiHeaders }
    );
    const searchBody = await searchResp.json();
    const existingUser = (searchBody?.data || []).find(
      (u: any) => u.username === TARGET_USER
    );

    if (existingUser) {
      g_targetUserId = existingUser.id;
      console.log(`[Setup] 用户 ${TARGET_USER} 已存在 (id=${g_targetUserId})`);
    } else {
      const regResp = await request.post('/api/user/register', {
        data: {
          username: TARGET_USER,
          password: TARGET_PASS,
          display_name: 'E2E Test User',
          email: `${TARGET_USER}@e2e.test`,
        },
      });
      if (regResp.ok()) {
        const regBody = await regResp.json();
        g_targetUserId = regBody?.data?.id ?? 0;
        console.log(`[Setup] 用户 ${TARGET_USER} 已创建 (id=${g_targetUserId})`);
      }
    }

    // 3. 确保预算池存在且额度充足
    const poolsResp = await request.get('/api/pool/?status=active', {
      headers: apiHeaders,
    });
    const poolsBody = await poolsResp.json();
    const pools: any[] = poolsBody?.data ?? [];
    const existingPool = pools.find((p: any) => p.name === POOL_NAME);

    if (existingPool) {
      g_poolId = existingPool.id;
      console.log(`[Setup] 预算池 "${POOL_NAME}" 已存在 (id=${g_poolId})`);
    }

    if (!g_poolId) {
      const createResp = await request.post('/api/pool/', {
        headers: apiHeaders,
        data: {
          name: POOL_NAME,
          total_funded: 0,
          period_type: 'oneoff',
          period_key: 'e2e-test',
        },
      });
      if (createResp.ok()) {
        const createBody = await createResp.json();
        g_poolId = createBody?.data?.id ?? 0;
        console.log(`[Setup] 预算池已创建 (id=${g_poolId})`);
      } else {
        console.error(`[Setup] 创建预算池失败: ${await createResp.text()}`);
      }
    }

    // 4. 确保池额度充足（充值到 ¥2000）
    if (g_poolId) {
      const poolResp = await request.get(`/api/pool/${g_poolId}`, {
        headers: apiHeaders,
      });
      const poolBody = await poolResp.json();
      const pool = poolBody?.data ?? poolBody;
      const funded = Number(pool?.total_funded ?? 0);
      if (funded < 2000) {
        const needed = 2000 - funded;
        const fundResp = await request.post(`/api/pool/${g_poolId}/fund`, {
          headers: apiHeaders,
          data: { amount: needed, remark: 'E2E auto fund' },
        });
        if (fundResp.ok()) {
          console.log(`[Setup] 预算池已充值 ¥${needed} (总额 ¥2000)`);
        } else {
          console.warn(`[Setup] 预算池充值失败: ${await fundResp.text()}`);
        }
      } else {
        console.log(`[Setup] 预算池额度充足 (¥${funded})`);
      }
    }
  });

  // ── 每个测试前登录管理员 ──────────────────────────────────
  test.beforeEach(async ({ page, loginPage }) => {
    await loginPage.goto();
    await loginPage.login(ADMIN_USER, ADMIN_PASS);
    await expect(page).toHaveURL(/\/(dashboard|pools)/, { timeout: 10000 });
    poolPage = new BudgetPoolPage(page);
  });

  // ── Helper: 通过 page.request (共享browser cookie) 获取数据 ──

  async function getUserBalance(page: any, userId: number): Promise<number> {
    const resp = await page.request.get(`/api/user/${userId}`);
    const body = await resp.json();
    const micro = body?.data?.balance ?? body?.balance ?? 0;
    return micro / 1_000_000;
  }

  async function getPoolData(page: any, poolId: number) {
    const resp = await page.request.get(`/api/pool/${poolId}`);
    const body = await resp.json();
    const pool = body?.data ?? body;
    return {
      total_funded: Number(pool.total_funded ?? 0),
      total_allocated: Number(pool.total_allocated ?? 0),
      available: Math.max(
        0,
        Number(pool.total_funded ?? 0) - Number(pool.total_allocated ?? 0)
      ),
    };
  }

  // ── UC1: 正常分配 ────────────────────────────────────────
  test.describe('UC1: 正常分配', () => {
    test('从预算池分配额度给用户，验证 Pool 和 User 数据变化', async ({
      page,
    }) => {
      const poolId = g_poolId;
      expect(poolId, 'beforeAll 应已创建预算池').toBeGreaterThan(0);

      await poolPage.goto();

      const poolBefore = await getPoolData(page, poolId);
      console.log(`[Before] Pool #${poolId}: allocated=¥${poolBefore.total_allocated.toFixed(2)}, available=¥${poolBefore.available.toFixed(2)}`);
      expect(poolBefore.available).toBeGreaterThanOrEqual(ALLOCATE_AMOUNT);

      const allocBefore = await poolPage.getPoolAllocated(0);
      const availBefore = await poolPage.getPoolAvailable(0);

      await poolPage.clickAllocateButton(0);
      await poolPage.searchAndSelectUser(TARGET_USER);
      await poolPage.fillAllocateAmount(ALLOCATE_AMOUNT);
      await poolPage.fillAllocateRemark(`E2E test ${Date.now()}`);
      await poolPage.submitAllocate();
      await poolPage.expectDialogClosed();

      await page.reload();
      await poolPage.goto();

      const poolAfter = await getPoolData(page, poolId);
      console.log(`[After] Pool #${poolId}: allocated=¥${poolAfter.total_allocated.toFixed(2)}, available=¥${poolAfter.available.toFixed(2)}`);

      const allocAfter = await poolPage.getPoolAllocated(0);
      const availAfter = await poolPage.getPoolAvailable(0);

      expect(poolAfter.total_allocated - poolBefore.total_allocated).toBe(ALLOCATE_AMOUNT);
      expect(poolBefore.available - poolAfter.available).toBe(ALLOCATE_AMOUNT);
      expect(allocAfter).toBeCloseTo(allocBefore + ALLOCATE_AMOUNT, 2);
      expect(availAfter).toBeCloseTo(availBefore - ALLOCATE_AMOUNT, 2);

      console.log(`✓ 分配 ¥${ALLOCATE_AMOUNT} 验证通过`);
    });
  });

  // ── UC2: 余额不足拦截 ────────────────────────────────────
  test.describe('UC2: 余额不足拦截', () => {
    test('分配金额超过可用额度时，应该被拦截', async ({ page }) => {
      await poolPage.goto();
      await poolPage.clickAllocateButton(0);
      await poolPage.searchAndSelectUser(TARGET_USER);
      await poolPage.fillAllocateAmount(999999);
      await poolPage.submitAllocate();

      const errorIndicator = page.locator(
        '[data-sonner-toaster] li, [role="status"], [role="alert"], .text-destructive'
      ).filter({ hasText: /error|fail|失败|不足|exceed/i });

      const hasError = await errorIndicator.first().isVisible().catch(() => false);
      const dialogStillOpen = await poolPage.allocateDialog.isVisible().catch(() => false);
      expect(hasError || dialogStillOpen, '超额分配应被拦截').toBe(true);
      console.log('✓ 超额分配被正确拦截');
    });
  });

  // ── UC3: 用户余额验证 ────────────────────────────────────
  test.describe('UC3: 分配后用户余额验证', () => {
    test('分配完成后，用户余额应增加对应金额', async ({ page }) => {
      expect(g_targetUserId, 'beforeAll 应已创建/找到目标用户').toBeGreaterThan(0);
      const poolId = g_poolId;
      expect(poolId).toBeGreaterThan(0);

      const poolBefore = await getPoolData(page, poolId);
      expect(poolBefore.available, `预算池余额不足 ¥${poolBefore.available}`).toBeGreaterThanOrEqual(ALLOCATE_AMOUNT);

      const balanceBefore = await getUserBalance(page, g_targetUserId);
      console.log(`[Before] User #${g_targetUserId} (${TARGET_USER}) balance=¥${balanceBefore.toFixed(2)}`);

      await poolPage.goto();
      await poolPage.clickAllocateButton(0);
      await poolPage.searchAndSelectUser(TARGET_USER);
      await poolPage.fillAllocateAmount(ALLOCATE_AMOUNT);
      await poolPage.fillAllocateRemark(`E2E balance verify ${Date.now()}`);
      await poolPage.submitAllocate();
      await page.waitForTimeout(2000);

      const balanceAfter = await getUserBalance(page, g_targetUserId);
      console.log(`[After] User #${g_targetUserId} balance=¥${balanceAfter.toFixed(2)}`);

      expect(balanceAfter - balanceBefore).toBe(ALLOCATE_AMOUNT);
      console.log(`✓ 用户余额验证通过: +¥${ALLOCATE_AMOUNT}`);
    });
  });
});
