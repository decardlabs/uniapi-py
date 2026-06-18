import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { EnhancedDataTable } from '@/components/ui/enhanced-data-table';
import { useNotifications } from '@/components/ui/notifications';
import { ResponsivePageContainer } from '@/components/ui/responsive-container';
import { STORAGE_KEYS, usePageSize } from '@/hooks/usePersistentState';
import { api } from '@/lib/api';
import { renderQuotaWithUsd } from '@/lib/utils';
import type { ColumnDef } from '@tanstack/react-table';
import {
  CheckCircle,
  XCircle,
  ChevronDown,
} from 'lucide-react';
import { useEffect, useRef, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';

interface RechargeRequest {
  id: number;
  user_id: number;
  amount: number;
  quota: number;
  status: number;
  remark: string;
  admin_remark: string;
  created_time: number;
  reviewed_time: number;
  reviewer_id: number;
  user?: { id: number; username: string };
}

export function RechargesPage() {
  const [data, setData] = useState<RechargeRequest[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = usePageSize(STORAGE_KEYS.PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const initializedRef = useRef(false);
  const { notify } = useNotifications();
  const { t } = useTranslation();

  // Inline review state — which row is in "review mode"
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  // Per-row reject reason: each row has its own independent textarea state
  const [rejectReasons, setRejectReasons] = useState<Record<number, string>>({});
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  // Portal position: where to render the review panel (escaped from table layout)
  const [portalPos, setPortalPos] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const tr = (key: string, defaultValue: string) =>
    t(`recharges.${key}`, { defaultValue });

  const load = async (p = 0, size = pageSize) => {
    setLoading(true);
    try {
      const res = await api.get(`/api/recharge/?p=${p + 1}&size=${size}`);
      if (res.data?.success) {
        setData(res.data.data || []);
        setTotal(res.data.total || 0);
        setPageIndex(p);
      }
    } catch (error) {
      console.error('Failed to load recharge requests:', error);
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(0, pageSize);
    initializedRef.current = true;
  }, []);

  // Helper to render quota (with USD equivalent)
  const renderQuota = (quota: number) => renderQuotaWithUsd(quota);

  // ── Approve action ──────────────────────────────
  const handleApprove = async (id: number) => {
    setSubmittingId(id);
    try {
      const res = await api.post(`/api/recharge/${id}/approve`, {});
      if (res.data?.success) {
        notify({ type: 'success', message: tr('notifications.approved', '✅ Request approved! User balance updated.') });
        setReviewingId(null);
        load(pageIndex, pageSize);
      } else {
        notify({ type: 'error', message: res.data?.message || tr('notifications.failed', 'Operation failed') });
      }
    } catch (error) {
      notify({ type: 'error', message: error instanceof Error ? error.message : tr('notifications.failed', 'Operation failed') });
    } finally {
      setSubmittingId(null);
    }
  };

  // ── Reject action ───────────────────────────────
  const handleReject = async (id: number) => {
    const reason = (rejectReasons[id] || '').trim();
    if (!reason) {
      notify({ type: 'warning', message: tr('notifications.reason_required', 'Please enter a rejection reason') });
      return;
    }
    setSubmittingId(id);
    try {
      const res = await api.post(`/api/recharge/${id}/reject`, { admin_remark: reason });
      if (res.data?.success) {
        notify({ type: 'success', message: tr('notifications.rejected', '❌ Request rejected') });
        setReviewingId(null);
        setRejectReasons(prev => { const next = { ...prev }; delete next[id]; return next; });
        load(pageIndex, pageSize);
      } else {
        notify({ type: 'error', message: res.data?.message || tr('notifications.failed', 'Operation failed') });
      }
    } catch (error) {
      notify({ type: 'error', message: error instanceof Error ? error.message : tr('notifications.failed', 'Operation failed') });
    } finally {
      setSubmittingId(null);
    }
  };

  // ── Cancel review mode ──────────────────────────
  const cancelReview = useCallback(() => {
    if (reviewingId) {
      setRejectReasons(prev => { const next = { ...prev }; delete next[reviewingId]; return next; });
    }
    setReviewingId(null);
    setPortalPos(null);
  }, [reviewingId]);

  // ── Open review panel with portal positioning ─────
  const openReview = useCallback((id: number, event: React.MouseEvent<HTMLButtonElement>) => {
    const btn = event.currentTarget;
    const rect = btn.getBoundingClientRect();
    // Position the portal below the button, right-aligned to the button
    setPortalPos({
      top: rect.bottom + window.scrollY + 4,
      left: rect.right - 280, // 260px min-width + some padding
    });
    setReviewingId(id);
    setRejectReasons(prev => ({ ...prev, [id]: prev[id] || '' }));
  }, []);

  // ── Status badge helper ─────────────────────────
  const statusBadge = (s: number) => {
    switch (s) {
      case 1:
        return <Badge className="bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800">{tr('status.pending', 'Pending')}</Badge>;
      case 2:
        return <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800">{tr('status.approved', 'Approved')}</Badge>;
      case 3:
        return <Badge variant="destructive">{tr('status.rejected', 'Rejected')}</Badge>;
      default:
        return null;
    }
  };

  // ── Columns definition ──────────────────────────
  const columns: ColumnDef<RechargeRequest>[] = [
    {
      accessorKey: 'id',
      header: tr('columns.id', 'ID'),
      cell: ({ row }) => <span className="font-mono text-sm">{row.original.id}</span>,
    },
    {
      accessorKey: 'user',
      header: tr('columns.user', 'User'),
      cell: ({ row }) => (
        <span className="font-medium">
          {row.original.user?.username || `User #${row.original.user_id}`}
        </span>
      ),
    },
    {
      accessorKey: 'amount',
      header: tr('columns.amount', 'Amount'),
      cell: ({ row }) => (
        <span className="font-mono font-medium text-primary">
          ${renderQuota(row.original.amount)}
        </span>
      ),
    },
    {
      accessorKey: 'status',
      header: tr('columns.status', 'Status'),
      cell: ({ row }) => statusBadge(row.original.status),
    },
    {
      accessorKey: 'remark',
      header: tr('columns.remark', 'Remark'),
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground max-w-[200px] truncate block" title={row.original.remark || undefined}>
          {row.original.remark || '-'}
        </span>
      ),
    },
    {
      accessorKey: 'admin_remark',
      header: tr('columns.admin_note', 'Admin Note'),
      cell: ({ row }) => (
        <span className="text-sm max-w-[200px] truncate block" title={row.original.admin_remark || undefined}>
          {row.original.admin_remark || '-'}
        </span>
      ),
    },
    {
      accessorKey: 'created_time',
      header: tr('columns.created', 'Created At'),
      cell: ({ row }) => (
        <span className="font-mono text-sm">{new Date(row.original.created_time * 1000).toLocaleString()}</span>
      ),
    },
    {
      id: 'actions',
      header: tr('columns.actions', 'Actions'),
      cell: ({ row }) => {
        const req = row.original;

        // Non-pending rows → no actions
        if (req.status !== 1) return null;

        // ─── Review mode: show a compact "editing" badge in the cell ───
        if (reviewingId === req.id) {
          return (
            <Badge className="bg-primary/10 text-primary border-primary/30 animate-pulse">
              {tr('actions.editing', 'Editing…')}
            </Badge>
          );
        }

        // ─── Default mode: show trigger button ───
        return (
          <Button
            ref={triggerRef as React.RefObject<HTMLButtonElement>}
            variant="outline"
            size="sm"
            onClick={(e) => openReview(req.id, e)}
            className="gap-1.5 text-xs border-dashed hover:border-solid"
          >
            <ChevronDown className="h-3.5 w-3.5" />
            {tr('actions.review', 'Review')}
          </Button>
        );
      },
    },
  ];

  return (
    <>
    <ResponsivePageContainer
      title={tr('title', 'Recharge Management')}
      description={tr('description', 'Review and process user recharge requests')}
    >
      <Card className="border border-l-4 border-l-primary/50 shadow-sm">
        <CardContent className="p-6">
          <EnhancedDataTable
            columns={columns}
            data={data}
            pageIndex={pageIndex}
            pageSize={pageSize}
            total={total}
            onPageChange={(p, s) => { setPageIndex(p); load(p, s); }}
            onPageSizeChange={(s) => { setPageSize(s); setPageIndex(0); }}
            onRefresh={() => load(pageIndex, pageSize)}
            loading={loading}
            emptyMessage={tr('empty', 'No recharge requests yet')}
          />
        </CardContent>
      </Card>
    </ResponsivePageContainer>

    {/* ── Portal: Review panel rendered outside table layout ── */}
    {reviewingId !== null && portalPos && createPortal(
      <div
        className="fixed z-50 flex items-start justify-center"
        style={{
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          pointerEvents: 'auto',
        }}
        onClick={(e) => {
          // Close on backdrop click (but not when clicking inside the panel)
          if (e.target === e.currentTarget) cancelReview();
        }}
      >
        {/* Backdrop overlay */}
        <div className="absolute inset-0 bg-black/10" />

        {/* Floating panel */}
        <div
          className="relative z-10 mt-20 mx-auto w-full max-w-sm flex flex-col gap-3 p-4 bg-background border rounded-lg shadow-xl animate-in fade-in zoom-in-95 duration-150"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Panel header */}
          <div className="text-sm font-medium text-muted-foreground">
            {tr('actions.review_title', 'Review Request')} #{reviewingId}
          </div>

          {/* Reason textarea — fully free from table layout constraints */}
          <textarea
            value={rejectReasons[reviewingId] || ''}
            onChange={(e) => setRejectReasons(prev => ({ ...prev, [reviewingId]: e.target.value }))}
            placeholder={tr('actions.reject_reason_placeholder', 'Enter rejection reason (required)...')}
            className="w-full min-h-[100px] max-h-[300px] px-3 py-2.5 text-sm rounded-md border border-input bg-background resize-y focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            disabled={submittingId === reviewingId}
            rows={4}
            autoFocus
          />

          {/* Action buttons */}
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="default"
              className="flex-1 gap-1.5"
              onClick={() => handleApprove(reviewingId)}
              disabled={submittingId === reviewingId}
            >
              {submittingId === reviewingId ? (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : (
                <CheckCircle className="h-3.5 w-3.5" />
              )}
              {tr('actions.approve_btn', 'Approve')}
            </Button>

            <Button
              variant="destructive"
              size="sm"
              className="flex-1 gap-1.5"
              onClick={() => {
                const reason = (rejectReasons[reviewingId] || '').trim();
                if (!reason) {
                  notify({ type: 'warning', message: tr('notifications.reason_required', 'Please enter a rejection reason') });
                  return;
                }
                handleReject(reviewingId);
              }}
              disabled={submittingId === reviewingId || !(rejectReasons[reviewingId] || '').trim()}
            >
              {submittingId === reviewingId ? (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : (
                <XCircle className="h-3.5 w-3.5" />
              )}
              {tr('actions.reject_submit', 'Reject')}
            </Button>
          </div>

          {/* Cancel link */}
          <button
            onClick={cancelReview}
            className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 self-center cursor-pointer"
          >
            {tr('actions.cancel', 'Cancel')}
          </button>
        </div>
      </div>,
      document.body
    )}
    </>
  );
}

export default RechargesPage;
