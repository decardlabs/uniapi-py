import { PasskeyPromptBanner } from '@/components/auth/PasskeyPromptBanner';
import { useIsDesktop, useIsMobile } from '@/hooks/useResponsive';
import { useAuthStore } from '@/lib/stores/auth';
import { cn } from '@/lib/utils';
import { Outlet } from 'react-router-dom';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Footer } from './Footer';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import {
  buildAuthenticatedNavItems,
  buildPublicNavItems,
  groupNavItems,
} from './navigation';

/**
 * Main layout — Sidebar + Header + Content + Footer
 *
 * Desktop (≥1024px):  Fixed sidebar on left, header on top of content area.
 * Mobile/Tablet (<1024px): No sidebar, full-width header with hamburger drawer.
 */
export function Layout() {
  const isMobile = useIsMobile();
  // JS-level breakpoint control for sidebar padding — avoids Tailwind lg: compilation issues
  const isDesktop = useIsDesktop();
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Build navigation from shared config
  const isAdmin = (user?.role ?? 0) >= 10;
  const navItems = user
    ? buildAuthenticatedNavItems(t, isAdmin)
    : buildPublicNavItems(t);
  const navGroups = groupNavItems(navItems);

  // Compute sidebar width as inline style — 100% reliable, no Tailwind dependency
  const sidebarPaddingLeft = isDesktop
    ? (sidebarCollapsed ? 68 : 256)
    : 0;

  return (
    <div
      className={cn(
        'bg-background min-h-screen-dvh w-full',
        // Smooth transition for layout shift when collapsing
        'transition-[padding-left] duration-300 ease-in-out'
      )}
      style={{ paddingLeft: sidebarPaddingLeft }}
    >
      {/* Fixed Sidebar — only visible on desktop */}
      <Sidebar
        navGroups={navGroups}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Right area: Header + Content + Footer */}
      <div className="flex flex-col min-h-dvh">
        <Header />

        <PasskeyPromptBanner />

        {/* Main content — grows to fill space */}
        <main
          className={cn(
            'w-full flex-1 min-h-0',
            isMobile ? 'px-3 py-4' : 'px-4 sm:px-6 py-6'
          )}
        >
          <Outlet />
        </main>

        <Footer />
      </div>
    </div>
  );
}
