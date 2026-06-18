import * as React from 'react';
import { flexRender, getCoreRowModel, useReactTable } from '@tanstack/react-table';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import { useResponsive } from '@/hooks/useResponsive';
import { cn } from '@/lib/utils';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { AdvancedPagination } from '@/components/ui/advanced-pagination';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  pageIndex?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (pageIndex: number, pageSize: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  // Server-side sorting support
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  onSortChange?: (sortBy: string, sortOrder: 'asc' | 'desc') => void;
  loading?: boolean;
}

export function DataTable<TData, TValue>({
  columns,
  data,
  pageIndex = 0,
  pageSize = 20,
  total = 0,
  onPageChange,
  onPageSizeChange,
  sortBy = '',
  sortOrder = 'desc',
  onSortChange,
  loading = false,
}: DataTableProps<TData, TValue>) {
  const { t } = useTranslation();
  const { isMobile } = useResponsive();
  // Client-side sorting state (for display only when no server-side sorting)
  const [sorting, setSorting] = React.useState<SortingState>([]);

  // Handle column header click for server-side sorting
  const handleSort = (accessorKey: string) => {
    if (!onSortChange) return;
    if (loading) return; // Prevent repeated actions while loading

    // If clicking the same column, toggle order
    if (sortBy === accessorKey) {
      const newOrder = sortOrder === 'desc' ? 'asc' : 'desc';
      onSortChange(accessorKey, newOrder);
    } else {
      // New column, default to desc
      onSortChange(accessorKey, 'desc');
    }
  };

  const getSortIcon = (accessorKey: string) => {
    if (!onSortChange) return null;

    if (sortBy === accessorKey) {
      return sortOrder === 'asc' ? <ArrowUp className="ml-2 h-4 w-4" /> : <ArrowDown className="ml-2 h-4 w-4" />;
    }
    return <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />;
  };

  // Enhanced columns with sorting support
  const enhancedColumns = columns.map((column) => {
    // Check if column has accessorKey for sorting
    const hasAccessorKey = 'accessorKey' in column && typeof column.accessorKey === 'string';
    const accessorKey = hasAccessorKey ? (column.accessorKey as string) : '';

    if (!accessorKey || !onSortChange) return column;

    return {
      ...column,
      header: () => {
        const headerContent = typeof column.header === 'string' ? column.header : accessorKey;

        return (
          <Button variant="ghost" onClick={() => handleSort(accessorKey)} className="h-auto p-0 font-semibold hover:bg-transparent">
            <span>{headerContent}</span>
            {getSortIcon(accessorKey)}
          </Button>
        );
      },
    } as ColumnDef<TData, TValue>;
  });

  const table = useReactTable({
    data,
    columns: enhancedColumns,
    state: {
      sorting,
      pagination: {
        pageIndex,
        pageSize,
      },
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: !!onSortChange, // Use manual sorting if server-side sorting is available
    manualPagination: true,
    pageCount: Math.ceil(total / pageSize),
  });

  // ── Keyboard row navigation (declared after `table`) ─────
  const [focusedRowIndex, setFocusedRowIndex] = useState<number>(-1);
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const rowCount = table.getRowModel().rows.length;

  // Reset focused row when data changes
  useEffect(() => {
    setFocusedRowIndex(-1);
  }, [data]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (isMobile) return;

      let nextIndex = focusedRowIndex;
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          nextIndex = focusedRowIndex + 1 >= rowCount ? 0 : focusedRowIndex + 1;
          break;
        case 'ArrowUp':
          e.preventDefault();
          nextIndex = focusedRowIndex - 1 < 0 ? rowCount - 1 : focusedRowIndex - 1;
          break;
        case 'Home':
          e.preventDefault();
          nextIndex = 0;
          break;
        case 'End':
          e.preventDefault();
          nextIndex = rowCount - 1;
          break;
        default:
          return; // Don't prevent default for non-navigation keys
      }
      setFocusedRowIndex(nextIndex);

      // Scroll the focused row into view using data attribute
      requestAnimationFrame(() => {
        const container = tableContainerRef.current;
        if (!container) return;
        const rowEl = container.querySelector<HTMLElement>(`[data-row-index="${nextIndex}"]`);
        rowEl?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
    },
    [focusedRowIndex, rowCount, isMobile]
  );

  return (
    <div className="space-y-2">
      <div className="relative">
        {/* Loading overlay to prevent repeated actions */}
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-background/60 backdrop-blur-sm">
            <div className="text-sm text-muted-foreground">{t('common.loading', 'Loading...')}</div>
          </div>
        )}
        {isMobile ? (
          <div className={cn('space-y-3', loading && 'pointer-events-none opacity-60')}>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <section key={row.id} className="rounded-xl border bg-card p-4 shadow-sm">
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef.meta as { mobileLabel?: string } | undefined;
                    const headerDef = cell.column.columnDef.header;
                    const label = meta?.mobileLabel || (typeof headerDef === 'string' ? headerDef : cell.column.id || '');

                    return (
                      <div key={cell.id} className="grid gap-1 border-b border-border/60 py-3 first:pt-0 last:border-b-0 last:pb-0">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{label}</span>
                        <div className="text-sm text-foreground break-words break-all">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </div>
                      </div>
                    );
                  })}
                </section>
              ))
            ) : (
              <div className="rounded-xl border bg-card px-4 py-10 text-center text-sm text-muted-foreground shadow-sm">
                {loading ? t('common.loading', 'Loading...') : t('common.no_data', 'No results.')}
              </div>
            )}
          </div>
        ) : (
          <div
            ref={tableContainerRef}
            className="rounded-md border overflow-x-auto"
            onKeyDown={handleKeyDown}
            tabIndex={0} // Allow the container to receive keyboard focus
            role="grid"
            aria-label="Data table"
            aria-rowcount={rowCount}
          >
            <Table className={loading ? 'pointer-events-none opacity-60' : ''}>
              <TableHeader>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead key={header.id} className="text-left mobile:whitespace-normal mobile:break-words">
                        {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows?.length ? (
                  table.getRowModel().rows.map((row, index) => (
                    <TableRow
                      key={row.id}
                      data-state={row.getIsSelected() && 'selected'}
                      data-row-index={index}
                      aria-rowindex={index + 1}
                      className={cn(
                        focusedRowIndex === index && 'ring-2 ring-primary/40 ring-inset'
                      )}
                    >
                      {row.getVisibleCells().map((cell) => {
                        const meta = cell.column.columnDef.meta as { mobileLabel?: string } | undefined;
                        const headerDef = cell.column.columnDef.header;
                        const label = meta?.mobileLabel || (typeof headerDef === 'string' ? headerDef : cell.column.id || '');
                        return (
                          <TableCell key={cell.id} data-label={label} className="mobile-table-cell break-words break-all">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={columns.length} className="h-24 text-center">
                      {loading ? t('common.loading', 'Loading...') : t('common.no_data', 'No results.')}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* Advanced Pagination */}
      <AdvancedPagination
        currentPage={pageIndex + 1}
        totalPages={Math.ceil(total / pageSize)}
        pageSize={pageSize}
        totalItems={total}
        onPageChange={(page) => onPageChange?.(page - 1, pageSize)}
        onPageSizeChange={(newPageSize) => {
          onPageSizeChange?.(newPageSize);
          // Reset to first page when changing page size
          onPageChange?.(0, newPageSize);
        }}
        loading={loading}
      />
    </div>
  );
}
