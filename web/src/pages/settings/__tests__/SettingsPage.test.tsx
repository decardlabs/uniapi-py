import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { SettingsPage } from '../SettingsPage';

vi.mock('@/components/ui/card', () => ({
  Card: ({ children }: any) => <div data-testid="card">{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('@/components/ui/tabs', () => ({
  Tabs: ({ children }: any) => <div>{children}</div>,
  TabsContent: ({ children, value }: any) => <div data-tab={value}>{children}</div>,
  TabsList: ({ children }: any) => <div>{children}</div>,
  TabsTrigger: ({ children, value }: any) => <button data-value={value}>{children}</button>,
}));

vi.mock('@/components/ui/responsive-container', () => ({
  ResponsivePageContainer: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('@/hooks/useResponsive', () => ({
  useResponsive: () => ({ isMobile: false }),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/lib/stores/auth', () => ({
  useAuthStore: vi.fn(),
}));

// Mock child components
vi.mock('../PersonalSettings', () => ({ PersonalSettings: () => <div>PersonalSettingsContent</div> }));
vi.mock('../SystemSettings', () => ({ SystemSettings: () => <div>SystemSettingsContent</div> }));

describe('SettingsPage', () => {
  it('shows only Personal tab for non-root users', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth');
    (useAuthStore as any).mockReturnValue({ user: { role: 1 } });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    expect(screen.getByText('settings.tabs.personal')).toBeInTheDocument();
    expect(screen.getByText('PersonalSettingsContent')).toBeInTheDocument();
    expect(screen.queryByText('settings.tabs.system')).not.toBeInTheDocument();
  });

  it('shows Personal and System tabs for root users', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth');
    (useAuthStore as any).mockReturnValue({ user: { role: 100 } });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    expect(screen.getByText('settings.tabs.personal')).toBeInTheDocument();
    expect(screen.getByText('PersonalSettingsContent')).toBeInTheDocument();
    expect(screen.getByText('settings.tabs.system')).toBeInTheDocument();
    expect(screen.getByText('SystemSettingsContent')).toBeInTheDocument();
  });
});
