import { formatNumber, renderQuotaWithUsd } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { Brain, Cpu, DollarSign, MousePointerClick } from 'lucide-react';
import { getDisplayInCurrency, getQuotaPerUnit } from '../types';

interface TopModelsProps {
  modelLeaders: {
    mostRequested: { model: string; requests: number } | null;
    mostTokens: { model: string; tokens: number } | null;
    mostQuota: { model: string; quota: number } | null;
  };
}

// (renderQuotaWithUsd imported from utils replaces the local renderQuota)

export function TopModels({ modelLeaders }: TopModelsProps) {
  const { t } = useTranslation();

  const items = [
    {
      label: t('dashboard.top_models.most_requests'),
      model: modelLeaders.mostRequested?.model,
      meta: modelLeaders.mostRequested ? t('dashboard.labels.requests_value', { value: formatNumber(modelLeaders.mostRequested.requests) }) : undefined,
      icon: MousePointerClick,
      accent: 'border-l-primary',
      iconBg: 'bg-primary/10',
      iconColor: 'text-primary',
    },
    {
      label: t('dashboard.top_models.most_tokens'),
      model: modelLeaders.mostTokens?.model,
      meta: modelLeaders.mostTokens ? t('dashboard.labels.tokens_value', { value: formatNumber(modelLeaders.mostTokens.tokens) }) : undefined,
      icon: Brain,
      accent: 'border-l-chart-3',
      iconBg: 'bg-chart-3/10',
      iconColor: 'text-chart-3',
    },
    {
      label: t('dashboard.top_models.highest_cost'),
      model: modelLeaders.mostQuota?.model,
      meta: modelLeaders.mostQuota ? t('dashboard.labels.quota_consumed', { value: renderQuotaWithUsd(modelLeaders.mostQuota.quota) }) : undefined,
      icon: DollarSign,
      accent: 'border-l-accent',
      iconBg: 'bg-accent/10',
      iconColor: 'text-accent',
    },
  ];

  return (
    <div className="bg-card rounded-lg border p-6 mb-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Cpu className="h-5 w-5 text-muted-foreground" />
        {t('dashboard.top_models.title')}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(Array.isArray(items) ? items : []).map((item) => (
          <div key={item.label} className={`rounded-lg border border-l-4 ${item.accent} bg-card/70 p-4`}>
            <div className="flex items-center gap-2 mb-2">
              <div className={`p-1.5 rounded-md ${item.iconBg}`}>
                <item.icon className={`h-3.5 w-3.5 ${item.iconColor}`} />
              </div>
              <span className="text-sm text-muted-foreground">{item.label}</span>
            </div>
            <div className="text-xl font-semibold mt-1 font-mono truncate" title={item.model || undefined}>
              {item.model || t('dashboard.labels.no_data')}
            </div>
            {item.meta && (
              <div className="text-xs text-muted-foreground mt-2">{item.meta}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
