# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: login.spec.ts >> 登录页面 >> 页面跳转 >> 点击忘记密码链接应该跳转到密码重置页面
- Location: e2e/login.spec.ts:180:5

# Error details

```
Error: page.goto: Target page, context or browser has been closed
Call log:
  - navigating to "http://localhost:3000/login", waiting until "load"

```

```
Error: write EPIPE
```