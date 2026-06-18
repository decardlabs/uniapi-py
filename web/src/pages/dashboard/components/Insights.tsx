import { formatNumber } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { CalendarCheck, Flame, Layers } from 'lucide-react';

interface InsightsProps {
  rangeInsights: {
    busiestDay: { date: string; requests: number } | null;
    tokenHeavyDay: { date: string; tokens: number } | null;
  };
  totalModels: number;
  totalRequests: number;
}

export function Insights({ rangeInsights, totalModels, totalRequests }: InsightsProps) {
  const { t } = useTranslation();

  const items = [
    {
      label: t('dashboard.insights.busiest_day'),
      value: rangeInsights.busiestDay?.date || t('dashboard.labels.no_data'),
      meta: rangeInsights.busiestDay ? t('dashboard.labels.requests_value', { value: formatNumber(rangeInsights.busiestDay.requests) }) : undefined,
      icon: CalendarCheck,
      accent: 'border-l-chart-2',
      iconBg: 'bg-chart-2/10',
      iconColor: 'text-chart-2',
    },
    {
      label: t('dashboard.insights.peak_token_day'),
      value: rangeInsights.tokenHeavyDay?.date || t('dashboard.labels.no_data'),
      meta: rangeInsights.tokenHeavyDay ? t('dashboard.labels.tokens_value', { value: formatNumber(rangeInsights.tokenHeavyDay.tokens) }) : undefined,
      icon: Flame,
      accent: 'border-l-accent',
      iconBg: 'bg-accent/10',
      iconColor: 'text-accent',
    },
    {
      label: t('dashboard.insights.models_in_use'),
      value: formatNumber(totalModels),
      meta: totalModels ? t('dashboard.insights.requests_per_model', { value: formatNumber(Math.round(totalRequests / totalModels)) }) : t('dashboard.labels.no_value'),
      icon: Layers,
      accent: 'border-l-primary',
      iconBg: 'bg-primary/10',
      iconColor: 'text-primary',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {(Array.isArray(items) ? items : []).map((item) => (
        <div key={item.label} className={`bg-card rounded-lg border border-l-4 ${item.accent} p-4`}>
          <div className="flex items-center gap-2 mb-2">
            <div className={`p-1.5 rounded-md ${item.iconBg}`}>
              <item.icon className={`h-3.5 w-3.5 ${item.iconColor}`} />
            </div>
            <span className="text-sm text-muted-foreground">{item.label}</span>
          </div>
          <div className="text-lg font-semibold mt-1 tabular-nums">{item.value}</div>
          {item.meta && (
            <div className="text-xs text-muted-foreground mt-2">{item.meta}</div>
          )}
        </div>
      ))}
    </div>
  );
}
