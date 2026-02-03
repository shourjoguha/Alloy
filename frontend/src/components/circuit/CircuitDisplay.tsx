import { Clock, Flame, Timer, Dumbbell, Zap, Target, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CircuitBlock, CircuitExercise } from '@/types';
import type { LucideIcon } from 'lucide-react';

// Circuit type configuration with distinct styling
const CIRCUIT_TYPE_CONFIG: Record<string, {
  label: string;
  icon: LucideIcon;
  color: string;
  bgColor: string;
  textColor: string;
  description: string;
}> = {
  AMRAP: { 
    label: 'AMRAP', 
    icon: Timer, 
    color: 'bg-amber-500', 
    bgColor: 'bg-amber-50',
    textColor: 'text-amber-700',
    description: 'As Many Rounds As Possible'
  },
  EMOM: { 
    label: 'EMOM', 
    icon: Clock, 
    color: 'bg-blue-500', 
    bgColor: 'bg-blue-50',
    textColor: 'text-blue-700',
    description: 'Every Minute On the Minute'
  },
  RFT: { 
    label: 'RFT', 
    icon: Target, 
    color: 'bg-green-500', 
    bgColor: 'bg-green-50',
    textColor: 'text-green-700',
    description: 'Rounds For Time'
  },
  LADDER: { 
    label: 'Ladder', 
    icon: Zap, 
    color: 'bg-purple-500', 
    bgColor: 'bg-purple-50',
    textColor: 'text-purple-700',
    description: 'Ascending/Descending Reps'
  },
  CHIPPER: { 
    label: 'Chipper', 
    icon: Flame, 
    color: 'bg-orange-500', 
    bgColor: 'bg-orange-50',
    textColor: 'text-orange-700',
    description: 'Complete in Order'
  },
  TABATA: { 
    label: 'Tabata', 
    icon: Zap, 
    color: 'bg-rose-500', 
    bgColor: 'bg-rose-50',
    textColor: 'text-rose-700',
    description: '20s Work / 10s Rest'
  },
  STATION: { 
    label: 'Station', 
    icon: Target, 
    color: 'bg-teal-500', 
    bgColor: 'bg-teal-50',
    textColor: 'text-teal-700',
    description: 'Station-Based Circuit'
  },
};

// Metric type color coding
const METRIC_COLORS: Record<string, {
  color: string;
  bgColor: string;
  textColor: string;
  icon: LucideIcon;
}> = {
  reps: { 
    color: 'blue', 
    bgColor: 'bg-blue-50',
    textColor: 'text-blue-700',
    icon: Target
  },
  time: { 
    color: 'amber', 
    bgColor: 'bg-amber-50',
    textColor: 'text-amber-700',
    icon: Clock
  },
  distance: { 
    color: 'green', 
    bgColor: 'bg-green-50',
    textColor: 'text-green-700',
    icon: Zap
  },
  calories: { 
    color: 'orange', 
    bgColor: 'bg-orange-50',
    textColor: 'text-orange-700',
    icon: Flame
  },
};

// Format exercise metric with proper units
function formatExerciseMetric(ex: CircuitExercise): { value: string; type: string; icon: LucideIcon } {
  const metric = ex.metric_type?.toLowerCase() || '';

  // Check for max reps pattern
  if (ex.reps === 999 && ex.notes && ex.notes.toLowerCase().includes('max')) {
    if (metric === 'calories') {
      return { value: 'Max Cals', type: 'calories', icon: METRIC_COLORS.calories.icon };
    }
    return { value: 'Max Reps', type: 'reps', icon: METRIC_COLORS.reps.icon };
  }

  // Time-based metrics
  if (metric === 'time' && ex.duration_seconds) {
    const total = ex.duration_seconds;
    if (total >= 60 && total % 60 === 0) {
      return { value: `${total / 60} min`, type: 'time', icon: METRIC_COLORS.time.icon };
    }
    return { value: `${total}s`, type: 'time', icon: METRIC_COLORS.time.icon };
  }

  // Distance-based metrics
  if (metric === 'distance' && ex.distance_meters) {
    const meters = ex.distance_meters;
    if (meters >= 1000 && meters % 1000 === 0) {
      return { value: `${meters / 1000} km`, type: 'distance', icon: METRIC_COLORS.distance.icon };
    }
    return { value: `${meters} m`, type: 'distance', icon: METRIC_COLORS.distance.icon };
  }

  // Calories-based metrics
  if (metric === 'calories' && ex.reps) {
    return { value: `${ex.reps} cal`, type: 'calories', icon: METRIC_COLORS.calories.icon };
  }

  // Rep-based metrics (default)
  if (ex.reps) {
    return { value: `${ex.reps} reps`, type: 'reps', icon: METRIC_COLORS.reps.icon };
  }

  return { value: '—', type: 'reps', icon: METRIC_COLORS.reps.icon };
}

// Helper function to validate if a value is a valid number
function isValidNumber(value: unknown): value is number {
  return typeof value === 'number' &&
    !Number.isNaN(value) &&
    !Number.isFinite(value) === false &&
    value !== null &&
    value !== undefined;
}

// Format circuit-level metrics based on circuit type
function formatCircuitMetrics(circuit: CircuitBlock): {
  timeCap?: string;
  rounds?: string;
  workRest?: string;
} {
  const metrics: { timeCap?: string; rounds?: string; workRest?: string } = {};
  const circuitType = circuit.circuit_type?.toUpperCase() || 'AMRAP';

  // AMRAP: Show time cap only
  if (circuitType === 'AMRAP' && circuit.estimated_duration_seconds && circuit.estimated_duration_seconds > 0) {
    const minutes = Math.round(circuit.estimated_duration_seconds / 60);
    metrics.timeCap = `${minutes} min`;
  }

  // EMOM: Show work/rest intervals
  if (circuitType === 'EMOM' && circuit.exercises?.[0]) {
    const firstEx = circuit.exercises[0];
    if (firstEx.duration_seconds && firstEx.rest_seconds) {
      metrics.workRest = `${firstEx.duration_seconds}s work / ${firstEx.rest_seconds}s rest`;
    }
  }

  // RFT, LADDER, CHIPPER, TABATA, STATION: Show rounds only
  if (['RFT', 'LADDER', 'CHIPPER', 'TABATA', 'STATION'].includes(circuitType)) {
    if (circuit.default_rounds && circuit.default_rounds > 0) {
      metrics.rounds = `${circuit.default_rounds} rounds`;
    }
  }

  return metrics;
}

// Exercise row component
function ExerciseRow({ 
  exercise, 
  index, 
  total 
}: { 
  exercise: CircuitExercise; 
  index: number; 
  total: number;
}) {
  const metric = formatExerciseMetric(exercise);
  const metricConfig = METRIC_COLORS[metric.type] || METRIC_COLORS.reps;
  const MetricIcon = metric.icon;

  const hasWeight = exercise.rx_weight_male || exercise.rx_weight_female;
  const hasRest = exercise.rest_seconds && exercise.rest_seconds > 0;

  return (
    <div className={cn(
      "group relative flex items-stretch gap-3 p-3 rounded-lg",
      "transition-all duration-200",
      "hover:bg-background-secondary",
      index !== total - 1 && "mb-2"
    )}>
      {/* Exercise number indicator */}
      <div className={cn(
        "flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center",
        "text-sm font-bold text-white",
        metricConfig.color
      )}>
        {index + 1}
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col justify-center">
        {/* Movement name */}
        <div className="flex items-center gap-2 mb-1">
          <h4 className="font-semibold text-foreground truncate">
            {exercise.movement}
          </h4>
          
          {/* Notes tag if present */}
          {exercise.notes && exercise.notes.toLowerCase().includes('max') && (
            <span className={cn(
              "text-xs px-2 py-0.5 rounded-full font-medium",
              metricConfig.bgColor,
              metricConfig.textColor
            )}>
              Max Effort
            </span>
          )}
        </div>

        {/* Secondary info row */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Prescribed weights */}
          {hasWeight && (
            <div className="flex items-center gap-1.5 text-xs">
              <Dumbbell className="h-3 w-3 text-foreground-muted" />
              {exercise.rx_weight_male && (
                <span className="text-foreground-muted">
                  ♂ {exercise.rx_weight_male}
                </span>
              )}
              {exercise.rx_weight_female && exercise.rx_weight_male && (
                <span className="text-foreground-muted/40">|</span>
              )}
              {exercise.rx_weight_female && (
                <span className="text-foreground-muted">
                  ♀ {exercise.rx_weight_female}
                </span>
              )}
            </div>
          )}

          {/* Rest between exercises */}
          {hasRest && (
            <div className="flex items-center gap-1.5 text-xs text-foreground-muted">
              <Clock className="h-3 w-3" />
              <span>Rest {exercise.rest_seconds}s</span>
            </div>
          )}
        </div>
      </div>

      {/* Metric badge */}
      <div className={cn(
        "flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg",
        "font-semibold text-sm",
        metricConfig.bgColor,
        metricConfig.textColor
      )}>
        <MetricIcon className="h-3.5 w-3.5" />
        <span>{metric.value}</span>
      </div>
    </div>
  );
}

// Main circuit display component
export function CircuitDisplay({ 
  circuit, 
  title = "Circuit Block",
  showMetrics = true 
}: { 
  circuit: CircuitBlock; 
  title?: string;
  showMetrics?: boolean;
}) {
  if (!circuit) return null;

  const circuitTypeKey = circuit.circuit_type?.toUpperCase() || 'AMRAP';
  const config = CIRCUIT_TYPE_CONFIG[circuitTypeKey] || CIRCUIT_TYPE_CONFIG.AMRAP;
  const CircuitIcon = config.icon;
  const metrics = formatCircuitMetrics(circuit);

  const hasExercises = circuit.exercises && circuit.exercises.length > 0;
  const hasMuscles = circuit.primary_muscles && circuit.primary_muscles.length > 0;

  return (
    <div className="my-4">
      {/* Section header */}
      <div className="flex items-center gap-2 mb-3">
        <Flame className="h-4 w-4 text-orange-500" />
        <h4 className="text-sm font-semibold text-foreground-muted uppercase tracking-wide">
          {title}
        </h4>
      </div>

      {/* Circuit card */}
      <div className="rounded-xl overflow-hidden border-2 border-border/30 bg-gradient-to-br from-background-card to-background-secondary">
        {/* Circuit header with type badge */}
        <div className={cn(
          "px-4 py-3 border-b border-border/30",
          config.bgColor
        )}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={cn(
                "w-10 h-10 rounded-lg flex items-center justify-center",
                config.color
              )}>
                <CircuitIcon className="h-5 w-5 text-white" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-foreground">
                  {circuit.name}
                </h3>
                <p className="text-xs text-foreground-muted">
                  {config.description}
                </p>
              </div>
            </div>

            {/* Circuit type badge */}
            <div className={cn(
              "px-3 py-1.5 rounded-lg font-bold text-sm",
              config.color,
              "text-white"
            )}>
              {config.label}
            </div>
          </div>

          {/* Circuit-level metrics row */}
          {showMetrics && (metrics.timeCap || metrics.rounds || metrics.workRest) && (
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              {metrics.timeCap && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/60 text-foreground text-xs font-medium">
                  <Clock className="h-3.5 w-3.5" />
                  <span>{metrics.timeCap}</span>
                </div>
              )}
              {metrics.rounds && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/60 text-foreground text-xs font-medium">
                  <Target className="h-3.5 w-3.5" />
                  <span>{metrics.rounds}</span>
                </div>
              )}
              {metrics.workRest && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/60 text-foreground text-xs font-medium">
                  <Timer className="h-3.5 w-3.5" />
                  <span>{metrics.workRest}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Muscle tags */}
        {hasMuscles && (
          <div className="px-4 py-2 border-b border-border/20 bg-background/50">
            <div className="flex items-center gap-1.5 flex-wrap">
              <Target className="h-3 w-3 text-foreground-muted" />
              {circuit.primary_muscles.map((muscle, idx) => (
                <span 
                  key={idx} 
                  className="text-xs px-2 py-0.5 rounded-md bg-primary/10 text-primary font-medium"
                >
                  {muscle}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Exercises list */}
        {hasExercises && (
          <div className="p-4 bg-background-card">
            <div className="space-y-1">
              {circuit.exercises.map((ex, idx) => (
                <ExerciseRow
                  key={ex.sequence || idx}
                  exercise={ex}
                  index={idx}
                  total={circuit.exercises.length}
                />
              ))}
            </div>

            {/* Circuit footer with total exercises */}
            <div className="mt-3 pt-3 border-t border-border/30">
              <div className="flex items-center justify-between text-xs text-foreground-muted">
                <div className="flex items-center gap-1">
                  <Flame className="h-3 w-3" />
                  <span>{circuit.exercises.length} exercises</span>
                </div>
                <div className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  <span>
                    {isValidNumber(circuit.estimated_duration_seconds) && circuit.estimated_duration_seconds > 0
                      ? `~${Math.round(circuit.estimated_duration_seconds / 60)} min`
                      : '— min'
                    }
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Compact version for use in tight spaces
export function CircuitDisplayCompact({ 
  circuit 
}: { 
  circuit: CircuitBlock; 
}) {
  if (!circuit) return null;

  const circuitTypeKey = circuit.circuit_type?.toUpperCase() || 'AMRAP';
  const config = CIRCUIT_TYPE_CONFIG[circuitTypeKey] || CIRCUIT_TYPE_CONFIG.AMRAP;
  const CircuitIcon = config.icon;

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-gradient-to-r from-background-secondary to-background-card border border-border/30">
      <div className={cn(
        "w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0",
        config.color
      )}>
        <CircuitIcon className="h-4 w-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h4 className="font-semibold text-foreground text-sm truncate">
            {circuit.name}
          </h4>
          <span className={cn(
            "text-xs px-1.5 py-0.5 rounded font-medium",
            config.color,
            "text-white"
          )}>
            {config.label}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-foreground-muted">
            {circuit.exercises?.length || 0} exercises
          </span>
          <span className="text-foreground-muted/40">•</span>
          <span className="text-xs text-foreground-muted">
            {isValidNumber(circuit.estimated_duration_seconds) && circuit.estimated_duration_seconds > 0
              ? `${Math.round(circuit.estimated_duration_seconds / 60)} min`
              : '— min'
            }
          </span>
          {isValidNumber(circuit.default_rounds) && circuit.default_rounds > 0 && (
            <>
              <span className="text-foreground-muted/40">•</span>
              <span className="text-xs text-foreground-muted">
                {circuit.default_rounds} {circuit.circuit_type === 'AMRAP' ? 'min cap' : 'rounds'}
              </span>
            </>
          )}
        </div>
      </div>
      <ChevronRight className="h-4 w-4 text-foreground-muted flex-shrink-0" />
    </div>
  );
}
