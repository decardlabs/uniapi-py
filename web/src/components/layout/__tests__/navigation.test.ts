import { describe, it, expect } from 'vitest';
import {
  buildAuthenticatedNavItems,
  buildPublicNavItems,
  groupNavItems,
} from '../navigation';
import type { TFunction } from 'i18next';

// Minimal t function for testing
const t = ((key: string) => {
  const map: Record<string, string> = {
    'nav.dashboard': 'Dashboard',
    'nav.management': 'Management',
    'nav.system': 'System',
    'nav.chat': 'Chat',
    'nav.channels': 'Channels',
    'nav.tokens': 'Tokens',
    'nav.logs': 'Logs',
    'nav.top_up': 'Top Up',
    'nav.users': 'Users',
    'nav.recharges': 'Recharges',
    'nav.pools': 'Pools',
    'nav.models': 'Models',
    'nav.settings': 'Settings',
    'nav.about': 'About',
    'nav.cache_analytics': 'Cache Analytics',
    'nav.mcp_servers': 'MCP Servers',
    'nav.status': 'Status',
    'nav.tools': 'Tools',
    'nav.realtime': 'Realtime',
    'nav.redemption': 'Redemption',
  };
  return map[key] || key;
}) as unknown as TFunction;

describe('buildAuthenticatedNavItems', () => {
  it('returns both management and system items for admin users', () => {
    const items = buildAuthenticatedNavItems(t, true);
    const paths = items.map(i => i.to);
    expect(paths).toContain('/dashboard');
    expect(paths).toContain('/channels');
    expect(paths).toContain('/users');
    expect(paths).toContain('/settings');
  });

  it('excludes admin-only items for non-admin users', () => {
    const items = buildAuthenticatedNavItems(t, false);
    const paths = items.map(i => i.to);
    expect(paths).toContain('/dashboard');
    // Admin items
    expect(paths).not.toContain('/users');
    expect(paths).not.toContain('/recharges');
    expect(paths).not.toContain('/pools');
    expect(paths).not.toContain('/redemption');
  });

  it('returns chat/tokens/logs items for non-admin', () => {
    const items = buildAuthenticatedNavItems(t, false);
    const paths = items.map(i => i.to);
    expect(paths).toContain('/chat');
    expect(paths).toContain('/tokens');
    expect(paths).toContain('/logs');
  });

  it('includes cache analytics for admin', () => {
    const items = buildAuthenticatedNavItems(t, true);
    const paths = items.map(i => i.to);
    expect(paths).toContain('/cache-analytics');
  });
});

describe('buildPublicNavItems', () => {
  it('returns only public items (models/status/tools)', () => {
    const items = buildPublicNavItems(t);
    const paths = items.map(i => i.to);
    expect(paths).toContain('/models');
    expect(paths).toContain('/status');
    expect(paths).not.toContain('/channels');
    expect(paths).not.toContain('/tokens');
  });
});

describe('groupNavItems', () => {
  it('groups items by their category labels', () => {
    const items = buildAuthenticatedNavItems(t, true);
    const groups = groupNavItems(items);
    const labels = groups.map(g => g.label);
    expect(labels.length).toBeGreaterThan(0);
  });

  it('returns multiple groups with items', () => {
    const items = buildAuthenticatedNavItems(t, true);
    const groups = groupNavItems(items);
    const totalItems = groups.reduce((sum, g) => sum + g.items.length, 0);
    expect(totalItems).toBe(items.length);
  });
});
