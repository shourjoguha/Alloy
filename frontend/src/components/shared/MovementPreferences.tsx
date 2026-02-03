import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMovements } from '@/api/settings';
import { apiClient } from '@/api/client';

import { 
  MovementPattern, 
  PrimaryRegion, 
  MovementRuleType,
  MovementRuleCreate,
  MovementRule,
  Movement
} from '@/types';

import { 
  ChevronDown, 
  ChevronUp, 
  ThumbsUp, 
  ThumbsDown,
  Search,
  Filter,
  Star
} from 'lucide-react';

export interface MovementPreferencesProps {
  onSelectionChange?: (selectedMovements: MovementRule[]) => void;
}

export function MovementPreferences({ onSelectionChange }: MovementPreferencesProps) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [selectedPattern, setSelectedPattern] = useState<MovementPattern | null>(null);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<'compound' | 'isolation' | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  const { data: movementsData, isLoading: movementsLoading } = useMovements({
    limit: 1000
  });
  
  const movements: Movement[] = movementsData?.movements ?? [];

  const { data: userRules, isLoading: rulesLoading } = useQuery({
    queryKey: ['user-movement-rules'],
    queryFn: async () => {
      const { data } = await apiClient.get('/settings/movement-rules');
      return data as MovementRule[];
    },
    staleTime: 2 * 60 * 1000,
  });

  const createRuleMutation = useMutation({
    mutationFn: async (data: MovementRuleCreate) => {
      const { data: response } = await apiClient.post('/settings/movement-rules', data);
      return response as MovementRule;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-movement-rules'] });
    },
  });

  const deleteRuleMutation = useMutation({
    mutationFn: async (ruleId: number) => {
      await apiClient.delete(`/settings/movement-rules/${ruleId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-movement-rules'] });
    },
  });

  const getMovementRule = (movementId: number) => {
    return userRules?.find((r: MovementRule) => r.movement_id === movementId);
  };

  const handlePreferenceChange = async (movementId: number, ruleType: MovementRuleType | null) => {
    const existingRule = getMovementRule(movementId);

    if (ruleType === null || ruleType === MovementRuleType.HARD_NO) {
      if (existingRule) {
        await deleteRuleMutation.mutateAsync(existingRule.id);
      }
    } else {
      const ruleData: MovementRuleCreate = {
        movement_id: movementId,
        rule_type: ruleType,
        cadence: 'PER_MICROCYCLE',
        notes: ''
      };
      
      if (existingRule) {
        await deleteRuleMutation.mutateAsync(existingRule.id);
      }
      await createRuleMutation.mutateAsync(ruleData);
    }
  };

  const getFilteredMovements = () => {
    return movements.filter((m: Movement) => {
      if (selectedPattern && m.primary_pattern !== selectedPattern) return false;
      if (selectedRegion && m.primary_region !== selectedRegion) return false;
      if (selectedType) {
        if (selectedType === 'compound' && !m.is_compound) return false;
        if (selectedType === 'isolation' && m.is_compound) return false;
      }
      if (search && !m.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  };

  const getSortedMovements = () => {
    const filtered = getFilteredMovements();
    
    return filtered.sort((a: Movement, b: Movement) => {
      const ruleA = getMovementRule(a.id);
      const ruleB = getMovementRule(b.id);
      
      const priorityA = ruleA ? getRulePriority(ruleA.rule_type) : -1;
      const priorityB = ruleB ? getRulePriority(ruleB.rule_type) : -1;
      
      if (priorityA !== priorityB) {
        return priorityB - priorityA;
      }
      
      return a.name.localeCompare(b.name);
    });
  };

  const getRulePriority = (ruleType?: string): number => {
    switch (ruleType) {
      case 'HARD_YES': return 3;
      case 'PREFERRED': return 2;
      case 'HARD_NO': return 1;
      default: return 0;
    }
  };

  const selectedMovements = useMemo(() => {
    if (!userRules) return [];
    return userRules.filter((r: MovementRule) => r.rule_type !== 'HARD_NO');
  }, [userRules]);

  useEffect(() => {
    if (onSelectionChange) {
      onSelectionChange(selectedMovements);
    }
  }, [selectedMovements, onSelectionChange]);

  if (movementsLoading || rulesLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const sortedMovements = getSortedMovements();

  return (
    <div className="space-y-6">
      {selectedMovements.length > 0 && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
          <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-blue-900 dark:text-blue-100">
            <Star className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            Your Selected Movements ({selectedMovements.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {selectedMovements.map((rule: MovementRule) => {
              const movement = movements.find((m: Movement) => m.id === rule.movement_id);
              if (!movement) return null;
              
              return (
                <div
                  key={rule.id}
                  className="flex items-center gap-2 bg-background-card rounded-lg p-2 text-sm"
                >
                  <span className="text-primary font-medium">
                    {rule.rule_type === 'HARD_YES' && '👍👍'}
                    {rule.rule_type === 'PREFERRED' && '👍'}
                  </span>
                  <span className="text-foreground truncate">
                    {movement.name}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4 flex-1">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-foreground-muted" />
            <input
              type="text"
              placeholder="Search movements..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 w-full border border-border rounded-lg focus:ring-2 focus:ring-primary bg-background-input text-foreground"
            />
          </div>
          
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 border border-border rounded-lg hover:bg-background-secondary text-foreground"
          >
            <Filter className="h-4 w-4" />
            Filters
            {showFilters ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {showFilters && (
        <div className="bg-background-card rounded-lg p-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            <span className="text-sm font-medium text-foreground">Pattern:</span>
            {Object.values(MovementPattern).map(pattern => (
              <button
                key={pattern}
                onClick={() => setSelectedPattern(selectedPattern === pattern ? null : pattern)}
                className={`px-3 py-1 rounded-full text-sm ${
                  selectedPattern === pattern
                    ? 'bg-primary text-background'
                    : 'bg-background-input text-foreground hover:bg-background-secondary'
                }`}
              >
                {pattern.replace('_', ' ')}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="text-sm font-medium text-foreground">Region:</span>
            {Object.values(PrimaryRegion).map(region => (
              <button
                key={region}
                onClick={() => setSelectedRegion(selectedRegion === region ? null : region)}
                className={`px-3 py-1 rounded-full text-sm ${
                  selectedRegion === region
                    ? 'bg-primary text-background'
                    : 'bg-background-input text-foreground hover:bg-background-secondary'
                }`}
              >
                {region.replace('_', ' ')}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="text-sm font-medium text-foreground">Type:</span>
            {[
              { value: 'compound' as const, label: 'Compound' },
              { value: 'isolation' as const, label: 'Isolation' },
            ].map(type => (
              <button
                key={type.value}
                onClick={() => setSelectedType(selectedType === type.value ? null : type.value)}
                className={`px-3 py-1 rounded-full text-sm ${
                  selectedType === type.value
                    ? 'bg-primary text-background'
                    : 'bg-background-input text-foreground hover:bg-background-secondary'
                }`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        {sortedMovements.map((movement: Movement) => {
          const rule = getMovementRule(movement.id);
          const ruleType = rule?.rule_type;

          return (
            <div
              key={movement.id}
              className="flex items-center justify-between p-4 bg-background-card rounded-lg border border-border hover:border-primary transition-colors"
            >
              <div className="flex-1">
                <div className="font-medium text-foreground">
                  {movement.name}
                </div>
                <div className="flex items-center gap-2 mt-1 text-sm text-foreground-muted">
                  <span>{movement.primary_pattern?.replace('_', ' ')}</span>
                  <span>•</span>
                  <span>{movement.primary_region?.replace('_', ' ')}</span>
                  <span>•</span>
                  <span>{movement.is_compound ? 'Compound' : 'Isolation'}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePreferenceChange(movement.id, MovementRuleType.HARD_YES)}
                  className={`p-2 rounded-lg transition-all ${
                    ruleType === 'HARD_YES'
                      ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 scale-110'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 hover:bg-green-50 dark:hover:bg-green-900/20'
                  }`}
                  title="Strongly prefer (double thumbs up)"
                >
                  <ThumbsUp className="h-5 w-5" />
                </button>

                <button
                  onClick={() => handlePreferenceChange(movement.id, MovementRuleType.PREFERRED)}
                  className={`p-2 rounded-lg transition-all ${
                    ruleType === 'PREFERRED'
                      ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 scale-110'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 hover:bg-blue-50 dark:hover:bg-blue-900/20'
                  }`}
                  title="Prefer (single thumbs up)"
                >
                  <div className="flex items-center gap-1">
                    <ThumbsUp className="h-5 w-5" />
                    <span className="text-xs font-medium">1</span>
                  </div>
                </button>

                <button
                  onClick={() => handlePreferenceChange(movement.id, MovementRuleType.HARD_NO)}
                  className={`p-2 rounded-lg transition-all ${
                    ruleType === 'HARD_NO'
                      ? 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 scale-110'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-500 hover:bg-red-50 dark:hover:bg-red-900/20'
                  }`}
                  title="Exclude (thumbs down)"
                >
                  <ThumbsDown className="h-5 w-5" />
                </button>
              </div>
            </div>
          );
        })}

        {sortedMovements.length === 0 && (
          <div className="text-center py-12 text-gray-500 dark:text-gray-400">
            No movements match your filters
          </div>
        )}
      </div>
    </div>
  );
}
