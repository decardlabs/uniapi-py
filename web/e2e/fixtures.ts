import type { Locator, Page } from '@playwright/test';
import { test as base, expect } from '@playwright/test';

/**
 * 自定义 fixtures，用于登录测试
 */
export class LoginPage {
  readonly page: Page;

  // Selectors
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly form: Locator;
  readonly errorMessage: Locator;
  readonly totpInput: Locator;
  readonly forgotPasswordLink: Locator;
  readonly signUpLink: Locator;
  readonly systemName: Locator;

  constructor(page: Page) {
    this.page = page;

    this.usernameInput = page.getByLabel(/username/i);
    this.passwordInput = page.getByLabel(/password/i);
    this.submitButton = page.getByRole('button', { name: /sign in/i });
    this.form = page.getByTestId('login-form');
    this.errorMessage = page.locator('[class*="text-destructive"]');
    this.totpInput = page.getByPlaceholder(/6-digit totp code/i);
    this.forgotPasswordLink = page.getByRole('link', { name: /forgot password/i });
    this.signUpLink = page.getByRole('link', { name: /sign up/i });
    this.systemName = page.getByText(/sign in to/i);
  }

  /**
   * 访问登录页面
   */
  async goto(redirectTo?: string) {
    const url = redirectTo ? `/login?redirect_to=${encodeURIComponent(redirectTo)}` : '/login';
    await this.page.goto(url);
    await this.expectLoaded();
  }

  /**
   * 等待页面加载
   */
  async expectLoaded() {
    await expect(this.form).toBeVisible();
    await expect(this.usernameInput).toBeVisible();
    await expect(this.passwordInput).toBeVisible();
    await expect(this.submitButton).toBeVisible();
  }

  /**
   * 执行登录
   */
  async login(username: string, password: string) {
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  /**
   * 输入 TOTP 验证码
   */
  async enterTotp(code: string) {
    await this.totpInput.fill(code);
    await this.page.getByRole('button', { name: /verify totp/i }).click();
  }

  /**
   * 返回登录表单（TOTP 模式）
   */
  async backToLogin() {
    await this.page.getByRole('button', { name: /back to login/i }).click();
  }

  /**
   * 导航到注册页面
   */
  async goToRegister() {
    await this.signUpLink.click();
  }

  /**
   * 导航到忘记密码页面
   */
  async goToForgotPassword() {
    await this.forgotPasswordLink.click();
  }
}

// 创建 fixture
export const test = base.extend<{ loginPage: LoginPage }>({
  loginPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await use(loginPage);
  },
});

export { expect };
export type { Locator, Page };

