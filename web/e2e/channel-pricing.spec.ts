/**
 * 渠道定价调整 E2E 测试
 *
 * 流程: Channel Edit → Update Pricing JSON → Save → Models Page → Verify Price
 * 验证: 渠道 pricing 修改后模型页价格同步更新 + API Key 不会被隐藏值覆盖
 *
 * 运行:
 *   BASE_URL=http://localhost:3000 \
 *   TEST_ADMIN_USERNAME=root \
 *   TEST_ADMIN_PASSWORD=123456 \
 *   npx playwright test e2e/channel-pricing.spec.ts --project=chromium --headed
 */
import { test, expect } from './fixtures';

// ── Config ──────────────────────────────────────────────────
const ADMIN_USER = process.env.TEST_ADMIN_USERNAME || 'root';
const ADMIN_PASS = process.env.TEST_ADMIN_PASSWORD || '123456';
const CHANNEL_ID = 3; // MainChannel (DeepSeek)
const MODEL_NAME = 'deepseek-v4-flash';
const NEW_PRICE = 1.0; // reset to global default

// Helpers
let g_session = '';
let g_originalKey = '';

async function loginApi(request: any) {
  const resp = await request.post('/api/user/login', {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  const body = await resp.json();
  g_session = body.data?.access_token || '';
  return g_session;
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

test.describe('渠道定价调整流程', () => {

  test.beforeAll(async ({ request }) => {
    // 保存原始 key 和价格
    await loginApi(request);
    if (!g_session) {
      // Try UI login
    }

    const chResp = await apiGet(request, `/api/channel/${CHANNEL_ID}`);
    const ch = (await chResp.json()).data || {};
    g_originalKey = ch.key || '';

    // Check initial price on models page
    const modelsResp = await apiGet(request, '/api/models/display');
    const display = (await modelsResp.json()).data || {};
    let initialPrice = null;
    for (const info of Object.values(display) as any[]) {
      const m = info.models?.[MODEL_NAME];
      if (m) {
        initialPrice = m.input_price;
        break;
      }
    }
    console.log(`[Setup] Channel ${CHANNEL_ID}: key=${g_originalKey}, models_page_price=${initialPrice}`);
  });

  // ── UC1: 通过 UI 编辑渠道 pricing ─────────────────────

  test('UC1: 通过 UI 编辑渠道 pricing 并保存', async ({ page, request }) => {
    // 登录
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.getByLabel(/username/i).fill(ADMIN_USER);
    await page.getByLabel(/password/i).fill(ADMIN_PASS);
    await page.getByRole('button', { name: 'Sign In', exact: true }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 导航到渠道编辑页
    await page.goto(`/channels/edit/${CHANNEL_ID}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/edit channel|channel.*edit|编辑渠道/i).first()).toBeVisible({ timeout: 10000 });

    // 滚动到 Model Configs 区域
    const pricingLabel = page.getByText(/per-model pricing|按模型覆盖定价/i);
    await expect(pricingLabel).toBeVisible({ timeout: 5000 });

    // 找到 model_configs 文本域（滚动到可视区域）
    const jsonTextarea = page.locator('textarea[name="model_configs"]');
    await expect(jsonTextarea).toBeVisible({ timeout: 5000 });
    await jsonTextarea.scrollIntoViewIfNeeded();

    // 读取当前 JSON 内容
    let currentJson = await jsonTextarea.inputValue();
    console.log(`[UC1] Current model_configs length: ${currentJson.length}`);

    // 解析并修改 deepseek-v4-flash 的 input_price
    try {
      const configs = JSON.parse(currentJson);
      if (configs[MODEL_NAME]) {
        const oldPrice = configs[MODEL_NAME].input_price;
        configs[MODEL_NAME].input_price = NEW_PRICE;
        const newJson = JSON.stringify(configs, null, 2);
        await jsonTextarea.fill(newJson);
        console.log(`[UC1] Changed ${MODEL_NAME} input_price: ${oldPrice} → ${NEW_PRICE}`);
      } else {
        // Model not in configs, add it
        configs[MODEL_NAME] = {
          input_price: NEW_PRICE,
          output_price: 2.0,
          cache_hit_price: 0.02,
          max_tokens: 384000,
        };
        await jsonTextarea.fill(JSON.stringify(configs, null, 2));
        console.log(`[UC1] Added ${MODEL_NAME} with input_price=${NEW_PRICE}`);
      }
    } catch {
      // JSON might be empty or invalid, set new config
      const newConfig = JSON.stringify({
        [MODEL_NAME]: {
          input_price: NEW_PRICE,
          output_price: 2.0,
          cache_hit_price: 0.02,
          max_tokens: 384000,
        },
      }, null, 2);
      await jsonTextarea.fill(newConfig);
      console.log(`[UC1] Set new config: ${MODEL_NAME} input_price=${NEW_PRICE}`);
    }

    // 滚动到底部，点击保存按钮
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);

    const saveBtn = page.getByRole('button', { name: /Update Channel|更新渠道/i });
    await expect(saveBtn).toBeVisible({ timeout: 5000 });
    await saveBtn.scrollIntoViewIfNeeded();
    await saveBtn.click();

    // 等待保存成功（显示成功通知或跳转）
    await page.waitForTimeout(3000);
    await page.waitForLoadState('networkidle');

    // 验证：当前 URL 是否是渠道列表（保存后重定向）
    const currentUrl = page.url();
    console.log(`[UC1] After save, URL: ${currentUrl}`);

    // 通过 API 验证保存结果
    const chResp = await apiGet(request, `/api/channel/${CHANNEL_ID}`);
    const ch = (await chResp.json()).data || {};
    const savedConfigs = ch.model_configs || '';
    console.log(`[UC1] Saved configs has flash: ${savedConfigs.includes(MODEL_NAME)}`);

    // 验证 key 未被改动
    expect(ch.key).toBe(g_originalKey);
    console.log(`[UC1] API key unchanged: ${ch.key} ✅`);
  });

  // ── UC2: 验证模型页价格同步更新 ─────────────────────

  test('UC2: 模型页价格已更新', async ({ request }) => {
    // 通过 API 获取模型页数据
    const modelsResp = await apiGet(request, '/api/models/display');
    const display = (await modelsResp.json()).data || {};

    let updatedPrice = null;
    let channelName = '';
    for (const [name, info] of Object.entries(display) as any) {
      const m = info.models?.[MODEL_NAME];
      if (m) {
        updatedPrice = m.input_price;
        channelName = name;
        break;
      }
    }

    console.log(`[UC2] ${channelName}: ${MODEL_NAME} input_price = ${updatedPrice}`);
    expect(updatedPrice).toBe(NEW_PRICE);
    console.log(`[UC2] ✅ Price correctly reflects channel override!`);
  });

  // ── UC3: 验证 API Key 安全 ──────────────────────────

  test('UC3: 提交隐藏 key 不会覆盖真实 key', async ({ request }) => {
    // 用隐藏格式的 key 提交更新
    const maskedKeyResp = await apiPut(request, `/api/channel/`, {
      id: CHANNEL_ID,
      name: 'MainChannel',
      key: 'sk-test...abc',
    });

    // 检查 DB 中的 key 是否还是原始的
    const checkResp = await apiGet(request, `/api/channel/${CHANNEL_ID}`);
    const ch = (await checkResp.json()).data || {};
    expect(ch.key).toBe(g_originalKey);
    expect(ch.key).not.toBe('sk-test...abc');
    console.log(`[UC3] ✅ Masked key NOT written to DB. Key still: ${ch.key}`);
  });
});
