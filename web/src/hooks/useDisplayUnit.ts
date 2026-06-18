import { useState, useEffect, useCallback, useMemo } from 'react';

/**
 * Display Unit Types
 *
 * - 'token': Show quota as token count (raw internal value)
 * - 'usd':  Show quota as US dollars
 * - 'cny': Show quota as Chinese Yuan (RMB)
 */
export type DisplayUnit = 'token' | 'usd' | 'cny';

/** LocalStorage key for persisting the user's display unit preference */
const DISPLAY_UNIT_KEY = 'display_unit';
/** Fallback default display unit */
const DEFAULT_DISPLAY_UNIT: DisplayUnit = 'token';

/** LocalStorage key for quota-per-USD conversion rate (from server) */
const QUOTA_PER_UNIT_KEY = 'quota_per_unit';
/** Default: 500,000 quota per USD ($1 = 500K quota) */
const DEFAULT_QUOTA_PER_UNIT = 500000;

/** Exchange rate: CNY per USD (from backend model.go) */
const EXCHANGE_RATE_RMB = 8;

/**
 * Get the current display mode from localStorage.
 * Supports migration from legacy `display_in_currency` boolean.
 */
export function getDisplayUnit(): DisplayUnit {
  const stored = localStorage.getItem(DISPLAY_UNIT_KEY);
  if (stored && ['token', 'usd', 'cny'].includes(stored)) {
    return stored as DisplayUnit;
  }

  // Migration from legacy boolean setting
  const legacyDisplayInCurrency = localStorage.getItem('display_in_currency');
  if (legacyDisplayInCurrency === 'true') {
    return 'usd'; // legacy "display as currency" → default to USD
  }

  return DEFAULT_DISPLAY_UNIT;
}

/**
 * Persist display unit preference to localStorage.
 * Also cleans up legacy keys.
 */
export function setDisplayUnit(unit: DisplayUnit): void {
  localStorage.setItem(DISPLAY_UNIT_KEY, unit);
  // Clean up legacy boolean key after migration
  if (localStorage.getItem('display_in_currency') !== null) {
    // Keep it for backward compat but it's no longer authoritative
  }
}

/**
 * Get the quota-per-unit conversion rate from localStorage.
 */
function getQuotaPerUnit(): number {
  const stored = parseFloat(localStorage.getItem(QUOTA_PER_UNIT_KEY) || '');
  return stored > 0 ? stored : DEFAULT_QUOTA_PER_UNIT;
}

/**
 * Convert internal quota value to the selected display unit.
 *
 * @param quota - Internal quota value (int64)
 * @param unit - Target display unit
 * @returns Converted numeric value
 */
export function quotaToValue(quota: number, unit: DisplayUnit): number {
  const quotaPerUnit = getQuotaPerUnit();

  switch (unit) {
    case 'token':
      // Raw token count (quota ≈ tokens in current system)
      return quota;
    case 'usd':
      return quota / quotaPerUnit;
    case 'cny':
      return (quota / quotaPerUnit) * EXCHANGE_RATE_RMB;
    default:
      return quota;
  }
}

/**
 * Format a quota value into a human-readable string based on display unit.
 *
 * @param quota - Internal quota value
 * @param unit - Display unit
 * @param options - Formatting options
 * @returns Formatted string like "1.5M tokens", "$3.00", "¥24.00"
 */
export function formatQuotaByUnit(
  quota: number,
  unit: DisplayUnit,
  options?: { decimals?: number; showSymbol?: boolean; showLabel?: boolean },
): string {
  const { decimals = 2, showSymbol = true, showLabel = true } = options || {};
  const value = quotaToValue(quota, unit);

  switch (unit) {
    case 'token': {
      const formatted = formatTokenCount(value);
      return showLabel ? `${formatted} ${showSymbol ? 'tokens' : ''}`.trim() : formatted;
    }
    case 'usd': {
      const formatted = value.toFixed(decimals);
      return showSymbol ? `$${formatted}` : formatted;
    }
    case 'cny': {
      const formatted = value.toFixed(decimals);
      return showSymbol ? `¥${formatted}` : formatted;
    }
    default:
      return String(value);
  }
}

/**
 * Format a large token count with K/M suffixes.
 */
function formatTokenCount(tokens: number): string {
  if (tokens >= 1_000_000) {
    return (tokens / 1_000_000).toFixed(1) + 'M';
  }
  if (tokens >= 1_000) {
    return (tokens / 1_000).toFixed(1) + 'K';
  }
  return Math.round(tokens).toLocaleString();
}

/**
 * Convert a user-input value in the given display unit back to internal quota.
 *
 * Examples:
 * - inputAmount=10, unit='usd', quotaPerUnit=500000 → returns 5,000,000
 * - inputAmount=1000, unit='token' → returns 1000
 * - inputAmount=80, unit='cny', quotaPerUnit=500000 → returns 5,000,000
 */
export function valueToQuota(inputAmount: number, unit: DisplayUnit): number {
  const quotaPerUnit = getQuotaPerUnit();

  switch (unit) {
    case 'token':
      return Math.round(inputAmount);
    case 'usd':
      return Math.round(inputAmount * quotaPerUnit);
    case 'cny':
      return Math.round((inputAmount / EXCHANGE_RATE_RMB) * quotaPerUnit);
    default:
      return Math.round(inputAmount);
  }
}

/**
 * React hook for unified quota display management.
 *
 * Provides:
 * - Current display unit (token/usd/cny)
 * - Formatted rendering functions
 * - Conversion utilities
 * - Unit switching capability
 *
 * @example
 * ```tsx
 * const { displayUnit, formatQuota, renderQuota, setDisplayUnit, unitLabel } = useDisplayUnit();
 *
 * // In component:
 * <span>{renderQuota(user.quota)}</span>  // e.g., "1.5M tokens" or "$3.00"
 * <select onChange={(e) => setDisplayUnit(e.target.value as DisplayUnit)}>
 *   <option value="token">Tokens</option>
 *   <option value="usd">USD</option>
 *   <option value="cny">CNY</option>
 * </select>
 * ```
 */
export interface UseDisplayUnitResult {
  /** Currently active display unit */
  displayUnit: DisplayUnit;
  /** Set the display unit and persist it */
  setDisplayUnit: (unit: DisplayUnit) => void;
  /** Format quota to a plain value string (no symbol/label by default) */
  formatQuotaValue: (quota: number, decimals?: number) => string;
  /** Render quota with full formatting (symbol + label), suitable for direct UI display */
  renderQuota: (quota: number, options?: { showLabel?: boolean }) => string;
  /** Render quota with prompt-style formatting (shows both units when helpful) */
  renderQuotaWithPrompt: (quota: number) => string;
  /** Convert display-unit value back to internal quota */
  toQuota: (inputAmount: number) => number;
  /** Convert internal quota to display-unit value */
  toValue: (quota: number) => number;
  /** Human-readable label for the current unit (e.g., "Tokens", "USD", "CNY") */
  unitLabel: string;
  /** Symbol for the current unit (e.g., "", "$", "¥") */
  unitSymbol: string;
  /** All available display units for building selectors */
  availableUnits: readonly { value: DisplayUnit; label: string; symbol: string }[];
  /** The quota-per-USD conversion rate */
  quotaPerUnit: number;
}

const UNIT_OPTIONS: readonly { value: DisplayUnit; label: string; symbol: string }[] = [
  { value: 'token', label: 'Tokens', symbol: '' },
  { value: 'usd', label: 'USD', symbol: '$' },
  { value: 'cny', label: 'CNY', symbol: '¥' },
] as const;

export const useDisplayUnit = (): UseDisplayUnitResult => {
  const [displayUnit, setDisplayUnitState] = useState<DisplayUnit>(getDisplayUnit);

  // Sync across tabs: listen for storage events
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === DISPLAY_UNIT_KEY && e.newValue) {
        const newUnit = e.newValue;
        if (['token', 'usd', 'cny'].includes(newUnit)) {
          setDisplayUnitState(newUnit as DisplayUnit);
        }
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const setDisplayUnitAction = useCallback((unit: DisplayUnit) => {
    setDisplayUnitState(unit);
    setDisplayUnit(unit);
  }, []);

  const formatQuotaValue = useCallback(
    (quota: number, decimals: number = 2): string => {
      return formatQuotaByUnit(quota, displayUnit, { decimals, showSymbol: true, showLabel: false });
    },
    [displayUnit],
  );

  const renderQuota = useCallback(
    (quota: number, options?: { showLabel?: boolean }): string => {
      return formatQuotaByUnit(quota, displayUnit, { decimals: 2, showSymbol: true, showLabel: options?.showLabel !== false });
    },
    [displayUnit],
  );

  const renderQuotaWithPrompt = useCallback(
    (quota: number): string => {
      // For token mode, just show token count
      if (displayUnit === 'token') {
        const value = quotaToValue(quota, 'token');
        return `${formatTokenCount(value)} tokens`;
      }
      // For currency modes, show both token count and currency value
      const tokenStr = formatTokenCount(quotaToValue(quota, 'token'));
      const currencyStr = formatQuotaByUnit(quota, displayUnit, { decimals: 4, showSymbol: true, showLabel: false });
      return `${tokenStr} tokens (${currencyStr})`;
    },
    [displayUnit],
  );

  const toQuota = useCallback(
    (inputAmount: number): number => valueToQuota(inputAmount, displayUnit),
    [displayUnit],
  );

  const toValue = useCallback(
    (quota: number): number => quotaToValue(quota, displayUnit),
    [displayUnit],
  );

  const unitInfo = useMemo(
    () => UNIT_OPTIONS.find((u) => u.value === displayUnit) || UNIT_OPTIONS[0],
    [displayUnit],
  );

  return {
    displayUnit,
    setDisplayUnit: setDisplayUnitAction,
    formatQuotaValue,
    renderQuota,
    renderQuotaWithPrompt,
    toQuota,
    toValue,
    unitLabel: unitInfo.label,
    unitSymbol: unitInfo.symbol,
    availableUnits: UNIT_OPTIONS,
    quotaPerUnit: getQuotaPerUnit(),
  };
};

// Re-export utility functions for non-hook usage (e.g., in utils.ts)
export { getQuotaPerUnit, EXCHANGE_RATE_RMB };
