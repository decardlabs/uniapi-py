/**
 * Recharge Service — encapsulates top-up / recharge request API calls.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface TopUpRequest {
  id: number;
  user_id: number;
  amount?: number; // eslint-disable-line @typescript-eslint/no-explicit-any
  quota: number;
  status: number;
  remark?: string; // eslint-disable-line @typescript-eslint/no-explicit-any
  admin_remark?: string; // eslint-disable-line @typescript-eslint/no-explicit-any
  created_at: string;
  created_time?: number; // eslint-disable-line @typescript-eslint/no-explicit-any
}

export interface CreateRechargeRequest {
  amount: number;
  remark?: string;
}

export interface PaginatedRechargeResponse {
  success: boolean;
  data: TopUpRequest[];
  total: number;
}

export interface ApiResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ── Endpoints ───────────────────────────────────────────

export async function getRechargeRequests(params?: {
  p?: number;
  size?: number;
}): Promise<AxiosResponse<PaginatedRechargeResponse>> {
  const query = params ? `?p=${params.p || 0}&size=${params.size || 10}` : '';
  return api.get(`/api/topup/${query}`);
}

export async function createRechargeRequest(
  data: CreateRechargeRequest
): Promise<AxiosResponse<ApiResult<TopUpRequest>>> {
  return api.post('/api/topup/', data);
}

export async function reviewRecharge(
  id: number,
  action: 'approve' | 'reject',
  adminRemark = ''
): Promise<AxiosResponse<ApiResult>> {
  return api.put('/api/topup/', { id, action, admin_remark: adminRemark });
}
