import { apiClient } from './client';

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user_id: number;
};

export type UserResponse = {
  id: number;
  email: string;
  name?: string | null;
  is_active: boolean;
  has_completed_onboarding: boolean;
};

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', { email, password });
  return data;
}

export async function register(email: string, password: string, name?: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/register', { email, password, name });
  return data;
}

export async function verifyToken(token: string): Promise<UserResponse> {
  const { data } = await apiClient.get<UserResponse>('/auth/verify-token', { params: { token } });
  return data;
}
