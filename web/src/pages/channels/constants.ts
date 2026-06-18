export interface ChannelType {
  key: number;
  text: string;
  value: number;
  color?: string;
  tip?: string;
  description?: string;
}

export interface Model {
  id: string;
  name: string;
}


import api from '@/lib/api';

/**
 * Fetch channel types from backend API.
 * Returns: Promise<ChannelType[]>
 */
export async function fetchChannelTypes(): Promise<ChannelType[]> {
  const res = await api.get('/api/channel/types');
  // API returns { success: true, data: [...] }
  if (res.data && Array.isArray(res.data.data)) {
    return res.data.data;
  }
  throw new Error('Failed to fetch channel types');
}

export const CHANNEL_TYPES_WITH_DEDICATED_BASE_URL = new Set<number>([50]);
export const CHANNEL_TYPES_WITH_CUSTOM_KEY_FIELD = new Set<number>();

// Mainstream model whitelist per channel type (5-8 models each).
// Used to filter the model dropdown to show only actively-used models.
// The "Fill All" button still exposes every model from the backend catalog.
export const MAINSTREAM_MODELS: Record<number, string[]> = {
  // OpenRouter (type 20) - curated 10 models
  20: [
    'anthropic/claude-opus-4.7',
    'anthropic/claude-opus-4.6',
    'anthropic/claude-sonnet-4.6',
    'openai/gpt-5.4',
    'openai/gpt-4',
    'openai/gpt-4o',
    'openai/gpt-4o-mini',
    'openai/gpt-5.3-codex',
    'xiaomi/mimo-v2-pro',
    'x-ai/grok-4.1-fast',
  ],
  // Tencent Hunyuan (type 23, 腾讯混元)
  23: ['hunyuan-lite', 'hunyuan-pro', 'hunyuan-turbo'],
  // Moonshot / Kimi (type 25)
  25: ['kimi-k2.6'],
  // MiniMax (type 27)
  27: ['MiniMax-Text-01', 'MiniMax-M1', 'MiniMax-M2.7', 'MiniMax-M2.7-highspeed', 'MiniMax-M2.5', 'MiniMax-M2.5-highspeed'],
  // DeepSeek (type 36) — models in deepseek adaptor pricing
  36: ['deepseek-v4-pro', 'deepseek-v4-flash'],
  // GLM / Zhipu OpenAI-compatible (type 37)
  37: ['glm-5.1'],
  // Zhipu native protocol (type 16)
  16: ['glm-5.1'],
  // Doubao (type 41) — top Ark endpoint models
  41: [
    'doubao-seed-2-0-pro-260215',
    'doubao-seed-2-0-lite-250820',
    'doubao-seed-2-0-mini-250820',
    'doubao-1-5-pro-32k-250115',
    'doubao-1-5-lite-32k-250115',
  ],
  // SiliconFlow (type 45) — top curated models
  45: [
    'Qwen/Qwen3-235B-A22B',
    'Qwen/Qwen3-32B',
    'Qwen/Qwen2.5-72B-Instruct',
    'deepseek-chat',
    'meta-llama/Meta-Llama-3.1-70B-Instruct',
  ],
  // Alibaba Qwen / DashScope (type 17)
  17: ['qwen3.6-plus', 'qwen3.6-flash'],
  // Tencent TokenHub (type 55) — top aggregated models
  55: [
    'hunyuan-turbos-latest',
    'hunyuan-t1-latest',
    'hunyuan-lite',
    'deepseek-v4-flash',
    'deepseek-v3',
    'deepseek-r1',
  ],
  // OpenAI Compatible (type 50, no whitelist — user defines their own models)
  50: [],
};

export const OPENAI_COMPATIBLE_API_FORMAT_OPTIONS = [
  { value: 'chat_completion', label: 'ChatCompletion (default)' },
  { value: 'response', label: 'Response' },
];

export const COZE_AUTH_OPTIONS = [
  {
    key: 'personal_access_token',
    text: 'Personal Access Token',
    value: 'personal_access_token',
  },
  { key: 'oauth_jwt', text: 'OAuth JWT', value: 'oauth_jwt' },
];

export const MODEL_MAPPING_EXAMPLE = {
  'client-facing-model': 'provider/actual-model-name',
  'gpt-4o-mini': 'openai/gpt-4o-mini',
  'claude-sonnet': 'anthropic/claude-sonnet-4',
};

export const MODEL_CONFIGS_EXAMPLE = {
  'provider/actual-model-name': {
    ratio: 1,
    completion_ratio: 1,
    max_tokens: 128000,
  },
  'vision/model-example': {
    ratio: 1.2,
    completion_ratio: 1.5,
    max_tokens: 65536,
  },
} satisfies Record<string, Record<string, unknown>>;

export const TOOLING_CONFIG_EXAMPLE = {
  whitelist: ['web_search'],
  pricing: {
    web_search: {
      usd_per_call: 0.025,
    },
  },
} satisfies Record<string, unknown>;

export const OAUTH_JWT_CONFIG_EXAMPLE = {
  client_type: 'jwt',
  client_id: '123456789',
  coze_www_base: 'https://www.coze.cn',
  coze_api_base: 'https://api.coze.cn',
  private_key: '-----BEGIN PRIVATE KEY-----\n***\n-----END PRIVATE KEY-----',
  public_key_id: '***********************************************************',
};

export const INFERENCE_PROFILE_ARN_MAP_EXAMPLE = {
  'anthropic.claude-3-5-sonnet-20240620-v1:0':
    'arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.anthropic.claude-3-5-sonnet-20240620-v1:0',
};
