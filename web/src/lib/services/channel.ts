/**
 * Channel Service — encapsulates all channel (model provider) API calls.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface Channel {
  id: number;
  type: string;
  key: string;
  status: number;
  name: string;
  base_url: string;
  models: string;
  group: string;
  model_mapping: string | Record<string, string>;
  priority: number;
  weight: number;
  other_info: string;
  // Pricing fields
  input_price?: number; // eslint-disable-line @typescript-eslint/no-explicit-any — backend optional
  output_price?: number; // eslint-disable-line @typescript-eslint/no-explicit-any
  cache_price?: number; // eslint-disable-line @typescript-eslint/no-explicit-any
}

export interface PaginatedChannelResponse {
  success: boolean;
  data: Channel[];
  total: number;
}

export interface ApiResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ── Endpoints ───────────────────────────────────────────

export async function getChannels(params?: {
  p?: number;
  size?: string;
  sort?: string;
  order?: 'asc' | 'desc';
}): Promise<AxiosResponse<PaginatedChannelResponse>> {
  const qs = new URLSearchParams();
  if (params) {
    if (params.p !== undefined) qs.set('p', String(params.p));
    if (params.size) qs.set('size', params.size);
    if (params.sort) { qs.set('sort', params.sort); qs.set('order', params.order || 'desc'); }
  }
  const query = qs.toString();
  return api.get(`/api/channel/${query ? '?' + query : ''}`);
}

export async function getChannel(
  id: number
): Promise<AxiosResponse<ApiResult<Channel>>> {
  return api.get(`/api/channel/${id}`);
}

export async function createChannel(
  data: Partial<Channel>
): Promise<AxiosResponse<ApiResult<Channel>>> {
  return api.post('/api/channel/', data);
}

export async function updateChannel(
  data: Partial<Channel> & { id: number }
): Promise<AxiosResponse<ApiResult<Channel>>> {
  return api.put('/api/channel/', data);
}

export async function deleteChannel(
  id: number
): Promise<AxiosResponse<ApiResult>> {
  return api.delete(`/api/channel/${id}`);
}

export async function testChannel(
  id: number
): Promise<AxiosResponse<ApiResult>> {
  return api.get(`/api/channel/test/${id}`);
}

export async function manageChannel(
  id: number,
  action: 'enable' | 'disable' | 'check'
): Promise<AxiosResponse<ApiResult>> {
  return api.put('/api/channel/', { id, action });
}

export async function searchChannels(
  keyword: string,
  size = 10
): Promise<AxiosResponse<PaginatedChannelResponse>> {
  return api.get(
    `/api/channel/search?keyword=${encodeURIComponent(keyword)}&size=${size}`
  );
}
