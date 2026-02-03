import { useEffect, useState, useMemo } from 'react';
import { MovementsStep } from '@/components/wizard/MovementsStep';
import { useUserMovementRules, useUpsertMovementRule, useDeleteMovementRule } from '@/api/movement-preferences';
import { useProgramWizardStore } from '@/stores/program-wizard-store';

export function FavoritesTab() {
  const { data: userPreferences, isLoading: isLoadingPreferences } = useUserMovementRules();
  const upsertMutation = useUpsertMovementRule();
  const deleteMutation = useDeleteMovementRule();
  const { movementRules, setMovementRules, addMovementRule, removeMovementRule } = useProgramWizardStore();

  const [preferenceIdMap, setPreferenceIdMap] = useState<Map<string, number>>(new Map());

  const wizardPreferences = useMemo(() => {
    if (!userPreferences?.items) return [];
    return userPreferences.items.map((pref) => ({
      movement_id: pref.movement_id,
      rule_type: pref.rule_type,
      cadence: pref.cadence || undefined,
      notes: pref.notes || undefined,
    }));
  }, [userPreferences]);

  const preferenceIdMapData = useMemo(() => {
    if (!userPreferences?.items) return new Map<string, number>();
    const newMap = new Map<string, number>();
    userPreferences.items.forEach((pref) => {
      const key = `${pref.movement_id}-${pref.rule_type}`;
      newMap.set(key, pref.id);
    });
    return newMap;
  }, [userPreferences]);

  useEffect(() => {
    setMovementRules(wizardPreferences);
  }, [wizardPreferences, setMovementRules]);

  useEffect(() => {
    setPreferenceIdMap(preferenceIdMapData);
  }, [preferenceIdMapData]);

  const handleAddRule = async (rule: { movement_id: number; rule_type: string; cadence?: string; notes?: string }) => {
    addMovementRule(rule);
    const response = await upsertMutation.mutateAsync(rule);
    
    const key = `${rule.movement_id}-${rule.rule_type}`;
    setPreferenceIdMap((prev) => new Map(prev).set(key, response.id));
  };

  const handleRemoveRule = async (movementId: number) => {
    const rule = movementRules.find((r) => r.movement_id === movementId);
    if (rule) {
      const key = `${rule.movement_id}-${rule.rule_type}`;
      const preferenceId = preferenceIdMap.get(key);
      
      removeMovementRule(movementId);
      
      if (preferenceId) {
        await deleteMutation.mutateAsync(preferenceId);
        setPreferenceIdMap((prev) => {
          const newMap = new Map(prev);
          newMap.delete(key);
          return newMap;
        });
      }
    }
  };

  return (
    <div className="h-[75vh] flex flex-col min-h-0">
      {isLoadingPreferences ? (
        <div className="flex-1 flex items-center justify-center text-foreground-muted">
          Loading your preferences...
        </div>
      ) : (
        <>
          <div className="shrink-0 mb-4 p-3 bg-cta/10 border border-cta/20 rounded-lg">
            <p className="text-sm text-cta">
              <span className="font-medium">Note:</span> Changes to your favorites here will apply to
              <span className="font-semibold">future programs</span> you create. Existing programs
              will not be affected.
            </p>
          </div>
          <MovementsStep 
            onAddRule={handleAddRule}
            onRemoveRule={handleRemoveRule}
            showMessaging={false}
          />
        </>
      )}
    </div>
  );
}
