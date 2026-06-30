/**
 * Token 创建页面 E2E 测试
 *
 * 通过 UI 创建 Token，验证创建成功、列表可见、数据正确。
 *
 * 运行:
 *   CI=true BASE_URL=http://localhost:3001 \
 *   TEST_ADMIN_USERNAME=root TEST_ADMIN_PASSWORD=123456 \
 *   npx playwright test e2e/token-create-ui.spec.ts --project=chromium
 */
import { test, expect, LoginPage } from './fixtures';

const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || '123456';
const TOKEN_NAME = `E2E-Create-${Date.now()}`;

test.describe('令牌创建页面', () => {

  test('UC1: 通过 UI 创建 Token（无过期时间）', async ({ page, request }) => {
    const loginPage = new LoginPage(page);

    // 1. 登录
    await loginPage.goto();
    await loginPage.login(ADMIN_USER, ADMIN_PASS);
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });

    // 2. 导航到令牌创建页
    await page.goto('/tokens/add');
    await page.waitForLoadState('networkidle');

    // 3. 等待表单渲染
    const nameInput = page.getByPlaceholder(/enter token name/i);
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    // 4. 填写 Token Name
    await nameInput.fill(TOKEN_NAME);

    // 5. 点击 "Never Expire"
    await page.getByRole('button', { name: /never expire/i }).click();
    await page.waitForTimeout(300);

    // 6. 点击提交
    await page.getByRole('button', { name: /create token/i }).click();

    // 7. 验证创建成功 — 应跳转到令牌列表页
    await page.waitForURL(/\/tokens/, { timeout: 10000 });

    // 8. 验证列表中有新建的 Token
    await expect(page.getByText(TOKEN_NAME)).toBeVisible({ timeout: 5000 });
  });

  test('UC2: 通过 UI 创建 Token（1 小时过期）', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.login(ADMIN_USER, ADMIN_PASS);
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });

    await page.goto('/tokens/add');
    await page.waitForLoadState('networkidle');

    const nameInput = page.getByPlaceholder(/enter token name/i);
    await expect(nameInput).toBeVisible({ timeout: 10000 });

    await nameInput.fill(`${TOKEN_NAME}-1h`);

    // 点击 "1 Hour"
    await page.getByRole('button', { name: /1 hour/i }).click();
    await page.waitForTimeout(300);

    await page.getByRole('button', { name: /create token/i }).click();

    await page.waitForURL(/\/tokens/, { timeout: 10000 });
    await expect(page.getByText(`${TOKEN_NAME}-1h`)).toBeVisible({ timeout: 5000 });
  });

  test('UC3: 空名称提交应显示验证错误', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.login(ADMIN_USER, ADMIN_PASS);
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });

    await page.goto('/tokens/add');
    await page.waitForLoadState('networkidle');

    // 名称留空，直接点击创建
    await page.getByRole('button', { name: /create token/i }).click();

    // 应显示验证错误提示
    await expect(page.getByText(/token name is required/i)).toBeVisible({ timeout: 5000 });
  });
});
