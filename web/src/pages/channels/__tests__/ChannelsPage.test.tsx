import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ChannelsPage } from '../ChannelsPage';
import { api } from '@/lib/api';

vi.mock('@/components/ui/notifications', () => ({
  useNotifications: () => ({ notify: vi.fn() }),
}));

// Mock Radix Select to avoid empty string value crash in jsdom
vi.mock('@/components/ui/select', () => ({
  Select: ({ children, value, onValueChange }: any) => (
    <select value={value || ''} onChange={(e) => onValueChange?.(e.target.value)} data-testid="radix-select">
      {children}
    </select>
  ),
  SelectContent: ({ children }: any) => <>{children}</>,
  SelectItem: ({ children, value }: any) => <option value={value}>{children}</option>,
  SelectTrigger: ({ children, 'aria-label': ariaLabel }: any) => (
    <span aria-label={ariaLabel} role="combobox">{children}</span>
  ),
  SelectValue: ({ placeholder }: any) => <span>{placeholder}</span>,
}));

// Mock the API
vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
}));

// Mock the responsive hook
vi.mock('@/hooks/useResponsive', () => ({
  useResponsive: () => ({ isMobile: false, isTablet: false }),
}));

// Mock EnhancedDataTable
vi.mock('@/components/ui/enhanced-data-table', () => ({
  EnhancedDataTable: ({
    columns,
    data,
    pageSize,
    total,
    onPageChange,
    onPageSizeChange,
    sortBy,
    sortOrder,
    onSortChange,
    toolbarActions,
    loading,
    ...props
  }: any) => (
    <div data-testid="enhanced-data-table">
      {loading && <span data-testid="loading">Loading...</span>}
      {toolbarActions}
      {data?.length > 0 && (
        <div data-testid="data-rows">
          {data.slice(0, pageSize).map((row: any) => (
            <div key={row.id} data-testid={`row-${row.id}`}>{row.name}</div>
          ))}
        </div>
      )}
      {/* Pagination controls */}
      <div data-testid="pagination">
        <span data-testid="total-count">{total}</span>
        <span data-testid="page-size">{pageSize}</span>
        <span data-testid="sort-by">{sortBy}</span>
        <span data-testid="sort-order">{sortOrder}</span>
        {Array.from({ length: Math.ceil(total / pageSize) }, (_, i) => (
          <button
            key={i}
            data-testid={`page-${i + 1}`}
            role="button"
            aria-label={`Page ${i + 1}`}
            onClick={() => onPageChange?.(i, pageSize)}
          >
            {i + 1}
          </button>
        ))}
        <select
          data-testid="page-size-select"
          role="combobox"
          aria-label="rows per page"
          value={pageSize}
          onChange={(e) => {
            const newSize = Number(e.target.value);
            onPageSizeChange?.(newSize);
            onPageChange?.(0, newSize);
          }}
        >
          <option value="10">10</option>
          <option value="20">20</option>
          <option value="50">50</option>
        </select>
        <button
          data-testid="sort-name"
          role="button"
          aria-label="name"
          onClick={() => onSortChange?.('name', sortOrder === 'asc' ? 'desc' : 'asc')}
        >
          Name
        </button>
      </div>
    </div>
  ),
}));

// Mock other UI components used by ChannelsPage
vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, className }: any) => <span className={className} data-testid="badge">{children}</span>,
}));

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));

vi.mock('@/components/ui/card', () => ({
  Card: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('@/components/ui/responsive-container', () => ({
  ResponsivePageContainer: ({ children, title }: any) => (
    <div data-testid="responsive-page">{title}{children}</div>
  ),
}));

vi.mock('@/components/ui/searchable-dropdown', () => ({
  SearchableDropdown: () => null,
}));

vi.mock('@/components/ui/timestamp', () => ({
  TimestampDisplay: ({ timestamp }: any) => (
    <span data-testid="timestamp">{timestamp ? new Date(timestamp * 1000).toLocaleString() : '—'}</span>
  ),
}));

vi.mock('@/components/ui/list-action-button', () => ({
  ListActionButton: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));

vi.mock('@/components/ui/responsive-action-group', () => ({
  ResponsiveActionGroup: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirmDialog: () => [{}, () => null],
}));

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [new URLSearchParams(), vi.fn()],
  };
});

// Mock i18n color utils
vi.mock('./utils/colorGenerator', () => ({
  resolveChannelColor: () => '#000',
}));

const mockApiGet = vi.mocked(api.get);

const mockChannelsData = {
  success: true,
  data: Array.from({ length: 25 }, (_, i) => ({
    id: i + 1,
    name: `Channel ${i + 1}`,
    type: 1,
    status: 1,
    created_time: Date.now(),
    priority: 0,
    weight: 0,
    models: 'gpt-3.5-turbo',
    group: 'default',
    balance: 100,
    used_quota: 0,
  })),
  total: 25,
};

describe('ChannelsPage Pagination', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockApiGet.mockResolvedValue({ data: mockChannelsData });
  });

  const renderChannelsPage = () => {
    return render(
      <BrowserRouter>
        <ChannelsPage />
      </BrowserRouter>
    );
  };

  it('should load initial data with default page size', async () => {
    renderChannelsPage();

    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/channel/?p=0&size=10&sort=id&order=desc');
    });

    const calls = mockApiGet.mock.calls.length;
    expect(calls).toBeGreaterThanOrEqual(1);
    expect(calls).toBeLessThanOrEqual(2);
  });

  it('should not make duplicate API calls when changing page size', async () => {
    renderChannelsPage();

    const user = userEvent.setup();

    // Wait for initial load
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledTimes(1);
    });

    // Clear the mock to track new calls
    mockApiGet.mockClear();

    // Find and click the page size selector
    const pageSizeSelect = screen.getByRole('combobox', { name: /rows per page/i });
    await user.selectOptions(pageSizeSelect, '20');

    // Wait for the API call
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/channel/?p=0&size=20&sort=id&order=desc');
    });

    // Should only make ONE API call, not multiple
    expect(mockApiGet).toHaveBeenCalledTimes(1);
  });

  it('should handle page navigation correctly', async () => {
    renderChannelsPage();

    // Wait for initial load
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledTimes(1);
    });

    // Clear the mock to track new calls
    mockApiGet.mockClear();

    // Find and click page 2
    const page2Button = screen.getByRole('button', { name: 'Page 2' });
    await userEvent.click(page2Button);

    // Wait for the API call
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/channel/?p=1&size=10&sort=id&order=desc');
    });

    expect(mockApiGet).toHaveBeenCalledTimes(1);
  });

  it('should handle sorting without duplicate calls', async () => {
    renderChannelsPage();

    // Wait for initial load
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledTimes(1);
    });

    // Clear the mock to track new calls
    mockApiGet.mockClear();

    // Find and click a sortable column header
    const nameHeader = screen.getByRole('button', { name: /name/i });
    await userEvent.click(nameHeader);

    // Wait for the API call
    await waitFor(() => {
      expect(mockApiGet).toHaveBeenCalledWith('/api/channel/?p=0&size=10&sort=name&order=asc');
    });

    expect(mockApiGet).toHaveBeenCalledTimes(1);
  });
});
