import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type { Program, ProgramCreate, ProgramWithMicrocycle, ProgramUpdate } from '@/types';
import { useAuthStore } from '@/stores/auth-store';

// Query keys
export const programKeys = {
  all: ['programs'] as const,
  lists: () => [...programKeys.all, 'list'] as const,
  list: (filters: { active_only?: boolean }) => [...programKeys.lists(), filters] as const,
  details: () => [...programKeys.all, 'detail'] as const,
  detail: (id: number) => [...programKeys.details(), id] as const,
};

// API functions
async function fetchPrograms(activeOnly = false): Promise<Program[]> {
  const params = activeOnly ? { active_only: true } : {};
  const { data } = await apiClient.get('/programs', { params });
  return data;
}

async function fetchProgram(id: number): Promise<ProgramWithMicrocycle> {
  const { data } = await apiClient.get(`/programs/${id}`);
  return data;
}

async function createProgram(program: ProgramCreate): Promise<Program> {
  const { data } = await apiClient.post('/programs', program);
  return data;
}

async function deleteProgram(id: number): Promise<void> {
  await apiClient.delete(`/programs/${id}`);
}

async function updateProgram(params: { id: number; data: ProgramUpdate }): Promise<Program> {
  const { id, data } = params;
  const { data: response } = await apiClient.patch(`/programs/${id}`, data);
  return response;
}

async function activateProgram(id: number): Promise<Program> {
  const { data } = await apiClient.post(`/programs/${id}/activate`);
  return data;
}

// React Query hooks
export function usePrograms(activeOnly = false) {
  const { isAuthenticated, token, _hasHydrated } = useAuthStore();
  return useQuery({
    queryKey: programKeys.list({ active_only: activeOnly }),
    queryFn: () => fetchPrograms(activeOnly),
    enabled: _hasHydrated && isAuthenticated && !!token, // Only fetch when authenticated with a token and hydration is complete
    staleTime: 5 * 60 * 1000, // 5 minutes - data remains fresh for this duration
    gcTime: 10 * 60 * 1000, // 10 minutes - cache data after it's no longer in use
    refetchOnWindowFocus: false, // Prevent refetching when window regains focus
    refetchOnMount: false, // Prevent refetching when component remounts
    refetchOnReconnect: true, // Still refetch on network reconnect
    retry: 1, // Only retry failed requests once
  });
}

export function useProgram(id: number) {
  return useQuery({
    queryKey: programKeys.detail(id),
    queryFn: () => fetchProgram(id),
    enabled: Number.isFinite(id),
    staleTime: 5 * 60 * 1000, // 5 minutes - data remains fresh for this duration
    gcTime: 10 * 60 * 1000, // 10 minutes - cache data after it's no longer in use
    refetchOnWindowFocus: false, // Prevent refetching when window regains focus
    refetchOnMount: false, // Prevent refetching when component remounts
    refetchOnReconnect: true, // Still refetch on network reconnect
    retry: 1, // Only retry failed requests once
  });
}

export function useCreateProgram() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: createProgram,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: programKeys.all });
    },
  });
}

export function useDeleteProgram() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: deleteProgram,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: programKeys.all });
    },
  });
}

export function useActivateProgram() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: activateProgram,
    onMutate: async (activatedProgramId) => {
      await queryClient.cancelQueries({ queryKey: programKeys.list({ active_only: false }) });
      
      const previousPrograms = queryClient.getQueryData<Program[]>(programKeys.list({ active_only: false }));
      
      queryClient.setQueryData(programKeys.list({ active_only: false }), (old: Program[] | undefined) => {
        if (!old) return old;
        return old
          .map((p) => 
            p.id === activatedProgramId 
              ? { ...p, is_active: true } 
              : { ...p, is_active: false }
          )
          .sort((a, b) => {
            if (a.is_active && !b.is_active) return -1;
            if (!a.is_active && b.is_active) return 1;
            return (b.created_at ? new Date(b.created_at).getTime() : 0) - 
                   (a.created_at ? new Date(a.created_at).getTime() : 0);
          });
      });
      
      return { previousPrograms };
    },
    onError: (err, activatedProgramId, context) => {
      if (context?.previousPrograms) {
        queryClient.setQueryData(programKeys.list({ active_only: false }), context.previousPrograms);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: programKeys.list({ active_only: false }) });
    },
  });
}

export function useUpdateProgram() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateProgram,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: programKeys.all });
    },
  });
}
