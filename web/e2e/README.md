# Playwright E2E Tests

## 快速开始

### 1. 安装依赖

```bash
cd web/modern
npm install -D @playwright/test
```

### 2. 安装浏览器

```bash
npx playwright install chromium
# 或安装所有浏览器
npx playwright install
```

### 3. 配置测试账号

复制环境变量文件并修改：

```bash
cp e2e/.env.example e2e/.env
```

### 4. 运行测试

```bash
# 开发模式 (自动启动 dev server)
npm run test:e2e

# 交互式 UI 模式
npm run test:e2e:ui

# 带 UI 运行 (非 headless)
npm run test:e2e:headed

# 只运行 Chromium
npm run test:e2e:chromium

# 只运行移动端
npm run test:e2e:mobile
```

## 调试

### 1. 使用 Playwright Inspector

```bash
npx playwright test --debug
```

### 2. 查看测试报告

```bash
npx playwright show-report
```

### 3. 查看追踪文件

打开 https://trace.playwright.dev 并上传 `trace.zip`

## 添加新测试

在 `e2e/` 目录下创建新的 `.spec.ts` 文件：

```typescript
import { test, expect } from './fixtures';

test.describe('新功能测试', () => {
  test('测试用例', async ({ page }) => {
    await page.goto('/');
    // ...
  });
});
```

## 常用命令

```bash
# 运行特定测试文件
npx playwright test e2e/login.spec.ts

# 运行特定测试用例
npx playwright test e2e/login.spec.ts --grep "应该正确渲染"

# 并行运行
npx playwright test --workers=4

# 生成截图和视频
npx playwright test --trace=on-first-retry --video=retain-on-failure
```
