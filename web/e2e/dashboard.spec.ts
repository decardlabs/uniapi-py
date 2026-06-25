import { expect, test } from '@playwright/test';

/**
 * Dashboard page E2E tests.
 * Data precondition: fresh DB, no logs → EmptyState shown,
 * but the filter bar (date inputs, preset buttons, Apply) is always visible.
 */
test.describe('Dashboard 页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel(/username/i).fill('root');
    await page.getByLabel(/password/i).fill('123456');
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await page.waitForURL(/\/(dashboard|users\/edit|settings)/, { timeout: 10000 });
  });

  test('登录后可以访问 Dashboard', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test('过滤器栏显示日期输入和预设按钮', async ({ page }) => {
    await page.goto('/dashboard');

    // Wait for filter to finish loading (skeleton resolves on next rAF)
    await expect(page.getByLabel(/from date/i)).toBeVisible({ timeout: 15000 });
    await expect(page.getByLabel(/to date/i)).toBeVisible({ timeout: 5000 });

    // Preset buttons should be clickable
    await expect(page.getByRole('button', { name: 'Today' })).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: '7D' })).toBeVisible();
    await expect(page.getByRole('button', { name: '30D' })).toBeVisible();
    await expect(page.getByRole('button', { name: /apply/i })).toBeVisible();
  });

  test('点击 Today 预设触发状态更新', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByLabel(/from date/i)).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: 'Today' }).click();
    // Click Apply to trigger reload with today's date
    await page.getByRole('button', { name: /apply/i }).click();
  });

  test('Admin 用户可以看到用户选择器', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByLabel(/user/i)).toBeVisible({ timeout: 15000 });
  });
});
