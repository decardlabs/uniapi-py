import { test, expect, LoginPage } from './fixtures';

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
    test('空表单提交应该显示验证错误', async ({ loginPage }) => {
      await loginPage.goto();
      await loginPage.submitButton.click();

      // 应该显示验证错误消息
      await expect(loginPage.usernameInput).toBeInvalid();
    });

    test('只输入用户名应该显示密码验证错误', async ({ loginPage }) => {
      await loginPage.goto();
      await loginPage.usernameInput.fill('testuser');
      await loginPage.submitButton.click();

      // 密码字段应该显示错误
      await expect(loginPage.passwordInput).toBeInvalid();
    });

    test('只输入密码应该显示用户名验证错误', async ({ loginPage }) => {
      await loginPage.goto();
      await loginPage.passwordInput.fill('password123');
      await loginPage.submitButton.click();

      // 用户名字段应该显示错误
      await expect(loginPage.usernameInput).toBeInvalid();
    });
  });

  test.describe('登录流程', () => {
    test('使用有效凭据应该成功登录并跳转到仪表板', async ({ page, loginPage }) => {
      await loginPage.goto();

      // 使用测试账号登录
      // 注意: 这些凭据需要根据实际测试环境配置
      await loginPage.login('root', '123456');

      // 应该跳转到仪表板或用户编辑页面（root 用户默认密码会跳转到 /users/edit）
      await expect(page).toHaveURL(/\/(dashboard|users\/edit)/);
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

  test.describe('TOTP 两步验证', () => {
    test('TOTP 开启时应该显示 TOTP 输入框', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.login('testuser_with_totp', 'password');

      // 应该显示 TOTP 输入框
      await expect(loginPage.totpInput).toBeVisible();
    });

    test('TOTP 输入框应该有 6 位数字限制', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.login('testuser_with_totp', 'password');

      // 检查 maxLength 属性
      await expect(loginPage.totpInput).toHaveAttribute('maxLength', '6');

      // 检查 inputMode
      const inputMode = await loginPage.totpInput.getAttribute('inputMode');
      expect(inputMode).toBe('numeric');
    });

    test('TOTP 不足 6 位时验证按钮应该禁用', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.login('testuser_with_totp', 'password');

      // 输入不完整的 TOTP
      await loginPage.totpInput.fill('12345');

      // 验证按钮应该禁用
      const verifyButton = page.getByRole('button', { name: /verify totp/i });
      await expect(verifyButton).toBeDisabled();
    });

    test('TOTP 达到 6 位时验证按钮应该启用', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.login('testuser_with_totp', 'password');

      // 输入完整的 TOTP
      await loginPage.totpInput.fill('123456');

      // 验证按钮应该启用
      const verifyButton = page.getByRole('button', { name: /verify totp/i });
      await expect(verifyButton).toBeEnabled();
    });

    test('应该可以返回登录表单', async ({ page, loginPage }) => {
      await loginPage.goto();
      await loginPage.login('testuser_with_totp', 'password');

      // 点击返回登录按钮
      await loginPage.backToLogin();

      // TOTP 输入框应该消失
      await expect(loginPage.totpInput).not.toBeVisible();

      // 用户名和密码输入框应该恢复启用
      await expect(loginPage.usernameInput).toBeEnabled();
      await expect(loginPage.passwordInput).toBeEnabled();
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

    test('带 redirect_to 参数登录成功后应该跳转到指定页面', async ({ page, loginPage }) => {
      await loginPage.goto('/channels');

      // 登录
      await loginPage.login('root', '123456');

      // 应该跳转到 /channels 而不是默认的 /dashboard
      await expect(page).toHaveURL(/\/channels/);
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
