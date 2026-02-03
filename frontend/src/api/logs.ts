import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';
import type {
  ActivityDefinition,
  ActivityInstanceCreate,
  CustomWorkoutCreate,
} from '@/types';

export const logsKeys = {
  all: ['logs'] as const,
  activities: () => [...logsKeys.all, 'activities'] as const,
  definitions: () => [...logsKeys.activities(), 'definitions'] as const,
  soreness: () => [...logsKeys.all, 'soreness'] as const,
};

// Activity Definitions
async function fetchActivityDefinitions(): Promise<ActivityDefinition[]> {
  const { data } = await apiClient.get('/activities/definitions');
  return data;
}

export function useActivityDefinitions() {
  return useQuery({
    queryKey: logsKeys.definitions(),
    queryFn: fetchActivityDefinitions,
    staleTime: 5 * 60 * 1000, // 5 minutes - data remains fresh for this duration
    gcTime: 10 * 60 * 1000, // 10 minutes - cache data after it's no longer in use
    refetchOnWindowFocus: false, // Prevent refetching when window regains focus
    refetchOnMount: false, // Prevent refetching when component remounts
    refetchOnReconnect: true, // Still refetch on network reconnect
    retry: 1, // Only retry failed requests once
  });
}

// Log Activity
async function logActivity(payload: ActivityInstanceCreate): Promise<{ id: number; status: string }> {
  const { data } = await apiClient.post('/activities/log', payload);
  return data;
}

export function useLogActivity() {
  return useMutation({
    mutationFn: logActivity,
    onSuccess: () => {
      // Invalidate relevant queries if needed (e.g. activity history)
    },
  });
}

// Log Custom Workout
async function logCustomWorkout(payload: CustomWorkoutCreate): Promise<{ id: number }> {
  const { data } = await apiClient.post('/workouts/custom', payload);
  return data;
}

export function useLogCustomWorkout() {
  return useMutation({
    mutationFn: logCustomWorkout,
    onSuccess: () => {
      // Invalidate workout history/dashboard
    },
  });
}

interface SorenessLogCreate {
  log_date?: string;
  body_part: string;
  soreness_1_5: number;
  notes?: string;
}

interface SorenessLogResponse {
  id: number;
  user_id?: number;
  log_date?: string;
  body_part: string;
  soreness_1_5: number;
  inferred_cause_session_id?: number;
  inferred_cause_description?: string;
  notes?: string;
  created_at?: string;
}

async function logSoreness(payload: SorenessLogCreate): Promise<SorenessLogResponse> {
  const { data } = await apiClient.post('/logs/soreness', payload);
  return data;
}

export function useLogSoreness() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logSoreness,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: logsKeys.soreness() });
    },
  });
}
