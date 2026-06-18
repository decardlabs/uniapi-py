/**
 * Settings Service — encapsulates system option / configuration API calls.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface OptionItem {
  key: string;
  value: string;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any — dynamic key-value from backend
type OptionValue = string | number | boolean | any;

export interface ApiResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ── Endpoints ───────────────────────────────────────────

export async function getOptions(): Promise<AxiosResponse<ApiResult<OptionItem[]>>> {
  return api.get('/api/option/');
}

export async function updateOption(
  key: string,
  value: OptionValue
): Promise<AxiosResponse<ApiResult>> {
  return api.put('/api/option/', { key, value: String(value) });
}

export async function getOptionByKey(
  key: string
): Promise<AxiosResponse<ApiResult<string>>> {
  return api.get(`/api/option/?key=${encodeURIComponent(key)}`);
}
