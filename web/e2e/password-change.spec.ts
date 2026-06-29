import { expect, test, LoginPage } from './fixtures';

/**
 * Password change E2E tests — uses a dedicated test user to avoid
 * interfering with root user used by login tests.
 */
test.describe('密码修改', () => {
  test.describe.configure({ mode: 'serial' });

  const TEST_USER = 'pwtest_' + Date.now();
  const TEST_PASS = 'InitPass1';
  const PASSWORD_A = 'FirstNewP1!';
  const PASSWORD_B = 'SecondNewP2!';

  /** Create a test user via registration API */
  async function createTestUser(request: import('@playwright/test').APIRequestContext) {
    const res = await request.post('/api/user/register', {
      data: {
        username: TEST_USER,
        password: TEST_PASS,
        display_name: 'PWTest',
      },
    });
    const body = await res.json();
    // Registration returns a session cookie — accept it silently
    return body;
  }

  /** Fill the password change form and submit */
  async function changePassword(
    page: import('@playwright/test').Page,
    current: string,
    newPwd: string,
    confirm: string,
  ) {
    const currentInput = page.getByPlaceholder('Enter current password', { exact: true });
    const newInput = page.getByPlaceholder('Enter new password', { exact: true });
    const confirmInput = page.getByPlaceholder('Re-enter new password', { exact: true });
    const updateBtn = page.getByRole('button', { name: 'Update Password' });

    await expect(currentInput).toBeVisible({ timeout: 10000 });
    await currentInput.fill(current);
    await newInput.fill(newPwd);
    await confirmInput.fill(confirm);
    await updateBtn.click();

    await expect(page.getByText('Password updated successfully').first()).toBeVisible({ timeout: 5000 });
  }

  /** Logout via header user menu */
  async function logout(page: import('@playwright/test').Page) {
    const userMenuBtn = page.getByRole('button', { name: 'Profile', exact: true });
    await userMenuBtn.click();

    const logoutMenuItem = page.getByRole('menuitem', { name: 'Logout' });
    await expect(logoutMenuItem).toBeVisible({ timeout: 5000 });
    await logoutMenuItem.click();

    // Handle optional confirmation dialog
    const confirmBtn = page.getByRole('button', { name: /log.?out|confirm|yes/i }).first();
    if (await confirmBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await confirmBtn.click();
    }

    await expect(page.getByTestId('login-form')).toBeVisible({ timeout: 10000 });
  }

  test('完整流程: 修改 → 登出 → 新密码登录 → 改回', async ({ page, request }) => {
    // 创建测试用户
    await createTestUser(request);

    const loginPage = new LoginPage(page);

    // 用测试用户登录
    await loginPage.goto();
    await loginPage.login(TEST_USER, TEST_PASS);
    await page.waitForURL(/\/(dashboard|settings)/, { timeout: 10000 });

    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // 改密码
    await changePassword(page, TEST_PASS, PASSWORD_A, PASSWORD_A);

    // 登出
    await logout(page);

    // 用新密码登录
    await loginPage.login(TEST_USER, PASSWORD_A);
    await page.waitForURL(/\/(dashboard|settings)/, { timeout: 10000 });

    // 再改回去（方便后续手动测试）
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await changePassword(page, PASSWORD_A, TEST_PASS, TEST_PASS);
  });

  test('连续改两次密码（不刷新页面、不改密码间不登出）', async ({ page }) => {
    const loginPage = new LoginPage(page);

    // 上一个测试已经把密码恢复为 TEST_PASS
    await loginPage.goto();
    await loginPage.login(TEST_USER, TEST_PASS);
    await page.waitForURL(/\/(dashboard|settings)/, { timeout: 10000 });

    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // 第一次: TEST_PASS → PASSWORD_A
    await changePassword(page, TEST_PASS, PASSWORD_A, PASSWORD_A);

    // 不刷新、不登出，验证表单已清空
    const currentInput = page.getByPlaceholder('Enter current password', { exact: true });
    const newInput = page.getByPlaceholder('Enter new password', { exact: true });
    const confirmInput = page.getByPlaceholder('Re-enter new password', { exact: true });
    const updateBtn = page.getByRole('button', { name: 'Update Password' });

    await expect(currentInput).toHaveValue('');
    await expect(newInput).toHaveValue('');
    await expect(confirmInput).toHaveValue('');
    await expect(updateBtn).toBeEnabled();

    // 第二次: PASSWORD_A → PASSWORD_B
    await changePassword(page, PASSWORD_A, PASSWORD_B, PASSWORD_B);

    // 第三次: PASSWORD_B → TEST_PASS（恢复原始密码）
    await changePassword(page, PASSWORD_B, TEST_PASS, TEST_PASS);
  });
});
