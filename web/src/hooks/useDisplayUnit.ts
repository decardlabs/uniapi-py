import { useState, useEffect, useCallback, useMemo } from 'react';

/**
 * Display Unit Types
 *
 * All input values are expected in micro-yuan (10^-6 yuan).
 * - 'cny':    Display as yuan (CNY) — divide by 1,000,000
 * - 'usd':    Display as US dollars — divide by 1M then by exchange rate
 * - 'token':  Display as approximate legacy quota units (÷2) — backward compat
 */
export type DisplayUnit = 'cny' | 'usd' | 'token';

/** LocalStorage key for persisting the user's display unit preference */
const DISPLAY_UNIT_KEY = 'display_unit';
/** Fallback default display unit */
const DEFAULT_DISPLAY_UNIT: DisplayUnit = 'cny';

/** Exchange rate: USD per CNY */
const USD_PER_CNY = 0.14;  // 1 CNY ≈ 0.14 USD
const CNY_PER_USD = 7.2;   // 1 USD ≈ 7.2 CNY


/**
 * Get the current display mode from localStorage.
 */
export function getDisplayUnit(): DisplayUnit {
  const stored = localStorage.getItem(DISPLAY_UNIT_KEY);
  if (stored && ['cny', 'usd', 'token'].includes(stored)) {
    return stored as DisplayUnit;
  }
  return DEFAULT_DISPLAY_UNIT;
}

/**
 * Persist display unit preference to localStorage.
 */
export function setDisplayUnit(unit: DisplayUnit): void {
  localStorage.setItem(DISPLAY_UNIT_KEY, unit);
}

/**
 * Convert micro-yuan to the selected display unit.
 *
 * @param micro - Value in micro-yuan (10^-6 yuan)
 * @param unit  - Target display unit
 * @returns Converted numeric value
 */
export function quotaToValue(micro: number, unit: DisplayUnit): number {
  switch (unit) {
    case 'token':
      return micro / 2;         // approximate legacy quota units
    case 'usd':
      return (micro / 1_000_000) * USD_PER_CNY;
    case 'cny':
      return micro / 1_000_000; // micro-yuan → yuan
    default:
      return micro / 1_000_000;
  }
}

/**
 * Convert a user-input display value back to micro-yuan.
 */
export function valueToQuota(inputAmount: number, unit: DisplayUnit): number {
  switch (unit) {
    case 'token':
      return Math.round(inputAmount * 2);
    case 'usd':
      return Math.round((inputAmount / USD_PER_CNY) * 1_000_000);
    case 'cny':
      return Math.round(inputAmount * 1_000_000);
    default:
      return Math.round(inputAmount * 1_000_000);
  }
}

/**
 * Format a micro-yuan value into a human-readable string.
 */
export function formatQuotaByUnit(
  micro: number,
  unit: DisplayUnit,
  options?: { decimals?: number; showSymbol?: boolean; showLabel?: boolean },
): string {
  const { decimals = 2, showSymbol = true, showLabel = true } = options || {};
  const value = quotaToValue(micro, unit);

  switch (unit) {
    case 'token': {
      const formatted = formatLargeNum(value);
      return showLabel ? `${formatted}${showSymbol ? ' tokens' : ''}`.trim() : formatted;
    }
    case 'usd':
      return showSymbol ? `$${value.toFixed(decimals)}` : value.toFixed(decimals);
    case 'cny':
      return showSymbol ? `¥${value.toFixed(decimals)}` : value.toFixed(decimals);
    default:
      return String(value);
  }
}

/** Format a large number with K/M suffixes. */
function formatLargeNum(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return Math.round(n).toLocaleString();
}

/**
 * React hook for unified billing display.
 *
 * All input values are expected in micro-yuan.
 *
 * ```tsx
 * const { renderQuota } = useDisplayUnit();
 * <span>{renderQuota(user.balance)}</span>  // "¥50.00" or "$7.00"
 * ```
 */
export interface UseDisplayUnitResult {
  displayUnit: DisplayUnit;
  setDisplayUnit: (unit: DisplayUnit) => void;
  formatQuotaValue: (micro: number, decimals?: number) => string;
  renderQuota: (micro: number, options?: { showLabel?: boolean }) => string;
  renderQuotaWithPrompt: (micro: number) => string;
  toQuota: (inputAmount: number) => number;
  toValue: (micro: number) => number;
  unitLabel: string;
  unitSymbol: string;
  availableUnits: readonly { value: DisplayUnit; label: string; symbol: string }[];
}

const UNIT_OPTIONS: readonly { value: DisplayUnit; label: string; symbol: string }[] = [
  { value: 'cny', label: 'CNY', symbol: '¥' },
  { value: 'usd', label: 'USD', symbol: '$' },
  { value: 'token', label: 'Tokens', symbol: '' },
] as const;

export const useDisplayUnit = (): UseDisplayUnitResult => {
  const [displayUnit, setDisplayUnitState] = useState<DisplayUnit>(getDisplayUnit);

  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === DISPLAY_UNIT_KEY && e.newValue && ['cny', 'usd', 'token'].includes(e.newValue)) {
        setDisplayUnitState(e.newValue as DisplayUnit);
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
    (micro: number, decimals: number = 2): string =>
      formatQuotaByUnit(micro, displayUnit, { decimals, showSymbol: true, showLabel: false }),
    [displayUnit],
  );

  const renderQuota = useCallback(
    (micro: number, options?: { showLabel?: boolean }): string =>
      formatQuotaByUnit(micro, displayUnit, { decimals: 2, showSymbol: true, showLabel: options?.showLabel !== false }),
    [displayUnit],
  );

  const renderQuotaWithPrompt = useCallback(
    (micro: number): string => {
      if (displayUnit === 'token') {
        return `${formatLargeNum(micro / 2)} tokens`;
      }
      const cny = micro / 1_000_000;
      const usd = cny * USD_PER_CNY;
      if (displayUnit === 'usd') return `$${usd.toFixed(2)} (≈¥${cny.toFixed(2)})`;
      return `¥${cny.toFixed(2)} (≈$${usd.toFixed(2)})`;
    },
    [displayUnit],
  );

  const toQuota = useCallback((inputAmount: number): number => valueToQuota(inputAmount, displayUnit), [displayUnit]);
  const toValue = useCallback((micro: number): number => quotaToValue(micro, displayUnit), [displayUnit]);
  const unitInfo = useMemo(() => UNIT_OPTIONS.find((u) => u.value === displayUnit) || UNIT_OPTIONS[0], [displayUnit]);

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
  };
};

export { USD_PER_CNY, CNY_PER_USD };
