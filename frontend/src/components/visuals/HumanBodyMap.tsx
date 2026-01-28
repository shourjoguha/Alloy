import { useCallback, memo } from 'react';
import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MuscleGroup } from '@/types/anatomy';

interface HumanBodyMapProps {
  selectedMuscles: MuscleGroup[];
  onToggleMuscle: (muscle: MuscleGroup) => void;
  onViewChange: (view: 'front' | 'back') => void;
  currentView: 'front' | 'back';
  className?: string;
}

const MUSCLE_COLORS = {
  unselected: '#1E293B',
  selected: '#F59E0B',
  hover: '#D97706',
} as const;

interface MusclePathProps {
  id: MuscleGroup;
  pathData: string;
  isSelected: boolean;
  isFaded: boolean;
  onClick: () => void;
  ariaLabel: string;
}

const MusclePath = memo(({ id, pathData, isSelected, isFaded, onClick, ariaLabel }: MusclePathProps) => {
  const opacity = isFaded ? 0.3 : 1;

  return (
    <g>
      <path
        id={id}
        d={pathData}
        fill={isSelected ? MUSCLE_COLORS.selected : MUSCLE_COLORS.unselected}
        fillOpacity={opacity}
        stroke={isSelected ? MUSCLE_COLORS.selected : MUSCLE_COLORS.unselected}
        strokeOpacity={opacity}
        strokeWidth="0.5"
        className="transition-all duration-300 ease-out cursor-pointer"
        style={{
          filter: isSelected ? 'drop-shadow(0 0 8px rgba(245, 158, 11, 0.4))' : 'none',
          touchAction: 'manipulation',
        }}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onClick();
        }}
        aria-label={ariaLabel}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onClick();
          }
        }}
      />
    </g>
  );
});

MusclePath.displayName = 'MusclePath';

const FRONT_MUSCLES: Array<{ id: MuscleGroup; path: string; label: string }> = [
  {
    id: 'front_delts',
    path: 'M85 95 L96 100 L106 95 L100 107 Z',
    label: 'Front Delts',
  },
  {
    id: 'chest',
    path: 'M72 102 L90 97 L110 97 L128 102 L123 127 L77 127 Z',
    label: 'Chest',
  },
  {
    id: 'biceps',
    path: 'M67 132 L72 162 L82 167 L87 132 Z M113 132 L118 167 L128 162 L133 132 Z',
    label: 'Biceps',
  },
  {
    id: 'forearms',
    path: 'M72 172 L77 212 L87 217 L84 172 Z M113 172 L116 217 L123 212 L128 172 Z',
    label: 'Forearms',
  },
  {
    id: 'core',
    path: 'M82 132 L118 132 L123 182 L77 182 Z',
    label: 'Core',
  },
  {
    id: 'obliques',
    path: 'M72 127 L82 132 L77 182 L67 177 Z M128 127 L133 177 L123 182 L118 132 Z',
    label: 'Obliques',
  },
  {
    id: 'quadriceps',
    path: 'M77 187 L95 182 L95 282 L72 287 Z M105 182 L123 187 L128 287 L105 282 Z',
    label: 'Quadriceps',
  },
  {
    id: 'hip_flexors',
    path: 'M72 182 L82 177 L95 182 L92 187 Z M108 187 L118 182 L128 177 L123 187 Z',
    label: 'Hip Flexors',
  },
  {
    id: 'adductors',
    path: 'M95 182 L105 182 L105 277 L95 277 Z',
    label: 'Adductors',
  },
  {
    id: 'calves',
    path: 'M72 292 L82 287 L87 352 L72 357 Z M118 287 L128 292 L128 357 L113 352 Z',
    label: 'Calves',
  },
];

const BACK_MUSCLES: Array<{ id: MuscleGroup; path: string; label: string }> = [
  {
    id: 'side_delts',
    path: 'M72 97 L82 102 L92 97 L87 107 Z M108 97 L118 102 L128 97 L123 107 Z',
    label: 'Side Delts',
  },
  {
    id: 'rear_delts',
    path: 'M62 102 L72 107 L77 102 L67 97 Z M123 102 L128 97 L138 102 L133 107 Z',
    label: 'Rear Delts',
  },
  {
    id: 'lats',
    path: 'M67 112 L77 107 L87 112 L92 147 L72 152 Z M113 112 L123 107 L133 112 L128 152 L108 147 Z',
    label: 'Lats',
  },
  {
    id: 'upper_back',
    path: 'M87 102 L95 97 L105 97 L113 102 L108 142 L92 142 Z',
    label: 'Upper Back',
  },
  {
    id: 'triceps',
    path: 'M67 157 L72 187 L82 192 L87 157 Z M113 157 L118 192 L128 187 L133 157 Z',
    label: 'Triceps',
  },
  {
    id: 'forearms',
    path: 'M67 197 L72 237 L82 242 L79 197 Z M118 197 L121 242 L128 237 L133 197 Z',
    label: 'Forearms',
  },
  {
    id: 'lower_back',
    path: 'M82 152 L100 147 L118 152 L123 187 L77 187 Z',
    label: 'Lower Back',
  },
  {
    id: 'glutes',
    path: 'M72 192 L87 187 L113 187 L128 192 L123 222 L77 222 Z',
    label: 'Glutes',
  },
  {
    id: 'hamstrings',
    path: 'M72 227 L87 222 L92 322 L67 327 Z M108 222 L123 227 L133 327 L108 322 Z',
    label: 'Hamstrings',
  },
  {
    id: 'calves',
    path: 'M67 332 L77 327 L82 392 L67 397 Z M123 327 L133 332 L133 397 L118 392 Z',
    label: 'Calves',
  },
];

export function HumanBodyMap({ selectedMuscles, onToggleMuscle, onViewChange, currentView, className }: HumanBodyMapProps) {
  const handleToggle = useCallback(
    (muscle: MuscleGroup) => {
      onToggleMuscle(muscle);
    },
    [onToggleMuscle]
  );

  const handleViewChange = useCallback(
    (newView: 'front' | 'back') => {
      onViewChange(newView);
    },
    [onViewChange]
  );

  const muscles = currentView === 'front' ? FRONT_MUSCLES : BACK_MUSCLES;

  return (
    <div className={cn('flex flex-col items-center w-full', className)}>
      <div className="mb-4 w-full max-w-xs mx-auto">
        <button
          type="button"
          onClick={() => handleViewChange(currentView === 'front' ? 'back' : 'front')}
          className={cn(
            'w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all',
            'bg-background-input text-foreground hover:bg-background-secondary border border-border'
          )}
        >
          <RefreshCw className={cn('w-4 h-4 transition-transform', currentView === 'back' ? 'rotate-180' : 'rotate-0')} />
          {currentView === 'front' ? 'Switch to Back' : 'Switch to Front'}
        </button>
      </div>

      <svg
        viewBox="0 0 200 420"
        className="w-full max-w-xs h-auto"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label={`Human body ${currentView} view - click to select muscles`}
      >
        <g>
          {muscles.map((muscle) => (
            <MusclePath
              key={muscle.id}
              id={muscle.id}
              pathData={muscle.path}
              isSelected={selectedMuscles.includes(muscle.id)}
              isFaded={false}
              onClick={() => handleToggle(muscle.id)}
              ariaLabel={muscle.label}
            />
          ))}
        </g>
      </svg>

      <div className="mt-4 flex gap-4 text-sm w-full max-w-xs mx-auto justify-center">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: MUSCLE_COLORS.unselected }} />
          <span className="text-foreground-muted">Normal</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded" style={{ backgroundColor: MUSCLE_COLORS.selected }} />
          <span className="text-foreground-muted">Sore</span>
        </div>
      </div>

      <p className="mt-2 text-xs text-foreground-muted text-center max-w-xs">
        {currentView === 'front' 
          ? 'Front view active. Tap muscles to select. Switching to Back view will deselect Front muscles.' 
          : 'Back view active. Tap muscles to select. Switching to Front view will deselect Back muscles.'}
      </p>
    </div>
  );
}
