const GITHUB_REPO_API = 'https://api.github.com/repos/decardlabs/uniapi';
const GITHUB_TAGS_PAGE = 'https://github.com/decardlabs/uniapi/tags';

const versionCollator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: 'base',
});

type GitHubTag = {
  name?: string;
};

type GitHubRelease = {
  tag_name?: string;
  body?: string;
  html_url?: string;
};

export type UpdateInfo = {
  tag_name: string;
  content: string;
  html_url: string;
};

function compareVersionTags(left: string, right: string) {
  return versionCollator.compare(right.replace(/^v/i, ''), left.replace(/^v/i, ''));
}

export function selectLatestTag(tags: GitHubTag[]): string | null {
  const candidates = tags
    .map((tag) => tag.name?.trim())
    .filter((tag): tag is string => Boolean(tag) && /^v?\d/.test(tag));

  if (candidates.length === 0) {
    return null;
  }

  return [...candidates].sort(compareVersionTags)[0];
}

async function fetchJSON<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`GitHub request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function fetchLatestVersion(): Promise<UpdateInfo | null> {
  try {
    const tags = await fetchJSON<GitHubTag[]>(`${GITHUB_REPO_API}/tags?per_page=20`);
    const latestTag = selectLatestTag(tags);
    if (latestTag) {
      return {
        tag_name: latestTag,
        content: '',
        html_url: GITHUB_TAGS_PAGE,
      };
    }
  } catch {
    // Fall back to releases when tag lookup is unavailable.
  }

  const latestRelease = await fetchJSON<GitHubRelease>(`${GITHUB_REPO_API}/releases/latest`);
  if (!latestRelease.tag_name) {
    return null;
  }

  return {
    tag_name: latestRelease.tag_name,
    content: latestRelease.body ?? '',
    html_url: latestRelease.html_url ?? GITHUB_TAGS_PAGE,
  };
}

export { GITHUB_TAGS_PAGE };