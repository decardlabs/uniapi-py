import { api } from '@/lib/api';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { RegisterPage } from '../RegisterPage';

vi.mock('@/lib/api');

const mockApiGet = vi.mocked(api.get);
const mockApiPost = vi.mocked(api.post);

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/hooks/useSystemStatus', () => ({
  useSystemStatus: () => ({
    systemStatus: { turnstile_check: false, github_oauth: false },
  }),
}));

vi.mock('@/components/Turnstile', () => ({
  default: () => null,
}));

const renderRegisterPage = () =>
  render(
    <MemoryRouter initialEntries={['/register']}>
      <RegisterPage />
    </MemoryRouter>
  );

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiGet.mockResolvedValue({ data: { success: true, data: {} } });
  });

  test('renders registration form', () => {
    renderRegisterPage();
    expect(screen.getAllByText('auth.register.title').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByPlaceholderText('auth.register.enter_username')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('auth.register.enter_email')).toBeInTheDocument();
  });

  test('catch block shows server error message from sendVerificationCode', async () => {
    mockApiPost.mockRejectedValue({
      response: {
        status: 400,
        data: { success: false, message: 'Server email error' },
      },
    });

    renderRegisterPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_email'), { target: { value: 'test@example.com' } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.register.send_code' }));
    });

    await waitFor(() => {
      expect(screen.getByText('Server email error')).toBeInTheDocument();
    });
  });

  test('catch block shows error.message on network failure for sendVerificationCode', async () => {
    mockApiPost.mockRejectedValue(new Error('Network Error'));

    renderRegisterPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_email'), { target: { value: 'test@example.com' } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.register.send_code' }));
    });

    await waitFor(() => {
      expect(screen.getByText('Network Error')).toBeInTheDocument();
    });
  });

  test('catch block shows server error from onSubmit', async () => {
    mockApiPost.mockRejectedValue({
      response: {
        status: 400,
        data: { success: false, message: 'Registration failed' },
      },
    });

    renderRegisterPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_username'), { target: { value: 'testuser' } });
    });
    const passwordInputs = screen.getAllByPlaceholderText('auth.register.enter_password');
    await act(async () => {
      fireEvent.change(passwordInputs[0], { target: { value: 'StrongPass1' } });
    });
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.confirm_password'), { target: { value: 'StrongPass1' } });
    });
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_email'), { target: { value: 'test@example.com' } });
    });
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_verification_code'), { target: { value: '123456' } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.register.title' }));
    });

    await waitFor(() => {
      expect(screen.getByText('Registration failed')).toBeInTheDocument();
    });
  });

  test('shows generic error message from success:false response (no field match)', async () => {
    mockApiPost.mockResolvedValue({
      data: { success: false, message: 'Generic server error' },
    });

    renderRegisterPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_username'), { target: { value: 'testuser' } });
    });
    const passwordInputs = screen.getAllByPlaceholderText('auth.register.enter_password');
    await act(async () => {
      fireEvent.change(passwordInputs[0], { target: { value: 'StrongPass1' } });
    });
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.confirm_password'), { target: { value: 'StrongPass1' } });
    });
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_email'), { target: { value: 'test@example.com' } });
    });
    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.register.enter_verification_code'), { target: { value: '000000' } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.register.title' }));
    });

    await waitFor(() => {
      expect(screen.getByText('Generic server error')).toBeInTheDocument();
    });
  });
});
