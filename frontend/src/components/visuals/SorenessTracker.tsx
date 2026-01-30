import { useState, useCallback } from 'react';
import { RotateCcw, Check, X, User, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { HumanBodyMap } from './HumanBodyMap';
import { RegionSelector } from './RegionSelector';
import { LoggedMuscles } from './LoggedMuscles';
import { useLogSoreness } from '@/api/logs';
import type { MuscleGroup, BodyZone } from '@/types/anatomy';
import { ZONE_MAPPING } from '@/types/anatomy';
import { cn } from '@/lib/utils';

interface SorenessTrackerProps {
  logDate?: string;
  onSuccess?: () => void;
  onCancel?: () => void;
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
  );
}

type OverrideLevel = 'none' | 'full-body' | 'front-back' | 'region' | 'manual';

export function SorenessTracker({ logDate, onSuccess, onCancel, className }: SorenessTrackerProps) {
  const [selectedMuscles, setSelectedMuscles] = useState<MuscleGroup[]>([]);
  const [sorenessLevels, setSorenessLevels] = useState<Record<MuscleGroup, SorenessLevel>>({} as Record<MuscleGroup, SorenessLevel>);
  const [overrideLevels, setOverrideLevels] = useState<Record<MuscleGroup, OverrideLevel>>({} as Record<MuscleGroup, OverrideLevel>);
  const [regionLevels, setRegionLevels] = useState<Record<BodyZone, SorenessLevel>>({} as Record<BodyZone, SorenessLevel>);
  const [fullBodyDefaultLevel, setFullBodyDefaultLevel] = useState<SorenessLevel>(1);
  const [notes, setNotes] = useState('');
  const [currentView, setCurrentView] = useState<'front' | 'back'>('front');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFullBodyExpanded, setIsFullBodyExpanded] = useState(false);
  const [frontLevel, setFrontLevel] = useState<SorenessLevel>(1);
  const [backLevel, setBackLevel] = useState<SorenessLevel>(1);
  const logSorenessMutation = useLogSoreness();

  const toggleMuscle = (muscle: MuscleGroup) => {
    setSelectedMuscles((prev) => {
      if (prev.includes(muscle)) {
        const next = prev.filter((m) => m !== muscle);
        const newLevels = { ...sorenessLevels };
        delete newLevels[muscle];
        setSorenessLevels(newLevels);
        setOverrideLevels((prev) => {
          const newOverrides = { ...prev };
          delete newOverrides[muscle];
          return newOverrides;
        });
        return next;
      } else {
        let inheritedLevel = fullBodyDefaultLevel;
        let inheritedOverride: OverrideLevel = 'full-body';

        const frontMuscles = ZONE_MAPPING['front'];
        const backMuscles = ZONE_MAPPING['back'];

        const regions: BodyZone[] = ['shoulder', 'anterior upper', 'posterior upper', 'core', 'anterior lower', 'posterior lower'];
        let muscleRegion: BodyZone | null = null;

        for (const region of regions) {
          if (ZONE_MAPPING[region]?.includes(muscle)) {
            muscleRegion = region;
            break;
          }
        }

        if (frontMuscles.includes(muscle)) {
          inheritedLevel = frontLevel;
          inheritedOverride = 'front-back';
        } else if (backMuscles.includes(muscle)) {
          inheritedLevel = backLevel;
          inheritedOverride = 'front-back';
        }

        if (muscleRegion && regionLevels[muscleRegion] !== undefined) {
          inheritedLevel = regionLevels[muscleRegion];
          inheritedOverride = 'region';
        }

        setSorenessLevels((prevLevels) => ({ ...prevLevels, [muscle]: inheritedLevel }));
        setOverrideLevels((prev) => ({ ...prev, [muscle]: inheritedOverride }));
        return [...prev, muscle];
      }
    });
  };

  const toggleFullBody = useCallback(() => {
    const allMuscles = ZONE_MAPPING['full body'];
    const isAllSelected = allMuscles.every((m: MuscleGroup) => selectedMuscles.includes(m));

    if (isAllSelected) {
      setSelectedMuscles([]);
      setSorenessLevels({} as Record<MuscleGroup, SorenessLevel>);
      setOverrideLevels({} as Record<MuscleGroup, OverrideLevel>);
      setRegionLevels({} as Record<BodyZone, SorenessLevel>);
    } else {
      setSelectedMuscles(allMuscles);
      const newLevels = { ...sorenessLevels };
      const newOverrides = { ...overrideLevels };
      allMuscles.forEach((m: MuscleGroup) => {
        newLevels[m] = fullBodyDefaultLevel;
        newOverrides[m] = 'full-body';
      });
      setSorenessLevels(newLevels as Record<MuscleGroup, SorenessLevel>);
      setOverrideLevels(newOverrides);
      setFrontLevel(fullBodyDefaultLevel);
      setBackLevel(fullBodyDefaultLevel);
    }
  }, [selectedMuscles, sorenessLevels, fullBodyDefaultLevel, overrideLevels]);

  const handleViewChange = useCallback((newView: 'front' | 'back') => {
    setCurrentView(newView);
  }, []);

  const setMuscleSorenessLevel = (muscle: MuscleGroup, level: number) => {
    setSorenessLevels((prev) => ({
      ...prev,
      [muscle]: level as SorenessLevel,
    }));
    setOverrideLevels((prev) => ({ ...prev, [muscle]: 'manual' }));
  };

  const setRegionSorenessLevel = (zone: BodyZone, level: number) => {
    const muscles = ZONE_MAPPING[zone];
    const newLevels = { ...sorenessLevels };
    const newOverrides = { ...overrideLevels };
    muscles.forEach((m: MuscleGroup) => {
      const currentOverride = overrideLevels[m];
      if (currentOverride !== 'manual') {
        newLevels[m] = level as SorenessLevel;
        newOverrides[m] = 'region';
      }
    });
    setSorenessLevels(newLevels as Record<MuscleGroup, SorenessLevel>);
    setOverrideLevels(newOverrides);
    setRegionLevels((prev) => ({ ...prev, [zone]: level as SorenessLevel }));
  };

  const toggleFront = () => {
    const frontMuscles = ZONE_MAPPING['front'];
    const isAllFrontSelected = frontMuscles.every((m: MuscleGroup) => selectedMuscles.includes(m));

    if (isAllFrontSelected) {
      setSelectedMuscles((prev) => prev.filter((m) => !frontMuscles.includes(m)));
      setSorenessLevels((prev) => {
        const newLevels = { ...prev };
        frontMuscles.forEach((m) => delete newLevels[m]);
        return newLevels;
      });
      setOverrideLevels((prev) => {
        const newOverrides = { ...prev };
        frontMuscles.forEach((m) => delete newOverrides[m]);
        return newOverrides;
      });
    } else {
      setSelectedMuscles((prev) => {
        const filtered = prev.filter((m) => !frontMuscles.includes(m));
        const newLevels = { ...sorenessLevels };
        const newOverrides = { ...overrideLevels };
        frontMuscles.forEach((m) => {
          newLevels[m] = frontLevel;
          newOverrides[m] = 'front-back';
        });
        setSorenessLevels(newLevels);
        setOverrideLevels(newOverrides);
        return [...filtered, ...frontMuscles];
      });
    }
  };

  const toggleBack = () => {
    const backMuscles = ZONE_MAPPING['back'];
    const isAllBackSelected = backMuscles.every((m: MuscleGroup) => selectedMuscles.includes(m));

    if (isAllBackSelected) {
      setSelectedMuscles((prev) => prev.filter((m) => !backMuscles.includes(m)));
      setSorenessLevels((prev) => {
        const newLevels = { ...prev };
        backMuscles.forEach((m) => delete newLevels[m]);
        return newLevels;
      });
      setOverrideLevels((prev) => {
        const newOverrides = { ...prev };
        backMuscles.forEach((m) => delete newOverrides[m]);
        return newOverrides;
      });
    } else {
      setSelectedMuscles((prev) => {
        const filtered = prev.filter((m) => !backMuscles.includes(m));
        const newLevels = { ...sorenessLevels };
        const newOverrides = { ...overrideLevels };
        backMuscles.forEach((m) => {
          newLevels[m] = backLevel;
          newOverrides[m] = 'front-back';
        });
        setSorenessLevels(newLevels);
        setOverrideLevels(newOverrides);
        return [...filtered, ...backMuscles];
      });
    }
  };

  const handleFrontLevelChange = (level: SorenessLevel) => {
    setFrontLevel(level);
    const frontMuscles = ZONE_MAPPING['front'];
    const newLevels = { ...sorenessLevels };
    const newOverrides = { ...overrideLevels };
    frontMuscles.forEach((m: MuscleGroup) => {
      const currentOverride = overrideLevels[m];
      if (selectedMuscles.includes(m) && currentOverride !== 'manual') {
        newLevels[m] = level;
        newOverrides[m] = 'front-back';
      }
    });
    setSorenessLevels(newLevels as Record<MuscleGroup, SorenessLevel>);
    setOverrideLevels(newOverrides);
  };

  const handleBackLevelChange = (level: SorenessLevel) => {
    setBackLevel(level);
    const backMuscles = ZONE_MAPPING['back'];
    const newLevels = { ...sorenessLevels };
    const newOverrides = { ...overrideLevels };
    backMuscles.forEach((m: MuscleGroup) => {
      const currentOverride = overrideLevels[m];
      if (selectedMuscles.includes(m) && currentOverride !== 'manual') {
        newLevels[m] = level;
        newOverrides[m] = 'front-back';
      }
    });
    setSorenessLevels(newLevels as Record<MuscleGroup, SorenessLevel>);
    setOverrideLevels(newOverrides);
  };

  const removeMuscle = (muscle: MuscleGroup) => {
    setSelectedMuscles((prev) => {
      const next = prev.filter((m) => m !== muscle);
      const newLevels = { ...sorenessLevels };
      delete newLevels[muscle];
      setSorenessLevels(newLevels);
      setOverrideLevels((prev) => {
        const newOverrides = { ...prev };
        delete newOverrides[muscle];
        return newOverrides;
      });
      return next;
    });
  };

  const clearAll = () => {
    setSelectedMuscles([]);
    setSorenessLevels({} as Record<MuscleGroup, SorenessLevel>);
    setOverrideLevels({} as Record<MuscleGroup, OverrideLevel>);
    setRegionLevels({} as Record<BodyZone, SorenessLevel>);
    setNotes('');
    setIsFullBodyExpanded(false);
  };

  const handleSubmit = async () => {
    if (selectedMuscles.length === 0) return;

    const musclesWithoutLevel = selectedMuscles.filter((m) => !sorenessLevels[m]);
    if (musclesWithoutLevel.length > 0) {
      alert('Please select a soreness level for all selected muscles');
      return;
    }

    setIsSubmitting(true);
    try {
      const promises = selectedMuscles.map((muscle) =>
        logSorenessMutation.mutateAsync({
          log_date: logDate,
          body_part: muscle,
          soreness_1_5: sorenessLevels[muscle],
          notes: notes || undefined,
        })
      );

      await Promise.all(promises);
      clearAll();
      onSuccess?.();
    } catch (error) {
      console.error('Failed to log soreness:', error);
      alert('Failed to log soreness. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card className={className}>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground leading-tight">Muscle Soreness Tracker</h2>
            <p className="text-sm text-foreground-muted mt-1.5 break-words">
              Select sore muscles and rate your discomfort level
            </p>
          </div>
          {onCancel && (
            <Button variant="ghost" size="icon" onClick={onCancel}>
              <X className="w-5 h-5" />
            </Button>
          )}
        </div>

        <div className="space-y-4">
          <div
            className={cn(
              'bg-background-card border border-border rounded-xl p-4 transition-all',
              isFullBodyExpanded ? 'border-accent/50' : 'hover:border-border/80'
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Button
                  type="button"
                  variant={selectedMuscles.length === ZONE_MAPPING['full body'].length ? 'cta' : 'outline'}
                  onClick={toggleFullBody}
                  className="flex-shrink-0"
                >
                  <User className="w-4 h-4 mr-2" />
                  {selectedMuscles.length === ZONE_MAPPING['full body'].length ? 'Deselect All' : 'Select Full Body'}
                </Button>
                <span className="text-sm text-foreground-muted">
                  Applies to all muscles in front and back
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsFullBodyExpanded(!isFullBodyExpanded)}
                className="p-2 hover:bg-background-secondary rounded-md transition-colors"
              >
                <ChevronLeft className={cn('w-5 h-5 transition-transform', isFullBodyExpanded ? 'rotate-90' : 'rotate-0')} />
              </button>
            </div>
            {isFullBodyExpanded && (
              <div className="mt-4 pt-4 border-t border-border">
                <div className="flex items-center gap-3">
                  <label htmlFor="fullBodyLevel" className="text-sm font-medium text-foreground whitespace-nowrap">
                    Full Body Level:
                  </label>
                  <NumberControl value={fullBodyDefaultLevel} onChange={setFullBodyDefaultLevel} />
                  <span className={cn('text-sm font-medium', SORENESS_LEVELS[fullBodyDefaultLevel].color)}>
                    {SORENESS_LEVELS[fullBodyDefaultLevel].label}
                  </span>
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div
              className={cn(
                'bg-background-card border border-border rounded-lg p-2.5 transition-all',
                'hover:border-border/80'
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <Button
                  type="button"
                  variant={ZONE_MAPPING['front'].every((m: MuscleGroup) => selectedMuscles.includes(m)) ? 'cta' : 'outline'}
                  onClick={toggleFront}
                  className="text-xs px-2.5 py-1.5 h-auto"
                >
                  Front
                </Button>
                {ZONE_MAPPING['front'].some((m: MuscleGroup) => selectedMuscles.includes(m)) && (
                  <div className="flex items-center gap-1">
                    <NumberControl value={frontLevel} onChange={handleFrontLevelChange} />
                  </div>
                )}
                <span className="text-xs text-foreground-muted whitespace-nowrap">
                  {ZONE_MAPPING['front'].filter((m: MuscleGroup) => selectedMuscles.includes(m)).length}/{ZONE_MAPPING['front'].length}
                </span>
              </div>
            </div>

            <div
              className={cn(
                'bg-background-card border border-border rounded-lg p-2.5 transition-all',
                'hover:border-border/80'
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <Button
                  type="button"
                  variant={ZONE_MAPPING['back'].every((m: MuscleGroup) => selectedMuscles.includes(m)) ? 'cta' : 'outline'}
                  onClick={toggleBack}
                  className="text-xs px-2.5 py-1.5 h-auto"
                >
                  Back
                </Button>
                {ZONE_MAPPING['back'].some((m: MuscleGroup) => selectedMuscles.includes(m)) && (
                  <div className="flex items-center gap-1">
                    <NumberControl value={backLevel} onChange={handleBackLevelChange} />
                  </div>
                )}
                <span className="text-xs text-foreground-muted whitespace-nowrap">
                  {ZONE_MAPPING['back'].filter((m: MuscleGroup) => selectedMuscles.includes(m)).length}/{ZONE_MAPPING['back'].length}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-center">
          <HumanBodyMap
            selectedMuscles={selectedMuscles}
            onToggleMuscle={toggleMuscle}
            onViewChange={handleViewChange}
            currentView={currentView}
            className="w-full"
          />
        </div>

        <div className="space-y-4">
          <LoggedMuscles
            selectedMuscles={selectedMuscles}
            sorenessLevels={sorenessLevels}
            onRemoveMuscle={removeMuscle}
            onSetMuscleLevel={setMuscleSorenessLevel}
          />

          <RegionSelector
            selectedMuscles={selectedMuscles}
            sorenessLevels={sorenessLevels}
            onSelectMuscle={toggleMuscle}
            onSetMuscleLevel={setMuscleSorenessLevel}
            onSetRegionLevel={setRegionSorenessLevel}
          />
        </div>

        <div>
          <label htmlFor="notes" className="block text-sm font-medium text-foreground mb-2">
            Notes (optional)
          </label>
          <textarea
            id="notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add any additional notes about your soreness..."
            rows={3}
            className="w-full px-3 py-2 bg-background-input border border-border rounded-lg text-sm text-foreground placeholder-foreground-subtle focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none break-words"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={clearAll}
            disabled={selectedMuscles.length === 0 || isSubmitting}
            className="flex-1"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Clear All
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={selectedMuscles.length === 0 || isSubmitting}
            className="flex-1"
          >
            {isSubmitting ? (
              'Submitting...'
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                Submit Report
              </>
            )}
          </Button>
        </div>
      </div>
    </Card>
  );
}
