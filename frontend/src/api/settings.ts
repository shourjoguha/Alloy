import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type {
  UserProfile,
  UserProfileUpdate,
  Movement,
  MovementCreate,
  MovementRule,
  MovementRuleCreate,
} from '@/types';
import type { MovementPattern } from '@/types';
import { useAuthStore } from '@/stores/auth-store';

type MovementsQueryOptions = {
  pattern?: MovementPattern | 'all';
  equipment?: string | 'all';
  search?: string;
  limit?: number;
  offset?: number;
};

interface MovementListResponse {
  movements: Movement[];
  total: number;
  limit?: number | null;
  offset?: number | null;
  filters_applied?: Record<string, unknown> | null;
}

interface MovementFiltersResponse {
  patterns: string[];
  regions: string[];
  equipment: string[];
  primary_disciplines: string[];
  types?: string[] | null;
}

export const settingsKeys = {
  all: ['settings'] as const,
  profile: () => [...settingsKeys.all, 'profile'] as const,
  movements: (params: MovementsQueryOptions) => [
    ...settingsKeys.all,
    'movements',
    params,
  ] as const,
  movementFilters: () => [...settingsKeys.all, 'movement-filters'] as const,
};

async function fetchUserProfile(): Promise<UserProfile> {
  const { data } = await apiClient.get('/settings/user/profile');
  return data;
}

async function updateUserProfile(data: UserProfileUpdate): Promise<UserProfile> {
  const { data: response } = await apiClient.patch(
    '/settings/user/profile',
    data,
  );
  return response;
}

async function fetchMovements(
  options: MovementsQueryOptions = {},
): Promise<MovementListResponse> {
  const { pattern, equipment, search, limit, offset } = options;
  const params: Record<string, unknown> = {};

  if (pattern && pattern !== 'all') {
    params.pattern = pattern;
  }
  if (equipment && equipment !== 'all') {
    params.equipment = equipment;
  }
  if (search) {
    params.search = search;
  }
  if (typeof limit === 'number') {
    params.limit = limit;
  }
  if (typeof offset === 'number') {
    params.offset = offset;
  }

  const { data } = await apiClient.get('/settings/movements', { params });
  return data;
}

async function fetchMovementFilters(): Promise<MovementFiltersResponse> {
  const { data } = await apiClient.get('/settings/movements/filters');
  return data;
}

async function createMovement(payload: MovementCreate): Promise<Movement> {
  const { data } = await apiClient.post('/settings/movements', payload);
  return data;
}

export function useUserProfile() {
  const { isAuthenticated, token, _hasHydrated } = useAuthStore();
  return useQuery({
    queryKey: settingsKeys.profile(),
    queryFn: fetchUserProfile,
    enabled: _hasHydrated && isAuthenticated && !!token, // Only fetch when authenticated with a token and hydration is complete
    staleTime: 5 * 60 * 1000, // 5 minutes - data remains fresh for this duration
    gcTime: 10 * 60 * 1000, // 10 minutes - cache data after it's no longer in use
    refetchOnWindowFocus: false, // Prevent refetching when window regains focus
    refetchOnMount: false, // Prevent refetching when component remounts
    refetchOnReconnect: true, // Still refetch on network reconnect
    retry: 1, // Only retry failed requests once
  });
}

export function useUpdateUserProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateUserProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.profile() });
    },
  });
}

export function useMovements(options: MovementsQueryOptions = { limit: 1000 }) {
  const queryOptions = { limit: 1000, ...options };

  return useQuery({
    queryKey: settingsKeys.movements(queryOptions),
    queryFn: () => fetchMovements(queryOptions),
    staleTime: 5 * 60 * 1000, // 5 minutes - data remains fresh for this duration
    gcTime: 10 * 60 * 1000, // 10 minutes - cache data after it's no longer in use
    refetchOnWindowFocus: false, // Prevent refetching when window regains focus
    refetchOnMount: false, // Prevent refetching when component remounts
    refetchOnReconnect: true, // Still refetch on network reconnect
    retry: 1, // Only retry failed requests once
  });
}

export function useMovementFilters() {
  return useQuery({
    queryKey: settingsKeys.movementFilters(),
    queryFn: fetchMovementFilters,
    staleTime: 10 * 60 * 1000, // 10 minutes - filters change less frequently
    gcTime: 15 * 60 * 1000, // 15 minutes - cache data after it's no longer in use
    refetchOnWindowFocus: false, // Prevent refetching when window regains focus
    refetchOnMount: false, // Prevent refetching when component remounts
    refetchOnReconnect: true, // Still refetch on network reconnect
    retry: 1, // Only retry failed requests once
  });
}

export function useCreateMovement() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createMovement,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: settingsKeys.all });
      queryClient.invalidateQueries({ queryKey: settingsKeys.movementFilters() });
    },
  });
}

async function fetchUserMovementRules(): Promise<MovementRule[]> {
  const { data } = await apiClient.get('/settings/movement-rules');
  return data;
}

async function createUserMovementRuleAPI(data: MovementRuleCreate): Promise<MovementRule> {
  const { data: response } = await apiClient.post('/settings/movement-rules', data);
  return response;
}

async function deleteUserMovementRuleAPI(ruleId: number): Promise<void> {
  await apiClient.delete(`/settings/movement-rules/${ruleId}`);
}

export function getUserMovementRules(): Promise<MovementRule[]> {
  return fetchUserMovementRules();
}

export function getAllMovements(options: MovementsQueryOptions = {}): Promise<MovementListResponse> {
  return fetchMovements(options);
}

export function createUserMovementRule(data: MovementRuleCreate): Promise<MovementRule> {
  return createUserMovementRuleAPI(data);
}

export function deleteUserMovementRule(ruleId: number): Promise<void> {
  return deleteUserMovementRuleAPI(ruleId);
}
