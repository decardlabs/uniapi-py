import { describe, expect, it } from 'vitest';
import { channelSchema } from './schemas';

describe('channelSchema', () => {
  it('accepts legacy string value for other field', () => {
    const result = channelSchema.safeParse({
      name: 'legacy-channel',
      type: 3,
      key: 'test-key',
      base_url: 'https://example.com',
      other: '2024-03-01-preview',
      models: ['gpt-4o'],
      groups: ['default'],
      priority: 0,
      weight: 0,
      ratelimit: 0,
      config: {},
    });

    expect(result.success).toBe(true);
  });
});
