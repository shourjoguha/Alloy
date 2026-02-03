import { useState, useMemo } from 'react';
import { MovementPattern, MovementRuleType, type Movement } from '@/types';
import { useProgramWizardStore } from '@/stores/program-wizard-store';
import { useMovements, useMovementFilters } from '@/api/settings';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Search, ThumbsUp, ThumbsDown, X, Plus, Layers, Dumbbell } from 'lucide-react';

const ACTIVITY_CATEGORIES = [
  {
    category: 'sports',
    name: 'Sports',
    activities: [
      { type: 'basketball', name: 'Basketball', icon: '🏀' },
      { type: 'soccer', name: 'Soccer', icon: '⚽' },
      { type: 'tennis', name: 'Tennis', icon: '🎾' },
      { type: 'golf', name: 'Golf', icon: '⛳' },
      { type: 'swimming', name: 'Swimming', icon: '🏊' },
      { type: 'martial_arts', name: 'Martial Arts', icon: '🥋' },
    ],
  },
  {
    category: 'cardio',
    name: 'Cardio',
    activities: [
      { type: 'running', name: 'Running', icon: '🏃' },
      { type: 'cycling', name: 'Cycling', icon: '🚴' },
      { type: 'rowing', name: 'Rowing', icon: '🚣' },
      { type: 'hiking', name: 'Hiking', icon: '🥾' },
      { type: 'jump_rope', name: 'Jump Rope', icon: '⏱️' },
    ],
  },
  {
    category: 'recovery',
    name: 'Recovery',
    activities: [
      { type: 'yoga', name: 'Yoga', icon: '🧘' },
      { type: 'stretching', name: 'Stretching', icon: '🤸' },
      { type: 'walking', name: 'Walking', icon: '🚶' },
      { type: 'foam_rolling', name: 'Foam Rolling', icon: '🛢️' },
      { type: 'sauna', name: 'Sauna', icon: '🧖' },
    ],
  },
] as const;

function SectionCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn(
      "rounded-2xl border-2 bg-gradient-to-br from-background-secondary to-background",
      "shadow-lg",
      className
    )}>
      {children}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, description }: { icon: React.ComponentType<{ className?: string }>; title: string; description: string }) {
  return (
    <div className="space-y-3 pb-4 border-b border-border">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 flex items-center justify-center">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-lg font-bold">{title}</h2>
          <p className="text-sm text-foreground-muted">{description}</p>
        </div>
      </div>
    </div>
  );
}

export function ActivitiesAndMovementsStep() {
  const { movementRules, addMovementRule, removeMovementRule, enjoyableActivities, addEnjoyableActivity, removeEnjoyableActivity } = useProgramWizardStore();
  const [showMovementPreferences, setShowMovementPreferences] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedPattern, setSelectedPattern] = useState<MovementPattern | 'all'>('all');
  const [selectedRegion, setSelectedRegion] = useState<string | 'all'>('all');
  const [selectedType, setSelectedType] = useState<'all' | 'compound' | 'accessory'>('all');
  const [customActivity, setCustomActivity] = useState('');
  const [customMovement, setCustomMovement] = useState('');
  const { data: movementsData, isLoading: movementsLoading } = useMovements({ limit: 1000 });
  const { data: filtersData } = useMovementFilters();

  const movements: Movement[] = movementsData?.movements ?? [];

  const patternOptions = useMemo<string[]>(
    () => filtersData?.patterns ?? [],
    [filtersData],
  );

  const regionOptions = useMemo<string[]>(
    () => filtersData?.regions ?? [],
    [filtersData],
  );

  const filteredMovements = movements.filter((movement: Movement) => {
    const matchesSearch = movement.name
      .toLowerCase()
      .includes(search.toLowerCase());

    const matchesPattern =
      selectedPattern === 'all' ||
      movement.primary_pattern === selectedPattern;

    const matchesRegion =
      selectedRegion === 'all' ||
      (movement.primary_region && movement.primary_region === selectedRegion);

    const matchesType =
      selectedType === 'all' ||
      (selectedType === 'compound' && movement.is_compound) ||
      (selectedType === 'accessory' && movement.is_compound === false);

    return matchesSearch && matchesPattern && matchesRegion && matchesType;
  });

  const getRule = (movementId: number) => {
    return movementRules.find((r) => r.movement_id === movementId);
  };

  const handleSetRule = (movementId: number, ruleType: MovementRuleType) => {
    const existing = getRule(movementId);
    if (existing?.rule_type === ruleType) {
      removeMovementRule(movementId);
    } else {
      addMovementRule({ movement_id: movementId, rule_type: ruleType });
    }
  };

  const isSelectedActivity = (activityType: string) => {
    return enjoyableActivities.some((a) => a.activity_type === activityType);
  };

  const toggleActivity = (activityType: string) => {
    if (isSelectedActivity(activityType)) {
      removeEnjoyableActivity(activityType);
    } else {
      addEnjoyableActivity({ activity_type: activityType });
    }
  };

  const addCustomActivity = () => {
    if (customActivity.trim()) {
      addEnjoyableActivity({
        activity_type: 'custom',
        custom_name: customActivity.trim(),
      });
      setCustomActivity('');
    }
  };

  const addCustomMovement = () => {
    if (customMovement.trim()) {
      addMovementRule({
        movement_id: 0,
        rule_type: 'preferred' as MovementRuleType,
      });
      setCustomMovement('');
    }
  };

  const hardNos = movementRules.filter((r) => r.rule_type === MovementRuleType.HARD_NO);
  const hardYes = movementRules.filter((r) => r.rule_type === MovementRuleType.HARD_YES);
  const preferred = movementRules.filter((r) => r.rule_type === MovementRuleType.PREFERRED);

  return (
    <div className="flex flex-col h-full min-h-0 space-y-4">
      <div className="space-y-4 shrink-0">
        <div className="text-center space-y-2">
          <h2 className="text-xl font-bold">Personalize Your Program</h2>
          <p className="text-foreground-muted text-sm">
            Tell Jerome about your preferences for a better experience
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Activities Section */}
        <SectionCard className="p-5">
          <SectionHeader
            icon={Layers}
            title="What activities do you enjoy?"
            description="Jerome will suggest these on rest days and work around your schedule"
          />

          <div className="space-y-4">
            {enjoyableActivities.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {enjoyableActivities.map((activity) => (
                  <span
                    key={activity.activity_type + (activity.custom_name || '')}
                    className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-full bg-primary/10 text-primary border border-primary/20"
                  >
                    {activity.custom_name || activity.activity_type}
                    <button
                      onClick={() => removeEnjoyableActivity(activity.activity_type)}
                      className="hover:bg-primary/20 rounded-full p-0.5 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            {ACTIVITY_CATEGORIES.map((category) => (
              <div key={category.category} className="space-y-3">
                <h3 className="text-sm font-medium text-foreground-muted uppercase tracking-wide">{category.name}</h3>
                <div className="flex flex-wrap gap-2">
                  {category.activities.map((activity) => (
                    <button
                      key={activity.type}
                      onClick={() => toggleActivity(activity.type)}
                      className={cn(
                        "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all",
                        isSelectedActivity(activity.type)
                          ? "bg-primary text-white shadow-lg shadow-primary/30"
                          : "bg-background-input hover:bg-background-secondary text-foreground"
                      )}
                    >
                      <span>{activity.icon}</span>
                      <span>{activity.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}

            <div className="space-y-3 pt-3 border-t border-border">
              <h3 className="text-sm font-medium text-foreground-muted uppercase tracking-wide">Something else?</h3>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Add custom activity..."
                  value={customActivity}
                  onChange={(e) => setCustomActivity(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addCustomActivity()}
                  className="flex-1 h-10 px-4 rounded-lg bg-background-input border-0 focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                />
                <button
                  onClick={addCustomActivity}
                  disabled={!customActivity.trim()}
                  className={cn(
                    "h-10 w-10 rounded-lg flex items-center justify-center transition-colors",
                    customActivity.trim()
                      ? "bg-primary text-white shadow-lg shadow-primary/30"
                      : "bg-background-input text-foreground-subtle cursor-not-allowed"
                  )}
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </SectionCard>

        {/* Movement Preferences Section */}
        <SectionCard className="p-5">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-4 border-b border-border">
              <div className="flex items-center gap-3 flex-1">
                <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-accent/20 to-accent/10 flex items-center justify-center">
                  <Dumbbell className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <h2 className="text-lg font-bold">Exercise Preferences</h2>
                  <p className="text-sm text-foreground-muted">
                    Customize which exercises you love or want to avoid
                  </p>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setShowMovementPreferences(false)}
                  className={cn(
                    "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                    !showMovementPreferences
                      ? "bg-accent text-white shadow-lg shadow-accent/30"
                      : "bg-background-input hover:bg-background-secondary text-foreground"
                  )}
                >
                  No
                </button>
                <button
                  onClick={() => setShowMovementPreferences(true)}
                  className={cn(
                    "px-4 py-2 rounded-lg text-sm font-medium transition-all",
                    showMovementPreferences
                      ? "bg-accent text-white shadow-lg shadow-accent/30"
                      : "bg-background-input hover:bg-background-secondary text-foreground"
                  )}
                >
                  Yes
                </button>
              </div>
            </div>

            {showMovementPreferences && (
              <div className="space-y-4">
                <div className="flex gap-2">
                  <select
                    value={selectedPattern}
                    onChange={(e) =>
                      setSelectedPattern(
                        e.target.value === 'all'
                          ? 'all'
                          : (e.target.value as MovementPattern)
                      )
                    }
                    className="flex-1 h-10 rounded-lg bg-background-input border-0 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="all">All Patterns</option>
                    {patternOptions.map((pattern) => (
                      <option key={pattern} value={pattern}>
                        {pattern.replace('_', ' ')}
                      </option>
                    ))}
                  </select>

                  <select
                    value={selectedRegion}
                    onChange={(e) => setSelectedRegion(e.target.value as typeof selectedRegion)}
                    className="flex-1 h-10 rounded-lg bg-background-input border-0 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="all">All Body Parts</option>
                    {regionOptions.map((region) => (
                      <option key={region} value={region}>
                        {region.replace('_', ' ')}
                      </option>
                    ))}
                  </select>

                  <select
                    value={selectedType}
                    onChange={(e) =>
                      setSelectedType(e.target.value as 'all' | 'compound' | 'accessory')
                    }
                    className="flex-1 h-10 rounded-lg bg-background-input border-0 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="all">All Types</option>
                    <option value="compound">Compound</option>
                    <option value="accessory">Accessory</option>
                  </select>
                </div>

                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" />
                    <input
                      type="text"
                      placeholder="Search movements..."
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="w-full h-10 pl-10 pr-4 rounded-lg bg-background-input border-0 focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                    />
                  </div>
                  <input
                    type="text"
                    placeholder="Add custom movement..."
                    value={customMovement}
                    onChange={(e) => setCustomMovement(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addCustomMovement()}
                    className="flex-1 h-10 px-4 rounded-lg bg-background-input border-0 focus:outline-none focus:ring-2 focus:ring-primary text-sm"
                  />
                  <button
                    onClick={addCustomMovement}
                    disabled={!customMovement.trim()}
                    className={cn(
                      "h-10 w-10 rounded-lg flex items-center justify-center transition-colors",
                      customMovement.trim()
                        ? "bg-primary text-white shadow-lg shadow-primary/30"
                        : "bg-background-input text-foreground-subtle cursor-not-allowed"
                    )}
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                </div>

                {movementRules.length > 0 && (
                  <Card variant="grouped" className="p-4 space-y-3">
                    <p className="text-sm font-medium">Your preferences:</p>

                    {hardYes.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {hardYes.map((rule) => (
                          <span
                            key={rule.movement_id}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-cta/20 text-cta border border-cta/30"
                          >
                            <span className="inline-flex items-center">
                              <ThumbsUp className="h-3 w-3" />
                              <ThumbsUp className="h-3 w-3 -ml-1" />
                            </span>
                            Movement #{rule.movement_id}
                            <button onClick={() => removeMovementRule(rule.movement_id)}>
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}

                    {preferred.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {preferred.map((rule) => (
                          <span
                            key={rule.movement_id}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-primary/20 text-primary border border-primary/30"
                          >
                            <ThumbsUp className="h-3 w-3" />
                            Movement #{rule.movement_id}
                            <button onClick={() => removeMovementRule(rule.movement_id)}>
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}

                    {hardNos.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {hardNos.map((rule) => (
                          <span
                            key={rule.movement_id}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-error/20 text-error border border-error/30"
                          >
                            <ThumbsDown className="h-3 w-3" />
                            Movement #{rule.movement_id}
                            <button onClick={() => removeMovementRule(rule.movement_id)}>
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </Card>
                )}

                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {movementsLoading ? (
                    <div className="text-center py-8 text-foreground-muted">Loading movements...</div>
                  ) : filteredMovements.length === 0 ? (
                    <div className="text-center py-8 text-foreground-muted">
                      No movements match your filters.
                    </div>
                  ) : (
                    filteredMovements.map((movement) => {
                      const rule = getRule(movement.id);
                      return (
                        <Card key={movement.id} className="p-3">
                          <div className="flex items-center gap-3">
                            <div className="flex-1 min-w-0">
                              <h4 className="font-medium text-sm">{movement.name}</h4>
                              <p className="text-xs text-foreground-muted">
                                {movement.primary_pattern} • {movement.default_equipment ?? 'Any equipment'}
                              </p>
                            </div>
                            <div className="flex gap-1">
                              <button
                                onClick={() => handleSetRule(movement.id, MovementRuleType.HARD_YES)}
                                className={cn(
                                  "h-8 w-8 rounded-lg flex items-center justify-center transition-colors",
                                  rule?.rule_type === MovementRuleType.HARD_YES
                                    ? "bg-cta text-white shadow-lg shadow-cta/30"
                                    : "bg-background-input hover:bg-cta/20 text-foreground-muted"
                                )}
                                title="Must include"
                              >
                                <span className="flex items-center">
                                  <ThumbsUp className="h-4 w-4" />
                                  <ThumbsUp className="h-4 w-4 -ml-1" />
                                </span>
                              </button>
                              <button
                                onClick={() => handleSetRule(movement.id, MovementRuleType.PREFERRED)}
                                className={cn(
                                  "h-8 w-8 rounded-lg flex items-center justify-center transition-colors",
                                  rule?.rule_type === MovementRuleType.PREFERRED
                                    ? "bg-primary text-white shadow-lg shadow-primary/30"
                                    : "bg-background-input hover:bg-primary/20 text-foreground-muted"
                                )}
                                title="Prefer"
                              >
                                <ThumbsUp className="h-4 w-4" />
                              </button>
                              <button
                                onClick={() => handleSetRule(movement.id, MovementRuleType.HARD_NO)}
                                className={cn(
                                  "h-8 w-8 rounded-lg flex items-center justify-center transition-colors",
                                  rule?.rule_type === MovementRuleType.HARD_NO
                                    ? "bg-error text-white shadow-lg shadow-error/30"
                                    : "bg-background-input hover:bg-error/20 text-foreground-muted"
                                )}
                                title="Never include"
                              >
                                <ThumbsDown className="h-4 w-4" />
                              </button>
                            </div>
                          </div>
                        </Card>
                      );
                    })
                  )}
                </div>
              </div>
            )}

            {!showMovementPreferences && (
              <p className="text-center text-xs text-foreground-muted pt-3">
                💡 Jerome will select appropriate exercises based on your goals.
              </p>
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
