import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import { Header } from './Header';
import { useAuthStore } from '@/lib/stores/auth';
import { api } from '@/lib/api';

type BreakpointState = {
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isLarge: boolean;
  currentBreakpoint: 'mobile' | 'tablet' | 'desktop' | 'large';
  width: number;
  height: number;
};

const mockUseResponsive = vi.fn();
let responsiveState: BreakpointState;

vi.mock('@/hooks/useResponsive', () => ({
  useResponsive: () => mockUseResponsive(),
}));

vi.mock('@/hooks/useSystemStatus', () => ({
  useSystemStatus: () => ({
    systemStatus: { system_name: 'OneAPI Test' },
  }),
}));

vi.mock('@/components/LanguageSelector', () => ({
  LanguageSelector: () => null,
}));

vi.mock('@/components/theme-toggle', () => ({
  ThemeToggle: () => null,
}));

vi.mock('@/components/ui/mobile-drawer', () => ({
  NavigationDrawer: ({ isOpen, onClose, navigationItems, title, footer }: any) =>
    isOpen ? (
      <div data-testid="mobile-drawer">
        <div>{title}</div>
        {navigationItems?.map((item: any) => (
          <a key={item.href} href={item.href}>
            {item.name}
          </a>
        ))}
        {footer}
      </div>
    ) : null,
}));

vi.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: any) => <>{children}</>,
  DropdownMenuTrigger: ({ children, asChild, ...props }: any) =>
    asChild ? <>{children}</> : <button {...props}>{children}</button>,
  DropdownMenuContent: ({ children }: any) => <div data-testid="dropdown-menu">{children}</div>,
  DropdownMenuItem: ({ children, onSelect, ...props }: any) => (
    <div role="menuitem" onClick={onSelect} {...props}>
      {children}
    </div>
  ),
  DropdownMenuLabel: ({ children }: any) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
}));

vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open }: any) => (open ? <>{children}</> : null),
  DialogContent: ({ children }: any) => <div>{children}</div>,
  DialogDescription: ({ children }: any) => <div>{children}</div>,
  DialogFooter: ({ children }: any) => <div>{children}</div>,
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));

vi.mock('@/lib/api', () => {
  const get = vi.fn();
  return {
    api: {
      get,
      defaults: { withCredentials: true },
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    },
  };
});

const renderHeader = () =>
  render(
    <MemoryRouter>
      <Header />
    </MemoryRouter>
  );

describe('Header logout UX', () => {
  let logoutMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockUseResponsive.mockReset();
    responsiveState = {
      isMobile: false,
      isTablet: false,
      isDesktop: true,
      isLarge: false,
      currentBreakpoint: 'desktop',
      width: 1280,
      height: 800,
    };
    mockUseResponsive.mockImplementation(() => responsiveState);

    logoutMock = vi.fn();

    useAuthStore.setState({
      user: {
        id: 1,
        username: 'demo-user',
        role: 10,
      } as any,
      token: 'token',
      isAuthenticated: true,
      login: vi.fn() as any,
      logout: logoutMock as any,
      updateUser: vi.fn() as any,
    });

    localStorage.clear();
    (api.get as any).mockReset();
    (api.get as any).mockResolvedValue({ data: { success: true } });
  });

  it('hides the logout action by default', () => {
    renderHeader();

    expect(screen.queryByRole('button', { name: /logout/i })).toBeNull();
  });

  it('confirms logout through the desktop dropdown menu', async () => {
    const user = userEvent.setup();
    renderHeader();

    // Click user avatar to open dropdown
    const accountMenuButton = screen.getByLabelText(/profile/i);
    await user.click(accountMenuButton);

    // Click Logout menu item
    const logoutMenuItem = await screen.findByText('Logout');
    await user.click(logoutMenuItem);

    // Confirm dialog should appear
    await screen.findByText(/confirm logout/i);

    const confirmButton = screen.getByRole('button', { name: /log out/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/user/logout');
    });
    expect(logoutMock).toHaveBeenCalled();
  });

  it('offers logout inside the mobile navigation drawer', async () => {
    responsiveState = {
      isMobile: true,
      isTablet: false,
      isDesktop: false,
      isLarge: false,
      currentBreakpoint: 'mobile',
      width: 375,
      height: 812,
    };

    const user = userEvent.setup();
    renderHeader();

    expect(screen.queryByRole('button', { name: /logout/i })).toBeNull();

    const mobileMenuButton = screen.getByLabelText(/navigation/i);
    await user.click(mobileMenuButton);

    // The drawer should now be open with a logout button in the footer
    const drawerLogoutButton = await screen.findByRole('button', { name: /logout/i });
    await user.click(drawerLogoutButton);

    await screen.findByText(/confirm logout/i);

    const confirmButton = screen.getByRole('button', { name: /log out/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/user/logout');
    });
    expect(logoutMock).toHaveBeenCalled();
  });
});
