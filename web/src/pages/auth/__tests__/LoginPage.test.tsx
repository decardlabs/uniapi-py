import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LoginPage } from '../LoginPage.impl';

// Mock the auth store
vi.mock('@/lib/stores/auth');
vi.mock('@/lib/api');

const mockLogin = vi.fn();
const mockUseAuthStore = useAuthStore as any;
const mockApiGet = vi.mocked(api.get);
const mockApiPost = vi.mocked(api.post);

// Mock localStorage
const store: Record<string, string> = {};
const mockLocalStorage = {
  getItem: vi.fn((key: string) => store[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
  removeItem: vi.fn((key: string) => { delete store[key]; }),
  clear: vi.fn(() => { for (const k of Object.keys(store)) delete store[k]; }),
};
Object.defineProperty(window, 'localStorage', { value: mockLocalStorage, configurable: true });

// Use spy instead of overwriting window.history to avoid breaking React Router
const replaceStateSpy = vi.spyOn(window.history, 'replaceState').mockImplementation(() => {});

const renderLoginPage = (initialEntries: Parameters<typeof MemoryRouter>[0]['initialEntries'] = ['/login']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <LoginPage />
    </MemoryRouter>
  );
};

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    replaceStateSpy.mockClear();
    mockLocalStorage.clear();
    mockApiGet.mockReset();
    mockApiGet.mockResolvedValue({
      data: {
        success: true,
        data: { turnstile_check: false },
      },
    } as any);
    mockUseAuthStore.mockReturnValue({
      login: mockLogin,
    });
    mockLocalStorage.setItem(
      'status',
      JSON.stringify({
        system_name: 'Test API',
        github_oauth: false,
      })
    );
  });

  it('renders login form correctly', async () => {
    renderLoginPage();

    // Wait for the brand name to be rendered (it comes from the status) to avoid act warning
    // We use a regex because of the potential space/newline in "Sign In to Test API"
    expect(await screen.findByText(/Sign In\s+to Test API/i)).toBeInTheDocument();

    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('handles redirect_to parameter correctly on successful login', async () => {
    mockApiPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: { id: 1, username: 'testuser', role: 1 },
      },
    });

    renderLoginPage(['/login?redirect_to=%2Fdashboard']);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalled();
    });
  });

  it('shows Turnstile required state after failed login', async () => {
    // Override system status to enable Turnstile checking
    mockApiGet.mockReset();
    mockApiGet.mockResolvedValue({
      data: {
        success: true,
        data: { turnstile_check: true, turnstile_site_key: '1x00000000000000000000AA' },
      },
    } as any);
    mockLocalStorage.setItem(
      'status',
      JSON.stringify({
        system_name: 'Test API',
        turnstile_check: true,
        turnstile_site_key: '1x00000000000000000000AA',
        github_oauth: false,
      })
    );

    const errorMsg = 'Turnstile required';
    mockApiPost.mockResolvedValueOnce({
      data: {
        success: false,
        message: errorMsg,
        data: { turnstile_required: true },
      },
    });

    renderLoginPage();

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      // After server returns turnstile_required, the Turnstile state is set
      // The submit button should become disabled (turnstileRequired=true but no token yet)
      expect(screen.getByRole('button', { name: /sign in/i })).toBeDisabled();
      expect(screen.getByText(errorMsg)).toBeInTheDocument();
    });
  });

  // ── Loading State ──

  it('shows loading state during login submission', async () => {
    // Delay the API response so we can observe loading state
    let resolvePromise!: (v: unknown) => void;
    const pendingPromise = new Promise((resolve) => { resolvePromise = resolve; });
    mockApiPost.mockReturnValueOnce(pendingPromise as any);

    renderLoginPage();

    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitBtn = screen.getByRole('button', { name: /sign in/i });

    await act(async () => {
      fireEvent.change(usernameInput, { target: { value: 'testuser' } });
      fireEvent.change(passwordInput, { target: { value: 'password123' } });
    });

    await act(async () => {
      fireEvent.click(submitBtn);
    });

    // After click, button should show "Signing In..." and be disabled
    await waitFor(() => {
      expect(submitBtn).toBeDisabled();
    });
    expect(submitBtn).toHaveTextContent(/signing in/i);

    // Resolve the pending request
    await act(async () => {
      resolvePromise({ data: { success: true, data: { id: 1, username: 'testuser', role: 1 } } });
    });

    // Wait for loading to finish
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalled();
    });
  });

  // ── Error Message ──

  it('displays API error message on login failure', async () => {
    const errorMsg = '密码错误';
    mockApiPost.mockResolvedValueOnce({
      data: {
        success: false,
        message: errorMsg,
        data: {},
      },
    });

    renderLoginPage();

    const usernameInput = screen.getByLabelText(/username/i);
    const passwordInput = screen.getByLabelText(/password/i);

    fireEvent.change(usernameInput, { target: { value: 'testuser' } });
    fireEvent.change(passwordInput, { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(errorMsg)).toBeInTheDocument();
    });
  });

  it('shows generic message when API returns no error message', async () => {
    mockApiPost.mockResolvedValueOnce({
      data: {
        success: false,
        message: null,
        data: {},
      },
    });

    renderLoginPage();

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Login failed')).toBeInTheDocument();
    });
  });

  // ── Success Message Banner ──

  it('shows success message banner from navigation state', async () => {
    const successMsg = 'Password has been reset successfully!';
    renderLoginPage([{ pathname: '/login', state: { message: successMsg } }]);

    await waitFor(() => {
      expect(screen.getByText(successMsg)).toBeInTheDocument();
    });
  });

  // ── Logo ──

  it('shows logo image when configured in system status', async () => {
    mockLocalStorage.setItem(
      'status',
      JSON.stringify({
        system_name: 'Test API',
        logo: 'https://example.com/logo.png',
        github_oauth: false,
      })
    );

    renderLoginPage();

    await waitFor(() => {
      const img = screen.getByAltText(/Test API logo/i) as HTMLImageElement;
      expect(img).toBeInTheDocument();
      expect(img.src).toBe('https://example.com/logo.png');
    });
  });

  // ── Root Password Warning ──

  it('logs warning when root logs in with default password', async () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    mockApiPost.mockResolvedValueOnce({
      data: {
        success: true,
        data: { id: 1, username: 'root', role: 100 },
      },
    });

    renderLoginPage();

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'root' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        expect.stringContaining('change the default root password')
      );
    });

    consoleWarnSpy.mockRestore();
  });
});
