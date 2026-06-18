/**
 * Navigation Configuration — single source of truth for all navigation items
 * Shared by Header, Sidebar, and MobileDrawer
 */

import {
    BarChart3,
    CreditCard,
    DollarSign,
    FileText,
    Gift,
    Home,
    Info,
    MessageSquare,
    PiggyBank,
    Radio,
    Server,
    Settings,
    Users,
    Wrench,
    Zap,
    type LucideIcon
} from 'lucide-react';

/** Navigation item definition */
export interface NavItem {
  /** Display name (already translated) */
  name: string;
  /** Route path */
  to: string;
  /** Icon component (Lucide) */
  icon: LucideIcon;
  /** Whether to show this item */
  show: boolean;
  /** Requires admin role */
  requiresAdmin?: boolean;
}

/** Navigation group for sidebar grouping */
export interface NavGroup {
  /** Group label key (i18n) */
  label: string;
  /** Items in this group */
  items: NavItem[];
}

// Icon mapping — path → Lucide icon component
const iconMap: Record<string, LucideIcon> = {
  '/dashboard': Home,
  '/cache-analytics': BarChart3,
  '/channels': Zap,
  '/tokens': CreditCard,
  '/logs': FileText,
  '/users': Users,
  '/recharges': Gift,
  '/pools': PiggyBank,
  '/topup': DollarSign,
  '/models': BarChart3,
  '/chat': MessageSquare,
  '/realtime': Radio,
  '/about': Info,
  '/settings': Settings,
  '/mcps': Server,
  '/tools': Wrench,
};

/** Get the icon for a given path */
export function getNavIcon(path: string): LucideIcon | undefined {
  return iconMap[path];
}

/**
 * Build authenticated user navigation items.
 * Call this inside components (needs i18n `t` function and isAdmin flag).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function buildAuthenticatedNavItems(t: any, isAdmin: boolean): NavItem[] {
  const rawItems = [
    { name: t('common.dashboard'), to: '/dashboard', show: true },
    { name: t('common.cache_analytics'), to: '/cache-analytics', show: isAdmin, requiresAdmin: true },
    { name: t('common.tokens'), to: '/tokens', show: true },
    { name: t('common.logs'), to: '/logs', show: true },
    { name: t('common.users'), to: '/users', show: isAdmin, requiresAdmin: true },
    { name: t('common.channels'), to: '/channels', show:isAdmin, requiresAdmin: true },
    { name: t('common.mcps'), to: '/mcps', show: isAdmin, requiresAdmin: true },
    { name: t('common.recharges'), to: '/recharges', show: isAdmin, requiresAdmin: true },
    { name: t('common.pools'), to: '/pools', show: isAdmin, requiresAdmin: true },
    { name: t('common.topup'), to: '/topup', show: true },
    { name: t('common.models'), to: '/models', show: true },
    { name: t('common.tools'), to: '/tools', show: true },
    { name: t('common.status'), to: '/status', show: true },
    { name: t('common.playground'), to: '/chat', show: true },
    { name: t('common.realtime'), to: '/realtime', show: false }, // hidden
    { name: t('common.about'), to: '/about', show: true },
    { name: t('common.settings'), to: '/settings', show: isAdmin, requiresAdmin: true },
  ];

  return rawItems
    .filter((item) => item.show)
    .map((item) => ({
      ...item,
      icon: getNavIcon(item.to)!,
      href: item.to,
    }));
}

/**
 * Build public (anonymous) navigation items.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function buildPublicNavItems(t: any): NavItem[] {
  const rawItems = [
    { name: t('common.models'), to: '/models', show: true },
    { name: t('common.tools'), to: '/tools', show: true },
    { name: t('common.status'), to: '/status', show: true },
  ];

  return rawItems
    .filter((item) => item.show)
    .map((item) => ({
      ...item,
      icon: getNavIcon(item.to)!,
      href: item.to,
    }));
}

/**
 * Group navigation items for sidebar display.
 * Core items (daily use) first, admin items in separate group, system items last.
 */
export function groupNavItems(items: NavItem[]): NavGroup[] {
  const corePaths = ['/dashboard', '/tokens', '/logs', '/topup', '/models', '/tools', '/status', '/chat', '/playground'];
  const adminPaths = ['/users', '/channels', '/mcps', '/recharges', '/pools'];
  const adminExtendedPaths = ['/cache-analytics'];
  const systemPaths = ['/about', '/settings'];

  const core = items.filter((item) => corePaths.includes(item.to));
  const admin = items.filter((item) => adminPaths.includes(item.to) || adminExtendedPaths.includes(item.to));
  const system = items.filter((item) => systemPaths.includes(item.to));

  const groups: NavGroup[] = [];

  if (core.length > 0) {
    groups.push({ label: 'nav.core', items: core });
  }
  if (admin.length > 0) {
    groups.push({ label: 'nav.admin', items: admin });
  }
  if (system.length > 0) {
    groups.push({ label: 'nav.system', items: system });
  }

  return groups;
}
