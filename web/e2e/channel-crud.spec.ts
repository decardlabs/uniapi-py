/**
 * Channel CRUD E2E test.
 *
 * Tests the full lifecycle: create -> read -> update -> delete for channels
 * via the management API. Relies on the test database (SQLITE_PATH=/tmp/uniapi_test.db)
 * which has root/123456 pre-seeded.
 *
 * Run:
 *   CI=true BASE_URL=http://localhost:3001 \
 *   npx playwright test e2e/channel-crud.spec.ts --project=chromium
 */

import { test as base, expect, request as pwRequest } from '@playwright/test';

const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || '123456';
const BASE = process.env.BASE_URL || 'http://localhost:3001';
const CHANNEL_NAME = `E2E Channel ${Date.now()}`;
const CHANNEL_TYPE = 39; // DeepSeek

let g_channelId = 0;

// Fixture: authenticated API request context (shares session cookie across tests)
const test = base.extend<{ api: any }>({
  api: async ({}, use) => {
    // Login once
    const loginResp = await (await pwRequest.newContext({ baseURL: BASE })).post('/api/user/login', {
      data: { username: ADMIN_USER, password: ADMIN_PASS },
    });
    expect(loginResp.ok(), `登录失败: ${await loginResp.text()}`).toBe(true);
    const cookie = (loginResp.headers()['set-cookie'] || '').split(';')[0];

    // Create authenticated context
    const ctx = await pwRequest.newContext({
      baseURL: BASE,
      extraHTTPHeaders: { Cookie: cookie },
    });
    await use(ctx);
    await ctx.dispose();
  },
});

test.describe('渠道 CRUD', () => {
  test('UC1: 创建渠道', async ({ api }) => {
    const resp = await api.post('/api/channel/', {
      data: {
        name: CHANNEL_NAME,
        type: CHANNEL_TYPE,
        models: 'deepseek-chat',
        key: 'sk-e2e-test-key',
        group: 'default',
        endpoint: 'https://api.deepseek.com',
        model_mapping: {},
      },
    });
    expect(resp.ok(), `创建失败: ${await resp.text()}`).toBe(true);
    const body = await resp.json();
    g_channelId = body?.data?.id ?? 0;
    expect(g_channelId).toBeGreaterThan(0);
    console.log(`[UC1] 渠道创建成功 (id=${g_channelId})`);
  });

  test('UC2: 查询列表包含新建渠道', async ({ api }) => {
    expect(g_channelId).toBeGreaterThan(0);
    const resp = await api.get(`/api/channel/search?q=${encodeURIComponent(CHANNEL_NAME)}`);
    expect(resp.ok()).toBe(true);
    const body = await resp.json();
    const channels: any[] = body?.data ?? [];
    const found = channels.find((c: any) => c.id === g_channelId);
    expect(found, '新建渠道应在搜索结果中').toBeDefined();
    expect(found?.name).toBe(CHANNEL_NAME);
    expect(found?.type).toBe(CHANNEL_TYPE);
    console.log(`[UC2] 渠道在搜索结果中: id=${found?.id}`);
  });

  test('UC3: 编辑渠道', async ({ api }) => {
    expect(g_channelId).toBeGreaterThan(0);
    const resp = await api.put('/api/channel/', {
      data: {
        id: g_channelId,
        name: CHANNEL_NAME,
        type: CHANNEL_TYPE,
        models: 'deepseek-chat,deepseek-reasoner',
        key: 'sk-e2e-test-key-updated',
        group: 'default',
        endpoint: 'https://api.deepseek.com',
        model_mapping: '{"gpt-4":"deepseek-chat"}',
        weight: 2,
      },
    });
    expect(resp.ok(), `编辑失败: ${await resp.text()}`).toBe(true);

    // Verify via detail endpoint
    const detail = await api.get(`/api/channel/${g_channelId}`);
    expect(detail.ok()).toBe(true);
    const dBody = await detail.json();
    const channel = dBody?.data ?? dBody;
    expect(channel.models).toContain('deepseek-reasoner');
    expect(channel.weight).toBe(2);
    console.log(`[UC3] 编辑成功: models=${channel.models}, weight=${channel.weight}`);
  });

  test('UC4: 删除渠道', async ({ api }) => {
    expect(g_channelId).toBeGreaterThan(0);
    const resp = await api.delete(`/api/channel/${g_channelId}`);
    expect(resp.ok(), `删除失败: ${await resp.text()}`).toBe(true);

    // Verify deletion
    const search = await api.get(`/api/channel/search?q=${encodeURIComponent(CHANNEL_NAME)}`);
    const sBody = await search.json();
    const channels: any[] = sBody?.data ?? [];
    const found = channels.find((c: any) => c.id === g_channelId);
    expect(found, '已删除渠道不应出现在搜索结果中').toBeUndefined();
    console.log(`[UC4] 删除成功 (id=${g_channelId})`);
  });
});
