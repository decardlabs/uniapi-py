import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { NotificationsProvider } from '@/components/ui/notifications';
import { api } from '@/lib/api';
import { SystemSettings } from './SystemSettings';

describe('SystemSettings', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders sensitive options and allows updating secret values', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        success: true,
        data: [
          { key: 'SMTPServer', value: 'smtp.example.com' },
          { key: 'SMTPPort', value: '587' },
          { key: 'SMTPAccount', value: 'mailer@example.com' },
          { key: 'SMTPFrom', value: 'noreply@example.com' },
        ],
      },
    });

    const putMock = vi.spyOn(api, 'put').mockResolvedValue({ data: { success: true } });

    const user = userEvent.setup();

    render(
      <NotificationsProvider>
        <SystemSettings />
      </NotificationsProvider>
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));

    expect(await screen.findByText('SMTPAccount')).toBeInTheDocument();
    expect(screen.getByText('SMTPToken')).toBeInTheDocument();

    const input = screen.getByLabelText('SMTPToken value') as HTMLInputElement;

    await user.type(input, 'super-secret-token');

    const saveButton = input.parentElement?.querySelector('button');
    expect(saveButton).toBeTruthy();

    await user.click(saveButton as HTMLButtonElement);

    await waitFor(() =>
      expect(putMock).toHaveBeenCalledWith('/api/option/', {
        key: 'SMTPToken',
        value: 'super-secret-token',
      })
    );

    expect(input.value).toBe('');
  });

  it('renders QuotaForNewUser option in the operations group', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        success: true,
        data: [{ key: 'QuotaForNewUser', value: '1000000' }],
      },
    });

    render(
      <NotificationsProvider>
        <SystemSettings />
      </NotificationsProvider>
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
    expect(screen.getByText('QuotaForNewUser')).toBeInTheDocument();
  });

  it('does not render dead options (MessagePusherAddress, RetryTimes, etc.)', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        success: true,
        data: [
          { key: 'RetryTimes', value: '3' },
          { key: 'PreConsumedQuota', value: '5000' },
          { key: 'MessagePusherAddress', value: 'http://push.example.com' },
          { key: 'MessagePusherToken', value: 'secret' },
          { key: 'EmailDomainWhitelist', value: 'example.com' },
          { key: 'AutomaticDisableChannelEnabled', value: 'false' },
        ],
      },
    });

    render(
      <NotificationsProvider>
        <SystemSettings />
      </NotificationsProvider>
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));

    expect(screen.queryByText('RetryTimes')).not.toBeInTheDocument();
    expect(screen.queryByText('PreConsumedQuota')).not.toBeInTheDocument();
    expect(screen.queryByText('MessagePusherAddress')).not.toBeInTheDocument();
    expect(screen.queryByText('MessagePusherToken')).not.toBeInTheDocument();
    expect(screen.queryByText('EmailDomainWhitelist')).not.toBeInTheDocument();
    expect(screen.queryByText('AutomaticDisableChannelEnabled')).not.toBeInTheDocument();
  });

  it('renders LogConsumeEnabled in the operations group', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      data: {
        success: true,
        data: [{ key: 'LogConsumeEnabled', value: 'true' }],
      },
    });

    render(
      <NotificationsProvider>
        <SystemSettings />
      </NotificationsProvider>
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
    expect(screen.getByText('LogConsumeEnabled')).toBeInTheDocument();
  });
});
