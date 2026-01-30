import { useState, useMemo } from 'react';
import { MovementPattern, MovementRuleType, type Movement } from '@/types';
import { useProgramWizardStore } from '@/stores/program-wizard-store';
import { useMovements, useMovementFilters } from '@/api/settings';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Search, ThumbsUp, ThumbsDown, X } from 'lucide-react';

interface MovementsStepProps {
  onAddRule?: (rule: { movement_id: number; rule_type: string; cadence?: string; notes?: string }) => void | Promise<void>;
  onRemoveRule?: (movementId: number) => void | Promise<void>;
  showMessaging?: boolean;
}

export function MovementsStep({ onAddRule, onRemoveRule, showMessaging = true }: MovementsStepProps) {
  const { movementRules, addMovementRule, removeMovementRule } = useProgramWizardStore(); 
  const [search, setSearch] = useState(''); 
  const [selectedPattern, setSelectedPattern] = useState<MovementPattern | 'all'>('all'); 
  const [selectedRegion, setSelectedRegion] = useState<string | 'all'>('all'); 
  const [selectedType, setSelectedType] = useState<'all' | 'compound' | 'accessory'>('all'); 
  const { data: movementsData, isLoading, error } = useMovements({ limit: 1000 }); 
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
 
  const handleSetRule = async (movementId: number, ruleType: MovementRuleType) => {
    const existing = getRule(movementId);
    if (existing?.rule_type === ruleType) {
      removeMovementRule(movementId);
      if (onRemoveRule) {
        await onRemoveRule(movementId);
      }
    } else {
      const rule = { movement_id: movementId, rule_type: ruleType };
      addMovementRule(rule);
      if (onAddRule) {
        await onAddRule(rule);
      }
    }
  }; 
 
  const hardNos = movementRules.filter((r) => r.rule_type === MovementRuleType.HARD_NO); 
  const hardYes = movementRules.filter((r) => r.rule_type === MovementRuleType.HARD_YES); 
  const preferred = movementRules.filter((r) => r.rule_type === MovementRuleType.PREFERRED); 
 
  return ( 
    <div className="flex flex-col h-full min-h-0 space-y-4"> 
      <div className="space-y-3 shrink-0"> 
        <div className="text-center space-y-2"> 
          <h2 className="text-xl font-bold">Movement Preferences</h2> 
          <p className="text-foreground-muted text-sm"> 
            Any exercises you love or want to avoid? This is optional. 
          </p> 
        </div> 
 
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2"> 
          <select 
            value={selectedPattern} 
            onChange={(e) => 
              setSelectedPattern( 
                e.target.value === 'all' 
                  ? 'all' 
                  : (e.target.value as MovementPattern) 
              ) 
            } 
            className="h-9 rounded-lg bg-background-input border-0 px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary" 
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
            className="h-9 rounded-lg bg-background-input border-0 px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary" 
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
            className="h-9 rounded-lg bg-background-input border-0 px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary" 
          > 
            <option value="all">All Types</option> 
            <option value="compound">Compound</option> 
            <option value="accessory">Accessory</option> 
          </select> 
        </div> 
 
        <div className="relative"> 
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" /> 
          <input 
            type="text" 
            placeholder="Search movements..." 
            value={search} 
            onChange={(e) => setSearch(e.target.value)} 
            className="w-full h-10 pl-10 pr-4 rounded-lg bg-background-input border-0 focus:outline-none focus:ring-2 focus:ring-primary text-sm" 
          /> 
        </div> 
 
        {movementRules.length > 0 && ( 
          <Card variant="grouped" className="p-4 space-y-3"> 
            <p className="text-sm font-medium">Your preferences:</p> 
 
            {hardYes.length > 0 && ( 
              <div className="flex flex-wrap gap-2"> 
                {hardYes.map((rule) => ( 
                  <span 
                    key={rule.movement_id} 
                    className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-cta/20 text-cta" 
                  > 
                    <span className="inline-flex items-center"> 
                      <ThumbsUp className="h-3 w-3" /> 
                      <ThumbsUp className="h-3 w-3 -ml-1" /> 
                    </span> 
                    Movement #{rule.movement_id} 
                    <button onClick={() => handleSetRule(rule.movement_id, MovementRuleType.HARD_YES)}> 
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
                    className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-primary/20 text-primary" 
                  > 
                    <ThumbsUp className="h-3 w-3" /> 
                    Movement #{rule.movement_id} 
                    <button onClick={() => handleSetRule(rule.movement_id, MovementRuleType.PREFERRED)}> 
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
                    className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-error/20 text-error" 
                  > 
                    <ThumbsDown className="h-3 w-3" /> 
                    Movement #{rule.movement_id} 
                    <button onClick={() => handleSetRule(rule.movement_id, MovementRuleType.HARD_NO)}> 
                      <X className="h-3 w-3" /> 
                    </button>
                  </span> 
                ))} 
              </div> 
            )} 
          </Card> 
        )} 
      </div> 
 
      <div className="flex-1 overflow-y-auto space-y-2"> 
        {isLoading ? ( 
          <div className="text-center py-8 text-foreground-muted">Loading movements...</div> 
        ) : error ? ( 
          <div className="text-center py-8 text-foreground-muted"> 
            Failed to load movements. Please check your connection. 
          </div> 
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
                          ? "bg-cta text-white" 
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
                          ? "bg-primary text-white" 
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
                          ? "bg-error text-white" 
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
 
      {showMessaging && (
        <p className="text-center text-xs text-foreground-subtle">
          💡 This is optional. Jerome will select appropriate exercises based on your goals.
        </p>
      )} 
    </div> 
  ); 
}