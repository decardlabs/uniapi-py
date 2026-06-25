/**
 * 预算池充值流程 E2E 测试
 *
 * 测试流程: Budget Pool → Allocate → User Account
 * 验证: Pool 数据变化 + User 余额变化的准确性
 *
 * 环境变量:
 *   TEST_ADMIN_USERNAME  - 管理员用户名 (默认 root)
 *   TEST_ADMIN_PASSWORD  - 管理员密码
 *   TEST_TARGET_USERNAME - 目标用户名
 *   TEST_ALLOCATE_AMOUNT - 分配金额 (默认 50)
 *
 * 运行:
 *   BASE_URL=https://api.ccbot.chat \
 *   TEST_ADMIN_USERNAME=root \
 *   TEST_ADMIN_PASSWORD=sunkiller \
 *   TEST_TARGET_USERNAME=testuser1 \
 *   TEST_ALLOCATE_AMOUNT=50 \
 *   npx playwright test e2e/pool-allocate.spec.ts --project=chromium
 */
import { test, expect } from './fixtures';
import { BudgetPoolPage } from './pages/BudgetPoolPage';

// ── Config ──────────────────────────────────────────────────
const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || 'sunkiller';
const TARGET_USER = process.env.TEST_TARGET_USERNAME || 'testuser1';
const ALLOCATE_AMOUNT = Number(process.env.TEST_ALLOCATE_AMOUNT || '50');

test.describe('预算池充值流程', () => {
  let poolPage: BudgetPoolPage;

  test.beforeEach(async ({ page, loginPage }) => {
    // 管理员登录
    await loginPage.goto();
    await loginPage.login(ADMIN_USER, ADMIN_PASS);
    // 等待登录成功跳转到 dashboard
    await expect(page).toHaveURL(/\/(dashboard|pools)/, { timeout: 10000 });

    poolPage = new BudgetPoolPage(page);
  });

  // ── Helper: 通过 API 获取用户余额 ──────────────────────────
  async function getUserBalance(request: any, userId: number): Promise<number> {
    const resp = await request.get(`/api/user/${userId}`);
    const body = await resp.json();
    // balance 是微元 (10^-6 yuan)，转换为元
    const micro = body?.data?.balance ?? body?.balance ?? 0;
    return micro / 1_000_000;
  }

  // ── Helper: 通过 API 获取 pool 数据 ───────────────────────
  async function getPoolData(request: any, poolId: number) {
    const resp = await request.get(`/api/pool/${poolId}`);
    const body = await resp.json();
    const pool = body?.data ?? body;
    return {
      total_funded: pool.total_funded ?? 0,
      total_allocated: pool.total_allocated ?? 0,
      available: Math.max(0, (pool.total_funded ?? 0) - (pool.total_allocated ?? 0)),
    };
  }

  test.describe('UC1: 正常分配', () => {
    test('从预算池分配额度给用户，验证 Pool 和 User 数据变化', async ({
      page,
      request,
    }) => {
      // ── Step 1: 导航到预算池页面 ─────────────────────────
      await poolPage.goto();

      // ── Step 2: 读取分配前的数据 ─────────────────────────
      const poolId = await poolPage.getFirstPoolId();
      expect(poolId, '应至少有一个活跃的预算池').toBeGreaterThan(0);

      const poolBefore = await getPoolData(request, poolId);
      console.log(`[Before] Pool #${poolId}: allocated=¥${poolBefore.total_allocated.toFixed(2)}, available=¥${poolBefore.available.toFixed(2)}`);
      expect(
        poolBefore.available,
        `预算池可用余额 ¥${poolBefore.available.toFixed(2)} 不足以分配 ¥${ALLOCATE_AMOUNT}`
      ).toBeGreaterThanOrEqual(ALLOCATE_AMOUNT);

      const allocBefore = await poolPage.getPoolAllocated(0);
      const availBefore = await poolPage.getPoolAvailable(0);
      console.log(`[Before UI] allocated=${allocBefore}, available=${availBefore}`);

      // ── Step 3: 打开分配弹窗 ─────────────────────────────
      await poolPage.clickAllocateButton(0);

      // ── Step 4: 搜索并选择目标用户 ────────────────────────
      await poolPage.searchAndSelectUser(TARGET_USER);

      // ── Step 5: 输入金额和备注 ───────────────────────────
      await poolPage.fillAllocateAmount(ALLOCATE_AMOUNT);
      await poolPage.fillAllocateRemark(`E2E test allocate ${Date.now()}`);

      // ── Step 6: 确认提交 ─────────────────────────────────
      await poolPage.submitAllocate();

      // ── Step 7: 验证 UI 反馈 ─────────────────────────────
      // 弹窗应该关闭
      await poolPage.expectDialogClosed();

      // 成功通知
      const successToast = page.locator('[data-sonner-toaster] li, [role="status"]')
        .filter({ hasText: /success|成功/i });
      // Sonner toast 可能出现也可能被 auto-dismiss，不强制校验

      // ── Step 8: 刷新页面读取分配后的数据 ──────────────────
      await page.reload();
      await poolPage.goto();

      const poolAfter = await getPoolData(request, poolId);
      console.log(`[After] Pool #${poolId}: allocated=¥${poolAfter.total_allocated.toFixed(2)}, available=¥${poolAfter.available.toFixed(2)}`);

      const allocAfter = await poolPage.getPoolAllocated(0);
      const availAfter = await poolPage.getPoolAvailable(0);
      console.log(`[After UI] allocated=${allocAfter}, available=${availAfter}`);

      // ── Step 9: 数据准确性验证 ───────────────────────────
      // 验证池总分配增加了 ALLOCATE_AMOUNT
      const allocatedDelta = poolAfter.total_allocated - poolBefore.total_allocated;
      expect(allocatedDelta).toBe(ALLOCATE_AMOUNT);

      // 验证池可用余额减少了 ALLOCATE_AMOUNT
      const availableDelta = poolBefore.available - poolAfter.available;
      expect(availableDelta).toBe(ALLOCATE_AMOUNT);

      // 验证 UI 数据也反映了变化
      expect(allocAfter).toBeCloseTo(allocBefore + ALLOCATE_AMOUNT, 2);
      expect(availAfter).toBeCloseTo(availBefore - ALLOCATE_AMOUNT, 2);

      console.log(`✓ 分配 ¥${ALLOCATE_AMOUNT} 验证通过: allocated +¥${allocatedDelta}, available -¥${availableDelta}`);
    });
  });

  test.describe('UC2: 余额不足拦截', () => {
    test('分配金额超过可用额度时，应该被拦截', async ({ page }) => {
      await poolPage.goto();

      const poolId = await poolPage.getFirstPoolId();
      expect(poolId).toBeGreaterThan(0);

      // 读取可用余额
      const availBefore = await poolPage.getPoolAvailable(0);

      // 尝试分配一个不可能的金额
      await poolPage.clickAllocateButton(0);
      await poolPage.searchAndSelectUser(TARGET_USER);
      await poolPage.fillAllocateAmount(availBefore + 99999);

      // 提交
      await poolPage.submitAllocate();

      // 应该显示错误（弹窗仍然存在，或出现 error toast）
      const errorIndicator = page.locator(
        '[data-sonner-toaster] li, [role="status"], [role="alert"], .text-destructive'
      ).filter({ hasText: /error|fail|失败|不足|exceed/i });

      const hasError = await errorIndicator.first().isVisible().catch(() => false);
      // 如果弹窗仍存在，说明提交被拦截
      const dialogStillOpen = await poolPage.allocateDialog
        .isVisible()
        .catch(() => false);

      expect(
        hasError || dialogStillOpen,
        '超额分配应该被拦截（错误提示 或 弹窗未关闭）'
      ).toBe(true);

      console.log('✓ 超额分配被正确拦截');
    });
  });

  test.describe('UC3: 分配后用户余额验证', () => {
    test('分配完成后，用户余额应增加对应金额', async ({
      page,
      request,
    }) => {
      // ── 先获取用户 ID ───────────────────────────────────
      const searchResp = await request.get(
        `/api/user/search?q=${TARGET_USER}`
      );
      const searchBody = await searchResp.json();
      const users = searchBody?.data ?? [];
      const targetUser = users.find(
        (u: any) => u.username === TARGET_USER
      );
      if (!targetUser) {
        test.skip(true, `用户 ${TARGET_USER} 不存在，跳过余额验证`);
        return;
      }
      const userId = targetUser.id;
      const balanceBefore = await getUserBalance(request, userId);
      console.log(`[Before] User #${userId} (${TARGET_USER}) balance=¥${balanceBefore.toFixed(2)}`);

      // ── 执行分配 ────────────────────────────────────────
      await poolPage.goto();
      const poolId = await poolPage.getFirstPoolId();
      const poolBefore = await getPoolData(request, poolId);

      if (poolBefore.available < ALLOCATE_AMOUNT) {
        test.skip(
          true,
          `预算池可用余额 ¥${poolBefore.available.toFixed(2)} 不足 ¥${ALLOCATE_AMOUNT}`
        );
        return;
      }

      await poolPage.clickAllocateButton(0);
      await poolPage.searchAndSelectUser(TARGET_USER);
      await poolPage.fillAllocateAmount(ALLOCATE_AMOUNT);
      await poolPage.fillAllocateRemark(`E2E user balance verify ${Date.now()}`);
      await poolPage.submitAllocate();

      // 等一会让后端处理
      await page.waitForTimeout(2000);

      // ── 验证用户余额增加 ─────────────────────────────────
      const balanceAfter = await getUserBalance(request, userId);
      console.log(`[After] User #${userId} (${TARGET_USER}) balance=¥${balanceAfter.toFixed(2)}`);

      const balanceDelta = balanceAfter - balanceBefore;
      expect(
        balanceDelta,
        `用户余额应增加 ¥${ALLOCATE_AMOUNT}，实际变化 ¥${balanceDelta.toFixed(2)}`
      ).toBe(ALLOCATE_AMOUNT);

      console.log(`✓ 用户余额验证通过: ¥${balanceBefore.toFixed(2)} → ¥${balanceAfter.toFixed(2)} (+¥${ALLOCATE_AMOUNT})`);
    });
  });
});
