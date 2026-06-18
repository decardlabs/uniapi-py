/**
 * User Service — encapsulates all user-related API calls.
 *
 * Centralizes user management, auth, and self-service endpoints
 * so page components don't need to know URL patterns or response shapes.
 */
import { api } from '@/lib/api';
import type { AxiosResponse } from 'axios';

// ── Types ───────────────────────────────────────────────

export interface UserInfo {
  id: number;
  username: string;
  display_name?: string;
  role: number;
  status: number;
  quota: number;
  group?: string;
  access_token?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password1: string;
  password2: string;
  email?: string;
}

export interface UpdateUserRequest {
  id: number;
  [key: string]: unknown; // eslint-disable-line @typescript-eslint/no-explicit-any
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total: number;
}

export interface ApiResult<T = unknown> {
  success: boolean;
  message?: string;
  data?: T;
}

// ── Auth Endpoints ──────────────────────────────────────

export async function login(
  data: LoginRequest
): Promise<AxiosResponse<ApiResult<UserInfo>>> {
  return api.post('/api/user/login', data);
}

export async function register(
  data: RegisterRequest
): Promise<AxiosResponse<ApiResult<UserInfo>>> {
  return api.post('/api/user/register', data);
}

export async function logout(): Promise<AxiosResponse<ApiResult>> {
  return api.get('/api/user/logout');
}

export async function getSelf(): Promise<AxiosResponse<ApiResult<UserInfo>>> {
  return api.get('/api/user/self');
}

// ── User Management (Admin) ─────────────────────────────

export async function getUsers(params?: {
  p?: number;
  size?: number;
}): Promise<AxiosResponse<PaginatedResponse<UserInfo>>> {
  const query = params ? `?p=${params.p || 0}&size=${params.size || 10}` : '';
  return api.get(`/api/user/${query}`);
}

export async function updateUser(
  id: number,
  data: Partial<UserInfo>
): Promise<AxiosResponse<ApiResult>> {
  return api.put(`/api/user/`, { ...data, id });
}

export async function deleteUser(id: number): Promise<AxiosResponse<ApiResult>> {
  return api.delete(`/api/user/${id}`);
}

export async function manageUser(
  id: number,
  action: 'enable' | 'disable' | 'promote' | 'demote'
): Promise<AxiosResponse<ApiResult>> {
  return api.put(`/api/user/`, { id, action });
}

export async function searchUsers(
  keyword: string,
  size = 10
): Promise<AxiosResponse<PaginatedResponse<UserInfo>>> {
  return api.get(
    `/api/user/search?keyword=${encodeURIComponent(keyword)}&size=${size}`
  );
}
