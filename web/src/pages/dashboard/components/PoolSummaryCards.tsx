import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn, renderQuota } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { PiggyBank, Wallet, ArrowRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface PoolSummary {
  id: number;
  name: string;
  total_quota: number;
  used_quota: number;
  status: string;
}

export function PoolSummaryCards() {
  const { t } = useTranslation();
  const [pools, setPools] = useState<PoolSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchPools = async () => {
      try {
        const res = await api.get('/api/pool/', {
          params: { status: 'active', page: 1, page_size: 50 },
        });
        if (!cancelled && res.data?.success) {
          setPools(res.data.data?.items || []);
        }
      } catch {
        // Silently fail — this is a dashboard widget
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchPools();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-card rounded-lg border p-4 animate-pulse">
            <div className="h-4 bg-muted/30 rounded w-24 mb-3" />
            <div className="h-7 bg-muted/30 rounded w-20" />
          </div>
        ))}
      </div>
    );
  }

  if (pools.length === 0) return null;

  const totalBudget = pools.reduce((s, p) => s + p.total_quota, 0);
  const totalUsed = pools.reduce((s, p) => s + p.used_quota, 0);
  const totalAvailable = totalBudget - totalUsed;

  const cards = [
    {
      title: t('dashboard.pool_summary.pool_count'),
      value: pools.length,
      icon: PiggyBank,
      accent: 'border-l-primary',
      iconBg: 'bg-primary/10',
      iconColor: 'text-primary',
    },
    {
      title: t('dashboard.pool_summary.total_budget'),
      value: renderQuota(totalBudget),
      icon: Wallet,
      accent: 'border-l-chart-1',
      iconBg: 'bg-chart-1/10',
      iconColor: 'text-chart-1',
    },
    {
      title: t('dashboard.pool_summary.total_available'),
      value: renderQuota(totalAvailable),
      subtitle: `${t('dashboard.pool_summary.total_allocated')}: ${renderQuota(totalUsed)}`,
      icon: ArrowRight,
      accent: 'border-l-chart-3',
      iconBg: 'bg-chart-3/10',
      iconColor: 'text-chart-3',
    },
  ];

  return (
    <Card className="mb-6 border-0 md:border shadow-none md:shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div>
          <CardTitle className="text-base font-semibold">{t('dashboard.pool_summary.title')}</CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">{t('dashboard.pool_summary.subtitle')}</p>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/pools">{t('dashboard.pool_summary.view_all')}</Link>
        </Button>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(Array.isArray(cards) ? cards : []).map((card) => (
            <div
              key={card.title}
              className={cn(
                'rounded-lg border border-l-4 p-4 transition-shadow hover:shadow-sm',
                card.accent,
              )}
            >
              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground font-medium">{card.title}</div>
                <div className={cn('p-2 rounded-md', card.iconBg)}>
                  <card.icon className={cn('h-4 w-4', card.iconColor)} />
                </div>
              </div>
              <div className="text-2xl font-bold mt-2 tracking-tight tabular-nums">
                {card.value}
              </div>
              {card.subtitle && (
                <div className="text-xs text-muted-foreground mt-2">{card.subtitle}</div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
