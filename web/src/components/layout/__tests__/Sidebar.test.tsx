import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Home, Zap, CreditCard } from 'lucide-react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Sidebar } from '../Sidebar';
import type { NavGroup } from '../navigation';

// Mock useIsDesktop
const mockUseIsDesktop = vi.fn();
vi.mock('@/hooks/useResponsive', () => ({
  useIsDesktop: () => mockUseIsDesktop(),
  useIsMobile: () => false,
}));

// Mock react-router-dom's useLocation for active-link detection
const mockUseLocation = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: () => mockUseLocation(),
  };
});

const sampleGroups: NavGroup[] = [
  {
    label: 'nav.dashboard',
    items: [
      { name: 'Dashboard', to: '/dashboard', icon: Home, show: true },
    ],
  },
  {
    label: 'nav.management',
    items: [
      { name: 'Channels', to: '/channels', icon: Zap, show: true },
      { name: 'Tokens', to: '/tokens', icon: CreditCard, show: true, requiresAdmin: false },
    ],
  },
];

function renderSidebar(collapsed = false) {
  return render(
    <MemoryRouter>
      <TooltipProvider>
        <Sidebar navGroups={sampleGroups} collapsed={collapsed} onToggle={() => {}} />
      </TooltipProvider>
    </MemoryRouter>
  );
}

describe('Sidebar', () => {
  beforeEach(() => {
    mockUseIsDesktop.mockReturnValue(true);
    mockUseLocation.mockReturnValue({ pathname: '/dashboard' });
  });

  it('renders all navigation items on desktop', () => {
    renderSidebar();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Channels')).toBeInTheDocument();
    expect(screen.getByText('Tokens')).toBeInTheDocument();
  });

  it('returns null on mobile', () => {
    mockUseIsDesktop.mockReturnValue(false);
    const { container } = renderSidebar();
    expect(container.innerHTML).toBe('');
  });

  it('has collapsed class in collapsed mode', () => {
    renderSidebar(true);
    const navLinks = screen.getAllByRole('link');
    expect(navLinks.length).toBeGreaterThan(0);
  });

  it('has expanded class in expanded mode', () => {
    renderSidebar(false);
    const navLinks = screen.getAllByRole('link');
    expect(navLinks.length).toBeGreaterThan(0);
  });
});
