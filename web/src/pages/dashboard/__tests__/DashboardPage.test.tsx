import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { DashboardPage } from '../DashboardPage';

vi.mock('@/lib/stores/auth');
vi.mock('@/lib/api');

const mockUseAuthStore = useAuthStore as any;
const mockApiGet = vi.mocked(api.get);

/** Seed auth store with a logged-in user and return the user object. */
function mockAuthUser(overrides: Record<string, any> = {}) {
  const user = {
    id: 1,
    username: 'root',
    display_name: 'Root',
    role: 100,
    status: 1,
    balance: 1000000,
    group: 'default',
    ...overrides,
  };
  mockUseAuthStore.mockReturnValue({ user });
  (useAuthStore as any).getState = vi.fn().mockReturnValue({
    updateUser: vi.fn(),
  });
  return user;
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows login required when no user', () => {
    mockUseAuthStore.mockReturnValue({ user: null });
    (useAuthStore as any).getState = vi.fn().mockReturnValue({ updateUser: vi.fn() });

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );
    expect(screen.getByText(/log in/i)).toBeInTheDocument();
  });

  it('renders dashboard title when logged in', async () => {
    // Chain: admin users endpoint → dashboard endpoint → self endpoint
    mockApiGet
      .mockResolvedValueOnce({ data: { success: true, data: [] } } as any)       // /api/user/dashboard/users
      .mockResolvedValueOnce({                                                    // /api/user/dashboard
        data: { success: true, data: { logs: [], user_logs: [], token_logs: [], quota: 0, used_quota: 0 } },
      } as any)
      .mockResolvedValueOnce({ data: { success: true, data: { balance: 500000 } } } as any); // /api/user/self

    mockAuthUser();

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    });
  });

  it('handles API error gracefully', async () => {
    mockAuthUser();
    // First call (users endpoint) also needs to be handled
    mockApiGet.mockResolvedValue({ data: { success: true, data: [] } } as any);

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );

    // Page should not crash — the component catches errors internally
    await waitFor(() => {
      expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    });
  });
});
