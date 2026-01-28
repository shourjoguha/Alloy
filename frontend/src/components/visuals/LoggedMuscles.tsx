import { X, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MuscleGroup } from '@/types/anatomy';
import { MUSCLE_DISPLAY_NAMES } from '@/types/anatomy';

interface LoggedMusclesProps {
  selectedMuscles: MuscleGroup[];
  sorenessLevels: Record<MuscleGroup, number>;
  onRemoveMuscle: (muscle: MuscleGroup) => void;
  onSetMuscleLevel?: (muscle: MuscleGroup, level: number) => void;
  className?: string;
}

type SorenessLevel = 0 | 1 | 2 | 3 | 4 | 5;

const SORENESS_LEVELS: Record<number, { label: string; color: string; bgColor: string; borderColor: string }> = {
  0: { label: 'None', color: 'text-slate-800', bgColor: 'bg-slate-100', borderColor: 'border-slate-200' },
  1: { label: 'Minimal', color: 'text-emerald-800', bgColor: 'bg-emerald-100', borderColor: 'border-emerald-200' },
  2: { label: 'Mild', color: 'text-teal-800', bgColor: 'bg-teal-100', borderColor: 'border-teal-200' },
  3: { label: 'Moderate', color: 'text-yellow-800', bgColor: 'bg-yellow-100', borderColor: 'border-yellow-200' },
  4: { label: 'Significant', color: 'text-orange-800', bgColor: 'bg-orange-100', borderColor: 'border-orange-200' },
  5: { label: 'Severe', color: 'text-red-800', bgColor: 'bg-red-100', borderColor: 'border-red-200' },
};

function NumberControl({ value, onChange }: { value: SorenessLevel; onChange: (newLevel: SorenessLevel) => void }) {
  const handleDecrement = () => {
    if (value > 0) onChange((value - 1) as SorenessLevel);
  };

  const handleIncrement = () => {
    if (value < 5) onChange((value + 1) as SorenessLevel);
  };

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={handleDecrement}
        disabled={value === 0}
        className={cn(
          'w-8 h-8 rounded-lg flex items-center justify-center transition-all',
          'bg-white/50 hover:bg-white/80 border border-black/10',
          'disabled:opacity-30 disabled:cursor-not-allowed'
        )}
        aria-label="Decrease level"
      >
        <ChevronLeft className="w-4 h-4 text-foreground/70" />
      </button>
      <div className="w-10 h-8 rounded-lg bg-white/80 border border-black/10 flex items-center justify-center">
        <span className="text-lg font-bold text-foreground">{value}</span>
      </div>
      <button
        type="button"
        onClick={handleIncrement}
        disabled={value === 5}
        className={cn(
          'w-8 h-8 rounded-lg flex items-center justify-center transition-all',
          'bg-white/50 hover:bg-white/80 border border-black/10',
          'disabled:opacity-30 disabled:cursor-not-allowed'
        )}
        aria-label="Increase level"
      >
        <ChevronRight className="w-4 h-4 text-foreground/70" />
      </button>
    </div>
  );
}

export function LoggedMuscles({
  selectedMuscles,
  sorenessLevels,
  onRemoveMuscle,
  onSetMuscleLevel,
  className,
}: LoggedMusclesProps) {
  if (selectedMuscles.length === 0) {
    return null;
  }

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-foreground">Logged Muscles</h3>
        <span className="text-sm text-foreground-muted">
          {selectedMuscles.length} {selectedMuscles.length === 1 ? 'muscle' : 'muscles'}
        </span>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin scrollbar-thumb-border scrollbar-track-transparent -mx-4 px-4">
        {selectedMuscles.map((muscle) => {
          const level = sorenessLevels[muscle] as SorenessLevel;
          const levelInfo = SORENESS_LEVELS[level] || SORENESS_LEVELS[0];

          return (
            <div
              key={muscle}
              className={cn(
                'flex-shrink-0 w-44 rounded-xl border p-3 transition-all hover:shadow-md animate-scale-in',
                levelInfo.bgColor,
                levelInfo.borderColor
              )}
            >
              <div className="flex items-start justify-between mb-3">
                <h4 className="font-semibold text-sm text-foreground leading-tight flex-1 pr-2 break-words min-w-0">
                  {MUSCLE_DISPLAY_NAMES[muscle]}
                </h4>
                <button
                  type="button"
                  onClick={() => onRemoveMuscle(muscle)}
                  className={cn(
                    'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center transition-colors',
                    'hover:bg-white/50'
                  )}
                  aria-label={`Remove ${MUSCLE_DISPLAY_NAMES[muscle]}`}
                >
                  <X className="w-4 h-4 text-foreground/70" />
                </button>
              </div>

              <div className="flex items-center justify-between">
                {onSetMuscleLevel ? (
                  <NumberControl value={level} onChange={(newLevel) => onSetMuscleLevel(muscle, newLevel)} />
                ) : (
                  <div className="flex items-center gap-1.5">
                    <span className={cn('text-2xl font-bold', levelInfo.color)}>
                      {level}
                    </span>
                    <span className={cn('text-xs font-medium', levelInfo.color)}>
                      {levelInfo.label}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
