import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { LoginPage } from '../LoginPage.impl';

// Mock the auth store
vi.mock('@/lib/stores/auth');
vi.mock('@/lib/api');

const mockLogin = vi.fn();
const mockUseAuthStore = useAuthStore as any;
const mockApiPost = vi.mocked(api.post);

// Mock localStorage
const store: Record<string, string> = {};
const mockLocalStorage = {
  getItem: vi.fn((key: string) => store[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
  removeItem: vi.fn((key: string) => { delete store[key]; }),
  clear: vi.fn(() => { for (const k of Object.keys(store)) delete store[k]; }),
};

const renderLoginPage = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <LoginPage />
    </MemoryRouter>
  );

describe('LoginPage lockout and error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLocalStorage.clear();
    mockApiPost.mockReset();
    mockUseAuthStore.mockReturnValue({ login: mockLogin });

    // Mock system status via GET for useSystemStatus
    const mockApiGet = vi.mocked(api.get);
    mockApiGet.mockResolvedValue({
      data: {
        success: true,
        data: { turnstile_check: false },
      },
    } as any);

    mockLocalStorage.setItem(
      'status',
      JSON.stringify({
        system_name: 'Test API',
        github_oauth: false,
      })
    );
  });

  // ── Lockout / attempts_remaining ──

  test('shows remaining attempts message when server returns attempts_remaining', async () => {
    mockApiPost.mockRejectedValue({
      response: {
        status: 401,
        data: {
          success: false,
          message: '用户名或密码错误',
          data: { attempts_remaining: 3 },
        },
      },
    });

    renderLoginPage();

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/attempts remaining/i)).toBeInTheDocument();
    });
  });

  test('shows wrong_password + attempts_remaining combined message', async () => {
    mockApiPost.mockRejectedValue({
      response: {
        status: 401,
        data: {
          success: false,
          message: '用户名或密码错误',
          data: { attempts_remaining: 3 },
        },
      },
    });

    renderLoginPage();

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/(wrong|attempts remaining|密码错误)/i)).toBeInTheDocument();
    });
  });

  test('shows locked message and reset link when account is locked', async () => {
    mockApiPost.mockRejectedValue({
      response: {
        status: 423,
        data: {
          success: false,
          message: '用户名或密码错误',
          data: { locked: true },
        },
      },
    });

    renderLoginPage();

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'lockeduser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/account locked|帐户已锁定/i)).toBeInTheDocument();
    });

    // The locked card has "Go to Password Reset" link (from locale)
    expect(screen.getByText('Go to Password Reset')).toBeInTheDocument();
  });

  test('locked message disappears and login succeeds on correct retry', async () => {
    // First: reject with locked
    mockApiPost.mockRejectedValueOnce({
      response: {
        status: 423,
        data: {
          success: false,
          message: '用户名或密码错误',
          data: { locked: true },
        },
      },
    });
    // Second: succeed
    mockApiPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: { id: 1, username: 'lockeduser', role: 1 },
      },
    });

    renderLoginPage();

    // First attempt fails (locked)
    await act(async () => {
      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'lockeduser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/account locked|帐户已锁定/i)).toBeInTheDocument();
    });

    // Second attempt succeeds
    await act(async () => {
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'correct' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalled();
    });

    expect(screen.queryByText(/account locked|帐户已锁定/i)).not.toBeInTheDocument();
  });

  // ── catch block fix ──

  test('catch block uses error.response.data.message for server errors', async () => {
    mockApiPost.mockRejectedValue({
      response: {
        status: 500,
        data: {
          success: false,
          message: 'Internal server error',
        },
      },
    });

    renderLoginPage();

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText('Internal server error')).toBeInTheDocument();
    });
  });

  test('catch block falls back when no response data available', async () => {
    mockApiPost.mockRejectedValue(new Error('Network Error'));

    renderLoginPage();

    await act(async () => {
      fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
      fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    });

    await waitFor(() => {
      expect(screen.getByText('Network Error')).toBeInTheDocument();
    });
  });
});
