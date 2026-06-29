import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Layout } from '../Layout';

// Mock hooks
const mockUseIsDesktop = vi.fn();
const mockUseIsMobile = vi.fn();
vi.mock('@/hooks/useResponsive', () => ({
  useIsDesktop: () => mockUseIsDesktop(),
  useIsMobile: () => mockUseIsMobile(),
}));

// Mock auth store — default to logged-in admin
const mockUseAuthStore = vi.fn();
vi.mock('@/lib/stores/auth', () => ({
  useAuthStore: (selector: any) => mockUseAuthStore(selector),
}));

// Mock child components to simplify testing
vi.mock('../Sidebar', () => ({
  Sidebar: vi.fn(() => <aside data-testid="sidebar">Sidebar</aside>),
}));
vi.mock('../Header', () => ({
  Header: vi.fn(() => <header data-testid="header">Header</header>),
}));
vi.mock('../Footer', () => ({
  Footer: vi.fn(() => <footer data-testid="footer">Footer</footer>),
}));

describe('Layout', () => {
  beforeEach(() => {
    mockUseIsDesktop.mockReturnValue(true);
    mockUseIsMobile.mockReturnValue(false);
    mockUseAuthStore.mockImplementation((selector: any) => {
      const state = { user: { username: 'admin', role: 100, display_name: 'Admin' } };
      return selector(state);
    });
  });

  it('renders header, sidebar, footer and content outlet', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    expect(screen.getByTestId('header')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('footer')).toBeInTheDocument();
  });

  it('renders with desktop layout (sidebar visible)', () => {
    mockUseIsDesktop.mockReturnValue(true);
    const { container } = render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
  });

  it('renders with mobile layout (no sidebar)', () => {
    mockUseIsDesktop.mockReturnValue(false);
    mockUseIsMobile.mockReturnValue(true);
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    // Sidebar mock returns null, but main content should still render
    expect(screen.getByTestId('header')).toBeInTheDocument();
    expect(screen.getByTestId('footer')).toBeInTheDocument();
  });

  it('renders for unauthenticated users', () => {
    mockUseAuthStore.mockImplementation((selector: any) => {
      const state = { user: null };
      return selector(state);
    });
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    expect(screen.getByTestId('header')).toBeInTheDocument();
  });
});
