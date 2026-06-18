import { LanguageSelector } from '@/components/LanguageSelector';
import { ThemeToggle } from '@/components/theme-toggle';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { NavigationDrawer } from '@/components/ui/mobile-drawer';
import { useResponsive } from '@/hooks/useResponsive';
import { useSystemStatus } from '@/hooks/useSystemStatus';
import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth';
import { LogOut, Menu, User } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  buildAuthenticatedNavItems,
  buildPublicNavItems,
} from './navigation';

export function Header() {
  const { t } = useTranslation();
  const { user, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isLogoutDialogOpen, setLogoutDialogOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const { isMobile, isTablet } = useResponsive();
  const { systemStatus } = useSystemStatus();

  const isAdmin = user?.role >= 10;

  // Build navigation items for mobile drawer (uses shared config from navigation.ts)
  const navItems = user
    ? buildAuthenticatedNavItems(t, isAdmin)
    : buildPublicNavItems(t);

  const navigationItems = navItems
    .map((item) => ({
      ...item,
      href: item.to,
      isActive: location.pathname === item.to,
    }));

  const performLogout = async () => {
    setIsLoggingOut(true);
    try {
      await api.get('/api/user/logout');
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setLogoutDialogOpen(false);
      setIsLoggingOut(false);
      logout();
      navigate('/login');
    }
  };

  return (
    <>
      {/* Simplified header — no nav items here (moved to Sidebar) */}
      <header className="border-b bg-background/95 backdrop-blur-sm sticky top-0 z-50 w-full">
        <div
          className="flex items-center justify-between h-14 gap-4"
          style={{
            // Left padding accounts for sidebar width on desktop; mobile has default padding
            paddingLeft: !isMobile && !isTablet ? '1rem' : undefined,
          }}
        >
          {/* Left area */}
          <div className="flex items-center flex-shrink-0 gap-3">
            {/* Mobile hamburger — opens NavigationDrawer */}
            {(isMobile || isTablet) && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMobileMenuOpen(true)}
                  className="touch-target p-2 h-9 w-9"
                  aria-label={t('header.navigation')}
                >
                  <Menu className="h-5 w-5" />
                </Button>
                {/* Mobile logo text */}
                <Link
                  to="/"
                  className="text-lg font-bold hover:text-primary transition-colors truncate max-w-[50vw]"
                >
                  {systemStatus.system_name || t('common.app_name', 'UniAPI')}
                </Link>
              </>
            )}
          </div>

          {/* Right area — actions & user menu */}
          <div className="flex items-center space-x-1 sm:space-x-2 flex-shrink-0">
            <LanguageSelector />
            <ThemeToggle />

            {user ? (
              <>
                {!isMobile && (
                  <span className="hidden xl:inline text-sm text-muted-foreground truncate max-w-32">
                    {user.username}
                  </span>
                )}

                {/* User menu — desktop dropdown / mobile handled in drawer */}
                {!isMobile && !isTablet ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="inline-flex touch-target"
                        aria-label={t('header.profile')}
                      >
                        <User className="h-5 w-5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                      <DropdownMenuLabel className="flex flex-col">
                        <span className="text-xs text-muted-foreground">
                          {t('header.signed_in_as')}
                        </span>
                        <span className="font-medium truncate">{user.username}</span>
                      </DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onSelect={() => navigate('/settings')}
                        className="flex items-center gap-2"
                      >
                        <User className="h-4 w-4" />
                        {t('header.profile')}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => setLogoutDialogOpen(true)}
                        className="flex items-center gap-2"
                      >
                        <LogOut className="h-4 w-4" />
                        {t('common.logout')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : null}
              </>
            ) : (
              <div className="flex items-center space-x-2">
                <Link
                  to="/register"
                  className="font-medium text-sm text-muted-foreground hover:text-primary transition-colors hidden sm:inline"
                >
                  {t('common.register')}
                </Link>
                <Button asChild size="sm" className="touch-target">
                  <Link to="/login">{t('common.login')}</Link>
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Mobile Navigation Drawer — full nav with profile/logout footer */}
        <NavigationDrawer
          isOpen={mobileMenuOpen}
          onClose={() => setMobileMenuOpen(false)}
          navigationItems={navigationItems}
          title={t('header.navigation')}
          footer={
            user ? (
              <div className="flex flex-col gap-2">
                <Button
                  variant="outline"
                  className="w-full touch-target gap-2"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    navigate('/settings');
                  }}
                >
                  <User className="h-4 w-4" />
                  {t('header.profile')}
                </Button>
                <Button
                  variant="outline"
                  className="w-full touch-target gap-2"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    setLogoutDialogOpen(true);
                  }}
                >
                  <LogOut className="h-4 w-4" />
                  {t('common.logout')}
                </Button>
              </div>
            ) : undefined
          }
        />
      </header>

      {/* Logout confirmation dialog */}
      <Dialog open={isLogoutDialogOpen} onOpenChange={setLogoutDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('header.confirm_logout')}</DialogTitle>
            <DialogDescription>{t('header.logout_description')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setLogoutDialogOpen(false)}
              disabled={isLoggingOut}
            >
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={performLogout}
              disabled={isLoggingOut}
            >
              {isLoggingOut ? t('header.logging_out') : t('header.log_out')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
