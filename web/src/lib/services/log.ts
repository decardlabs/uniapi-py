/**
 * Log Service — encapsulates log / usage record API calls.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface LogEntry {
  id: number;
  user_id: number;
  created_at: number;
  type: number;
  content: string;
  token_name?: string;
  model_name?: string;
  quota: number;
  channel_id?: number; // eslint-disable-line @typescript-eslint/no-explicit-any
  is_stream?: boolean;
}

export interface LogSearchParams {
  p?: number;
  size?: string | number;
  token_name?: string;
  model_name?: string;
  start_timestamp?: string;
  end_timestamp?: string;
  type?: string;
  username?: string;
  keyword?: string;
  sort?: string;
  order?: 'asc' | 'desc';
}

export interface PaginatedLogResponse {
  success: boolean;
  data: LogEntry[];
  total: number;
}

export interface ApiResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ── Endpoints ───────────────────────────────────────────

export async function getLogs(
  params: LogSearchParams = {}
): Promise<AxiosResponse<PaginatedLogResponse>> {
  const qs = new URLSearchParams();
  if (params.p !== undefined) qs.set('p', String(params.p));
  if (params.size) qs.set('size', String(params.size));
  if (params.token_name) qs.set('token_name', params.token_name);
  if (params.model_name) qs.set('model_name', params.model_name);
  if (params.start_timestamp) qs.set('start_timestamp', params.start_timestamp);
  if (params.end_timestamp) qs.set('end_timestamp', params.end_timestamp);
  if (params.type) qs.set('type', params.type);
  if (params.username) qs.set('username', params.username);
  if (params.keyword) qs.set('keyword', params.keyword);
  if (params.sort) { qs.set('sort', params.sort); qs.set('order', params.order || 'desc'); }

  const query = qs.toString();
  return api.get(`/api/log/${query ? '?' + query : ''}`);
}

export async function searchLogs(
  keyword: string,
  size = 10
): Promise<AxiosResponse<PaginatedLogResponse>> {
  return api.get(
    `/api/log/search?keyword=${encodeURIComponent(keyword)}&size=${size}`
  );
}

export async function deleteLogs(
  targetTimestamp: number
): Promise<AxiosResponse<ApiResult>> {
  return api.delete(`/api/log/?target_timestamp=${targetTimestamp}`);
}
