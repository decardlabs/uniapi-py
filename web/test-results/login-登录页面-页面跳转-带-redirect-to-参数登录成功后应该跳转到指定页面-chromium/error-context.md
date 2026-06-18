# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: login.spec.ts >> 登录页面 >> 页面跳转 >> 带 redirect_to 参数登录成功后应该跳转到指定页面
- Location: e2e/login.spec.ts:188:5

# Error details

```
Error: Channel closed
```

```
Error: page.goto: Target page, context or browser has been closed
Call log:
  - navigating to "http://localhost:3000/login?redirect_to=%2Fchannels", waiting until "load"

```

```
Error: browserContext.close: Target page, context or browser has been closed
```