import { useOnboardingStore } from '@/stores/onboarding-store';
import { QuestionRenderer } from './QuestionRenderer';
import {
  ONBOARDING_FLOW,
  getVisibleQuestions,
  getPreviousQuestionId,
  getNextQuestionId,
  getVisibleQuestionCount,
  getCurrentQuestionIndex,
  isFirstQuestion,
  isLastQuestion,
} from '@/config/onboarding-flow';
import { submitOnboarding } from '@/api/onboarding';
import { useNavigate } from '@tanstack/react-router';
import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';
import { useUIStore } from '@/stores/ui-store';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ONBOARDING_FEATURES } from '@/config/features';

export function OnboardingContainer() {
  const navigate = useNavigate();
  const { addToast } = useUIStore();
  const { setHasCompletedOnboarding, hasCompletedOnboarding } = useAuthStore();

  const {
    currentQuestionId,
    setCurrentQuestionId,
    answers,
    reset,
    isSubmitting,
    setIsSubmitting,
    setError,
    error,
  } = useOnboardingStore();

  const [isInitialized, setIsInitialized] = useState(false);
  const [showErrorView, setShowErrorView] = useState(false);

  useEffect(() => {
    // Check if onboarding is enabled
    if (!ONBOARDING_FEATURES.enabled) {
      navigate({ to: '/dashboard' });
      return;
    }

    // Check if completion is required for new users
    // If required and user has already completed onboarding, redirect to dashboard
    if (ONBOARDING_FEATURES.requiredForNewUsers && hasCompletedOnboarding) {
      navigate({ to: '/dashboard' });
      return;
    }

    const firstVisibleQuestion = ONBOARDING_FLOW[0]?.questionId;
    if (firstVisibleQuestion && !currentQuestionId) {
      setCurrentQuestionId(firstVisibleQuestion);
    }
    setIsInitialized(true);
  }, [navigate, currentQuestionId, setCurrentQuestionId, hasCompletedOnboarding]);

  const visibleQuestions = getVisibleQuestions(answers);
  const totalQuestions = getVisibleQuestionCount(answers);

  const handleNext = () => {
    if (!currentQuestionId) return;
    
    const nextQuestionId = getNextQuestionId(currentQuestionId, answers);
    
    if (nextQuestionId) {
      setCurrentQuestionId(nextQuestionId);
    } else {
      handleSubmit();
    }
  };

  const handlePrevious = () => {
    if (!currentQuestionId) return;
    
    const prevQuestionId = getPreviousQuestionId(currentQuestionId, answers);
    
    if (prevQuestionId) {
      setCurrentQuestionId(prevQuestionId);
    }
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    setShowErrorView(false);

    try {
      const response = await submitOnboarding(answers);

      addToast({
        type: 'success',
        message: response.message,
      });

      setHasCompletedOnboarding(true);

      navigate({ to: '/dashboard' });

      // Reset answers after navigation to prevent UI flicker and state loss
      reset();
    } catch (error: any) {
      console.error('Onboarding submission error:', error);
      const errorMessage = error.response?.data?.detail || 'Failed to submit onboarding. Please try again.';

      addToast({
        type: 'error',
        message: errorMessage,
      });

      setError(errorMessage);
      setShowErrorView(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRetry = () => {
    setError(null);
    setShowErrorView(false);
    handleSubmit();
  };

  const handleExit = () => {
    // Check if skip is allowed
    if (!ONBOARDING_FEATURES.allowSkip) {
      addToast({
        type: 'error',
        message: 'Completing onboarding is required to continue.',
      });
      return;
    }

    // Check if completion is enforced for new users
    if (ONBOARDING_FEATURES.requiredForNewUsers && !hasCompletedOnboarding) {
      addToast({
        type: 'error',
        message: 'Please complete onboarding to continue.',
      });
      return;
    }

    navigate({ to: '/dashboard' });
  };

  if (!isInitialized || !currentQuestionId) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  const currentIndex = getCurrentQuestionIndex(currentQuestionId, answers);
  const isLastQuestionVal = isLastQuestion(currentQuestionId, answers);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <div className="flex-1 flex flex-col max-w-2xl mx-auto w-full p-4 md:p-8">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">Get started</h1>
            <p className="text-xs text-foreground-muted/70 mt-1">
              A few quick questions to personalize your experience
            </p>
          </div>
          {ONBOARDING_FEATURES.allowSkip && (
            <button
              onClick={handleExit}
              className="text-xs text-foreground-muted/70 hover:text-foreground"
            >
              Skip
            </button>
          )}
        </div>

        {showErrorView && error ? (
          <Card className="mb-6 p-4 border-error/20 bg-error/5">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0 mt-0.5">
                <AlertCircle className="h-4 w-4 text-error" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-error mb-1.5">
                  Submission Failed
                </h3>
                <p className="text-foreground text-xs mb-3">
                  {error}
                </p>
                <div className="flex gap-2">
                  <Button
                    onClick={handleRetry}
                    disabled={isSubmitting}
                    className="flex-1 h-9 text-xs"
                  >
                    {isSubmitting ? (
                      <>
                        <RefreshCw className="mr-2 h-3 w-3 animate-spin" />
                        Retrying...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="mr-2 h-3 w-3" />
                        Retry
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={() => setShowErrorView(false)}
                    variant="outline"
                    className="flex-1 h-9 text-xs"
                  >
                    Review
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ) : (
          <div className="flex-1">
            <QuestionRenderer
              questionId={currentQuestionId}
              onNext={handleNext}
              onPrevious={handlePrevious}
              isLastQuestion={isLastQuestionVal}
              isFirstQuestion={isFirstQuestion(currentQuestionId, answers)}
              currentQuestionIndex={currentIndex}
              totalQuestions={totalQuestions}
              isSubmitting={isSubmitting}
            />
          </div>
        )}
      </div>
    </div>
  );
}
