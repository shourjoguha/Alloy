import { useMemo, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Filter, Search, Settings2, Plus, ArrowUp, ArrowDown, User, X } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useMovements, useCreateMovement, useMovementFilters } from '@/api/settings';
import { useCircuits } from '@/api/circuits';
import { 
  MovementPattern, 
  PrimaryRegion, 
  PrimaryMuscle, 
  SkillLevel, 
  CNSLoad, 
  MetricType,
  type Movement, 
  type MovementCreate,
  CircuitType, 
  type CircuitTemplate
} from '@/types';
import { cn } from '@/lib/utils';
import { Flame, Clock, ListChecks, ChevronDown, ChevronRight } from 'lucide-react';

export const Route = createFileRoute('/library')({
  component: LibraryPage,
});

type ColumnId =
  | 'name'
  | 'primary_pattern'
  | 'primary_region'
  | 'primary_muscle'
  | 'secondary_muscles'
  | 'equipment_tags'
  | 'skill_level'
  | 'is_compound'
  | 'cns_load'
  | 'metric_type'
  | 'user_id';

interface ColumnConfig {
  id: ColumnId;
  label: string;
  render: (movement: Movement) => React.ReactNode;
}

const ALL_COLUMNS: ColumnConfig[] = [
  {
    id: 'name',
    label: 'Name',
    render: (m) => (
      <div className="flex items-center gap-2">
        <span className="font-medium">{m.name}</span>
        {m.user_id && (
          <span title="Custom Movement" className="text-primary">
            <User className="h-3 w-3" />
          </span>
        )}
      </div>
    ),
  },
  {
    id: 'primary_pattern',
    label: 'Pattern',
    render: (m) => <span className="capitalize">{m.primary_pattern?.replace('_', ' ')}</span>,
  },
  {
    id: 'primary_region',
    label: 'Region',
    render: (m) => <span className="capitalize">{m.primary_region?.replace('_', ' ')}</span>,
  },
  {
    id: 'primary_muscle',
    label: 'Primary Muscle',
    render: (m) => <span className="capitalize">{m.primary_muscles?.[0]?.replace('_', ' ')}</span>,
  },
  {
    id: 'secondary_muscles',
    label: 'Secondary Muscles',
    render: (m) => (
      <div className="flex flex-wrap gap-1">
        {m.secondary_muscles?.slice(0, 3).map(muscle => (
          <span key={muscle} className="text-[10px] px-1.5 py-0.5 bg-background border border-border rounded-full capitalize">
            {muscle.replace('_', ' ')}
          </span>
        ))}
        {(m.secondary_muscles?.length ?? 0) > 3 && (
          <span className="text-[10px] px-1.5 py-0.5 text-foreground-muted">
            +{m.secondary_muscles!.length - 3} more
          </span>
        )}
      </div>
    ),
  },
  {
    id: 'equipment_tags',
    label: 'Equipment Tags',
    render: (m) => (m.equipment_tags && m.equipment_tags.length > 0 ? m.equipment_tags.join(', ') : ''),
  },
  {
    id: 'skill_level',
    label: 'Skill Level',
    render: (m) => m.skill_level ?? '',
  },
  {
    id: 'is_compound',
    label: 'Compound',
    render: (m) => (m.is_compound != null ? (m.is_compound ? 'Yes' : 'No') : ''),
  },
  {
    id: 'cns_load',
    label: 'CNS Load',
    render: (m) => m.cns_load ?? '',
  },
  {
    id: 'metric_type',
    label: 'Metric Type',
    render: (m) => m.metric_type ?? '',
  },
];

const DEFAULT_VISIBLE_COLUMNS: ColumnId[] = [
  'name',
  'primary_pattern',
  'primary_region',
  'equipment_tags',
  'is_compound',
];

type SortConfig = {
  key: ColumnId;
  direction: 'asc' | 'desc';
} | null;

function AddMovementModal({ onClose, equipmentOptions }: { onClose: () => void; equipmentOptions: string[] }) {
  const createMutation = useCreateMovement();
  const [formData, setFormData] = useState<MovementCreate>({
    name: '',
    primary_pattern: MovementPattern.SQUAT,
    is_compound: true,
    default_equipment: 'Barbell',
    primary_region: PrimaryRegion.ANTERIOR_LOWER,
    primary_muscles: [PrimaryMuscle.QUADRICEPS],
    secondary_muscles: [],
    equipment_tags: [],
    complexity: 3,
    skill_level: SkillLevel.INTERMEDIATE,
    cns_load: CNSLoad.MODERATE,
    metric_type: MetricType.REPS,
  });
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name) {
      setError('Name is required');
      return;
    }
    try {
      await createMutation.mutateAsync(formData);
      onClose();
    } catch {
      setError('Failed to create movement. Name might be taken.');
    }
  };

  const toggleSecondaryMuscle = (muscle: PrimaryMuscle) => {
    setFormData(prev => {
      const current = prev.secondary_muscles || [];
      if (current.includes(muscle)) {
        return { ...prev, secondary_muscles: current.filter(m => m !== muscle) };
      } else {
        return { ...prev, secondary_muscles: [...current, muscle] };
      }
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="w-full max-w-3xl flex flex-col max-h-[85vh] rounded-lg bg-white border border-border shadow-xl">
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="text-xl font-bold text-foreground">Add Custom Movement</h2>
          <button onClick={onClose} className="text-foreground-muted hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 rounded bg-error/10 p-3 text-sm text-error">
              {error}
            </div>
          )}

          <form id="create-movement-form" onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="col-span-1 md:col-span-2">
                <label className="mb-1.5 block text-sm font-medium text-foreground">Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="e.g. My Custom Squat"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">Pattern</label>
                <select
                  value={formData.primary_pattern}
                  onChange={(e) => setFormData({ ...formData, primary_pattern: e.target.value as MovementPattern })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary capitalize"
                >
                  {Object.values(MovementPattern).map((p) => (
                    <option key={p} value={p}>{p.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">Region</label>
                <select
                  value={formData.primary_region}
                  onChange={(e) => setFormData({ ...formData, primary_region: e.target.value as PrimaryRegion })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary capitalize"
                >
                  {Object.values(PrimaryRegion).map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">Primary Muscle</label>
                <select
                  value={formData.primary_muscles?.[0] || ''}
                  onChange={(e) => setFormData({ ...formData, primary_muscles: [e.target.value as PrimaryMuscle] })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary capitalize"
                >
                  <option value="">Select Primary Muscle</option>
                  {Object.values(PrimaryMuscle).map((m) => (
                    <option key={m} value={m}>{m.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">Equipment</label>
                <select
                  value={formData.default_equipment}
                  onChange={(e) => setFormData({ ...formData, default_equipment: e.target.value })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">Select Equipment</option>
                  {equipmentOptions.filter(e => e !== 'all').map((e) => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                  <option value="Other">Other</option>
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">Skill Level</label>
                <select
                  value={formData.skill_level}
                  onChange={(e) => setFormData({ ...formData, skill_level: e.target.value as SkillLevel })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary capitalize"
                >
                  {Object.values(SkillLevel).map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">CNS Load</label>
                <select
                  value={formData.cns_load}
                  onChange={(e) => setFormData({ ...formData, cns_load: e.target.value as CNSLoad })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary capitalize"
                >
                  {Object.values(CNSLoad).map((l) => (
                    <option key={l} value={l}>{l.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-foreground">Metric Type</label>
                <select
                  value={formData.metric_type}
                  onChange={(e) => setFormData({ ...formData, metric_type: e.target.value as MetricType })}
                  className="w-full rounded-lg border-0 bg-background-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary capitalize"
                >
                  {Object.values(MetricType).map((m) => (
                    <option key={m} value={m}>{m.replace('_', ' ')}</option>
                  ))}
                </select>
              </div>

              <div className="flex items-center pt-6">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_compound}
                    onChange={(e) => setFormData({ ...formData, is_compound: e.target.checked })}
                    className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                  />
                  <span className="text-sm font-medium text-foreground">Compound Movement</span>
                </label>
              </div>

              <div className="col-span-1 md:col-span-2">
                <label className="mb-2 block text-sm font-medium text-foreground">Secondary Muscles</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 max-h-40 overflow-y-auto p-2 border border-border rounded-lg bg-background-input">
                  {Object.values(PrimaryMuscle).map((muscle) => (
                    <label key={muscle} className="flex items-center gap-2 text-xs cursor-pointer hover:bg-background-secondary p-1 rounded">
                      <input
                        type="checkbox"
                        checked={formData.secondary_muscles?.includes(muscle)}
                        onChange={() => toggleSecondaryMuscle(muscle)}
                        className="h-3 w-3 rounded border-border bg-background text-primary accent-primary"
                      />
                      <span className="capitalize">{muscle.replace('_', ' ')}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </form>
        </div>

        <div className="flex items-center justify-end gap-3 p-6 border-t border-border bg-background-input">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-medium text-foreground-muted hover:bg-background-secondary hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="create-movement-form"
            disabled={createMutation.isPending}
            className="rounded-lg bg-cta px-6 py-2 text-sm font-medium text-white hover:bg-cta/90 disabled:opacity-50 transition-colors shadow-sm"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Movement'}
          </button>
        </div>
      </div>
    </div>
  );
}

type CircuitFilter = 'all' | CircuitType;

const CIRCUIT_FILTERS: { key: CircuitFilter; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: CircuitType.ROUNDS_FOR_TIME, label: 'Rounds for time' },
  { key: CircuitType.AMRAP, label: 'AMRAP' },
  { key: CircuitType.EMOM, label: 'EMOM' },
  { key: CircuitType.CHIPPER, label: 'Chipper' },
  { key: CircuitType.LADDER, label: 'Ladder' },
  { key: CircuitType.TABATA, label: 'Tabata' },
  { key: CircuitType.STATION, label: 'Station' },
];

interface CircuitExercise {
  original?: string;
  movement_id?: number | null;
  movement_name?: string | null;
  reps?: number | null;
  distance_meters?: number | null;
  duration_seconds?: number | null;
  rest_seconds?: number | null;
  notes?: string | null;
  metric_type?: string | null;
  rx_weight_male?: number | null;
  rx_weight_female?: number | null;
}

interface CircuitCardProps {
  circuit: CircuitTemplate;
}

function CircuitCard({ circuit }: CircuitCardProps) {
  const [expanded, setExpanded] = useState(false);

  const formatType = (type: CircuitType) => type.replace(/_/g, ' ');

  const exercises = (circuit.exercises_json ?? []) as CircuitExercise[];
  const workoutExercises = exercises.filter(
    (ex) =>
      ex.movement_id != null ||
      (ex.movement_name && ex.movement_name.trim().length > 0) ||
      (ex.original && ex.original.trim().length > 0)
  );

  const description = circuit.description || '';
  let metaTokens: string[] = [];
  let stimulusText: string | undefined;

  if (description) {
    const parts = description.split('\n\n');
    const first = parts[0] || '';
    const rest = parts.slice(1).join('\n\n');
    const hasMeta =
      first.includes('Time Cap:') ||
      first.includes('Rounds:') ||
      first.includes('Interval:');

    if (hasMeta) {
      metaTokens = first.split('|').map((t) => t.trim()).filter(Boolean);
      stimulusText = rest.trim() || undefined;
    } else {
      stimulusText = description;
    }
  }

  const lowerTokens = metaTokens.map((t) => t.toLowerCase());
  const timeIdx = lowerTokens.findIndex((t) => t.startsWith('time cap'));
  const roundsIdx = lowerTokens.findIndex((t) => t.startsWith('rounds'));
  const intervalIdx = lowerTokens.findIndex((t) => t.startsWith('interval'));

  const timeToken = timeIdx >= 0 ? metaTokens[timeIdx] : undefined;
  const roundsToken = roundsIdx >= 0 ? metaTokens[roundsIdx] : undefined;
  const intervalToken = intervalIdx >= 0 ? metaTokens[intervalIdx] : undefined;

  const formatExerciseScheme = (ex: CircuitExercise): string => {
    const metric = ex.metric_type?.toLowerCase() ?? '';

    if (ex.reps === 999 && ex.notes && ex.notes.toLowerCase().includes('max')) {
      if (metric === 'calories') {
        return 'max cals';
      }
      return 'max reps';
    }

    if (metric === 'time' && ex.duration_seconds) {
      const total = ex.duration_seconds;
      if (total % 60 === 0) {
        return `${total / 60} min`;
      }
      return `${total}s`;
    }

    if (metric === 'distance' && ex.distance_meters) {
      const meters = ex.distance_meters;
      if (meters >= 1000 && meters % 1000 === 0) {
        return `${meters / 1000} km`;
      }
      return `${meters} m`;
    }

    if (metric === 'calories' && ex.reps) {
      return `${ex.reps} cal`;
    }

    if (ex.reps) {
      return `${ex.reps} reps`;
    }

    return '';
  };

  return (
    <div className="border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <button
          type="button"
          className="flex flex-1 items-start gap-2 text-left"
          onClick={() => setExpanded((prev) => !prev)}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-foreground-muted mt-0.5" />
          ) : (
            <ChevronRight className="h-4 w-4 text-foreground-muted mt-0.5" />
          )}
          <div className="space-y-1 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="font-medium">{circuit.name}</h2>
              <span className="inline-flex items-center rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-medium text-accent uppercase tracking-wide">
                {formatType(circuit.circuit_type)}
              </span>
            </div>
            {(timeToken || roundsToken || intervalToken) && (
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-foreground-muted">
                {timeToken && (
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {timeToken.replace(/time cap[:]?/i, '').trim()}
                  </span>
                )}
                {roundsToken && (
                  <span className="inline-flex items-center gap-1">
                    <ListChecks className="h-3 w-3" />
                    {roundsToken.replace(/rounds[:]?/i, '').trim()}
                  </span>
                )}
                {intervalToken && (
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {intervalToken.replace(/interval[:]?/i, '').trim()}
                  </span>
                )}
              </div>
            )}
            {workoutExercises.length > 0 && (
              <div className="space-y-1 text-xs">
                {workoutExercises.map((ex, index) => {
                  const name = (ex.movement_name || ex.original || '').trim();
                  const scheme = formatExerciseScheme(ex);
                  if (!name && !scheme) return null;
                  return (
                    <div key={`${name}-${index}`} className="flex items-baseline gap-2">
                      <span className="text-foreground-muted">{index + 1}.</span>
                      <span className="text-foreground">
                        {scheme && <span className="font-medium mr-1">{scheme}</span>}
                        {name}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </button>
        <div className="flex flex-col items-end gap-1 text-xs text-foreground-muted">
          <span className="inline-flex items-center gap-1">
            <Flame className="h-3 w-3" />
            Level {circuit.difficulty_tier}
          </span>
        </div>
      </div>

      {circuit.tags && circuit.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {circuit.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-border px-2 py-0.5 text-[10px] text-foreground-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {expanded && (
        <div className="space-y-3 pt-1">
          {stimulusText && (
            <p className="text-xs text-foreground-muted whitespace-pre-line border-t border-border pt-2">
              {stimulusText}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function MovementsTab() {
  const { data, error } = useMovements({ limit: 1000 });
  const { data: filtersData } = useMovementFilters();
  const [search, setSearch] = useState('');
  const [selectedPattern, setSelectedPattern] = useState<MovementPattern | 'all'>('all');
  const [selectedEquipment, setSelectedEquipment] = useState<string | 'all'>('all');
  const [visibleColumns, setVisibleColumns] = useState<ColumnId[]>(DEFAULT_VISIBLE_COLUMNS);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [showMultiFilters, setShowMultiFilters] = useState(false);
  const [selectedRegions, setSelectedRegions] = useState<PrimaryRegion[]>([]);
  const [selectedMuscles, setSelectedMuscles] = useState<PrimaryMuscle[]>([]);
  const [selectedSkillLevels, setSelectedSkillLevels] = useState<SkillLevel[]>([]);
  const [selectedCNSLoads, setSelectedCNSLoads] = useState<CNSLoad[]>([]);
  const [selectedMetricTypes, setSelectedMetricTypes] = useState<MetricType[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sortConfig, setSortConfig] = useState<SortConfig>(null);

  const movements: Movement[] = useMemo(
    () => data?.movements ?? [],
    [data],
  );

  const patternOptions: { value: MovementPattern | 'all'; label: string }[] =
    useMemo(() => {
      const patterns: string[] = filtersData?.patterns ?? [];
      return [
        { value: 'all', label: 'All Patterns' },
        ...patterns.map((p: string) => ({
          value: p as MovementPattern,
          label: p.replace('_', ' '),
        })),
      ];
    }, [filtersData]);

  const equipmentOptions = useMemo(() => {
    const fromFilters = filtersData?.equipment ?? [];
    if (fromFilters.length > 0) {
      return ['all', ...fromFilters];
    }

    const set = new Set<string>();
    for (const m of movements) {
      if (m.default_equipment) {
        set.add(m.default_equipment);
      }
      if (m.equipment_tags) {
        for (const tag of m.equipment_tags) {
          set.add(tag);
        }
      }
    }
    return ['all', ...Array.from(set).sort()];
  }, [filtersData, movements]);

  const filteredMovements = useMemo(() => {
    let result = movements.filter((movement) => {
      const matchesSearch = movement.name.toLowerCase().includes(search.toLowerCase());
      const matchesPattern =
        selectedPattern === 'all' ||
        movement.primary_pattern === selectedPattern;

      const matchesEquipment =
        selectedEquipment === 'all' ||
        movement.default_equipment === selectedEquipment ||
        (movement.equipment_tags && movement.equipment_tags.includes(selectedEquipment));

      const matchesRegion =
        selectedRegions.length === 0 ||
        (movement.primary_region && selectedRegions.includes(movement.primary_region));

      const matchesMuscle =
        selectedMuscles.length === 0 ||
        (movement.primary_muscles && movement.primary_muscles.some(m => selectedMuscles.includes(m)));

      const matchesSkillLevel =
        selectedSkillLevels.length === 0 ||
        (movement.skill_level && selectedSkillLevels.includes(movement.skill_level));

      const matchesCNSLoad =
        selectedCNSLoads.length === 0 ||
        (movement.cns_load && selectedCNSLoads.includes(movement.cns_load));

      const matchesMetricType =
        selectedMetricTypes.length === 0 ||
        (movement.metric_type && selectedMetricTypes.includes(movement.metric_type));

      return matchesSearch && matchesPattern && matchesEquipment && matchesRegion && matchesMuscle && matchesSkillLevel && matchesCNSLoad && matchesMetricType;
    });

    if (sortConfig) {
      result = [...result].sort((a, b) => {
        let aValue = a[sortConfig.key as keyof Movement];
        let bValue = b[sortConfig.key as keyof Movement];

        if (sortConfig.key === 'is_compound') {
          aValue = a.is_compound ? 1 : 0;
          bValue = b.is_compound ? 1 : 0;
        }

        if (aValue == null) aValue = '';
        if (bValue == null) bValue = '';

        const aString = String(aValue).toLowerCase();
        const bString = String(bValue).toLowerCase();

        if (aString < bString) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aString > bString) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }

    return result;
  }, [movements, search, selectedPattern, selectedEquipment, selectedRegions, selectedMuscles, selectedSkillLevels, selectedCNSLoads, selectedMetricTypes, sortConfig]);

  if (error) {
    return (
      <div className="rounded bg-error/10 p-3 text-sm text-error">
        Failed to load movements. Please try refreshing the page or check your connection.
      </div>
    );
  }

  const toggleColumn = (id: ColumnId) => {
    setVisibleColumns((current) =>
      current.includes(id) ? current.filter((col) => col !== id) : [...current, id],
    );
  };

  const handleSort = (key: ColumnId) => {
    setSortConfig((current) => {
      if (current?.key === key) {
        if (current.direction === 'asc') return { key, direction: 'desc' };
        return null;
      }
      return { key, direction: 'asc' };
    });
  };

  const columnsToRender = ALL_COLUMNS.filter((col) => visibleColumns.includes(col.id));

  return (
    <div className="flex flex-col min-h-0">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Movements</h2>
          <p className="mt-2 text-sm text-foreground-muted">
            Browse all movements with filters and customizable columns.
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-cta px-3 py-1.5 text-xs font-medium text-white hover:bg-cta/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Add
        </button>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted" />
          <input
            type="text"
            placeholder="Search movements..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border-0 bg-background-input px-9 py-2 text-sm text-foreground placeholder:text-foreground-muted focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-foreground-muted" />
          <select
            value={selectedPattern}
            onChange={(e) =>
              setSelectedPattern(
                e.target.value === 'all'
                  ? 'all'
                  : (e.target.value as MovementPattern),
              )
            }
            className="h-9 flex-1 rounded-lg border-0 bg-background-input px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {patternOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-foreground-muted" />
          <select
            value={selectedEquipment}
            onChange={(e) =>
              setSelectedEquipment(e.target.value as typeof selectedEquipment)
            }
            className="h-9 flex-1 rounded-lg border-0 bg-background-input px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {equipmentOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt === 'all' ? 'All Equipment' : opt}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="text-xs text-foreground-muted">
          Showing {filteredMovements.length} of {movements.length} movements
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowMultiFilters((v) => !v)}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground hover:bg-background-secondary"
          >
            <Filter className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setShowAdvancedFilters((v) => !v)}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground hover:bg-background-secondary"
          >
            <Settings2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {showAdvancedFilters && (
        <div className="mb-4 rounded-lg border border-border bg-background-input p-4">
          <h3 className="mb-3 text-sm font-medium text-foreground">Pick your Poison</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {ALL_COLUMNS.map((col) => (
              <label key={col.id} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(col.id)}
                  onChange={() => toggleColumn(col.id)}
                  className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                />
                <span className="text-xs text-foreground">{col.label}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {showMultiFilters && (
        <div className="mb-4 rounded-lg border border-border bg-background-input p-4">
          <h3 className="mb-3 text-sm font-medium text-foreground">Some Assembly Required</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="mb-2 block text-xs font-medium text-foreground">Region</label>
              <div className="max-h-40 overflow-y-auto border border-border rounded-lg bg-background p-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="checkbox"
                    checked={selectedRegions.length === Object.values(PrimaryRegion).length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedRegions(Object.values(PrimaryRegion));
                      } else {
                        setSelectedRegions([]);
                      }
                    }}
                    className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                  />
                  <span className="text-xs text-foreground">Select All</span>
                </label>
                {Object.values(PrimaryRegion).map((region) => (
                  <label key={region} className="flex items-center gap-2 cursor-pointer py-1">
                    <input
                      type="checkbox"
                      checked={selectedRegions.includes(region)}
                      onChange={() => {
                        setSelectedRegions((current) =>
                          current.includes(region)
                            ? current.filter((r) => r !== region)
                            : [...current, region]
                        );
                      }}
                      className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                    />
                    <span className="text-xs text-foreground capitalize">{region.replace('_', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs font-medium text-foreground">Primary Muscle</label>
              <div className="max-h-40 overflow-y-auto border border-border rounded-lg bg-background p-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="checkbox"
                    checked={selectedMuscles.length === Object.values(PrimaryMuscle).length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedMuscles(Object.values(PrimaryMuscle));
                      } else {
                        setSelectedMuscles([]);
                      }
                    }}
                    className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                  />
                  <span className="text-xs text-foreground">Select All</span>
                </label>
                {Object.values(PrimaryMuscle).map((muscle) => (
                  <label key={muscle} className="flex items-center gap-2 cursor-pointer py-1">
                    <input
                      type="checkbox"
                      checked={selectedMuscles.includes(muscle)}
                      onChange={() => {
                        setSelectedMuscles((current) =>
                          current.includes(muscle)
                            ? current.filter((m) => m !== muscle)
                            : [...current, muscle]
                        );
                      }}
                      className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                    />
                    <span className="text-xs text-foreground capitalize">{muscle.replace('_', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs font-medium text-foreground">Skill Level</label>
              <div className="max-h-40 overflow-y-auto border border-border rounded-lg bg-background p-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="checkbox"
                    checked={selectedSkillLevels.length === Object.values(SkillLevel).length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedSkillLevels(Object.values(SkillLevel));
                      } else {
                        setSelectedSkillLevels([]);
                      }
                    }}
                    className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                  />
                  <span className="text-xs text-foreground">Select All</span>
                </label>
                {Object.values(SkillLevel).map((level) => (
                  <label key={level} className="flex items-center gap-2 cursor-pointer py-1">
                    <input
                      type="checkbox"
                      checked={selectedSkillLevels.includes(level)}
                      onChange={() => {
                        setSelectedSkillLevels((current) =>
                          current.includes(level)
                            ? current.filter((l) => l !== level)
                            : [...current, level]
                        );
                      }}
                      className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                    />
                    <span className="text-xs text-foreground capitalize">{level}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs font-medium text-foreground">CNS Load</label>
              <div className="max-h-40 overflow-y-auto border border-border rounded-lg bg-background p-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="checkbox"
                    checked={selectedCNSLoads.length === Object.values(CNSLoad).length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedCNSLoads(Object.values(CNSLoad));
                      } else {
                        setSelectedCNSLoads([]);
                      }
                    }}
                    className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                  />
                  <span className="text-xs text-foreground">Select All</span>
                </label>
                {Object.values(CNSLoad).map((load) => (
                  <label key={load} className="flex items-center gap-2 cursor-pointer py-1">
                    <input
                      type="checkbox"
                      checked={selectedCNSLoads.includes(load)}
                      onChange={() => {
                        setSelectedCNSLoads((current) =>
                          current.includes(load)
                            ? current.filter((l) => l !== load)
                            : [...current, load]
                        );
                      }}
                      className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                    />
                    <span className="text-xs text-foreground capitalize">{load.replace('_', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-2 block text-xs font-medium text-foreground">Metric Type</label>
              <div className="max-h-40 overflow-y-auto border border-border rounded-lg bg-background p-2">
                <label className="flex items-center gap-2 cursor-pointer py-1">
                  <input
                    type="checkbox"
                    checked={selectedMetricTypes.length === Object.values(MetricType).length}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedMetricTypes(Object.values(MetricType));
                      } else {
                        setSelectedMetricTypes([]);
                      }
                    }}
                    className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                  />
                  <span className="text-xs text-foreground">Select All</span>
                </label>
                {Object.values(MetricType).map((type) => (
                  <label key={type} className="flex items-center gap-2 cursor-pointer py-1">
                    <input
                      type="checkbox"
                      checked={selectedMetricTypes.includes(type)}
                      onChange={() => {
                        setSelectedMetricTypes((current) =>
                          current.includes(type)
                            ? current.filter((t) => t !== type)
                            : [...current, type]
                        );
                      }}
                      className="h-4 w-4 rounded border-border bg-background text-primary accent-primary"
                    />
                    <span className="text-xs text-foreground capitalize">{type.replace('_', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto border border-border rounded-lg">
        {filteredMovements.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-foreground-muted">
            No movements found.
          </div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead className="bg-background-input sticky top-0">
              <tr>
                {columnsToRender.map((col) => (
                  <th
                    key={col.id}
                    onClick={() => handleSort(col.id)}
                    className="cursor-pointer select-none px-4 py-3 text-xs font-medium text-foreground-muted hover:text-foreground"
                  >
                    <div className="flex items-center gap-1">
                      {col.label}
                      {sortConfig?.key === col.id && (
                        sortConfig.direction === 'asc' ? (
                          <ArrowUp className="h-3 w-3" />
                        ) : (
                          <ArrowDown className="h-3 w-3" />
                        )
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredMovements.map((movement) => (
                <tr
                  key={movement.id}
                  className="hover:bg-background-secondary transition-colors"
                >
                  {columnsToRender.map((col) => (
                    <td key={col.id} className="px-4 py-3 text-foreground">
                      {col.render(movement)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {isModalOpen && (
        <AddMovementModal onClose={() => setIsModalOpen(false)} equipmentOptions={equipmentOptions} />
      )}
    </div>
  );
}

function CircuitsTab() {
  const [filter, setFilter] = useState<CircuitFilter>('all');
  const { data: circuits, isLoading, error } = useCircuits(filter);

  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded bg-error/10 p-3 text-sm text-error">
        Failed to load circuits. Please try refreshing the page or check your connection.
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-0">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Circuits</h2>
          <p className="mt-2 text-sm text-foreground-muted">
            Browse CrossFit-style circuits by type.
          </p>
        </div>
      </div>

      <div className="mb-4 flex gap-2 overflow-x-auto pb-1">
        {CIRCUIT_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              "whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              filter === f.key
                ? "bg-cta text-white hover:bg-cta/90"
                : "bg-background-input text-foreground hover:bg-background-secondary"
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {!circuits || circuits.length === 0 ? (
        <div className="flex h-32 items-center justify-center rounded-lg border border-border text-sm text-foreground-muted">
          No circuits found for this filter.
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-3">
          {circuits.map((circuit) => (
            <CircuitCard key={circuit.id} circuit={circuit} />
          ))}
        </div>
      )}
    </div>
  );
}

function LibraryPage() {
  return (
    <div className="container-app py-6 flex flex-col min-h-0">
      <h1 className="text-2xl font-bold text-foreground mb-6">Library</h1>

      <Tabs defaultValue="movements" className="space-y-6 flex flex-col min-h-0">
        <TabsList className="w-full justify-start border-b border-border bg-transparent p-0">
          <TabsTrigger
            value="movements"
            className="rounded-none border-b-2 border-transparent px-4 py-2 text-sm font-medium text-foreground-muted data-[state=active]:border-primary data-[state=active]:text-foreground"
          >
            Movements
          </TabsTrigger>
          <TabsTrigger
            value="circuits"
            className="rounded-none border-b-2 border-transparent px-4 py-2 text-sm font-medium text-foreground-muted data-[state=active]:border-primary data-[state=active]:text-foreground"
          >
            Circuits
          </TabsTrigger>
        </TabsList>

        <TabsContent value="movements" className="mt-6 flex flex-col min-h-0">
          <MovementsTab />
        </TabsContent>

        <TabsContent value="circuits" className="mt-6 flex flex-col min-h-0">
          <CircuitsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
