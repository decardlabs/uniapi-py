import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useConfirmDialog } from '@/components/ui/confirm-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { EnhancedDataTable } from '@/components/ui/enhanced-data-table';
import { Input } from '@/components/ui/input';
import { SearchableDropdown, type SearchOption } from '@/components/ui/searchable-dropdown';
import { useNotifications } from '@/components/ui/notifications';
import { ResponsivePageContainer } from '@/components/ui/responsive-container';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { STORAGE_KEYS, usePageSize } from '@/hooks/usePersistentState';
import { api } from '@/lib/api';
import type { ColumnDef } from '@tanstack/react-table';
import {
  Plus,
  RotateCcw,
  ArrowRightLeft,
  Archive,
  Wallet,
} from 'lucide-react';
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

// ── Types ─────────────────────────────────────────────
interface Pool {
  id: number;
  name: string;
  total_funded: number;
  total_allocated: number;
  total_consumed: number;
  available: number;       // computed: total_funded - total_allocated
  used_quota: number;      // alias for total_allocated (frontend compat)
  period_type: string;
  period_key: string;
  status: string;
  created_at: number;      // ms timestamp
  closed_at?: number;
}

interface PoolAllocation {
  id: number;
  pool_id: number;
  user_id: number;
  username?: string;
  amount: number;
  consumed: number;
  recalled: number;
  net_allocated: number;
  remaining: number;
  status: string;
  created_at: number;
  updated_at: number;
}

// ── Page Component ────────────────────────────────────
export default function BudgetPoolsPage() {
  const { t } = useTranslation();
  const { notify } = useNotifications();
  const [confirmAction, ConfirmDialog] = useConfirmDialog();

  const tr = (key: string, defaultValue: string) =>
    t(`pool.${key}`, { defaultValue });

  // Data state
  const [data, setData] = useState<Pool[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = usePageSize(STORAGE_KEYS.PAGE_SIZE);
  const [total, setTotal] = useState(0);
  const initializedRef = useRef(false);

  // Filter state
  const [filterPeriod, setFilterPeriod] = useState('__all__');
  const [filterStatus, setFilterStatus] = useState('__all__');

  // Dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [purchaseOpen, setPurchaseOpen] = useState(false);
  const [allocateOpen, setAllocateOpen] = useState(false);
  const [recallOpen, setRecallOpen] = useState(false);
  const [rolloverOpen, setRolloverOpen] = useState(false);
  const [reconcileOpen, setReconcileOpen] = useState(false);

  // Form state
  const [selectedPool, setSelectedPool] = useState<Pool | null>(null);

  // ── Period key generation ──────────────────────────────
  const generatePeriodKey = useCallback((type: string): string => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    switch (type) {
      case 'monthly': return `${y}-${m}`;
      case 'quarterly': return `${y}-Q${Math.ceil((now.getMonth() + 1) / 3)}`;
      case 'yearly': return String(y);
      default: return '';
    }
  }, []);

  const generatePoolName = useCallback((type: string, key: string): string => {
    if (!key) return '';
    const periodLabels: Record<string, string> = {
      monthly: 'Monthly Budget',
      quarterly: 'Quarterly Budget',
      yearly: 'Yearly Budget',
      oneoff: 'Budget',
    };
    return `${key} ${periodLabels[type] || 'Budget'}`;
  }, []);

  // Create form
  const [createForm, setCreateForm] = useState(() => ({
    name: '',
    total_funded: '',
    period_type: 'monthly',
    period_key: '',
  }));

  // Auto-set period_key and name when period_type changes
  useEffect(() => {
    const key = generatePeriodKey(createForm.period_type);
    setCreateForm(prev => ({
      ...prev,
      period_key: key,
      name: prev.name || generatePoolName(createForm.period_type, key),
    }));
  }, [createForm.period_type, generatePeriodKey, generatePoolName]);

  // Period key options for Select
  const periodKeyOptions = useMemo(() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth() + 1;
    const q = Math.ceil(m / 3);
    const opts: { label: string; value: string }[] = [];

    switch (createForm.period_type) {
      case 'monthly':
        // Current month and next 2 months
        for (let i = 0; i < 3; i++) {
          const ym = m + i;
          let yy = y;
          let mm = ym;
          if (mm > 12) { yy++; mm -= 12; }
          opts.push({
            label: `${yy}-${String(mm).padStart(2, '0')}`,
            value: `${yy}-${String(mm).padStart(2, '0')}`,
          });
        }
        break;
      case 'quarterly': {
        const qLabels = ['Q1 (Jan-Mar)', 'Q2 (Apr-Jun)', 'Q3 (Jul-Sep)', 'Q4 (Oct-Dec)'];
        for (let i = 0; i < 4; i++) {
          opts.push({
            label: `${y}-${qLabels[i]}`,
            value: `${y}-Q${i + 1}`,
          });
        }
        break;
      }
      case 'yearly':
        for (let i = 0; i < 3; i++) {
          opts.push({
            label: String(y + i),
            value: String(y + i),
          });
        }
        break;
      case 'oneoff':
        // Single custom period key — no auto options
        opts.push({ label: 'One-off', value: '' });
        break;
    }
    return opts;
  }, [createForm.period_type]);

  // Purchase form
  const [purchaseAmount, setPurchaseAmount] = useState('');
  const [purchaseRemark, setPurchaseRemark] = useState('');

  // Allocate form
  const [allocateUserId, setAllocateUserId] = useState('');
  const [allocateAmount, setAllocateAmount] = useState('');
  const [allocateRemark, setAllocateRemark] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Recall form
  const [recallUserId, setRecallUserId] = useState('');
  const [recallAmount, setRecallAmount] = useState('');
  const [recallMax, setRecallMax] = useState(0);
  const [recallRemark, setRecallRemark] = useState('');

  // Rollover form
  const [rolloverPeriodType, setRolloverPeriodType] = useState('monthly');
  const [rolloverPeriodKey, setRolloverPeriodKey] = useState('');
  const [rolloverName, setRolloverName] = useState('');

  // Rollover period key options
  const rolloverPeriodKeyOptions = useMemo(() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth() + 1;
    const q = Math.ceil(m / 3);
    const opts: { label: string; value: string }[] = [];

    switch (rolloverPeriodType) {
      case 'monthly':
        for (let i = 0; i < 3; i++) {
          const ym = m + i;
          let yy = y;
          let mm = ym;
          if (mm > 12) { yy++; mm -= 12; }
          opts.push({
            label: `${yy}-${String(mm).padStart(2, '0')}`,
            value: `${yy}-${String(mm).padStart(2, '0')}`,
          });
        }
        break;
      case 'quarterly': {
        const qLabels = ['Q1 (Jan-Mar)', 'Q2 (Apr-Jun)', 'Q3 (Jul-Sep)', 'Q4 (Oct-Dec)'];
        for (let i = 0; i < 4; i++) {
          opts.push({
            label: `${y}-${qLabels[i]}`,
            value: `${y}-Q${i + 1}`,
          });
        }
        break;
      }
      case 'yearly':
        for (let i = 0; i < 3; i++) {
          opts.push({
            label: String(y + i),
            value: String(y + i),
          });
        }
        break;
    }
    return opts;
  }, [rolloverPeriodType]);

  const generateRolloverName = useCallback((type: string, key: string): string => {
    if (!key) return '';
    const periodLabels: Record<string, string> = {
      monthly: 'Monthly Budget',
      quarterly: 'Quarterly Budget',
      yearly: 'Yearly Budget',
    };
    return `${key} ${periodLabels[type] || 'Budget'}`;
  }, []);

  // Reconciliation data
  const [reconcileData, setReconcileData] = useState<any>(null);

  // ── Data loading ────────────────────────────────────
  const loadPools = useCallback(
    async (p = 0, size = pageSize) => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = {
          p,
          size,
        };
        if (filterPeriod && filterPeriod !== '__all__') params.period_type = filterPeriod;
        if (filterStatus && filterStatus !== '__all__') params.status = filterStatus;

        const res = await api.get('/api/pool/', { params });
        if (res.data?.success) {
          // Backend returns { success, data: Pool[], total: N }
          const pools: Pool[] = (res.data.data || []).map((p: any) => ({
            ...p,
            available: Math.max(0, p.total_funded - p.total_allocated),
          }));
          setData(pools);
          setTotal(res.data.total || 0);
          setPageIndex(p);
        }
      } catch (error) {
        console.error('Failed to load pools:', error);
        setData([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [pageSize, filterPeriod, filterStatus]
  );

  useEffect(() => {
    loadPools(0, pageSize);
    initializedRef.current = true;
  }, [loadPools]);

  // ── API actions ─────────────────────────────────────
  const handleCreate = async () => {
    setSubmitting(true);
    try {
      const res = await api.post('/api/pool/', {
        name: createForm.name,
        total_funded: Number(createForm.total_funded),
        period_type: createForm.period_type,
        period_key: createForm.period_key,
      });
      if (res.data?.success) {
        notify({ type: 'success', message: tr('create', 'Budget pool created') });
        setCreateOpen(false);
        resetCreateForm();
        loadPools(0, pageSize);
      } else {
        notify({
          type: 'error',
          message: res.data?.message || 'Failed to create pool',
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to create pool',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handlePurchase = async () => {
    if (!selectedPool) return;
    setSubmitting(true);
    try {
      const res = await api.post(`/api/pool/${selectedPool.id}/fund`, {
        amount: Number(purchaseAmount),
        remark: purchaseRemark,
      });
      if (res.data?.success) {
        notify({ type: 'success', message: tr('purchase_success', 'Purchase successful') });
        setPurchaseOpen(false);
        resetPurchaseForm();
        loadPools(pageIndex, pageSize);
      } else {
        notify({
          type: 'error',
          message: res.data?.message || 'Purchase failed',
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Purchase failed',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleAllocate = async () => {
    if (!selectedPool) return;
    setSubmitting(true);
    try {
      const res = await api.post(`/api/pool/${selectedPool.id}/allocate`, {
        user_id: Number(allocateUserId),
        amount: Number(allocateAmount),
        remark: allocateRemark,
      });
      if (res.data?.success) {
        notify({ type: 'success', message: tr('allocate_success', 'Allocation successful') });
        setAllocateOpen(false);
        resetAllocateForm();
        loadPools(pageIndex, pageSize);
      } else {
        notify({
          type: 'error',
          message: res.data?.message || 'Allocation failed',
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Allocation failed',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecall = async () => {
    if (!selectedPool) return;
    setSubmitting(true);
    try {
      const res = await api.post(`/api/pool/${selectedPool.id}/recall`, {
        user_id: Number(recallUserId),
        amount: Number(recallAmount),
        remark: recallRemark,
      });
      if (res.data?.success) {
        notify({ type: 'success', message: tr('recall_success', 'Recall successful') });
        setRecallOpen(false);
        resetRecallForm();
        loadPools(pageIndex, pageSize);
      } else {
        notify({
          type: 'error',
          message: res.data?.message || 'Recall failed',
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Recall failed',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleClosePool = async (pool: Pool) => {
    const confirmed = await confirmAction({
      title: tr('close_confirm', 'Close Budget Pool'),
      description: tr('close_confirm_desc', `Are you sure you want to close "${pool.name}"? Unused balance will be returned.`),
      variant: 'destructive',
    });
    if (!confirmed) return;
    try {
      const res = await api.post(`/api/pool/${pool.id}/close`, {});
      if (res.data?.success) {
        notify({ type: 'success', message: tr('close_success', 'Budget pool closed') });
        loadPools(pageIndex, pageSize);
      } else {
        notify({
          type: 'error',
          message: res.data?.message || 'Failed to close pool',
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to close pool',
      });
    }
  };

  const handleRollover = async () => {
    if (!selectedPool) return;
    setSubmitting(true);
    try {
      const newName = rolloverName || generateRolloverName(rolloverPeriodType, rolloverPeriodKey);
      const res = await api.post(`/api/pool/${selectedPool.id}/rollover`, {
        new_period_key: rolloverPeriodKey,
        new_name: newName,
      });
      if (res.data?.success) {
        notify({ type: 'success', message: tr('rollover_success', 'Budget pool rolled over') });
        setRolloverOpen(false);
        resetRolloverForm();
        loadPools(pageIndex, pageSize);
      } else {
        notify({
          type: 'error',
          message: res.data?.message || 'Rollover failed',
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Rollover failed',
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleReconcile = async (pool: Pool) => {
    try {
      const res = await api.get(`/api/pool/${pool.id}/reconciliation`);
      if (res.data?.success) {
        setReconcileData(res.data.data);
        setReconcileOpen(true);
      } else {
        notify({
          type: 'error',
          message: res.data?.message || 'Failed to load reconciliation',
        });
      }
    } catch (error) {
      notify({
        type: 'error',
        message: error instanceof Error ? error.message : 'Failed to load reconciliation',
      });
    }
  };

  const handleRecallAll = async () => {
    if (!selectedPool || !reconcileData?.allocations?.length) return;

    for (const a of reconcileData.allocations) {
      if (a.remaining <= 0) continue;
      try {
        await api.post(`/api/pool/${selectedPool.id}/recall_all`, {
          user_id: a.user_id,
        });
      } catch {
        // continue recalling from other users
      }
    }
    notify({ type: 'success', message: tr('recall_success', 'Recall successful') });
    handleReconcile(selectedPool);
    loadPools(pageIndex, pageSize);
  };

  // ── Form resets ─────────────────────────────────────
  const resetCreateForm = () => {
    const key = generatePeriodKey('monthly');
    setCreateForm({ name: '', total_funded: '', period_type: 'monthly', period_key: key });
  };
  const resetPurchaseForm = () => {
    setPurchaseAmount('');
    setPurchaseRemark('');
  };
  const resetAllocateForm = () => {
    setAllocateUserId('');
    setAllocateAmount('');
    setAllocateRemark('');
  };
  const resetRecallForm = () => {
    setRecallUserId('');
    setRecallAmount('');
    setRecallMax(0);
    setRecallRemark('');
  };
  const resetRolloverForm = () => {
    setRolloverPeriodType('monthly');
    setRolloverPeriodKey('');
    setRolloverName('');
  };

  // ── Helper ──────────────────────────────────────────
  const formatYuan = (value: number) => `¥${value.toFixed(2)}`;

  const openAllocateDialog = (pool: Pool, userId: number, maxRecall: number) => {
    setSelectedPool(pool);
    setRecallUserId(String(userId));
    setRecallMax(maxRecall);
    setRecallOpen(true);
  };

  const periodLabel = (type: string) => {
    const map: Record<string, string> = {
      monthly: tr('period_monthly', 'Monthly'),
      quarterly: tr('period_quarterly', 'Quarterly'),
      yearly: tr('period_yearly', 'Yearly'),
      oneoff: tr('period_oneoff', 'One-off'),
    };
    return map[type] || type;
  };

  // ── Columns ─────────────────────────────────────────
  const columns: ColumnDef<Pool>[] = [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: ({ row }) => <span className="font-mono text-sm">{row.original.id}</span>,
    },
    {
      accessorKey: 'name',
      header: tr('name', 'Name'),
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
    },
    {
      accessorKey: 'period_type',
      header: tr('period_type', 'Period Type'),
      cell: ({ row }) => periodLabel(row.original.period_type),
    },
    {
      accessorKey: 'period_key',
      header: tr('period_key', 'Period Key'),
      cell: ({ row }) => <span className="font-mono text-sm">{row.original.period_key}</span>,
    },
    {
      accessorKey: 'total_funded',
      header: tr('total_funded', 'Total Funded'),
      cell: ({ row }) => (
        <span className="font-mono font-medium">{formatYuan(row.original.total_funded)}</span>
      ),
    },
    {
      id: 'total_allocated',
      header: tr('allocated', 'Allocated'),
      cell: ({ row }) => (
        <span className="font-mono">{formatYuan(row.original.total_allocated)}</span>
      ),
    },
    {
      id: 'available',
      header: tr('available', 'Available'),
      cell: ({ row }) => (
        <span className="font-mono text-emerald-600 dark:text-emerald-400">
          {formatYuan(row.original.available)}
        </span>
      ),
    },
    {
      accessorKey: 'status',
      header: tr('status', 'Status'),
      cell: ({ row }) => {
        if (row.original.status === 'active') {
          return (
            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800">
              {tr('active', 'Active')}
            </Badge>
          );
        }
        return (
          <Badge variant="secondary">
            {tr('closed', 'Closed')}
          </Badge>
        );
      },
    },
    {
      accessorKey: 'created_at',
      header: tr('created_at', 'Created At'),
      cell: ({ row }) => {
        // Backend uses ms timestamps
        const ts = row.original.created_at > 1e12 ? row.original.created_at : row.original.created_at * 1000;
        return (
          <span className="font-mono text-sm">
            {new Date(ts).toLocaleDateString()}
          </span>
        );
      },
    },
    {
      id: 'actions',
      header: tr('actions', 'Actions'),
      cell: ({ row }) => {
        const pool = row.original;
        const isClosed = pool.status === 'closed';
        return (
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="gap-1 text-xs"
              onClick={() => {
                setSelectedPool(pool);
                setPurchaseOpen(true);
              }}
              disabled={isClosed}
              title={tr('purchase', 'Purchase')}
            >
              <Wallet className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1 text-xs"
              onClick={() => {
                setSelectedPool(pool);
                setAllocateOpen(true);
              }}
              disabled={isClosed}
              title={tr('allocate', 'Allocate')}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1 text-xs"
              onClick={() => handleReconcile(pool)}
              title={tr('reconciliation', 'Reconcile')}
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1 text-xs"
              onClick={() => {
                setSelectedPool(pool);
                const ptype = pool.period_type || 'monthly';
                setRolloverPeriodType(ptype);
                // Auto-fill rollover form: next period
                const now = new Date();
                const y = now.getFullYear();
                const m = now.getMonth() + 1;
                const q = Math.ceil(m / 3);
                let nextKey = '';
                if (ptype === 'monthly') {
                  const nm = m === 12 ? 1 : m + 1;
                  const ny = m === 12 ? y + 1 : y;
                  nextKey = `${ny}-${String(nm).padStart(2, '0')}`;
                } else if (ptype === 'quarterly') {
                  nextKey = `${y}-Q${q}`;
                } else if (ptype === 'yearly') {
                  nextKey = String(y + 1);
                }
                setRolloverPeriodKey(nextKey);
                setRolloverName('');
                setRolloverOpen(true);
              }}
              disabled={isClosed}
              title={tr('rollover', 'Rollover')}
            >
              <ArrowRightLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="gap-1 text-xs"
              onClick={() => handleClosePool(pool)}
              disabled={isClosed}
              title={tr('close', 'Close')}
            >
              <Archive className="h-3.5 w-3.5" />
            </Button>
          </div>
        );
      },
    },
  ];

  // ── Render ──────────────────────────────────────────
  return (
    <>
      <ResponsivePageContainer
        title={tr('title', 'Budget Pool Management')}
        description={tr('description', 'Manage budget pool creation, allocation, recall and reconciliation')}
        actions={
          <Button
            onClick={() => setCreateOpen(true)}
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            {tr('create', 'New Budget Pool')}
          </Button>
        }
      >
        {/* Filter bar */}
        <div className="flex items-center gap-3">
          <Select value={filterPeriod} onValueChange={setFilterPeriod}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder={tr('filter_period_type', 'All Periods')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">{tr('filter_period_type', 'All Periods')}</SelectItem>
              <SelectItem value="monthly">{tr('period_monthly', 'Monthly')}</SelectItem>
              <SelectItem value="quarterly">{tr('period_quarterly', 'Quarterly')}</SelectItem>
              <SelectItem value="yearly">{tr('period_yearly', 'Yearly')}</SelectItem>
              <SelectItem value="oneoff">{tr('period_oneoff', 'One-off')}</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder={tr('filter_status', 'All Status')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">{tr('filter_status', 'All Status')}</SelectItem>
              <SelectItem value="active">{tr('active', 'Active')}</SelectItem>
              <SelectItem value="closed">{tr('closed', 'Closed')}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Pool table */}
        <Card className="border border-l-4 border-l-primary/50 shadow-sm">
          <CardContent className="p-6">
            <EnhancedDataTable
              columns={columns}
              data={data}
              pageIndex={pageIndex}
              pageSize={pageSize}
              total={total}
              onPageChange={(p, s) => { setPageIndex(p); loadPools(p, s); }}
              onPageSizeChange={(s) => { setPageSize(s); setPageIndex(0); }}
              onRefresh={() => loadPools(pageIndex, pageSize)}
              loading={loading}
              emptyMessage={tr('no_data', 'No budget pools yet')}
            />
          </CardContent>
        </Card>
      </ResponsivePageContainer>

      <ConfirmDialog />

      {/* ── Create Pool Dialog ────────────────────────── */}
      <Dialog open={createOpen} onOpenChange={(open) => { setCreateOpen(open); if (!open) resetCreateForm(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{tr('create', 'New Budget Pool')}</DialogTitle>
            <DialogDescription>
              {tr('create', 'New Budget Pool')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{tr('name', 'Name (optional)')}</label>
              <Input
                value={createForm.name}
                onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                placeholder={generatePoolName(createForm.period_type, createForm.period_key) || tr('name_placeholder', 'e.g. Monthly Budget Pool')}
                className="mt-1"
              />
              {!createForm.name && (
                <p className="text-xs text-muted-foreground mt-1">
                  {tr('name_auto_hint', 'Auto: {{name}}').replace('{{name}}', generatePoolName(createForm.period_type, createForm.period_key))}
                </p>
              )}
            </div>
            <div>
              <label className="text-sm font-medium">{tr('total_funded', 'Total Funded (¥)')}</label>
              <Input
                type="number"
                value={createForm.total_funded}
                onChange={(e) => setCreateForm({ ...createForm, total_funded: e.target.value })}
                placeholder={tr('total_funded_placeholder', 'e.g. 10000')}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">{tr('period_type', 'Period Type')}</label>
              <Select value={createForm.period_type} onValueChange={(v) => setCreateForm({ ...createForm, period_type: v })}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monthly">{tr('period_monthly', 'Monthly')}</SelectItem>
                  <SelectItem value="quarterly">{tr('period_quarterly', 'Quarterly')}</SelectItem>
                  <SelectItem value="yearly">{tr('period_yearly', 'Yearly')}</SelectItem>
                  <SelectItem value="oneoff">{tr('period_oneoff', 'One-off')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium">{tr('period_key', 'Period Key')}</label>
              <Select
                value={createForm.period_key}
                onValueChange={(v) => setCreateForm(prev => ({
                  ...prev,
                  period_key: v,
                  name: prev.name || generatePoolName(prev.period_type, v),
                }))}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {periodKeyOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setCreateOpen(false); resetCreateForm(); }}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={handleCreate} disabled={submitting || !createForm.total_funded || !createForm.period_key}>
              {t('common.submit', 'Submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Purchase Dialog ───────────────────────────── */}
      <Dialog open={purchaseOpen} onOpenChange={(open) => { setPurchaseOpen(open); if (!open) resetPurchaseForm(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{tr('purchase_title', 'Add Purchase')}</DialogTitle>
            <DialogDescription>
              {selectedPool?.name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{tr('purchase_amount', 'Amount')}</label>
              <Input
                type="number"
                value={purchaseAmount}
                onChange={(e) => setPurchaseAmount(e.target.value)}
                placeholder={tr('purchase_amount_placeholder', 'Enter amount to add')}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">{tr('purchase_remark', 'Remark')}</label>
              <Input
                value={purchaseRemark}
                onChange={(e) => setPurchaseRemark(e.target.value)}
                placeholder={tr('purchase_remark_placeholder', 'Enter remark (optional)')}
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setPurchaseOpen(false); resetPurchaseForm(); }}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={handlePurchase} disabled={submitting || !purchaseAmount || Number(purchaseAmount) <= 0}>
              {t('common.submit', 'Submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Allocate Dialog ───────────────────────────── */}
      <Dialog open={allocateOpen} onOpenChange={(open) => { setAllocateOpen(open); if (!open) resetAllocateForm(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{tr('allocate_title', 'Allocate Quota')}</DialogTitle>
            <DialogDescription>
              {selectedPool?.name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{tr('allocate_user', 'User')}</label>
              <SearchableDropdown
                options={[]}
                value={allocateUserId ? `#${allocateUserId}` : ''}
                placeholder={tr('allocate_user_placeholder', 'Search user by name...')}
                searchPlaceholder={tr('allocate_user_search', 'Type username...')}
                searchEndpoint="/api/user/search"
                transformResponse={(data: any[]) =>
                  (data || []).map((u: any) => ({
                    key: String(u.id),
                    value: u.username,
                    text: `${u.username} (#${u.id})`,
                  }))
                }
                debounceMs={300}
                minQueryLength={1}
                onSelect={(key) => setAllocateUserId(key)}
                noResultsMessage={tr('allocate_user_no_results', 'No users found')}
              />
              {allocateUserId && (
                <p className="text-xs text-muted-foreground mt-1">
                  {tr('allocate_user_selected', 'Selected user ID: {{id}}').replace('{{id}}', allocateUserId)}
                </p>
              )}
            </div>
            <div>
              <label className="text-sm font-medium">{tr('allocate_amount', 'Amount (¥)')}</label>
              <Input
                type="number"
                value={allocateAmount}
                onChange={(e) => setAllocateAmount(e.target.value)}
                placeholder={tr('allocate_amount_placeholder', 'e.g. 500')}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">{tr('allocate_remark', 'Remark')}</label>
              <Input
                value={allocateRemark}
                onChange={(e) => setAllocateRemark(e.target.value)}
                placeholder={tr('allocate_remark_placeholder', 'Enter remark (optional)')}
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setAllocateOpen(false); resetAllocateForm(); }}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={handleAllocate} disabled={submitting || !allocateUserId || !allocateAmount || Number(allocateAmount) <= 0}>
              {t('common.submit', 'Submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Recall Dialog ─────────────────────────────── */}
      <Dialog open={recallOpen} onOpenChange={(open) => { setRecallOpen(open); if (!open) resetRecallForm(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{tr('recall_title', 'Recall Quota')}</DialogTitle>
            <DialogDescription>
              {selectedPool?.name} — {tr('recall_user', 'User')} #{recallUserId}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{tr('recall_amount', 'Amount')}</label>
              <Input
                type="number"
                value={recallAmount}
                onChange={(e) => setRecallAmount(e.target.value)}
                placeholder={tr('recall_amount_placeholder', 'Enter amount').replace('{{max}}', String(recallMax))}
                className="mt-1"
                max={recallMax}
              />
              <p className="text-xs text-muted-foreground mt-1">
                {tr('recall_amount_placeholder', 'Max: {{max}}').replace('{{max}}', formatYuan(recallMax))}
              </p>
            </div>
            <div>
              <label className="text-sm font-medium">{tr('recall_remark', 'Remark')}</label>
              <Input
                value={recallRemark}
                onChange={(e) => setRecallRemark(e.target.value)}
                placeholder={tr('recall_remark_placeholder', 'Enter remark (optional)')}
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setRecallOpen(false); resetRecallForm(); }}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={handleRecall} disabled={submitting || !recallAmount || Number(recallAmount) <= 0 || Number(recallAmount) > recallMax}>
              {t('common.submit', 'Submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Rollover Dialog ───────────────────────────── */}
      <Dialog open={rolloverOpen} onOpenChange={(open) => { setRolloverOpen(open); if (!open) resetRolloverForm(); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{tr('rollover_title', 'Rollover Budget Pool')}</DialogTitle>
            <DialogDescription>
              {selectedPool?.name}
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {tr('rollover_hint', 'Rollover the unallocated balance to a new period.')}
          </p>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{tr('rollover_new_name', 'New Name (optional)')}</label>
              <Input
                value={rolloverName}
                onChange={(e) => setRolloverName(e.target.value)}
                placeholder={generateRolloverName(rolloverPeriodType, rolloverPeriodKey) || tr('rollover_new_name_placeholder', 'e.g. Next Budget Pool')}
                className="mt-1"
              />
              {!rolloverName && (
                <p className="text-xs text-muted-foreground mt-1">
                  {tr('rollover_name_auto_hint', 'Auto: {{name}}').replace('{{name}}', generateRolloverName(rolloverPeriodType, rolloverPeriodKey))}
                </p>
              )}
            </div>
            <div>
              <label className="text-sm font-medium">{tr('period_type', 'Period Type')}</label>
              <Select value={rolloverPeriodType} onValueChange={(v) => {
                setRolloverPeriodType(v);
                // Auto-generate period key for new type
                const now = new Date();
                const y = now.getFullYear();
                const m = now.getMonth() + 1;
                const q = Math.ceil(m / 3);
                let key = '';
                if (v === 'monthly') key = `${y}-${String(m).padStart(2, '0')}`;
                else if (v === 'quarterly') key = `${y}-Q${q}`;
                else if (v === 'yearly') key = String(y + 1);
                setRolloverPeriodKey(key);
                // Only clear name if user hasn't entered a custom one
                setRolloverName(prev => prev && prev !== generateRolloverName(rolloverPeriodType, rolloverPeriodKey) ? prev : '');
              }}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monthly">{tr('period_monthly', 'Monthly')}</SelectItem>
                  <SelectItem value="quarterly">{tr('period_quarterly', 'Quarterly')}</SelectItem>
                  <SelectItem value="yearly">{tr('period_yearly', 'Yearly')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium">{tr('rollover_new_period_key', 'New Period Key')}</label>
              <Select value={rolloverPeriodKey} onValueChange={(v) => {
                setRolloverPeriodKey(v);
                // Only auto-set name if user hasn't entered a custom one
                setRolloverName(prev => prev && prev !== generateRolloverName(rolloverPeriodType, rolloverPeriodKey) ? prev : generateRolloverName(rolloverPeriodType, v));
              }}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {rolloverPeriodKeyOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setRolloverOpen(false); resetRolloverForm(); }}>
              {t('common.cancel', 'Cancel')}
            </Button>
            <Button onClick={handleRollover} disabled={submitting || !rolloverPeriodKey}>
              {t('common.submit', 'Submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Reconciliation Dialog ─────────────────────── */}
      <Dialog open={reconcileOpen} onOpenChange={setReconcileOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{tr('reconciliation_summary', 'Pool Summary')}</DialogTitle>
            <DialogDescription>
              {selectedPool?.name}
            </DialogDescription>
          </DialogHeader>
          {reconcileData && (
            <div className="space-y-4">
              {/* Summary cards */}
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-lg border p-3 text-center">
                  <div className="text-xs text-muted-foreground">{tr('total_funded', 'Total Funded')}</div>
                  <div className="text-lg font-bold font-mono">{formatYuan(reconcileData.pool?.total_funded || 0)}</div>
                </div>
                <div className="rounded-lg border p-3 text-center">
                  <div className="text-xs text-muted-foreground">{tr('reconciliation_allocated', 'Total Allocated')}</div>
                  <div className="text-lg font-bold font-mono">{formatYuan(reconcileData.pool?.total_allocated || 0)}</div>
                </div>
                <div className="rounded-lg border p-3 text-center">
                  <div className="text-xs text-muted-foreground">{tr('reconciliation_available', 'Available')}</div>
                  <div className="text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400">
                    {formatYuan(reconcileData.pool?.available || 0)}
                  </div>
                </div>
              </div>

              {/* Allocations table */}
              {reconcileData.allocations && reconcileData.allocations.length > 0 ? (
                <div className="rounded-lg border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="px-3 py-2 text-left">{tr('reconciliation_user', 'User')}</th>
                        <th className="px-3 py-2 text-right">{tr('reconciliation_net_allocated', 'Net Allocated')}</th>
                        <th className="px-3 py-2 text-right">{tr('reconciliation_consumed', 'Consumed')}</th>
                        <th className="px-3 py-2 text-right">{tr('reconciliation_remaining', 'Balance')}</th>
                        <th className="px-3 py-2 text-right">{tr('reconciliation_recallable', 'Recallable')}</th>
                        <th className="px-3 py-2 text-right">{tr('actions', 'Actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reconcileData.allocations.map((a: PoolAllocation) => {
                        return (
                          <tr key={a.id} className="border-b last:border-0">
                            <td className="px-3 py-2">{a.username || `User #${a.user_id}`}</td>
                            <td className="px-3 py-2 text-right font-mono">{formatYuan(a.net_allocated)}</td>
                            <td className="px-3 py-2 text-right font-mono">{formatYuan(a.consumed)}</td>
                            <td className="px-3 py-2 text-right font-mono">{formatYuan(a.remaining)}</td>
                            <td className="px-3 py-2 text-right font-mono">{formatYuan(a.remaining)}</td>
                            <td className="px-3 py-2 text-right">
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-xs"
                                onClick={() => openAllocateDialog(selectedPool!, a.user_id, a.remaining)}
                                disabled={a.remaining <= 0}
                              >
                                {tr('recall', 'Recall')}
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-6">
                  {tr('reconciliation_no_allocations', 'No allocation records')}
                </p>
              )}

              {/* Actions */}
              {selectedPool && selectedPool.status === 'active' && (
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRecallAll}
                    disabled={!reconcileData.allocations || reconcileData.allocations.length === 0}
                  >
                    {tr('reconciliation_recall_all', 'Recall All Remaining')}
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
