import { ONBOARDING_QUESTIONS, ICON_MAPPINGS, type Question, type QuestionOption } from '@/config/onboarding-questions';
import { useOnboardingStore } from '@/stores/onboarding-store';
import { useUIStore } from '@/stores/ui-store';
import { SexToggle } from './SexToggle';
import { Slider5Point } from './Slider5Point';
import { YesNoCard } from './YesNoCard';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ChevronRight, ChevronLeft, Loader2, RefreshCw, CheckCircle2, Check, Tennis, Mountain, Bike, Droplets, CircleDot, Flag, Flower2, Fist, Music, Sparkles, Dumbbell, Building, ArrowDown, ArrowUp, Trophy, Footprints, Flame, Zap, Target, Heart, Leaf, Activity } from 'lucide-react';
import { saveOnboardingProgress } from '@/api/onboarding';
import { useState } from 'react';

interface QuestionRendererProps {
  questionId: string;
  onNext: () => void;
  onPrevious: () => void;
  isLastQuestion: boolean;
  isFirstQuestion: boolean;
  currentQuestionIndex: number;
  totalQuestions: number;
  isSubmitting: boolean;
}

type SaveStatus = 'idle' | 'saving' | 'success' | 'error';

// Icon component mapping
const ICON_COMPONENTS: Record<string, React.ComponentType<{ className?: string; strokeWidth?: number }>> = {
  'Tennis': Tennis,
  'Mountain': Mountain,
  'Bike': Bike,
  'Droplets': Droplets,
  'CircleDot': CircleDot,
  'Flag': Flag,
  'Flower2': Flower2,
  'Fist': Fist,
  'Music': Music,
  'Sparkles': Sparkles,
  'Dumbbell': Dumbbell,
  'Building': Building,
  'ArrowDown': ArrowDown,
  'ArrowUp': ArrowUp,
  'Trophy': Trophy,
  'Footprints': Footprints,
  'Flame': Flame,
  'Zap': Zap,
  'Target': Target,
  'Heart': Heart,
  'Leaf': Leaf,
};

// Render the appropriate icon component
const renderIcon = (iconName: string) => {
  const IconComponent = ICON_COMPONENTS[iconName];
  if (!IconComponent) return null;
  return <IconComponent className="h-6 w-6 text-foreground/70" strokeWidth={1.5} />;
};

export function QuestionRenderer({ 
  questionId, 
  onNext, 
  onPrevious,
  isLastQuestion,
  isFirstQuestion,
  currentQuestionIndex,
  totalQuestions,
  isSubmitting 
}: QuestionRendererProps) {
  const question = ONBOARDING_QUESTIONS.find(q => q.id === questionId);
  const { answers, setAnswer, canProceed } = useOnboardingStore();
  const { addToast } = useUIStore();
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');

  if (!question) {
    return null;
  }

  const currentValue = answers[questionId];

  // Handle multi-select toggle for cards
  const handleCardSelection = (optionId: string) => {
    if (question.multiSelect) {
      // For multi-select, toggle the option in an array
      const currentSelections = Array.isArray(currentValue) ? currentValue : [];
      const isSelected = currentSelections.includes(optionId);

      if (isSelected) {
        // Remove the option if already selected
        setAnswer(questionId, currentSelections.filter(id => id !== optionId));
      } else {
        // Add the option if not selected
        setAnswer(questionId, [...currentSelections, optionId]);
      }
    } else {
      // For single-select, just set the value
      setAnswer(questionId, optionId);
      // Auto-proceed to next question for single-answer questions
      if (shouldAutoProceed()) {
        handleNext(optionId);
      }
    }
  };

  // Check if an option is selected
  const isOptionSelected = (optionId: string) => {
    if (question.multiSelect) {
      return Array.isArray(currentValue) && currentValue.includes(optionId);
    }
    return currentValue === optionId;
  };

  const saveProgress = async (value: unknown, retryCount = 0): Promise<boolean> => {
    setSaveStatus('saving');

    try {
      await saveOnboardingProgress(questionId, value);
      setSaveStatus('success');
      return true;
    } catch (error) {
      setSaveStatus('error');

      // Show toast notification
      addToast({
        type: 'warning',
        message: 'Could not save your progress. Your answers are being saved locally.',
        duration: 4000,
      });

      console.error('Failed to save onboarding progress:', error);

      // Auto-retry once if this is the first attempt
      if (retryCount === 0) {
        console.log('Retrying save...');
        await new Promise(resolve => setTimeout(resolve, 1000));
        return saveProgress(value, 1);
      }

      return false;
    }
  };

  const handleNext = async (value?: unknown) => {
    // Save progress in background - don't block user from proceeding
    const valueToSave = value !== undefined ? value : currentValue;
    const saved = await saveProgress(valueToSave);

    // If save failed, show retry option toast
    if (!saved) {
      addToast({
        type: 'error',
        message: 'Failed to save progress. You can continue, but we\'ll try saving again.',
        duration: 5000,
      });
    }

    // Reset save status after a short delay so user can see the result
    setTimeout(() => setSaveStatus('idle'), 2000);

    // Proceed regardless of save status to not block user
    onNext();
  };

  const handleRetrySave = async () => {
    const saved = await saveProgress(currentValue);
    if (saved) {
      addToast({
        type: 'success',
        message: 'Progress saved successfully!',
        duration: 3000,
      });
    }
  };

  const handlePrevious = () => {
    onPrevious();
  };

  // Determine if a question should auto-proceed after selection
  const shouldAutoProceed = () => {
    // Only auto-proceed for single-answer question types and not on the last question
    if (isLastQuestion) return false;

    // Never auto-proceed for multi-select questions
    if (question.multiSelect) return false;

    // Single-answer question types
    const singleAnswerTypes = ['sex_toggle', 'cards'];

    if (!singleAnswerTypes.includes(question.type)) return false;

    // For cards type, only auto-proceed for specific questions that have single-answer semantics
    const singleAnswerCardQuestions = ['gym_comfort_level', 'goal_category'];

    // If it's a cards question, check if it's a single-answer card question
    if (question.type === 'cards' && !singleAnswerCardQuestions.includes(questionId)) {
      return false;
    }

    return true;
  };

  const renderInput = () => {
    switch (question.type) {
      case 'text':
        return (
          <input
            type="text"
            value={currentValue as string || ''}
            onChange={(e) => setAnswer(questionId, e.target.value)}
            placeholder="Type your answer here..."
            className="w-full rounded-lg border border-border/30 bg-background-input/50 px-4 py-2.5 text-sm focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
          />
        );
      
      case 'date':
        return (
          <input
            type="date"
            value={currentValue as string || ''}
            onChange={(e) => setAnswer(questionId, e.target.value)}
            className="w-full rounded-lg border border-border/30 bg-background-input/50 px-4 py-2.5 text-sm focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 transition-all"
          />
        );
      
      case 'sex_toggle':
        return (
          <SexToggle
            value={currentValue as string | null}
            onChange={(value: string) => {
              setAnswer(questionId, value);
              // Auto-proceed to next question for single-answer questions
              if (shouldAutoProceed()) {
                handleNext(value);
              }
            }}
          />
        );
      
      case 'cards':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {question.options?.map((option: QuestionOption) => {
              const iconName = ICON_MAPPINGS[option.id];
              const isSelected = isOptionSelected(option.id);
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => handleCardSelection(option.id)}
                  className={`flex items-center gap-3 p-3.5 rounded-lg border transition-all duration-200 text-left ${
                    isSelected
                      ? 'border-primary/40 bg-primary/5'
                      : 'border-border/20 bg-background-card hover:bg-background-secondary/50 hover:border-border/40'
                  }`}
                >
                  {iconName && renderIcon(iconName)}
                  <div className="flex-1">
                    <h3 className="font-medium text-sm">{option.label}</h3>
                    {option.description && <p className="text-xs text-foreground-muted/70 mt-0.5">{option.description}</p>}
                  </div>
                  {isSelected && (
                    <Check className="h-4 w-4 text-primary flex-shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        );
      
      case 'slider':
        return (
          <Slider5Point
            value={currentValue as Record<string, number> || {}}
            onChange={(value: Record<string, number>) => setAnswer(questionId, value)}
            options={question.options || []}
            labels={{
              1: 'Never touched it',
              2: 'Used it a few times',
              3: 'Comfortable with it',
              4: 'Very familiar',
              5: 'Best friends',
            }}
          />
        );
      
      case 'yes_no':
        return (
          <YesNoCard
            value={currentValue as Record<string, boolean> || {}}
            onChange={(value: Record<string, boolean>) => setAnswer(questionId, value)}
            options={question.options || []}
          />
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1">
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-foreground-muted/70">
              {currentQuestionIndex + 1} / {totalQuestions}
            </p>
            {/* Save Status Indicator */}
            <div className="flex items-center gap-2">
              {saveStatus === 'saving' && (
                <div className="flex items-center gap-1.5 text-xs text-foreground-muted/70">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Saving...</span>
                </div>
              )}
              {saveStatus === 'success' && (
                <div className="flex items-center gap-1.5 text-xs text-success">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Saved</span>
                </div>
              )}
              {saveStatus === 'error' && (
                <button
                  onClick={handleRetrySave}
                  className="flex items-center gap-1.5 text-xs text-error hover:text-error/80 transition-colors"
                  title="Retry saving progress"
                >
                  <RefreshCw className="h-3 w-3" />
                  <span>Retry</span>
                </button>
              )}
            </div>
          </div>
          <div className="h-0.5 bg-background-input/50 rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary/80 transition-all duration-500"
              style={{ width: `${((currentQuestionIndex + 1) / totalQuestions) * 100}%` }}
            />
          </div>
        </div>
      </div>

      <div className="flex-1">
        <h1 className="text-xl font-semibold mb-1.5">{question.text}</h1>
        {question.subtext && (
          <p className="text-xs text-foreground-muted/70 mb-6">{question.subtext}</p>
        )}

        <Card className="p-4 border-border/30">
          {renderInput()}
        </Card>
      </div>

      <div className="flex gap-2 pt-4 border-t border-border/20">
        {!isFirstQuestion && (
          <Button
            variant="ghost"
            onClick={handlePrevious}
            className="flex-1 h-10"
            aria-label="Go to previous question"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        )}
        <Button
          onClick={handleNext}
          className="flex-1 h-10"
          disabled={!canProceed(questionId) || isSubmitting}
          aria-label={isLastQuestion ? "Complete onboarding" : "Go to next question"}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              {isLastQuestion ? 'Complete' : <ChevronRight className="h-4 w-4" />}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
