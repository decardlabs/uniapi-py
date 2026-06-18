import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TopUpPage } from './TopUpPage';

vi.mock('@/lib/api', () => {
  const get = vi.fn();
  const post = vi.fn();
  return {
    api: {
      get,
      post,
      defaults: { withCredentials: true },
      interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
    },
  };
});

vi.mock('@/components/ui/notifications', () => ({
  useNotifications: () => ({ notify: vi.fn() }),
}));

vi.mock('@/hooks/useDisplayUnit', () => ({
  useDisplayUnit: () => ({
    renderQuota: (quota: number) => `$${(quota / 500000).toFixed(2)}`,
  }),
}));

describe('TopUpPage', () => {
  beforeEach(() => {
    // Reset store
    useAuthStore.setState({
      user: {
        id: 1,
        username: 'testuser',
        role: 1,
        status: 1,
        quota: 1000,
        used_quota: 0,
        group: 'default',
      } as any,
      token: 'token',
      isAuthenticated: true,
      login: vi.fn() as any,
      logout: vi.fn() as any,
      updateUser: vi.fn() as any,
    });

    // Clear and set localStorage defaults used by the page
    localStorage.clear();
    localStorage.setItem('status', JSON.stringify({ top_up_link: 'https://pay.example.com' }));

    // Reset API mocks
    (api.get as any).mockReset();
    (api.post as any).mockReset();
    (api.get as any).mockResolvedValue({
      data: {
        success: true,
        data: { id: 1, username: 'testuser', quota: 1000 },
      },
    });
    // Recharge self list returns empty
    (api.get as any).mockImplementation((url: string) => {
      if (url.includes('/api/recharge/')) {
        return Promise.resolve({ data: { success: true, data: [] } });
      }
      return Promise.resolve({
        data: { success: true, data: { id: 1, username: 'testuser', quota: 1000 } },
      });
    });
    (api.post as any).mockResolvedValue({ data: { success: true, data: 500 } });
  });

  it('loads user quota on mount', async () => {
    render(<TopUpPage />);

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/api/user/self');
    });

    // Shows current balance section
    await screen.findByText(/current balance/i);
  });

  it('renders the recharge request form', async () => {
    render(<TopUpPage />);

    // Should show the recharge form title (use heading role for precision)
    const heading = await screen.findByRole('heading', { name: /submit recharge request/i });
    expect(heading).toBeInTheDocument();

    // Should have an amount input
    const amountInput = screen.getByPlaceholderText(/enter token count/i);
    expect(amountInput).toBeInTheDocument();

    // Should have a remark textarea
    const remarkInput = screen.getByPlaceholderText(/notes for the admin/i);
    expect(remarkInput).toBeInTheDocument();

    // Should have submit button
    const submitBtn = screen.getByRole('button', { name: /submit request/i });
    expect(submitBtn).toBeInTheDocument();
  });

  it('submits a recharge request', async () => {
    render(<TopUpPage />);

    // Wait for mount — use heading role to avoid matching description text
    await screen.findByRole('heading', { name: /submit recharge request/i });

    // Fill in amount
    const amountInput = screen.getByPlaceholderText(/enter token count/i);
    fireEvent.change(amountInput, { target: { value: '1' } });

    // Fill in remark
    const remarkInput = screen.getByPlaceholderText(/notes for the admin/i);
    fireEvent.change(remarkInput, { target: { value: 'Test recharge' } });

    // Submit
    const submitBtn = screen.getByRole('button', { name: /submit request/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/api/recharge/', {
        amount: 1000000,
        remark: 'Test recharge',
      });
    });
  });

  it('shows online payment link when top_up_link is set', async () => {
    render(<TopUpPage />);

    await screen.findByText(/online payment/i);
    await screen.findByText(/open payment portal/i);
  });
});
