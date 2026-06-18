import { describe, expect, it, vi } from 'vitest';

import { fetchLatestVersion, selectLatestTag } from './versionCheck';

describe('selectLatestTag', () => {
  it('returns the highest semantic-looking tag from the tag list', () => {
    expect(selectLatestTag([{ name: 'v3.0.0' }, { name: 'v3.8.1' }, { name: 'v3.8.0' }])).toBe('v3.8.1');
  });

  it('ignores empty and non-version tags', () => {
    expect(selectLatestTag([{ name: '' }, { name: 'latest' }, { name: 'release-candidate' }])).toBeNull();
  });
});

describe('fetchLatestVersion', () => {
  it('prefers the latest tag over the latest release', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ name: 'v3.0.0' }, { name: 'v3.8.1' }],
      } as Response);

    await expect(fetchLatestVersion()).resolves.toEqual({
      tag_name: 'v3.8.1',
      content: '',
      html_url: 'https://github.com/decardlabs/uniapi/tags',
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    fetchMock.mockRestore();
  });

  it('falls back to the latest release when tag lookup fails', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: false, status: 403 } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          tag_name: 'v3.0.0',
          body: 'stable release',
          html_url: 'https://github.com/decardlabs/uniapi/releases/tag/v3.0.0',
        }),
      } as Response);

    await expect(fetchLatestVersion()).resolves.toEqual({
      tag_name: 'v3.0.0',
      content: 'stable release',
      html_url: 'https://github.com/decardlabs/uniapi/releases/tag/v3.0.0',
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    fetchMock.mockRestore();
  });
});