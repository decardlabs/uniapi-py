/**
 * Token CRUD E2E test.
 *
 * Tests the full lifecycle: create -> read -> delete for API tokens
 * via the management API.
 *
 * Run:
 *   CI=true BASE_URL=http://localhost:3001 \
 *   npx playwright test e2e/token-crud.spec.ts --project=chromium
 */

import { test as base, expect, request as pwRequest } from '@playwright/test';

const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || '123456';
const BASE = process.env.BASE_URL || 'http://localhost:3001';
const TOKEN_NAME = `E2E Token ${Date.now()}`;

let g_tokenId = 0;
let g_tokenKey = '';

// Fixture: authenticated API request context
const test = base.extend<{ api: any }>({
  api: async ({}, use) => {
    const loginResp = await (await pwRequest.newContext({ baseURL: BASE })).post('/api/user/login', {
      data: { username: ADMIN_USER, password: ADMIN_PASS },
    });
    expect(loginResp.ok(), `登录失败: ${await loginResp.text()}`).toBe(true);
    const cookie = (loginResp.headers()['set-cookie'] || '').split(';')[0];
    const ctx = await pwRequest.newContext({
      baseURL: BASE,
      extraHTTPHeaders: { Cookie: cookie },
    });
    await use(ctx);
    await ctx.dispose();
  },
});

test.describe('Token CRUD', () => {
  test('UC1: 创建 Token', async ({ api }) => {
    const resp = await api.post('/api/token/', {
      data: {
        name: TOKEN_NAME,
        models: 'gpt-4,deepseek-chat',
        expired_time: '',
      },
    });
    expect(resp.ok(), `创建失败: ${await resp.text()}`).toBe(true);
    const body = await resp.json();
    const token = body?.data ?? body;
    g_tokenId = token?.id ?? 0;
    g_tokenKey = token?.key ?? '';
    expect(g_tokenId).toBeGreaterThan(0);
    expect(g_tokenKey).toBeTruthy();
    expect(g_tokenKey).toContain('sk-');
    console.log(`[UC1] Token 创建成功 (id=${g_tokenId}, key=${g_tokenKey.slice(0, 12)}...)`);
  });

  test('UC2: 列表包含新建 Token', async ({ api }) => {
    expect(g_tokenId).toBeGreaterThan(0);
    const resp = await api.get('/api/token/?p=0&size=20');
    expect(resp.ok()).toBe(true);
    const body = await resp.json();
    const tokens: any[] = body?.data ?? [];
    const found = tokens.find((t: any) => t.id === g_tokenId);
    expect(found, '新建 Token 应在列表中').toBeDefined();
    expect(found?.name).toBe(TOKEN_NAME);
    expect(found?.status).toBe(1);
    console.log(`[UC2] Token 在列表中: id=${found?.id}, name=${found?.name}`);
  });

  test('UC3: 删除 Token', async ({ api }) => {
    expect(g_tokenId).toBeGreaterThan(0);
    const resp = await api.delete(`/api/token/${g_tokenId}`);
    expect(resp.ok(), `删除失败: ${await resp.text()}`).toBe(true);

    // Verify deletion
    const list = await api.get('/api/token/?p=0&size=20');
    const lBody = await list.json();
    const tokens: any[] = lBody?.data ?? [];
    const found = tokens.find((t: any) => t.id === g_tokenId);
    expect(found, '已删除 Token 不应在列表中').toBeUndefined();
    console.log(`[UC3] Token 删除成功 (id=${g_tokenId})`);
  });
});
