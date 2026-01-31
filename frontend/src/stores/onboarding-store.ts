import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Answers, AnswerValue } from '../config/onboarding-flow';

interface OnboardingState {
  answers: Answers;
  currentQuestionId: string | null;
  isSubmitting: boolean;
  error: string | null;
  
  setAnswer: (questionId: string, value: AnswerValue) => void;
  setCurrentQuestionId: (questionId: string | null) => void;
  setIsSubmitting: (isSubmitting: boolean) => void;
  setError: (error: string | null) => void;
  reset: () => void;
  canProceed: (questionId: string) => boolean;
  getRequiredAnswers: () => Answers;
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
  answers: {},
  currentQuestionId: null,
  isSubmitting: false,
  error: null,

  setAnswer: (questionId, value) => {
    set(state => ({
      answers: {
        ...state.answers,
        [questionId]: value,
      },
    }));
  },

  setCurrentQuestionId: (questionId) => {
    set({ currentQuestionId: questionId });
  },

  setIsSubmitting: (isSubmitting) => {
    set({ isSubmitting });
  },

  setError: (error) => {
    set({ error });
  },

  reset: () => {
    set({
      answers: {},
      currentQuestionId: null,
      isSubmitting: false,
      error: null,
    });
  },

  canProceed: (questionId) => {
    const { answers } = get();
    const value = answers[questionId];

    if (questionId === 'name') {
      return typeof value === 'string' && value.trim().length >= 2;
    }
    if (questionId === 'date_of_birth') {
      return value !== null && value !== undefined && value !== '';
    }
    if (questionId === 'sex') {
      return value !== null && value !== undefined && value !== '';
    }
    if (questionId === 'gym_comfort_level') {
      return value !== null && value !== undefined;
    }
    if (questionId === 'equipment_familiarity') {
      return value !== null && typeof value === 'object' && Object.keys(value).length > 0;
    }
    if (questionId === 'goal_category') {
      return value !== null && value !== undefined && value !== '';
    }
    // For multi-select questions (like athletic_activities), always allow proceeding
    // since they're optional (not required)
    if (questionId === 'athletic_activities') {
      return true;
    }

    return true;
  },

  getRequiredAnswers: () => {
    const { answers } = get();
    const required: Answers = {};

    const requiredFields = ['date_of_birth', 'sex', 'gym_comfort_level', 'equipment_familiarity', 'goal_category'];

    for (const field of requiredFields) {
      if (answers[field] !== undefined && answers[field] !== null) {
        required[field] = answers[field];
      }
    }

    return required;
  },
    }),
    {
      name: 'alloy-onboarding-storage',
      partialize: (state) => ({
        answers: state.answers,
        currentQuestionId: state.currentQuestionId,
      }),
    }
  )
);