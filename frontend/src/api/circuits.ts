import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type { CircuitTemplate, CircuitTemplateAdminDetail, CircuitType } from '@/types';

export const circuitKeys = {
  all: ['circuits'] as const,
  lists: () => [...circuitKeys.all, 'list'] as const,
  list: (filters: { circuit_type?: CircuitType | 'all' }) => [...circuitKeys.lists(), filters] as const,
  adminDetail: (id: number) => [...circuitKeys.all, 'admin', id] as const,
};

async function fetchCircuits(circuitType?: CircuitType | 'all'): Promise<CircuitTemplate[]> {
  const params =
    circuitType && circuitType !== 'all'
      ? { circuit_type: circuitType }
      : {};

  const { data } = await apiClient.get('/circuits', { params });
  return data;
}

export function useCircuits(circuitType?: CircuitType | 'all') {
  return useQuery({
    queryKey: circuitKeys.list({ circuit_type: circuitType }),
    queryFn: () => fetchCircuits(circuitType),
  });
}

async function fetchCircuitAdmin(circuitId: number): Promise<CircuitTemplateAdminDetail> {
  const adminToken = import.meta.env.VITE_ADMIN_API_TOKEN;
  const headers = adminToken ? { 'X-Admin-Token': adminToken } : {};
  const { data } = await apiClient.get(`/circuits/admin/${circuitId}`, { headers });
  return data;
}

export function useCircuitAdmin(circuitId: number) {
  return useQuery({
    queryKey: circuitKeys.adminDetail(circuitId),
    queryFn: () => fetchCircuitAdmin(circuitId),
    staleTime: 5 * 60 * 1000, // 5 minutes - data remains fresh for this duration
    gcTime: 10 * 60 * 1000, // 10 minutes - cache data after it's no longer in use
    refetchOnWindowFocus: false, // Prevent refetching when window regains focus
    refetchOnMount: false, // Prevent refetching when component remounts
    refetchOnReconnect: true, // Still refetch on network reconnect
    retry: 1, // Only retry failed requests once
  });
}

interface UpdateCircuitPayload {
  exercises_json: Record<string, unknown>[];
}

async function updateCircuitAdmin(circuitId: number, payload: UpdateCircuitPayload): Promise<CircuitTemplate> {
  const adminToken = import.meta.env.VITE_ADMIN_API_TOKEN;
  const headers = adminToken ? { 'X-Admin-Token': adminToken } : {};
  const { data } = await apiClient.put(`/circuits/admin/${circuitId}`, payload, { headers });
  return data;
}

export function useUpdateCircuitAdmin(circuitId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateCircuitPayload) => updateCircuitAdmin(circuitId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: circuitKeys.all });
      queryClient.invalidateQueries({ queryKey: circuitKeys.adminDetail(circuitId) });
    },
  });
}
