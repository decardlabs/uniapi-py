import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DashboardFilter } from '../components/DashboardFilter';
import type { UserOption } from '../types';

/** Build required props with defaults so each test overrides only what it cares about. */
function buildProps(overrides: Record<string, any> = {}) {
  return {
    filtersReady: true,
    fromDate: '2026-06-18',
    toDate: '2026-06-24',
    dashUser: 'all',
    userOptions: [] as UserOption[],
    isAdmin: false,
    loading: false,
    dateError: '',
    getMinDate: () => '2026-01-01',
    getMaxDate: () => '2026-06-24',
    setFromDate: vi.fn(),
    setToDate: vi.fn(),
    setDashUser: vi.fn(),
    applyPreset: vi.fn(),
    loadStats: vi.fn(),
    ...overrides,
  };
}

describe('DashboardFilter', () => {
  // ── Render states ──

  it('renders date inputs and preset buttons', () => {
    render(<DashboardFilter {...buildProps()} />);
    expect(screen.getByLabelText(/from/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/to/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /today/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /apply/i })).toBeInTheDocument();
  });

  it('shows skeleton when filtersReady is false', () => {
    const { container } = render(<DashboardFilter {...buildProps({ filtersReady: false })} />);
    // Skeleton has animate-pulse class
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('does not render user select for non-admin', () => {
    render(<DashboardFilter {...buildProps({ isAdmin: false })} />);
    expect(screen.queryByLabelText(/user/i)).not.toBeInTheDocument();
  });

  it('renders user select for admin users', () => {
    render(<DashboardFilter {...buildProps({ isAdmin: true, userOptions: [{ id: 1, username: 'alice', display_name: 'Alice' }] })} />);
    expect(screen.getByLabelText(/user/i)).toBeInTheDocument();
  });

  // ── User interactions ──

  it('calls setFromDate when from date changes', async () => {
    const setFromDate = vi.fn();
    render(<DashboardFilter {...buildProps({ setFromDate })} />);
    const fromInput = screen.getByLabelText(/from/i);
    fireEvent.change(fromInput, { target: { value: '2026-06-20' } });
    expect(setFromDate).toHaveBeenCalledWith('2026-06-20');
  });

  it('calls setToDate when to date changes', async () => {
    const setToDate = vi.fn();
    render(<DashboardFilter {...buildProps({ setToDate })} />);
    const toInput = screen.getByLabelText(/to/i);
    fireEvent.change(toInput, { target: { value: '2026-06-25' } });
    expect(setToDate).toHaveBeenCalledWith('2026-06-25');
  });

  it('calls applyPreset when Today button is clicked', async () => {
    const applyPreset = vi.fn();
    render(<DashboardFilter {...buildProps({ applyPreset })} />);
    await userEvent.click(screen.getByRole('button', { name: /today/i }));
    expect(applyPreset).toHaveBeenCalledWith('today');
  });

  it('calls applyPreset when 7D button is clicked', async () => {
    const applyPreset = vi.fn();
    render(<DashboardFilter {...buildProps({ applyPreset })} />);
    await userEvent.click(screen.getByRole('button', { name: '7D' }));
    expect(applyPreset).toHaveBeenCalledWith('7d');
  });

  it('calls loadStats when Apply button is clicked', async () => {
    const loadStats = vi.fn();
    render(<DashboardFilter {...buildProps({ loadStats })} />);
    await userEvent.click(screen.getByRole('button', { name: /apply/i }));
    expect(loadStats).toHaveBeenCalled();
  });

  it('disables Apply button while loading', () => {
    render(<DashboardFilter {...buildProps({ loading: true })} />);
    expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled();
  });

  it('calls setDashUser when admin selects a user', async () => {
    const setDashUser = vi.fn();
    const userOptions: UserOption[] = [
      { id: 1, username: 'alice', display_name: 'Alice' },
    ];
    render(<DashboardFilter {...buildProps({ isAdmin: true, userOptions, setDashUser })} />);

    // Open the select and click the option
    const trigger = screen.getByLabelText(/user/i);
    await userEvent.click(trigger);
    const option = await screen.findByText('Alice');
    await userEvent.click(option);
    expect(setDashUser).toHaveBeenCalledWith('1');
  });
});
