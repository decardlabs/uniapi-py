import { useTranslation } from 'react-i18next';
import { BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface EmptyStateProps {
  /** Optional custom message override */
  message?: string;
  /** Optional custom sub-message */
  description?: string;
  /** Additional className */
  className?: string;
}

export function EmptyState({ message, description, className }: EmptyStateProps) {
  const { t } = useTranslation();

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-16 px-4 text-center',
        className
      )}
      role="status"
    >
      {/* Illustration: abstract chart icon with decorative rings */}
      <div className="relative mb-6">
        {/* Decorative background circles */}
        <div className="absolute inset-0 -m-4 rounded-full bg-primary/5 animate-pulse" />
        <div className="absolute inset-0 -m-8 rounded-full bg-primary/[0.03] animate-pulse [animation-delay:500ms]" />

        {/* Icon container */}
        <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-primary/10 ring-1 ring-primary/20">
          <BarChart3 className="h-10 w-10 text-primary/60" strokeWidth={1.5} />
        </div>
      </div>

      <h3 className="text-base font-semibold text-foreground mb-1.5">
        {message || t('dashboard.empty.title', 'No data yet')}
      </h3>
      <p className="text-sm text-muted-foreground max-w-sm">
        {description ||
          t('dashboard.empty.description', 'Start making API requests to see usage statistics and charts here.')}
      </p>
    </div>
  );
}
