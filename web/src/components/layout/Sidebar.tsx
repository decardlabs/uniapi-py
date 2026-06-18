import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useIsDesktop } from '@/hooks/useResponsive';
import type { NavGroup, NavItem } from './navigation';

interface SidebarProps {
  navGroups: NavGroup[];
  collapsed: boolean;
  onToggle: () => void;
}

/**
 * Sidebar navigation component — fixed left panel with collapsible support.
 * Desktop (≥1024px): always visible, can collapse to icon-only mode.
 * Mobile (<1024px): not rendered (use NavigationDrawer instead).
 */
export function Sidebar({ navGroups, collapsed, onToggle }: SidebarProps) {
  const location = useLocation();
  const { t } = useTranslation();
  // JS-level responsive control — avoids reliance on Tailwind lg: breakpoint compilation
  const isDesktop = useIsDesktop();

  // Don't render sidebar at all on mobile/tablet
  if (!isDesktop) {
    return null;
  }

  return (
    <aside
      className={cn(
        // Fixed position on desktop — no hidden/lg:flex needed since we conditionally render
        'fixed inset-y-0 left-0 z-40',
        // Background + border
        'bg-background border-r border-border',
        // Smooth width transition when collapsing
        'transition-all duration-300 ease-in-out',
        // Width states
        collapsed ? 'w-[68px]' : 'w-64',
        // Flex column for internal layout
        'flex flex-col'
      )}
      role="navigation"
      aria-label="Sidebar navigation"
    >
      {/* Logo area — always visible */}
      <div className={cn(
        'flex items-center h-16 border-b border-border flex-shrink-0',
        collapsed ? 'justify-center px-2' : 'px-4 gap-3'
      )}>
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary text-primary-foreground font-bold text-sm flex-shrink-0">
          O
        </div>
        {!collapsed && (
          <span className="text-lg font-bold truncate">UniAPI</span>
        )}
      </div>

      {/* Scrollable nav content */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-4 px-3 space-y-6">
        {navGroups.map((group) => (
          <div key={group.label}>
            {/* Group label — hidden when collapsed */}
            {!collapsed && group.label && (
              <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t(group.label, group.label === 'nav.core' ? '核心功能' : group.label === 'nav.admin' ? '管理功能' : '系统')}
              </p>
            )}

            {/* Group divider when not collapsed */}
            {!collapsed && group.label && <div className="mx-3 mb-3 border-t border-border" />}

            {/* Nav items */}
            <ul className="space-y-1">
              {group.items.map((item) => (
                <NavItemRow
                  key={item.to}
                  item={item}
                  isActive={location.pathname === item.to}
                  collapsed={collapsed}
                />
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Collapse toggle button — bottom of sidebar */}
      <div className="flex-shrink-0 border-t border-border p-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          className={cn(
            'w-full touch-target',
            collapsed ? 'justify-center px-2' : 'justify-start gap-2'
          )}
          aria-label={collapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span className="text-xs text-muted-foreground">{t('sidebar.collapse', '收起')}</span>
            </>
          )}
        </Button>
      </div>
    </aside>
  );
}

/** Single navigation item row inside the sidebar */
function NavItemRow({ item, isActive, collapsed }: { item: NavItem; isActive: boolean; collapsed: boolean }) {
  const Icon = item.icon;

  if (collapsed) {
    // Collapsed mode — icon only with tooltip
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <Link
            to={item.to}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'flex items-center justify-center w-full h-10 rounded-md transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            )}
          >
            {Icon && <Icon className="h-5 w-5" />}
          </Link>
        </TooltipTrigger>
        <TooltipContent side="right" className="font-normal">
          {item.name}
        </TooltipContent>
      </Tooltip>
    );
  }

  // Expanded mode — icon + label
  return (
    <li>
      <Link
        to={item.to}
        aria-current={isActive ? 'page' : undefined}
        className={cn(
          'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors w-full',
          isActive
            ? 'bg-primary/10 text-primary dark:bg-primary/20' // subtle active state for sidebar
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
        )}
      >
        {Icon && <Icon className="h-[18px] w-[18px] flex-shrink-0" />}
        <span className="truncate">{item.name}</span>
        {/* Active indicator dot */}
        {isActive && (
          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
        )}
      </Link>
    </li>
  );
}
