import { expect, test, LoginPage } from './fixtures';

/**
 * Email verification code E2E tests.
 *
 * Uses a debug endpoint (DEBUG=true only) to retrieve the stored
 * verification code from the in-memory store, since no SMTP is configured
 * in the dev environment. The code is still generated and stored even
 * when SMTP is not configured.
 */
test.describe('邮箱验证', () => {
  const TEST_EMAIL = `e2e-${Date.now()}@test.com`;

  /** Send verification code and retrieve it from the debug endpoint */
  async function sendAndGetCode(request: import('@playwright/test').APIRequestContext): Promise<string> {
    // Send verification code (stored in memory even without SMTP)
    await request.get(`/api/verification?email=${encodeURIComponent(TEST_EMAIL)}`);

    // Retrieve via debug endpoint
    const debugResp = await request.get(`/api/internal/verification-code?email=${encodeURIComponent(TEST_EMAIL)}`);
    const data = await debugResp.json();
    if (!data.success) throw new Error('Failed to get verification code: ' + data.message);
    return data.data.code;
  }

  test('Settings 页面: 发送验证码并绑定邮箱', async ({ page, request }) => {
    const loginPage = new LoginPage(page);

    // Login as root
    await loginPage.goto();
    await loginPage.login('root', '123456');
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });

    // Navigate to settings
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // Wait for the profile form to render
    await expect(page.getByText('Profile Information').first()).toBeVisible({ timeout: 10000 });

    // Scroll the email field into view and fill
    const emailInput = page.locator('input[type="email"]').first();
    await expect(emailInput).toBeVisible({ timeout: 5000 });
    await emailInput.fill(TEST_EMAIL);

    // Click "Send Verification Code"
    const sendCodeBtn = page.getByRole('button', { name: /send verification code/i });
    await sendCodeBtn.click();
    await page.waitForTimeout(1000);

    // Retrieve the verification code from the in-memory store
    const code = await sendAndGetCode(request);
    expect(code).toBeTruthy();
    expect(code.length).toBe(6);

    // Enter verification code
    const codeInput = page.getByPlaceholder('Enter email verification code');
    await expect(codeInput).toBeVisible({ timeout: 5000 });
    await codeInput.fill(code);

    // Click "Bind Email"
    const bindBtn = page.getByRole('button', { name: /bind email/i });
    await bindBtn.click();

    // Wait for success notification
    await expect(page.getByText(/success/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('Settings 页面: 错误验证码应该显示错误', async ({ page, request }) => {
    const loginPage = new LoginPage(page);

    // Login as root
    await loginPage.goto();
    await loginPage.login('root', '123456');
    await page.waitForURL(/\/dashboard/, { timeout: 10000 });

    // Navigate to settings
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    // Wait for the profile form
    await expect(page.getByText('Profile Information').first()).toBeVisible({ timeout: 10000 });

    // Enter new email
    const emailInput = page.locator('input[type="email"]').first();
    await expect(emailInput).toBeVisible({ timeout: 5000 });
    await emailInput.fill(TEST_EMAIL);

    // Send verification code
    const sendCodeBtn = page.getByRole('button', { name: /send verification code/i });
    await sendCodeBtn.click();
    await page.waitForTimeout(500);

    // Enter WRONG verification code
    const codeInput = page.getByPlaceholder('Enter email verification code');
    await expect(codeInput).toBeVisible({ timeout: 5000 });
    await codeInput.fill('000000');

    // Click "Bind Email"
    const bindBtn = page.getByRole('button', { name: /bind email/i });
    await bindBtn.click();

    // Should show error message about wrong code
    await expect(page.getByText(/验证码错误/i).first()).toBeVisible({ timeout: 5000 });
  });
});
