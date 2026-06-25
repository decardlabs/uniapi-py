import { expect, test, LoginPage } from './fixtures';

/**
 * Password change E2E tests — all share the same DB, so run serially
 * and always restore the original password at the end.
 */
test.describe('密码修改', () => {
  test.describe.configure({ mode: 'serial' });

  const ORIGINAL_PASSWORD = 'RootPass123';
  const PASSWORD_A = 'FirstNewP1!';
  const PASSWORD_B = 'SecondNewP2!';

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

  test('完整流程: 修改 → 登出 → 新密码登录 → 改回', async ({ page }) => {
    const loginPage = new LoginPage(page);

    // 数据库初始密码是 123456，先升到强密码 ORIGINAL_PASSWORD
    await loginPage.goto();
    await loginPage.login('root', '123456');
    await page.waitForURL(/\/(dashboard|users\/edit|settings)/, { timeout: 10000 });

    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await changePassword(page, '123456', ORIGINAL_PASSWORD, ORIGINAL_PASSWORD);

    // ORIGINAL_PASSWORD → PASSWORD_A
    await changePassword(page, ORIGINAL_PASSWORD, PASSWORD_A, PASSWORD_A);

    // Logout
    await logout(page);

    // Login with new password
    await loginPage.login('root', PASSWORD_A);
    await page.waitForURL(/\/(dashboard|users\/edit|settings)/, { timeout: 10000 });

    // Back to settings and restore
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    await changePassword(page, PASSWORD_A, ORIGINAL_PASSWORD, ORIGINAL_PASSWORD);
  });

  test('连续改两次密码（不刷新页面、不改密码间不登出）', async ({ page }) => {
    const loginPage = new LoginPage(page);

    // 上一个测试已经把密码恢复为 ORIGINAL_PASSWORD
    await loginPage.goto();
    await loginPage.login('root', ORIGINAL_PASSWORD);
    await page.waitForURL(/\/(dashboard|users\/edit|settings)/, { timeout: 10000 });

    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // 第一次: ORIGINAL_PASSWORD → PASSWORD_A
    await changePassword(page, ORIGINAL_PASSWORD, PASSWORD_A, PASSWORD_A);

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

    // 第三次: PASSWORD_B → 123456（恢复原始密码）
    await changePassword(page, PASSWORD_B, ORIGINAL_PASSWORD, ORIGINAL_PASSWORD);
  });
});
