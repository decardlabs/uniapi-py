/**
 * Token Service — encapsulates all token (API key) related API calls.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface Token {
  id: number;
  key: string;
  name: string;
  status: number;
  remain_quota: number;
  unlimited_quota: boolean;
  expired_time: number | string;
  created_time: number;
  models?: string; // comma-separated or array
  subnet?: string;
  used_quota?: number;
}

export type CreateTokenRequest = Omit<Token, 'id' | 'key' | 'status' | 'created_time' | 'used_quota'>;

export type UpdateTokenRequest = Partial<CreateTokenRequest> & { id: number };

export interface PaginatedTokenResponse {
  success: boolean;
  data: Token[];
  total: number;
}

export interface ApiResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ── Endpoints ───────────────────────────────────────────

export async function getTokens(params?: {
  p?: number;
  size?: string;
}): Promise<AxiosResponse<PaginatedTokenResponse>> {
  const query = params
    ? `?p=${params.p || 0}&size=${params.size || ''}`
    : '';
  return api.get(`/api/token/${query}`);
}

export async function getToken(
  id: string | number
): Promise<AxiosResponse<ApiResult<Token>>> {
  return api.get(`/api/token/${id}`);
}

export async function createToken(
  data: CreateTokenRequest
): Promise<AxiosResponse<ApiResult<Token>>> {
  return api.post('/api/token/', data);
}

export async function updateToken(
  data: UpdateTokenRequest
): Promise<AxiosResponse<ApiResult>> {
  return api.put('/api/token/', data);
}

export async function deleteToken(id: number): Promise<AxiosResponse<ApiResult>> {
  return api.delete(`/api/token/${id}`);
}

export async function getAvailableModels(): Promise<AxiosResponse<ApiResult<string[]>>> {
  return api.get('/api/user/available_models');
}
