/**
 * 同名渠道定价同步 E2E 测试
 *
 * 流程:
 *   编辑 Minimaxchannel (ID 1) MiniMax-M3 价格 → 保存
 *   → 验证 Minimaxchannel (#2) (ID 2) 价格同步更新
 *   → 恢复原始价格
 *
 * 运行:
 *   BASE_URL=http://localhost:3000 \
 *   TEST_ADMIN_USERNAME=root \
 *   TEST_ADMIN_PASSWORD=123456 \
 *   npx playwright test e2e/pricing-sync.spec.ts --project=chromium --headed
 */
import { test, expect } from './fixtures';

const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || '123456';

// 两个 Minimaxchannel
const CH1_ID = 1;
const CH2_ID = 2;

let g_session = '';
let g_originalCh1Price = 0;
let g_originalCh2Price = 0;

async function loginApi(request: any) {
  const resp = await request.post('/api/user/login', {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  const body = await resp.json();
  g_session = body.data?.access_token || '';
}

async function apiGet(request: any, path: string) {
  return request.get(path, { headers: { Authorization: `Bearer ${g_session}` } });
}

async function apiPut(request: any, path: string, data: any) {
  return request.put(path, {
    headers: { Authorization: `Bearer ${g_session}`, 'Content-Type': 'application/json' },
    data,
  });
}

test.describe('同名渠道定价同步', () => {

  test.beforeAll(async ({ request }) => {
    await loginApi(request);

    // 保存两个渠道原始的 MiniMax-M3 价格
    async function getM3Price(chId: number) {
      const resp = await apiGet(request, `/api/channel/${chId}`);
      const ch = (await resp.json()).data || {};
      const mc = ch.model_configs || '{}';
      try {
        const parsed = JSON.parse(mc);
        return parsed['MiniMax-M3']?.input_price || 0;
      } catch { return 0; }
    }

    g_originalCh1Price = await getM3Price(CH1_ID);
    g_originalCh2Price = await getM3Price(CH2_ID);
    console.log(`[Setup] Ch1 M3 price = ${g_originalCh1Price}`);
    console.log(`[Setup] Ch2 M3 price = ${g_originalCh2Price}`);
  });

  // ── UC1: 修改渠道 1 价格，验证渠道 2 同步 ───────────

  test('UC1: 修改同名渠道 pricing 并验证同步', async ({ page, request }) => {
    // UI 登录
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.getByLabel(/username/i).fill(ADMIN_USER);
    await page.getByLabel(/password/i).fill(ADMIN_PASS);
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 导航到渠道 1 编辑页
    await page.goto(`/channels/edit/${CH1_ID}`);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('textarea[name="model_configs"]')).toBeVisible({ timeout: 10000 });

    // 读取当前 model_configs，把 MiniMax-M3 input_price +1
    const textarea = page.locator('textarea[name="model_configs"]');
    const currentJson = await textarea.inputValue();
    const configs = JSON.parse(currentJson);
    const testPrice = g_originalCh1Price + 1;
    configs['MiniMax-M3'].input_price = testPrice;
    await textarea.fill(JSON.stringify(configs, null, 2));
    console.log(`[UC1] Ch1 M3 price: ${g_originalCh1Price} → ${testPrice}`);

    // 保存
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);
    const saveBtn = page.getByRole('button', { name: /Update Channel|更新渠道/i });
    await saveBtn.scrollIntoViewIfNeeded();
    await saveBtn.click();
    await page.waitForTimeout(2000);
    await page.waitForLoadState('networkidle');
    console.log(`[UC1] Saved, redirected to: ${page.url()}`);

    // 验证：渠道 2 的 MiniMax-M3 价格已同步
    const ch2Resp = await apiGet(request, `/api/channel/${CH2_ID}`);
    const ch2 = (await ch2Resp.json()).data || {};
    const ch2Mc = JSON.parse(ch2.model_configs || '{}');
    const ch2Price = ch2Mc['MiniMax-M3']?.input_price;
    console.log(`[UC1] Ch2 M3 price after sync = ${ch2Price}`);
    expect(ch2Price).toBe(testPrice);
    console.log(`[UC1] ✅ Ch2 price synced!`);
  });

  // ── UC2: 恢复原始价格 ──────────────────────────────

  test('UC2: 恢复原始价格', async ({ request }) => {
    // 把两个渠道的价格都恢复为原始值（通过 API 批量恢复）
    const restoreConfig = JSON.stringify({
      'MiniMax-M3': { input_price: g_originalCh1Price, output_price: 8, cache_hit_price: 0.5, max_tokens: 128000 },
      'MiniMax-M2.7': { input_price: 2.16, output_price: 8.64, cache_hit_price: 0.43, max_tokens: 128000 },
      'MiniMax-M2.7-highspeed': { input_price: 4.32, output_price: 17.28, cache_hit_price: 0.43, max_tokens: 128000 },
      'MiniMax-M2.5': { input_price: 2.16, output_price: 8.64, cache_hit_price: 0.22, max_tokens: 128000 },
      'MiniMax-M2.5-highspeed': { input_price: 4.32, output_price: 17.28, cache_hit_price: 0.22, max_tokens: 128000 },
      'MiniMax-M2.1': { input_price: 2.16, output_price: 8.64, cache_hit_price: 0.22, max_tokens: 128000 },
      'MiniMax-M2.1-highspeed': { input_price: 4.32, output_price: 17.28, cache_hit_price: 0.22, max_tokens: 128000 },
      'MiniMax-M2': { input_price: 2.16, output_price: 8.64, cache_hit_price: 0.22, max_tokens: 128000 },
    });

    await apiPut(request, '/api/channel/', { id: CH1_ID, model_configs: restoreConfig });
    await apiPut(request, '/api/channel/', { id: CH2_ID, model_configs: restoreConfig });

    // 验证恢复
    const verifyResp = await apiGet(request, `/api/channel/${CH1_ID}`);
    const ch = (await verifyResp.json()).data || {};
    const mc = JSON.parse(ch.model_configs || '{}');
    expect(mc['MiniMax-M3']?.input_price).toBe(g_originalCh1Price);
    console.log(`[UC2] ✅ Restored Ch1 M3 price to ${g_originalCh1Price}`);
  });
});
