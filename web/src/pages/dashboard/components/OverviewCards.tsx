import { cn } from '@/lib/utils';
import { formatNumber } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { Banknote, BarChart3, MousePointerClick, TrendingUp } from 'lucide-react';

interface OverviewCardsProps {
  totalRequests: number;
  totalTokens: number;
  avgDailyRequests: number;
  avgDailyTokens: number;
  avgCostPerRequestRaw: number;
  avgTokensPerRequest: number;
  balance: number;
}

const COST_PER_USD = 1_000_000; // 1 USD = 1,000,000 micro-yuan

export function OverviewCards({
  totalRequests,
  totalTokens,
  avgDailyRequests,
  avgDailyTokens,
  avgCostPerRequestRaw,
  avgTokensPerRequest,
  balance,
}: OverviewCardsProps) {
  const { t } = useTranslation();
  const balanceCny = balance / COST_PER_USD;

  const cards = [
    {
      title: t('dashboard.cards.total_requests'),
      value: formatNumber(totalRequests),
      subtitle: t('dashboard.cards.avg_daily', { value: formatNumber(Math.round(avgDailyRequests || 0)) }),
      icon: MousePointerClick,
      accent: 'border-l-primary',
      iconBg: 'bg-primary/10',
      iconColor: 'text-primary',
    },
    {
      title: t('dashboard.cards.current_balance'),
      value: `¥${balanceCny.toFixed(2)}`,
      subtitle: balanceCny < 10 ? t('dashboard.cards.balance_low') : t('dashboard.cards.balance_available'),
      icon: Banknote,
      accent: balanceCny < 10 ? 'border-l-warning' : 'border-l-accent',
      iconBg: balanceCny < 10 ? 'bg-warning/10' : 'bg-accent/10',
      iconColor: balanceCny < 10 ? 'text-warning' : 'text-accent',
    },
    {
      title: t('dashboard.cards.tokens_consumed'),
      value: formatNumber(totalTokens),
      subtitle: t('dashboard.cards.avg_daily', { value: formatNumber(Math.round(avgDailyTokens || 0)) }),
      icon: BarChart3,
      accent: 'border-l-chart-3',
      iconBg: 'bg-chart-3/10',
      iconColor: 'text-chart-3',
    },
    {
      title: t('dashboard.cards.avg_cost'),
      value: `¥${(avgCostPerRequestRaw / COST_PER_USD).toFixed(4)}`,
      subtitle: t('dashboard.cards.tokens_per_request', { value: Math.round(avgTokensPerRequest || 0) }),
      icon: TrendingUp,
      accent: 'border-l-chart-2',
      iconBg: 'bg-chart-2/10',
      iconColor: 'text-chart-2',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
      {(Array.isArray(cards) ? cards : []).map((card) => (
        <div key={card.title} className={cn(
          'bg-card rounded-lg border border-l-4 p-4 transition-shadow hover:shadow-sm',
          card.accent,
        )}>
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted-foreground font-medium">{card.title}</div>
            <div className={cn('p-2 rounded-md', card.iconBg)}>
              <card.icon className={cn('h-4 w-4', card.iconColor)} />
            </div>
          </div>
          <div className="text-2xl font-bold mt-2 tracking-tight tabular-nums">{card.value}</div>
          <div className="text-xs text-muted-foreground mt-2">
            {card.subtitle}
          </div>
        </div>
      ))}
    </div>
  );
}
