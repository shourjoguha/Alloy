import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { ChevronDown, ChevronUp, Clock, Flame, Coffee, Dumbbell, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Session, ExerciseBlock, CircuitExercise, CircuitBlock } from '@/types';

interface SessionCardProps {
  session: Session;
  defaultExpanded?: boolean;
}

// Session type display config
const SESSION_TYPE_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  upper: { label: 'Upper Body', icon: '💪', color: 'bg-blue-500' },
  lower: { label: 'Lower Body', icon: '🦵', color: 'bg-green-500' },
  push: { label: 'Push', icon: '🏋️', color: 'bg-red-500' },
  pull: { label: 'Pull', icon: '🧲', color: 'bg-purple-500' },
  legs: { label: 'Legs', icon: '🦵', color: 'bg-green-500' },
  full_body: { label: 'Full Body', icon: '⚡', color: 'bg-yellow-500' },
  cardio: { label: 'Cardio', icon: '❤️', color: 'bg-pink-500' },
  mobility: { label: 'Mobility', icon: '🧘', color: 'bg-teal-500' },
  recovery: { label: 'Rest Day', icon: '😴', color: 'bg-gray-500' },
  skill: { label: 'Skill', icon: '🎯', color: 'bg-orange-500' },
  custom: { label: 'Custom', icon: '⚙️', color: 'bg-gray-500' },
};

// Format circuit exercise metrics
function formatCircuitExercise(ex: CircuitExercise): string {
  const metric = ex.metric_type?.toLowerCase() || '';

  // Check for max reps pattern
  if (ex.reps === 999 && ex.notes && ex.notes.toLowerCase().includes('max')) {
    if (metric === 'calories') {
      return 'max cals';
    }
    return 'max reps';
  }

  // Time-based metrics
  if (metric === 'time' && ex.duration_seconds) {
    const total = ex.duration_seconds;
    if (total % 60 === 0) {
      return `${total / 60} min`;
    }
    return `${total}s`;
  }

  // Distance-based metrics
  if (metric === 'distance' && ex.distance_meters) {
    const meters = ex.distance_meters;
    if (meters >= 1000 && meters % 1000 === 0) {
      return `${meters / 1000} km`;
    }
    return `${meters} m`;
  }

  // Calories-based metrics
  if (metric === 'calories' && ex.reps) {
    return `${ex.reps} cal`;
  }

  // Rep-based metrics (default)
  if (ex.reps) {
    return `${ex.reps} reps`;
  }

  return '';
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function ExerciseList({ exercises, title }: { exercises: ExerciseBlock[] | null | undefined; title: string }) {
  if (!exercises || exercises.length === 0) return null;

  return (
    <div className="mt-3">
      <h4 className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2">
        {title}
      </h4>
      <div className="space-y-1.5">
        {exercises.map((exercise, idx) => (
          <div key={idx} className="flex items-center justify-between text-sm">
            <span className="text-foreground">{exercise.movement}</span>
            <span className="text-foreground-muted text-xs">
              {exercise.sets && (
                <>
                  {exercise.sets}×
                  {exercise.reps
                    ? `${exercise.reps} reps`
                    : exercise.rep_range_min && exercise.rep_range_max
                    ? `${exercise.rep_range_min}-${exercise.rep_range_max}`
                    : exercise.duration_seconds
                    ? `${exercise.duration_seconds}s`
                    : '—'}
                </>
              )}
              {exercise.target_rpe && (
                <span className="ml-1 text-primary">@{exercise.target_rpe}</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CircuitDisplay({ circuit, title = "Circuit Block" }: { circuit: CircuitBlock; title?: string }) {
  if (!circuit) return null;

  return (
    <div className="mt-3">
      <h4 className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2 flex items-center gap-1">
        <Flame className="h-3 w-3 text-orange-500" />
        {title}
      </h4>
      <div className="p-3 bg-background-input rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <span className="font-medium text-foreground">{circuit.name}</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-primary bg-primary/10 px-2 py-0.5 rounded font-medium">
              {circuit.circuit_type}
            </span>
            {circuit.estimated_duration_seconds && typeof circuit.estimated_duration_seconds === 'number' && circuit.estimated_duration_seconds > 0 && (
            <span className="text-xs text-foreground-muted bg-background-input px-2 py-0.5 rounded">
              {Math.round(circuit.estimated_duration_seconds / 60)} min
            </span>
          )}
          {circuit.default_rounds && typeof circuit.default_rounds === 'number' && circuit.default_rounds > 0 && (
            <span className="text-xs text-foreground-muted bg-background-input px-2 py-0.5 rounded">
              {circuit.default_rounds} rounds
            </span>
          )}
          </div>
        </div>
        
        {circuit.primary_muscles && circuit.primary_muscles.length > 0 && (
          <div className="flex gap-1 flex-wrap mb-2">
            {circuit.primary_muscles.map((muscle: string, idx: number) => (
              <span key={idx} className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded">
                {muscle}
              </span>
            ))}
          </div>
        )}
        
        {circuit.exercises && circuit.exercises.length > 0 && (
          <div className="border-t border-border/50 pt-2">
            <div className="text-xs text-foreground-muted mb-2">Exercises:</div>
            <div className="space-y-1">
              {circuit.exercises.map((ex: CircuitExercise, idx: number) => (
                <div key={idx} className="flex items-center justify-between text-sm">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-foreground font-medium">{ex.movement}</span>
                      {(ex.rx_weight_male || ex.rx_weight_female) && (
                        <div className="flex items-center gap-1 text-xs text-foreground-muted">
                          <Dumbbell className="h-3 w-3" />
                          {ex.rx_weight_male && (
                            <span>♂ {ex.rx_weight_male}</span>
                          )}
                          {ex.rx_weight_female && (
                            <span>♀ {ex.rx_weight_female}</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-foreground-muted">
                    <span className="bg-background-input px-2 py-0.5 rounded">
                      {formatCircuitExercise(ex)}
                    </span>
                    {ex.rest_seconds && (
                      <span className="text-foreground-muted/60">
                        rest {ex.rest_seconds}s
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function SessionCard({ session, defaultExpanded = false }: SessionCardProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [notesExpanded, setNotesExpanded] = useState(false);
  
  const config = SESSION_TYPE_CONFIG[session.session_type] || SESSION_TYPE_CONFIG.custom;
  const hasContent = session.main && session.main.length > 0;
  const isRestDay = session.session_type === 'recovery';
  const isGenerating = !isRestDay && !hasContent;
  const hasCoachNotes = session.coach_notes && session.coach_notes.length > 0;
  
  // Detect error state from coach_notes
  const isError = hasCoachNotes && session.coach_notes ? (
    session.coach_notes.toLowerCase().includes('error') ||
    session.coach_notes.toLowerCase().includes('failed') ||
    session.coach_notes.toLowerCase().includes('issue') ||
    session.coach_notes.toLowerCase().includes('problem') ||
    session.coach_notes.toLowerCase().includes('unable')
  ) : false;

  return (
    <Card variant="grouped"
      className={cn(
        "overflow-hidden transition-all",
        isRestDay && "opacity-60"
      )}
    >
      {/* Error banner */}
      {isError && (
        <div className="bg-amber-500/10 border-b border-amber-500/30 px-4 py-2">
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 text-sm">
            <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <span>Session generation failed. Please regenerate or contact support.</span>
          </div>
        </div>
      )}
      
      {/* Header - always visible */}
      <button
        onClick={() => hasContent && setIsExpanded(!isExpanded)}
        className={cn(
          "w-full p-4 flex items-center gap-3 text-left",
          hasContent && "cursor-pointer hover:bg-background-secondary"
        )}
        disabled={!hasContent}
      >
        {/* Day indicator */}
        <div className={cn(
          "w-10 h-10 rounded-lg flex items-center justify-center text-lg",
          config.color,
          "bg-opacity-20"
        )}>
          {config.icon}
        </div>

        {/* Session info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium">{config.label}</span>
            {isRestDay && <Coffee className="h-3 w-3 text-foreground-muted" />}
            {isGenerating && (
              <span className="text-xs text-foreground-muted">Generating…</span>
            )}
          </div>
          <div className="text-xs text-foreground-muted flex items-center gap-2">
            <span>Day {session.day_number}</span>
            {session.session_date && (
              <>
                <span>•</span>
                <span>{formatDate(session.session_date)}</span>
              </>
            )}
          </div>
        </div>

        {/* Duration & expand */}
        <div className="flex items-center gap-2">
          {session.estimated_duration_minutes && (
            <div className="flex items-center gap-1 text-xs text-foreground-muted">
              <Clock className="h-3 w-3" />
              <span>{session.estimated_duration_minutes}m</span>
            </div>
          )}
          {hasContent && (
            <div className="text-foreground-muted">
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </div>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && hasContent && (
        <div className="px-4 pb-4 border-t border-border/50">
          {/* Intent tags */}
          {session.intent_tags && session.intent_tags.length > 0 && (
            <div className="flex gap-1 flex-wrap mt-3">
              {session.intent_tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-0.5 bg-background-input rounded text-foreground-muted"
                >
                  {tag.replace('_', ' ')}
                </span>
              ))}
            </div>
          )}

          {/* Exercise sections */}
          <ExerciseList exercises={session.warmup} title="Warmup" />
          <ExerciseList exercises={session.main} title="Main" />
          
          {/* Mutually exclusive: Either circuit block OR accessory block, never both */}
          <ExerciseList exercises={session.accessory} title="Accessory" />
          
          {/* Finisher - only finisher_circuit */}
          {session.finisher_circuit && (
            <CircuitDisplay circuit={session.finisher_circuit} title="Finisher" />
          )}

          <ExerciseList exercises={session.cooldown} title="Cooldown" />

          {/* Coach notes */}
          {hasCoachNotes && session.coach_notes && (
            <div className="mt-3 p-2 bg-background-input rounded text-xs text-foreground-muted">
              <div className="flex items-start justify-between">
                <span className="font-medium">Jerome's Notes:</span>
              </div>
              <div className={cn(
                "mt-1",
                !notesExpanded && "line-clamp-3"
              )}>
                {session.coach_notes}
              </div>
              {session.coach_notes.length > 150 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setNotesExpanded(!notesExpanded);
                  }}
                  className="mt-2 flex items-center gap-1 text-xs text-primary hover:text-primary/80 transition-colors"
                >
                  {notesExpanded ? 'Show less' : 'See more'}
                  {notesExpanded ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
