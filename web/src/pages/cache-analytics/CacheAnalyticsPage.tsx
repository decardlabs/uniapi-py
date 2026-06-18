import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ResponsivePageContainer } from '@/components/ui/responsive-container';
import { api } from '@/lib/api';
import { useAuthStore } from '@/lib/stores/auth';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

type CacheSummary = {
  request_count: number;
  prompt_tokens: number;
  cached_prompt_tokens: number;
  completion_tokens: number;
  cached_completion_tokens: number;
  quota: number;
  cache_hit_rate: number;
  estimated_savings_rate: number;
};

type CacheTimeseriesRow = {
  day: string;
  request_count: number;
  prompt_tokens: number;
  cached_prompt_tokens: number;
  quota: number;
  cache_hit_rate: number;
  estimated_savings_rate: number;
  completion_tokens: number;
  cached_completion_tokens: number;
};

type CacheBreakdownRow = {
  model_name: string;
  channel_id: number;
  request_format: string;
  channel_name: string;
  request_count: number;
  prompt_tokens: number;
  cached_prompt_tokens: number;
  completion_tokens: number;
  cached_completion_tokens: number;
  quota: number;
  cache_hit_rate: number;
  estimated_savings_rate: number;
};

type CacheCompare = {
  compare_date: string;
  before: CacheSummary;
  after: CacheSummary;
};

type CacheAnalyticsResponse = {
  summary: CacheSummary;
  timeseries: CacheTimeseriesRow[];
  breakdown: CacheBreakdownRow[];
  compare: CacheCompare;
};

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function formatInt(value: number): string {
  return new Intl.NumberFormat().format(value || 0);
}

export default function CacheAnalyticsPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const isAdmin = useMemo(() => (user?.role ?? 0) >= 10, [user]);

  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  const today = new Date();
  const last7 = new Date(today);
  last7.setDate(today.getDate() - 6);

  const [fromDate, setFromDate] = useState(fmt(last7));
  const [toDate, setToDate] = useState(fmt(today));
  const [modelName, setModelName] = useState('');
  const [channelID, setChannelID] = useState('');
  const [requestFormat, setRequestFormat] = useState('');
  const [compareDate, setCompareDate] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [data, setData] = useState<CacheAnalyticsResponse | null>(null);

  const loadData = async () => {
    if (!isAdmin) return;
    setLoading(true);
    setError('');

    try {
      const params = new URLSearchParams();
      params.set('from_date', fromDate);
      params.set('to_date', toDate);
      if (modelName.trim() !== '') {
        params.set('model_name', modelName.trim());
      }
      if (channelID.trim() !== '') {
        params.set('channel_id', channelID.trim());
      }
      if (requestFormat.trim() !== '') {
        params.set('request_format', requestFormat.trim());
      }
      if (compareDate.trim() !== '') {
        params.set('compare_date', compareDate.trim());
      }

      const res = await api.get('/api/user/cache-analytics?' + params.toString());
      const { success, message, data: payload } = res.data || {};
      if (!success) {
        setData(null);
        setError(message || t('cacheAnalytics.errors.fetch_failed'));
        return;
      }

      setData(payload as CacheAnalyticsResponse);
    } catch {
      setData(null);
      setError(t('cacheAnalytics.errors.fetch_failed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      loadData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAdmin]);

  if (!user) {
    return <div>{t('dashboard.login_required')}</div>;
  }

  if (!isAdmin) {
    return <div>{t('cacheAnalytics.unauthorized')}</div>;
  }

  const summary = data?.summary;
  const timeseries = data?.timeseries || [];
  const breakdown = data?.breakdown || [];
  const compare = data?.compare;
  const compareDelta = (compare?.after?.cache_hit_rate || 0) - (compare?.before?.cache_hit_rate || 0);

  return (
    <ResponsivePageContainer title={t('cacheAnalytics.title')} description={t('cacheAnalytics.description')}>
      <div className="mb-4 grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-7">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">{t('cacheAnalytics.filters.from')}</label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">{t('cacheAnalytics.filters.to')}</label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">{t('cacheAnalytics.filters.model')}</label>
          <Input
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder={t('cacheAnalytics.filters.all_models')}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">{t('cacheAnalytics.filters.channel_id')}</label>
          <Input
            value={channelID}
            onChange={(e) => setChannelID(e.target.value)}
            placeholder={t('cacheAnalytics.filters.all_channels')}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">{t('cacheAnalytics.filters.request_format')}</label>
          <Input
            value={requestFormat}
            onChange={(e) => setRequestFormat(e.target.value)}
            placeholder={t('cacheAnalytics.filters.all_formats')}
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">{t('cacheAnalytics.filters.compare_date')}</label>
          <Input type="date" value={compareDate} onChange={(e) => setCompareDate(e.target.value)} />
        </div>
        <div className="flex items-end gap-2">
          <Button variant="outline" onClick={() => {
            const now = new Date();
            const start = new Date(now);
            start.setDate(now.getDate() - 6);
            setFromDate(fmt(start));
            setToDate(fmt(now));
          }}>
            {t('cacheAnalytics.filters.last_7d')}
          </Button>
          <Button onClick={loadData} disabled={loading}>{t('cacheAnalytics.filters.apply')}</Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4 mb-6">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">{t('cacheAnalytics.cards.cache_hit_rate')}</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{formatPercent(summary?.cache_hit_rate || 0)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">{t('cacheAnalytics.cards.estimated_savings_rate')}</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{formatPercent(summary?.estimated_savings_rate || 0)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">{t('cacheAnalytics.cards.cached_prompt_tokens')}</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{formatInt(summary?.cached_prompt_tokens || 0)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">{t('cacheAnalytics.cards.total_quota')}</CardTitle></CardHeader>
          <CardContent className="text-2xl font-semibold">{formatInt(summary?.quota || 0)}</CardContent>
        </Card>
      </div>

      {compare?.compare_date ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 mb-6">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">{t('cacheAnalytics.compare.before')}</CardTitle></CardHeader>
            <CardContent className="text-2xl font-semibold">{formatPercent(compare.before?.cache_hit_rate || 0)}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">{t('cacheAnalytics.compare.after')}</CardTitle></CardHeader>
            <CardContent className="text-2xl font-semibold">{formatPercent(compare.after?.cache_hit_rate || 0)}</CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">{t('cacheAnalytics.compare.delta')}</CardTitle></CardHeader>
            <CardContent className={`text-2xl font-semibold ${compareDelta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {formatPercent(compareDelta)}
            </CardContent>
          </Card>
        </div>
      ) : null}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>{t('cacheAnalytics.sections.trend')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeseries}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.25} />
                <XAxis dataKey="day" />
                <YAxis domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <Tooltip formatter={(value: unknown) => formatPercent(Number(value || 0))} />
                <Line type="monotone" dataKey="cache_hit_rate" name={t('cacheAnalytics.cards.cache_hit_rate')} stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="estimated_savings_rate" name={t('cacheAnalytics.cards.estimated_savings_rate')} stroke="hsl(var(--chart-2))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('cacheAnalytics.sections.breakdown')}</CardTitle>
        </CardHeader>
        <CardContent>
          {breakdown.length === 0 && !loading ? (
            <div className="text-sm text-muted-foreground">{t('cacheAnalytics.empty')}</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="px-2 py-2">{t('cacheAnalytics.table.model')}</th>
                    <th className="px-2 py-2">{t('cacheAnalytics.table.channel')}</th>
                    <th className="px-2 py-2">{t('cacheAnalytics.table.request_format')}</th>
                    <th className="px-2 py-2">{t('cacheAnalytics.table.requests')}</th>
                    <th className="px-2 py-2">{t('cacheAnalytics.table.prompt_tokens')}</th>
                    <th className="px-2 py-2">{t('cacheAnalytics.table.cached_prompt_tokens')}</th>
                    <th className="px-2 py-2">{t('cacheAnalytics.table.cache_hit_rate')}</th>
                    <th className="px-2 py-2">{t('cacheAnalytics.table.quota')}</th>
                  </tr>
                </thead>
                <tbody>
                  {breakdown.map((row) => (
                    <tr key={`${row.model_name}-${row.channel_id}-${row.request_format}`} className="border-b">
                      <td className="px-2 py-2">{row.model_name}</td>
                      <td className="px-2 py-2">{row.channel_name || row.channel_id}</td>
                      <td className="px-2 py-2">{row.request_format || 'unknown'}</td>
                      <td className="px-2 py-2">{formatInt(row.request_count)}</td>
                      <td className="px-2 py-2">{formatInt(row.prompt_tokens)}</td>
                      <td className="px-2 py-2">{formatInt(row.cached_prompt_tokens)}</td>
                      <td className="px-2 py-2">{formatPercent(row.cache_hit_rate)}</td>
                      <td className="px-2 py-2">{formatInt(row.quota)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </ResponsivePageContainer>
  );
}
