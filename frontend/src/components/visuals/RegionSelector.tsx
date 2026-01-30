import { useState, useEffect } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { MuscleGroup, BodyZone } from '@/types/anatomy';
import { ZONE_MAPPING, BODY_ZONE_LABELS, MUSCLE_DISPLAY_NAMES } from '@/types/anatomy';

interface RegionSelectorProps {
  selectedMuscles: MuscleGroup[];
  sorenessLevels: Record<MuscleGroup, number>;
  onSelectMuscle: (muscle: MuscleGroup) => void;
  onSetMuscleLevel: (muscle: MuscleGroup, level: number) => void;
  onSetRegionLevel: (zone: BodyZone, level: number) => void;
  className?: string;
}

type SorenessLevel = 0 | 1 | 2 | 3 | 4 | 5;

const SORENESS_LEVELS: Array<{ value: SorenessLevel; label: string; color: string }> = [
  { value: 0, label: 'None', color: 'bg-slate-800/50 text-slate-200 border-slate-700' },
  { value: 1, label: 'Minimal', color: 'bg-emerald-900/50 text-emerald-200 border-emerald-700' },
  { value: 2, label: 'Mild', color: 'bg-teal-900/50 text-teal-200 border-teal-700' },
  { value: 3, label: 'Moderate', color: 'bg-yellow-900/50 text-yellow-200 border-yellow-700' },
  { value: 4, label: 'Significant', color: 'bg-orange-900/50 text-orange-200 border-orange-700' },
  { value: 5, label: 'Severe', color: 'bg-red-900/50 text-red-200 border-red-700' },
];

function NumberControl({ value, onChange, label }: { value: SorenessLevel; onChange: (newLevel: SorenessLevel) => void; label?: string }) {
  const handleDecrement = () => {
    if (value > 0) onChange((value - 1) as SorenessLevel);
  };

  const handleIncrement = () => {
    if (value < 5) onChange((value + 1) as SorenessLevel);
  };

  const levelInfo = SORENESS_LEVELS[value];

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={handleDecrement}
          disabled={value === 0}
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center transition-all',
            'bg-background-input hover:bg-background-secondary border border-border',
            'disabled:opacity-30 disabled:cursor-not-allowed'
          )}
          aria-label="Decrease level"
        >
          <ChevronLeft className="w-4 h-4 text-foreground/70" />
        </button>
        <div className="w-10 h-8 rounded-lg bg-background-elevated border border-border flex items-center justify-center">
          <span className="text-lg font-bold text-foreground">{value}</span>
        </div>
        <button
          type="button"
          onClick={handleIncrement}
          disabled={value === 5}
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center transition-all',
            'bg-background-input hover:bg-background-secondary border border-border',
            'disabled:opacity-30 disabled:cursor-not-allowed'
          )}
          aria-label="Increase level"
        >
          <ChevronRight className="w-4 h-4 text-foreground/70" />
        </button>
      </div>
      {label && <span className={cn('text-sm font-medium', levelInfo.color)}>{label}</span>}
    </div>
  );
}

const REGIONS: Array<{ zone: BodyZone; label: string }> = [
  { zone: 'shoulder', label: 'Shoulder' },
  { zone: 'anterior upper', label: 'Anterior Upper' },
  { zone: 'posterior upper', label: 'Posterior Upper' },
  { zone: 'core', label: 'Core' },
  { zone: 'anterior lower', label: 'Anterior Lower' },
  { zone: 'posterior lower', label: 'Posterior Lower' },
];

export function RegionSelector({
  selectedMuscles,
  sorenessLevels,
  onSelectMuscle,
  onSetMuscleLevel,
  onSetRegionLevel,
  className,
}: RegionSelectorProps) {
  const [selectedRegion, setSelectedRegion] = useState<BodyZone | null>(null);
  const [applyToAll, setApplyToAll] = useState(true);
  const [regionLevel, setRegionLevel] = useState<SorenessLevel>(2);

  const handleRegionSelect = (zone: BodyZone) => {
    if (selectedRegion === zone) {
      setSelectedRegion(null);
    } else {
      setSelectedRegion(zone);
      setApplyToAll(true);
      setRegionLevel(2);
    }
  };

  const handleSetRegionLevel = (level: SorenessLevel) => {
    setRegionLevel(level);
    if (applyToAll && selectedRegion) {
      onSetRegionLevel(selectedRegion, level);
    }
  };

  useEffect(() => {
    if (applyToAll && selectedRegion) {
      onSetRegionLevel(selectedRegion, regionLevel);
    }
  }, [applyToAll, selectedRegion, regionLevel, onSetRegionLevel]);

  const handleMuscleToggle = (muscle: MuscleGroup) => {
    onSelectMuscle(muscle);
    if (selectedRegion && applyToAll && !selectedMuscles.includes(muscle)) {
      onSetMuscleLevel(muscle, regionLevel);
    }
  };

  const handleMuscleLevelChange = (muscle: MuscleGroup, level: SorenessLevel) => {
    onSetMuscleLevel(muscle, level);
  };

  const getRegionStats = (zone: BodyZone) => {
    const muscles = ZONE_MAPPING[zone];
    const selectedCount = muscles.filter((m) => selectedMuscles.includes(m)).length;
    const total = muscles.length;
    return { selectedCount, total };
  };

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div className="relative">
        <select
          value={selectedRegion || ''}
          onChange={(e) => handleRegionSelect(e.target.value as BodyZone)}
          className="w-full appearance-none bg-background-card border border-border rounded-xl px-4 py-3 text-base font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary cursor-pointer transition-shadow"
        >
          <option value="">Select a body region...</option>
          {REGIONS.map((region) => {
            const stats = getRegionStats(region.zone);
            return (
              <option key={region.zone} value={region.zone}>
                {region.label} {stats.selectedCount > 0 ? `(${stats.selectedCount}/${stats.total})` : ''}
              </option>
            );
          })}
        </select>
        <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-foreground-muted pointer-events-none" />
      </div>

      {selectedRegion && (
        <div className="bg-background-card border border-border rounded-xl p-4 space-y-4 animate-slide-up">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-foreground">{BODY_ZONE_LABELS[selectedRegion]}</h3>
            <button
              type="button"
              onClick={() => setSelectedRegion(null)}
              className="p-1 hover:bg-background-secondary rounded-md transition-colors"
            >
              <X className="w-5 h-5 text-foreground-muted" />
            </button>
          </div>

          <div>
            <div className="flex items-center justify-between mb-3">
              <label className="text-sm font-medium text-foreground">Region Soreness Level</label>
              <button
                type="button"
                onClick={() => setApplyToAll(!applyToAll)}
                className={cn(
                  'flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium transition-colors',
                  applyToAll
                    ? 'bg-accent text-white'
                    : 'bg-background-input text-foreground-muted hover:bg-background-secondary'
                )}
              >
                <span className="w-3 h-3 rounded-full border border-current flex items-center justify-center">
                  {applyToAll && <div className="w-1.5 h-1.5 rounded-full bg-current" />}
                </span>
                Auto-apply to new muscles
              </button>
            </div>
            <NumberControl
              value={regionLevel}
              onChange={handleSetRegionLevel}
              label={SORENESS_LEVELS[regionLevel].label}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-3">
              Individual Muscles
            </label>
            <div className="space-y-2">
              {ZONE_MAPPING[selectedRegion].map((muscle) => {
                const isSelected = selectedMuscles.includes(muscle);
                const currentLevel = sorenessLevels[muscle] as SorenessLevel;

                return (
                  <div
                    key={muscle}
                    className={cn(
                      'p-3 rounded-lg border transition-all',
                      isSelected
                        ? 'bg-background-elevated border-accent/30'
                        : 'bg-background-card border-border'
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => handleMuscleToggle(muscle)}
                        className={cn(
                          'flex-shrink-0 text-left flex items-center gap-2 px-3 py-2 rounded-md transition-colors',
                          isSelected
                            ? 'text-foreground'
                            : 'text-foreground-muted hover:text-foreground'
                        )}
                      >
                        {isSelected ? (
                          <div className="w-5 h-5 rounded-full bg-accent flex items-center justify-center">
                            <Check className="w-3 h-3 text-white" />
                          </div>
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-border" />
                        )}
                        <span className="font-medium">{MUSCLE_DISPLAY_NAMES[muscle]}</span>
                      </button>
                      {isSelected && (
                        <NumberControl
                          value={currentLevel}
                          onChange={(newLevel) => handleMuscleLevelChange(muscle, newLevel)}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
