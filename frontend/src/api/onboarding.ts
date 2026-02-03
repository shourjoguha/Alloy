import apiClient from './client';
import type { Answers, AnswerValue } from '../config/onboarding-flow';

export interface OnboardingStatusResponse {
  completed: boolean;
  version: string | null;
}

export interface OnboardingSubmitResponse {
  message: string;
  completed_at: string;
  version: string;
}

export async function getOnboardingStatus(): Promise<OnboardingStatusResponse> {
  const { data } = await apiClient.get<OnboardingStatusResponse>('/onboarding/status');
  return data;
}

export async function submitOnboarding(answers: Answers): Promise<OnboardingSubmitResponse> {
  const { data } = await apiClient.post<OnboardingSubmitResponse>('/onboarding/submit', answers);
  return data;
}

export async function saveOnboardingProgress(questionId: string, answerValue: AnswerValue): Promise<{ message: string }> {
  const { data } = await apiClient.patch<{ message: string }>('/onboarding/progress', {
    question_id: questionId,
    answer_value: answerValue,
    question_set_version: 'v1',
  });
  return data;
}