import { api } from '@/lib/api';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { PasswordResetPage } from '../PasswordResetPage';

vi.mock('@/lib/api');

const mockApiGet = vi.mocked(api.get);

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/hooks/useSystemStatus', () => ({
  useSystemStatus: () => ({
    systemStatus: { turnstile_check: false },
  }),
}));

vi.mock('@/components/Turnstile', () => ({
  default: () => null,
}));

const renderResetPage = () =>
  render(
    <MemoryRouter initialEntries={['/reset']}>
      <PasswordResetPage />
    </MemoryRouter>
  );

describe('PasswordResetPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders password reset form', async () => {
    renderResetPage();
    expect(await screen.findByText('auth.reset.title')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('auth.reset.enter_email')).toBeInTheDocument();
  });

  test('catch block shows server error message', async () => {
    mockApiGet.mockRejectedValue({
      response: {
        status: 400,
        data: { success: false, message: 'Server error message' },
      },
    });

    renderResetPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.reset.enter_email'), { target: { value: 'test@example.com' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.reset.send_link' }));
    });

    await waitFor(() => {
      expect(screen.getByText('Server error message')).toBeInTheDocument();
    });
  });

  test('catch block shows error.message on network failure', async () => {
    mockApiGet.mockRejectedValue(new Error('Network Error'));

    renderResetPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.reset.enter_email'), { target: { value: 'test@example.com' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.reset.send_link' }));
    });

    await waitFor(() => {
      expect(screen.getByText('Network Error')).toBeInTheDocument();
    });
  });

  test('shows error message from success:false response', async () => {
    mockApiGet.mockResolvedValue({
      data: { success: false, message: 'Failed to send reset email' },
    });

    renderResetPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.reset.enter_email'), { target: { value: 'test@example.com' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.reset.send_link' }));
    });

    await waitFor(() => {
      expect(screen.getByText('Failed to send reset email')).toBeInTheDocument();
    });
  });

  test('shows success state after successful send', async () => {
    mockApiGet.mockResolvedValue({
      data: { success: true, message: 'Reset link sent' },
    });

    renderResetPage();

    await act(async () => {
      fireEvent.change(screen.getByPlaceholderText('auth.reset.enter_email'), { target: { value: 'test@example.com' } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'auth.reset.send_link' }));
    });

    await waitFor(() => {
      expect(screen.getByText('auth.reset.sent_title')).toBeInTheDocument();
    });
  });
});
