/**
 * Recharge Service — encapsulates top-up / recharge request API calls.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface TopUpRequest {
  id: number;
  user_id: number;
  amount: number;
  quota: number;
  status: number;
  remark: string;
  admin_remark: string;
  created_time: number;
  reviewed_time: number;
  reviewer_id: number;
  username?: string;
  user?: { id: number; username: string };
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

// ── Admin Queries ───────────────────────────────────────

export async function getRechargeRequests(params?: {
  p?: number;
  size?: number;
}): Promise<AxiosResponse<PaginatedRechargeResponse>> {
  const p = params?.p ?? 0;
  const size = params?.size ?? 10;
  return api.get(`/api/recharge/?p=${p}&size=${size}`);
}

export async function createRechargeRequest(
  data: CreateRechargeRequest
): Promise<AxiosResponse<ApiResult<TopUpRequest>>> {
  return api.post('/api/recharge/', data);
}

export async function getSelfRechargeRequests(params?: {
  p?: number;
  size?: number;
}): Promise<AxiosResponse<PaginatedRechargeResponse>> {
  const p = params?.p ?? 0;
  const size = params?.size ?? 10;
  return api.get(`/api/recharge/self?p=${p}&size=${size}`);
}

// ── Admin Actions ───────────────────────────────────────

export async function approveRecharge(
  rechargeId: number
): Promise<AxiosResponse<ApiResult>> {
  return api.post(`/api/recharge/${rechargeId}/approve`, {});
}

export async function rejectRecharge(
  rechargeId: number,
  adminRemark: string
): Promise<AxiosResponse<ApiResult>> {
  return api.post(`/api/recharge/${rechargeId}/reject`, { admin_remark: adminRemark });
}

export async function adminTopup(
  data: { user_id: number; quota: number; remark?: string; pool_id?: number }
): Promise<AxiosResponse<ApiResult>> {
  return api.post('/api/topup/', data);
}
