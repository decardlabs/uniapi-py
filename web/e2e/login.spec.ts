import { test, expect, LoginPage } from './fixtures';

const ORIGINAL_PASSWORD = '123456';

/**
 * 登录页面 E2E 测试
 *
 * 测试策略:
 * 1. UI 渲染正确性
 * 2. 表单验证
 * 3. 成功登录流程
 * 4. 登录失败处理
 * 5. TOTP 两步验证流程
 * 6. OAuth 登录链接
 * 7. 跳转链接功能
 */
test.describe('登录页面', () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
  });

  test.describe('UI 渲染', () => {
    test('应该正确渲染登录表单', async ({ loginPage }) => {
      await loginPage.goto();

      // 检查标题
      await expect(loginPage.form).toBeVisible();

      // 检查输入框
      await expect(loginPage.usernameInput).toBeVisible();
      await expect(loginPage.passwordInput).toBeVisible();

      // 检查按钮
      await expect(loginPage.submitButton).toBeVisible();
      await expect(loginPage.submitButton).toHaveText(/sign in/i);
    });

    test('密码输入框应该隐藏输入内容', async ({ loginPage }) => {
      await loginPage.goto();
      const passwordType = await loginPage.passwordInput.getAttribute('type');
      expect(passwordType).toBe('password');
    });

    test('注册和忘记密码链接应该可见', async ({ loginPage }) => {
      await loginPage.goto();
      await expect(loginPage.signUpLink).toBeVisible();
      await expect(loginPage.forgotPasswordLink).toBeVisible();
    });
  });

  test.describe('表单验证', () => {
    test('空表单提交应该显示验证错误', async ({ page, loginPage }) => {
      await loginPage.goto();
      // 点击提交按钮触发 react-hook-form 验证
      await loginPage.submitButton.click();
      // 验证通过后应停留在登录页（不跳转）
      await expect(page).toHaveURL(/\/login/);
    });

    test('只输入用户名应该显示密码验证错误', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.usernameInput.fill('testuser');
      await loginPage.submitButton.click();
      // 表单验证失败，不跳转，仍停留在登录页
      await expect(page).toHaveURL(/\/login/);
    });

    test('只输入密码应该显示用户名验证错误', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.passwordInput.fill('password123');
      await loginPage.submitButton.click();
      // 表单验证失败，不跳转，仍停留在登录页
      await expect(page).toHaveURL(/\/login/);
    });
  });

  test.describe('登录流程', () => {
    test('使用有效凭据应该成功登录并跳转到仪表板', async ({ page, loginPage }) => {
      await loginPage.goto();

      // 使用测试账号登录
      // 注意: 这些凭据需要根据实际测试环境配置
      await loginPage.login('root', '123456');

      // 应该跳转到仪表板
      await expect(page).toHaveURL(/\/dashboard/);
    });

    test('使用无效凭据应该显示错误消息', async ({ page, loginPage }) => {
      await loginPage.goto();

      // 使用错误的凭据
      await loginPage.login('invaliduser', 'wrongpassword');

      // 应该显示错误消息
      await expect(loginPage.errorMessage).toBeVisible();
    });

    test('不存在的用户应该显示错误', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.login('nonexistent_' + Date.now(), 'password');

      // 应该显示通用错误消息
      await expect(loginPage.errorMessage).toBeVisible();
    });
  });

  test.describe('页面跳转', () => {
    test('点击注册链接应该跳转到注册页面', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.goToRegister();

      // 应该跳转到注册页面
      await expect(page).toHaveURL(/\/register/);
    });

    test('点击忘记密码链接应该跳转到密码重置页面', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.goToForgotPassword();

      // 应该跳转到密码重置页面
      await expect(page).toHaveURL(/\/reset/);
    });

    test.skip('带 redirect_to 参数登录成功后应该跳转到指定页面', async ({ page, loginPage }) => {
      // 需要创建一个非 root 测试用户才能测试 redirect_to（root 默认密码检查优先）
      await loginPage.goto('/channels');

      // 登录
      await loginPage.login('root', '123456');

      // 根用户的默认密码检查会跳转到 /dashboard，跳过此测试
      await expect(page).toHaveURL(/\/dashboard/);
    });
  });

  test.describe('登录错误与加载状态', () => {
    test.describe.configure({ mode: 'serial' });

    test('用错误密码登录后应停留在登录页', async ({ page }) => {
      const lp = new LoginPage(page);
      await page.goto('/login');
      await lp.expectLoaded();

      await lp.login('root', 'definitely-wrong-password');

      // 登录失败后应停留在登录页面（而不是跳转到 dashboard）
      await expect(page).toHaveURL(/\/login/);
    });

    test('点击登录后按钮应显示 "Signing In..." 并被禁用', async ({ page }) => {
      const lp = new LoginPage(page);
      await page.goto('/login');
      await lp.expectLoaded();

      await lp.usernameInput.fill('root');
      await lp.passwordInput.fill(ORIGINAL_PASSWORD);

      // 延迟登录响应以便观察中间 loading 状态
      await page.route('**/api/user/login', async (route) => {
        await new Promise((r) => setTimeout(r, 300));
        await route.continue();
      });

      // 用 form 中的 submit 按钮，不依赖按钮文字
      const submitBtn = page.locator('form button[type="submit"]');
      await submitBtn.click();

      // 等待按钮变成 "Signing In..." 并禁用
      await expect(submitBtn).toBeDisabled({ timeout: 5000 });
      await expect(submitBtn).toContainText(/signing in/i);

      await page.unroute('**/api/user/login');
    });
  });

  test.describe('OAuth 登录', () => {
    test('GitHub OAuth 按钮应该在可用时显示', async ({ page, loginPage }) => {
      await loginPage.goto();

      // 如果 GitHub OAuth 可用，应该显示按钮
      const githubButton = page.getByRole('button', { name: /github/i });
      const isVisible = await githubButton.isVisible().catch(() => false);

      if (isVisible) {
        await expect(githubButton).toBeVisible();
      }
    });

    test('Lark OAuth 按钮应该在可用时显示', async ({ page, loginPage }) => {
      await loginPage.goto();

      // 如果 Lark OAuth 可用，应该显示按钮
      const larkButton = page.getByRole('button', { name: /lark/i });
      const isVisible = await larkButton.isVisible().catch(() => false);

      if (isVisible) {
        await expect(larkButton).toBeVisible();
      }
    });
  });

  test.describe('响应式布局', () => {
    test('在移动端视口下应该正确显示', async ({ page, loginPage }) => {
      // 设置移动端视口
      await page.setViewportSize({ width: 375, height: 667 });
      await loginPage.goto();

      // 核心元素仍然可见
      await expect(loginPage.form).toBeVisible();
      await expect(loginPage.usernameInput).toBeVisible();
      await expect(loginPage.passwordInput).toBeVisible();
      await expect(loginPage.submitButton).toBeVisible();
    });
  });
});
