import { cn } from '@/lib/utils';

interface SkeletonProps {
  /** Additional className */
  className?: string;
  /** Number of skeleton lines (for text blocks) */
  lines?: number;
  /** Inline styles (for dynamic sizing in chart skeletons) */
  style?: React.CSSProperties;
}

/** Animated skeleton placeholder — use for loading states */
export function Skeleton({ className, lines, style }: SkeletonProps) {
  if (lines && lines > 1) {
    return (
      <div className={cn('space-y-2', className)}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={cn(
              'h-4 rounded-md bg-muted animate-pulse',
              i === lines - 1 && 'w-3/4'
            )}
            style={{ animationDelay: `${i * 100}ms` }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'rounded-md bg-muted animate-pulse',
        className
      )}
      style={style}
    />
  );
}

// ── Pre-built layout skeletons ──────────────────────────────

/** Skeleton mimicking OverviewCards (4-column grid) */
export function CardsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="bg-card rounded-lg border border-l-4 p-4">
          <div className="flex items-center justify-between mb-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-9 rounded-md" />
          </div>
          <Skeleton className="h-7 w-32 mb-2" />
          <Skeleton className="h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

/** Skeleton mimicking a data table */
export function TableSkeleton({ rows = 8, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-md border overflow-hidden">
      {/* Header */}
      <div className="flex gap-4 px-4 py-3 bg-muted/50 border-b">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={`h-${i}`} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <div key={`r-${r}`} className="flex gap-4 px-4 py-3 border-b last:border-b-0">
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={`${r}-${c}`} className="h-4 flex-1" style={{ animationDelay: `${(r * cols + c) * 50}ms` }} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Skeleton mimicking a chart area */
export function ChartSkeleton() {
  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <div className="flex justify-between items-center">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>
      <div className="relative h-[280px] w-full">
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-6 w-10 flex flex-col justify-between">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-3 w-8" />
          ))}
        </div>
        {/* Chart area */}
        <div className="ml-12 h-[240px] flex items-end gap-2">
          {Array.from({ length: 20 }).map((_, i) => (
            <Skeleton
              key={i}
              className="flex-1 rounded-t"
              style={{
                height: `${30 + Math.random() * 70}%`,
                animationDelay: `${i * 60}ms`,
                minHeight: '8px',
              }}
            />
          ))}
        </div>
        {/* X-axis baseline hint */}
        <div className="ml-12 h-2 mt-1">
          <Skeleton className="w-full h-px" />
        </div>
      </div>
    </div>
  );
}

/** Full-page dashboard skeleton combining all elements */
export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Filter bar */}
      <div className="flex flex-wrap gap-3">
        <Skeleton className="h-10 w-36" />
        <Skeleton className="h-10 w-36" />
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-9 w-20 rounded-md self-end" />
      </div>

      <CardsSkeleton />

      {/* Top models / insights row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-card rounded-lg border p-4 space-y-3">
          <Skeleton className="h-5 w-32" />
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-8 w-8 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-28" />
                  <Skeleton className="h-2.5 w-16" />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-card rounded-lg border p-4 space-y-3">
          <Skeleton className="h-5 w-32" />
          <div className="grid grid-cols-2 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-muted/50 rounded-md p-3 text-center">
                <Skeleton className="h-6 w-16 mx-auto mb-1" />
                <Skeleton className="h-3 w-20 mx-auto" />
              </div>
            ))}
          </div>
        </div>
      </div>

      <ChartSkeleton />
      <ChartSkeleton />
    </div>
  );
}
