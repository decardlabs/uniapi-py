import { api } from '@/lib/api';

export interface Pool {
  id: number;
  name: string;
  total_funded: number;
  total_allocated: number;
  total_consumed: number;
  available: number;
  period_type: string;
  period_key: string;
  status: string;
  created_at: number;
  closed_at?: number;
}

export interface PoolAllocation {
  id: number;
  pool_id: number;
  user_id: number;
  username?: string;
  amount: number;
  consumed: number;
  recalled: number;
  net_allocated: number;
  remaining: number;
  status: string;
  created_at: number;
  updated_at: number;
}

export interface PoolTransaction {
  id: number;
  pool_id: number;
  type: string;
  amount: number;
  user_id?: number;
  allocation_id?: number;
  remark: string;
  created_at: number;
}

export interface ReconcileData {
  pool: Pool & { used_quota: number };
  allocations: PoolAllocation[];
}

export async function getPools(params?: {
  p?: number;
  size?: number;
  status?: string;
  period_type?: string;
}) {
  return api.get('/api/pool/', { params });
}

export async function getPool(id: number) {
  return api.get(`/api/pool/${id}`);
}

export async function createPool(data: {
  name: string;
  total_funded: number;
  period_type: string;
  period_key: string;
}) {
  return api.post('/api/pool/', data);
}

export async function fundPool(id: number, data: { amount: number; remark?: string }) {
  return api.post(`/api/pool/${id}/fund`, data);
}

export async function allocateToUser(id: number, data: { user_id: number; amount: number; remark?: string }) {
  return api.post(`/api/pool/${id}/allocate`, data);
}

export async function recallFromUser(id: number, data: { user_id: number; amount: number; remark?: string }) {
  return api.post(`/api/pool/${id}/recall`, data);
}

export async function recallAllFromUser(id: number, data: { user_id: number }) {
  return api.post(`/api/pool/${id}/recall_all`, data);
}

export async function closePool(id: number) {
  return api.post(`/api/pool/${id}/close`, {});
}

export async function rolloverPool(id: number, data: { new_period_key: string; new_name?: string }) {
  return api.post(`/api/pool/${id}/rollover`, data);
}

export async function getReconciliation(id: number) {
  return api.get(`/api/pool/${id}/reconciliation`);
}

export async function getPoolTransactions(id: number, params?: { p?: number; size?: number }) {
  return api.get(`/api/pool/${id}/transactions`, { params });
}
