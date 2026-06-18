import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Header } from '../Header';

// Mock all Header dependencies
vi.mock('@/hooks/useResponsive', () => ({
  useResponsive: () => ({ isMobile: true, isTablet: false, isDesktop: false }),
}));

vi.mock('@/hooks/useSystemStatus', () => ({
  useSystemStatus: () => ({
    systemStatus: { system_name: 'One API Test Brand' },
  }),
}));

vi.mock('@/components/LanguageSelector', () => ({
  LanguageSelector: () => null,
}));

vi.mock('@/components/theme-toggle', () => ({
  ThemeToggle: () => null,
}));

vi.mock('@/components/ui/mobile-drawer', () => ({
  NavigationDrawer: () => null,
}));

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    defaults: { withCredentials: true },
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  },
}));

vi.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: any) => <>{children}</>,
  DropdownMenuTrigger: ({ children }: any) => <>{children}</>,
  DropdownMenuContent: ({ children }: any) => <>{children}</>,
  DropdownMenuItem: ({ children, onSelect }: any) => <div onClick={onSelect}>{children}</div>,
  DropdownMenuLabel: ({ children }: any) => <div>{children}</div>,
  DropdownMenuSeparator: () => null,
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

describe('Header mobile overflow prevention', () => {
  it('renders header with no horizontal overflow and truncates brand text', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Header />
      </MemoryRouter>
    );

    // Header root should use full width sizing
    const header = screen.getByRole('banner');
    expect(header.className).toContain('w-full');

    // Brand text should truncate on small screens to avoid pushing layout
    const brand = screen.getByRole('link', { name: 'One API Test Brand' });
    expect(brand.className).toContain('truncate');
  });
});
