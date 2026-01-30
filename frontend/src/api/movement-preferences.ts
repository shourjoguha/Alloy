import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type { MovementRuleType } from '@/types';

export interface MovementPreference {
  id: number;
  user_id: number | null;
  movement_id: number;
  movement_name: string | null;
  rule_type: string;
  substitute_movement_id: number | null;
  substitute_movement_name: string | null;
  cadence: string | null;
  reason: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MovementPreferenceCreate {
  movement_id: number;
  rule_type: MovementRuleType | string;
  rule_operator?: string;
  cadence?: string;
  notes?: string;
}

export interface MovementPreferenceUpdate {
  rule_type?: MovementRuleType | string;
  rule_operator?: string;
  cadence?: string;
  notes?: string;
}

export interface MovementPreferenceListResponse {
  items: MovementPreference[];
  total: number;
}

export interface BatchUpsertRequest {
  preferences: MovementPreferenceCreate[];
}

export interface BatchUpsertResponse {
  created: MovementPreference[];
  skipped: { movement_id: number; reason: string }[];
  errors: unknown[];
  summary: {
    total: number;
    created: number;
    skipped: number;
    failed: number;
  };
}

type MovementPreferencesQueryOptions = {
  rule_type?: string;
  include_favorites_only?: boolean;
};

export const movementPreferencesKeys = {
  all: ['movement-preferences'] as const,
  lists: () => [...movementPreferencesKeys.all, 'list'] as const,
  list: (filters: MovementPreferencesQueryOptions) => [
    ...movementPreferencesKeys.lists(),
    filters,
  ] as const,
  details: () => [...movementPreferencesKeys.all, 'detail'] as const,
  detail: (id: number) => [...movementPreferencesKeys.details(), id] as const,
};

async function fetchMovementPreferences(
  options: MovementPreferencesQueryOptions = {},
): Promise<MovementPreferenceListResponse> {
  const { rule_type, include_favorites_only } = options;
  const params: Record<string, unknown> = {};

  if (rule_type) {
    params.rule_type = rule_type;
  }
  if (include_favorites_only) {
    params.include_favorites_only = true;
  }

  const { data } = await apiClient.get('/movement-preferences', { params });
  return data;
}

async function fetchMovementPreference(id: number): Promise<MovementPreference> {
  const { data } = await apiClient.get(`/movement-preferences/${id}`);
  return data;
}

async function createMovementPreference(
  preference: MovementPreferenceCreate,
): Promise<MovementPreference> {
  const { data } = await apiClient.post('/movement-preferences', preference);
  return data;
}

async function deleteMovementPreference(id: number): Promise<void> {
  await apiClient.delete(`/movement-preferences/${id}`);
}

async function batchUpsertMovementPreferences(
  request: BatchUpsertRequest,
): Promise<BatchUpsertResponse> {
  const { data } = await apiClient.post('/movement-preferences/batch', request);
  return data;
}

export function useUserMovementRules(
  options: MovementPreferencesQueryOptions = {},
) {
  return useQuery({
    queryKey: movementPreferencesKeys.list(options),
    queryFn: () => fetchMovementPreferences(options),
  });
}

export function useFavorites() {
  return useUserMovementRules({ include_favorites_only: true });
}

export function useMovementPreference(id: number) {
  return useQuery({
    queryKey: movementPreferencesKeys.detail(id),
    queryFn: () => fetchMovementPreference(id),
    enabled: !!id,
  });
}

export function useUpsertMovementRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (preference: MovementPreferenceCreate) => {
      return createMovementPreference(preference);
    },
    onMutate: async (newPreference) => {
      await queryClient.cancelQueries({ queryKey: movementPreferencesKeys.all });

      const previousPreferences = queryClient.getQueryData<MovementPreferenceListResponse>(
        movementPreferencesKeys.list({}),
      );

      queryClient.setQueryData<MovementPreferenceListResponse>(
        movementPreferencesKeys.list({}),
        (old) => {
          if (!old) return old;

          const existingIndex = old.items.findIndex(
            (p) =>
              p.movement_id === newPreference.movement_id &&
              p.rule_type === newPreference.rule_type,
          );

          if (existingIndex >= 0) {
            const updated = { ...old };
            updated.items[existingIndex] = {
              ...updated.items[existingIndex],
              rule_type: newPreference.rule_type,
              cadence: newPreference.cadence || updated.items[existingIndex].cadence,
              notes: newPreference.notes || updated.items[existingIndex].notes,
              updated_at: new Date().toISOString(),
            };
            return updated;
          } else {
            return {
              ...old,
              items: [
                ...old.items,
                {
                  id: Date.now(),
                  user_id: null,
                  movement_id: newPreference.movement_id,
                  movement_name: null,
                  rule_type: newPreference.rule_type,
                  substitute_movement_id: null,
                  substitute_movement_name: null,
                  cadence: newPreference.cadence || null,
                  reason: null,
                  notes: newPreference.notes || null,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ],
            };
          }
        },
      );

      return { previousPreferences };
    },
    onError: (err, newPreference, context) => {
      if (context?.previousPreferences) {
        queryClient.setQueryData(
          movementPreferencesKeys.list({}),
          context.previousPreferences,
        );
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: movementPreferencesKeys.all });
    },
  });
}

export function useDeleteMovementRule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteMovementPreference,
    onMutate: async (deletedId) => {
      await queryClient.cancelQueries({ queryKey: movementPreferencesKeys.all });

      const previousPreferences = queryClient.getQueryData<MovementPreferenceListResponse>(
        movementPreferencesKeys.list({}),
      );

      queryClient.setQueryData<MovementPreferenceListResponse>(
        movementPreferencesKeys.list({}),
        (old) => {
          if (!old) return old;

          return {
            ...old,
            items: old.items.filter((p) => p.id !== deletedId),
          };
        },
      );

      return { previousPreferences };
    },
    onError: (err, deletedId, context) => {
      if (context?.previousPreferences) {
        queryClient.setQueryData(
          movementPreferencesKeys.list({}),
          context.previousPreferences,
        );
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: movementPreferencesKeys.all });
    },
  });
}

export function useBatchUpsertMovementRules() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: batchUpsertMovementPreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: movementPreferencesKeys.all });
    },
  });
}

export function usePersistWizardPreferences() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: batchUpsertMovementPreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: movementPreferencesKeys.all });
    },
  });
}
