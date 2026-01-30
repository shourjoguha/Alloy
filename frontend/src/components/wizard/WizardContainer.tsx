import { ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { ArrowLeft, ArrowRight, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WizardContainerProps {
  currentStep: number;
  totalSteps: number;
  stepLabels: string[];
  onNext: () => void;
  onBack: () => void;
  onSubmit: () => void;
  canProceed: boolean;
  isSubmitting?: boolean;
  children: ReactNode;
}

export function WizardContainer({
  currentStep,
  totalSteps,
  stepLabels,
  onNext,
  onBack,
  onSubmit,
  canProceed,
  isSubmitting = false,
  children,
}: WizardContainerProps) {
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;
  const progress = ((currentStep + 1) / totalSteps) * 100;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-background-card/95 backdrop-blur border-b border-border">
        <div className="container-app py-3">
          <div className="flex items-center justify-between mb-3">
            <Link to="/program/new" className="text-foreground-muted hover:text-foreground">
              <ArrowLeft className="h-5 w-5" />
            </Link>
            <h1 className="text-sm font-medium">Build with Jerome</h1>
            <span className="text-sm text-foreground-muted">
              {currentStep + 1}/{totalSteps}
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-1 bg-background-input rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Step indicator */}
          <p className="text-xs text-foreground-muted text-center mt-2">
            {stepLabels[currentStep]}
          </p>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 container-app py-6 overflow-y-auto">
        {children}
      </main>

      {/* Footer navigation */}
      <footer className="sticky bottom-0 bg-background-card/95 backdrop-blur border-t border-border">
        <div className="container-app py-4">
          <div className="flex gap-3">
            {!isFirstStep && (
              <Button
                variant="secondary"
                onClick={onBack}
                className="flex-1"
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            )}

            {isLastStep ? (
              <Button
                variant="cta"
                onClick={onSubmit}
                disabled={!canProceed || isSubmitting}
                isLoading={isSubmitting}
                className="flex-1"
              >
                <Check className="h-4 w-4 mr-2" />
                Create Program
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={onNext}
                disabled={!canProceed}
                className={cn("flex-1", isFirstStep && "w-full")}
              >
                Next
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            )}
          </div>
          
          {/* Skip option for optional steps */}
          {!isLastStep && !isFirstStep && currentStep >= 2 && (
            <button
              onClick={onNext}
              className="w-full text-center text-sm text-foreground-muted hover:text-foreground mt-3 py-2"
            >
              Skip this step
            </button>
          )}
        </div>
      </footer>
    </div>
  );
}
