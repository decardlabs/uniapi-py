# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: login.spec.ts >> 登录页面 >> 表单验证 >> 只输入用户名应该显示密码验证错误
- Location: e2e/login.spec.ts:60:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByTestId('login-form')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for getByTestId('login-form')

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - generic [ref=e3]:
      - generic [ref=e4]: 语言
      - generic [ref=e5]:
        - button "中文" [pressed] [ref=e6] [cursor=pointer]
        - button "English" [ref=e7] [cursor=pointer]
    - generic [ref=e11]:
      - generic [ref=e12]:
        - img "Ccbot Logo" [ref=e14]
        - heading "Ccbot" [level=1] [ref=e15]
        - paragraph [ref=e16]: 登录您的管理账号
      - generic [ref=e18]:
        - generic [ref=e19]:
          - generic [ref=e20]: 邮箱地址
          - generic [ref=e21]:
            - textbox "name@company.com" [ref=e22]
            - img [ref=e23]
        - generic [ref=e26]:
          - generic [ref=e27]: 密码
          - generic [ref=e28]:
            - textbox "••••••••" [ref=e29]
            - img [ref=e30]
        - button "登录" [ref=e33] [cursor=pointer]:
          - text: 登录
          - img [ref=e34]
      - paragraph [ref=e36]:
        - text: 还没有账号？
        - link "立即注册" [ref=e37] [cursor=pointer]:
          - /url: /register
      - paragraph [ref=e39]: Ccbot 智能系统
  - alert [ref=e40]
```

# Test source

```ts
  1   | import type { Locator, Page } from '@playwright/test';
  2   | import { test as base, expect } from '@playwright/test';
  3   | 
  4   | /**
  5   |  * 自定义 fixtures，用于登录测试
  6   |  */
  7   | export class LoginPage {
  8   |   readonly page: Page;
  9   | 
  10  |   // Selectors
  11  |   readonly usernameInput: Locator;
  12  |   readonly passwordInput: Locator;
  13  |   readonly submitButton: Locator;
  14  |   readonly form: Locator;
  15  |   readonly errorMessage: Locator;
  16  |   readonly totpInput: Locator;
  17  |   readonly forgotPasswordLink: Locator;
  18  |   readonly signUpLink: Locator;
  19  |   readonly systemName: Locator;
  20  | 
  21  |   constructor(page: Page) {
  22  |     this.page = page;
  23  | 
  24  |     this.usernameInput = page.getByLabel(/username/i);
  25  |     this.passwordInput = page.getByLabel(/password/i);
  26  |     this.submitButton = page.getByRole('button', { name: /sign in/i });
  27  |     this.form = page.getByTestId('login-form');
  28  |     this.errorMessage = page.locator('[class*="text-destructive"]');
  29  |     this.totpInput = page.getByPlaceholder(/6-digit totp code/i);
  30  |     this.forgotPasswordLink = page.getByRole('link', { name: /forgot password/i });
  31  |     this.signUpLink = page.getByRole('link', { name: /sign up/i });
  32  |     this.systemName = page.getByText(/sign in to/i);
  33  |   }
  34  | 
  35  |   /**
  36  |    * 访问登录页面
  37  |    */
  38  |   async goto(redirectTo?: string) {
  39  |     const url = redirectTo ? `/login?redirect_to=${encodeURIComponent(redirectTo)}` : '/login';
  40  |     await this.page.goto(url);
  41  |     await this.expectLoaded();
  42  |   }
  43  | 
  44  |   /**
  45  |    * 等待页面加载
  46  |    */
  47  |   async expectLoaded() {
> 48  |     await expect(this.form).toBeVisible();
      |                             ^ Error: expect(locator).toBeVisible() failed
  49  |     await expect(this.usernameInput).toBeVisible();
  50  |     await expect(this.passwordInput).toBeVisible();
  51  |     await expect(this.submitButton).toBeVisible();
  52  |   }
  53  | 
  54  |   /**
  55  |    * 执行登录
  56  |    */
  57  |   async login(username: string, password: string) {
  58  |     await this.usernameInput.fill(username);
  59  |     await this.passwordInput.fill(password);
  60  |     await this.submitButton.click();
  61  |   }
  62  | 
  63  |   /**
  64  |    * 输入 TOTP 验证码
  65  |    */
  66  |   async enterTotp(code: string) {
  67  |     await this.totpInput.fill(code);
  68  |     await this.page.getByRole('button', { name: /verify totp/i }).click();
  69  |   }
  70  | 
  71  |   /**
  72  |    * 返回登录表单（TOTP 模式）
  73  |    */
  74  |   async backToLogin() {
  75  |     await this.page.getByRole('button', { name: /back to login/i }).click();
  76  |   }
  77  | 
  78  |   /**
  79  |    * 导航到注册页面
  80  |    */
  81  |   async goToRegister() {
  82  |     await this.signUpLink.click();
  83  |   }
  84  | 
  85  |   /**
  86  |    * 导航到忘记密码页面
  87  |    */
  88  |   async goToForgotPassword() {
  89  |     await this.forgotPasswordLink.click();
  90  |   }
  91  | }
  92  | 
  93  | // 创建 fixture
  94  | export const test = base.extend<{ loginPage: LoginPage }>({
  95  |   loginPage: async ({ page }, use) => {
  96  |     const loginPage = new LoginPage(page);
  97  |     await use(loginPage);
  98  |   },
  99  | });
  100 | 
  101 | export { expect };
  102 | export type { Locator, Page };
  103 | 
  104 | 
```