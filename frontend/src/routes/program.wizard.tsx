import { useState, useEffect } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import type { AxiosError } from 'axios';
import { useProgramWizardStore } from '@/stores/program-wizard-store';
import { useCreateProgram } from '@/api/programs';
import { useUserMovementRules } from '@/api/movement-preferences';
import { useUserProfile } from '@/api/settings';
import { WizardContainer } from '@/components/wizard/WizardContainer';
import {
  GoalsStep,
  SplitStep,
  ActivitiesAndMovementsStep,
  CoachStep,
} from '@/components/wizard';
import {
  PersonaTone,
  PersonaAggression,
  type ProgramCreate
} from '@/types';
import { useUIStore } from '@/stores/ui-store';

const PUSH_INTENSITY_TO_AGGRESSION: Record<number, PersonaAggression> = {
  1: PersonaAggression.CONSERVATIVE,
  2: PersonaAggression.MODERATE_CONSERVATIVE,
  3: PersonaAggression.BALANCED,
  4: PersonaAggression.MODERATE_AGGRESSIVE,
  5: PersonaAggression.AGGRESSIVE,
};

export const Route = createFileRoute('/program/wizard')({
  component: ProgramWizardPage,
});

const STEP_LABELS = [
  'Set Your Goals',
  'Choose Your Schedule',
  'Preferences',
  'Meet Your Coach',
];

// Map communication style to PersonaTone
const TONE_MAP: Record<string, PersonaTone> = {
  encouraging: PersonaTone.SUPPORTIVE,
  drill_sergeant: PersonaTone.DRILL_SERGEANT,
  scientific: PersonaTone.ANALYTICAL,
  casual: PersonaTone.MOTIVATIONAL,
};

function ProgramWizardPage() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const createProgram = useCreateProgram();
  const { addToast } = useUIStore();
  const { data: userPreferences } = useUserMovementRules();
  const { data: userProfile } = useUserProfile();
  
  const {
    goals,
    isGoalsValid,
    daysPerWeek,
    maxDuration,
    movementRules,
    enjoyableActivities,
    communicationStyle,
    pushIntensity,
    durationWeeks,
    reset,
    initializeFromUserPreferences,
    initializeFromOnboardingData,
  } = useProgramWizardStore();

  // Initialize wizard with user preferences and onboarding data on mount
  useEffect(() => {
    reset();
    if (userPreferences && userPreferences.items) {
      initializeFromUserPreferences(userPreferences.items);
    }
    if (userProfile) {
      const onboardingData = {
        gym_comfort_level: userProfile.gym_comfort_level,
        goal_category: userProfile.long_term_goal_category,
        goal_description: userProfile.long_term_goal_description,
      };
      initializeFromOnboardingData(onboardingData);
    }
  }, [userPreferences, userProfile, reset, initializeFromUserPreferences, initializeFromOnboardingData]);

  const canProceed = (): boolean => {
    switch (currentStep) {
      case 0: // Goals
        return isGoalsValid();
      case 1: // Split
        return true;
      case 2: // ActivitiesAndMovements (optional)
        return true;
      case 3: // Coach
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < STEP_LABELS.length - 1) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleSubmit = async () => {
    // Validate required fields before submitting
    if (!isGoalsValid()) {
      addToast({
        type: 'error',
        message: 'Please complete your goals (1-3 goals totaling $10)',
      });
      setCurrentStep(0);
      return;
    }

    if (!durationWeeks || durationWeeks < 8 || durationWeeks > 12) {
      addToast({
        type: 'error',
        message: 'Please select a program duration (8-12 weeks)',
      });
      setCurrentStep(3);
      return;
    }

    if (!daysPerWeek || daysPerWeek < 2 || daysPerWeek > 7) {
      addToast({
        type: 'error',
        message: 'Please select training frequency (2-7 days per week)',
      });
      setCurrentStep(1);
      return;
    }

    // Build the program create payload
    const payload: ProgramCreate = {
      goals: goals,
      duration_weeks: durationWeeks,
      days_per_week: daysPerWeek,
      split_template: useProgramWizardStore.getState().splitPreference || undefined,
      max_session_duration: maxDuration,
      persona_tone: TONE_MAP[communicationStyle] || PersonaTone.SUPPORTIVE,
      persona_aggression: PUSH_INTENSITY_TO_AGGRESSION[pushIntensity] || PersonaAggression.BALANCED,
      movement_rules: movementRules.length > 0 ? movementRules : undefined,
      enjoyable_activities: enjoyableActivities.length > 0 ? enjoyableActivities : undefined,
    };

    console.log('Submitting program creation payload:', JSON.stringify(payload, null, 2));

    try {
      const program = await createProgram.mutateAsync(payload);
      reset();
      // Navigate to the new program detail page
      navigate({ 
        to: '/program/$programId', 
        params: { programId: String(program.id) } 
      });
    } catch (error) {
      console.error('Failed to create program:', error);
      const err = error as AxiosError<unknown>;

      if (!err.response) {
        addToast({
          type: 'error',
          message: 'Network error while creating program. Please check that the server is running.',
        });
        return;
      }

      const data = err.response?.data;
      
      if (Array.isArray(data)) {
        const messages = data.map((d: { loc?: string[]; msg?: string }) => {
          const field = d.loc?.slice(1)?.join('.') || 'unknown field';
          return `${field}: ${d.msg}`;
        });
        addToast({
          type: 'error',
          message: `Validation failed: ${messages.join(' | ')}`,
        });
      } else if (typeof data === 'string') {
        addToast({ type: 'error', message: data });
      } else if (data && typeof data === 'object') {
        const detail = (data as { detail?: unknown }).detail;
        if (typeof detail === 'string') {
          addToast({ type: 'error', message: detail });
        } else if (Array.isArray(detail)) {
          const messages = detail.map((d: { loc?: string[]; msg?: string }) => {
            const field = d.loc?.slice(1)?.join('.') || 'unknown field';
            return `${field}: ${d.msg}`;
          });
          addToast({
            type: 'error',
            message: `Validation failed: ${messages.join(' | ')}`,
          });
        } else {
          addToast({
            type: 'error',
            message: `Error: ${JSON.stringify(data)}`,
          });
        }
      } else {
        addToast({
          type: 'error',
          message: 'Failed to create program. Please check your selections and try again.',
        });
      }
    }
  };

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return <GoalsStep />;
      case 1:
        return <SplitStep />;
      case 2:
        return <ActivitiesAndMovementsStep />;
      case 3:
        return <CoachStep />;
      default:
        return null;
    }
  };

  return (
    <WizardContainer
      currentStep={currentStep}
      totalSteps={STEP_LABELS.length}
      stepLabels={STEP_LABELS}
      onNext={handleNext}
      onBack={handleBack}
      onSubmit={handleSubmit}
      canProceed={canProceed()}
      isSubmitting={createProgram.isPending}
    >
      {renderStep()}
    </WizardContainer>
  );
}
