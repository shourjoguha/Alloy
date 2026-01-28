import { useMemo, useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Filter, Search, Settings2, Plus, ArrowUp, ArrowDown, User, X } from 'lucide-react';
import { useMovements, useCreateMovement, useMovementFilters } from '@/api/settings';
import { 
  MovementPattern, 
  PrimaryRegion, 
  PrimaryMuscle, 
  SkillLevel, 
  CNSLoad, 
  MetricType,
  type Movement, 
  type MovementCreate 
} from '@/types';
import { cn } from '@/lib/utils';

export const Route = createFileRoute('/movements')({
  component: MovementsPage,
});

type ColumnId =
  | 'name'
  | 'primary_pattern'
  | 'primary_region'
  | 'primary_muscle'
  | 'secondary_muscles'
  | 'default_equipment'
  | 'equipment_tags'
  | 'complexity'
  | 'skill_level'
  | 'is_compound'
  | 'cns_load'
  | 'metric_type'
  | 'user_id'; // Add user_id column

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
    id: 'default_equipment',
    label: 'Equipment',
    render: (m) => m.default_equipment ?? '',
  },
  {
    id: 'equipment_tags',
    label: 'Equipment Tags',
    render: (m) => (m.equipment_tags && m.equipment_tags.length > 0 ? m.equipment_tags.join(', ') : ''),
  },
  {
    id: 'complexity',
    label: 'Complexity',
    render: (m) => m.complexity ?? '',
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
  'default_equipment',
  'complexity',
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

function MovementsPage() {
  const { data, isLoading, error } = useMovements({ limit: 1000 });
  const { data: filtersData } = useMovementFilters();
  const [search, setSearch] = useState('');
  const [selectedPattern, setSelectedPattern] = useState<MovementPattern | 'all'>('all');
  const [selectedEquipment, setSelectedEquipment] = useState<string | 'all'>('all');
  const [visibleColumns, setVisibleColumns] = useState<ColumnId[]>(DEFAULT_VISIBLE_COLUMNS);
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
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

      return matchesSearch && matchesPattern && matchesEquipment;
    });

    if (sortConfig) {
      result = [...result].sort((a, b) => {
        let aValue = a[sortConfig.key as keyof Movement];
        let bValue = b[sortConfig.key as keyof Movement];

        // Handle specific columns if needed
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
  }, [movements, search, selectedPattern, selectedEquipment, sortConfig]);

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
    <div className="container-app py-6">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Movement Library</h1>
          <p className="mt-2 text-sm text-foreground-muted">
            Browse all movements with filters and customizable columns.
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-cta px-3 py-1.5 text-xs font-medium text-white hover:bg-cta/90 transition-colors"
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

        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => setShowAdvancedFilters((prev) => !prev)}
            className={cn(
              'inline-flex items-center rounded-lg border border-border bg-background-input px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-background-secondary',
            )}
          >
            <Settings2 className="h-4 w-4" />
          </button>
        </div>

        <div className="text-xs text-foreground-muted flex items-center">
          Showing {filteredMovements.length} of {movements.length} movements
        </div>
      </div>

      {showAdvancedFilters && (
        <div className="mb-4 rounded-lg border border-border bg-background-input p-3 space-y-3">
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
              className="flex-1 h-9 rounded-lg border-0 bg-background-input px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
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
              className="flex-1 h-9 rounded-lg border-0 bg-background-input px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {equipmentOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt === 'all' ? 'All Equipment' : opt}
                </option>
              ))}
            </select>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-foreground-muted">
              Select columns to display:
            </p>
            <div className="flex flex-wrap gap-3">
              {ALL_COLUMNS.map((col) => (
                <label key={col.id} className="flex items-center gap-2 text-xs text-foreground">
                  <input
                    type="checkbox"
                    checked={visibleColumns.includes(col.id)}
                    onChange={() => setVisibleColumns((current) =>
                      current.includes(col.id) ? current.filter((c) => c !== col.id) : [...current, col.id],
                    )}
                    className="h-3 w-3 rounded border-border bg-background text-primary accent-primary"
                  />
                  <span>{col.label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="rounded-2xl border border-border bg-white">
        {isLoading ? (
          <div className="py-10 text-center text-foreground-muted text-sm">
            Loading movements...
          </div>
        ) : error ? (
          <div className="py-10 text-center text-foreground-muted text-sm">
            Failed to load movements. Please check your connection.
          </div>
        ) : filteredMovements.length === 0 ? (
          <div className="py-10 text-center text-foreground-muted text-sm">
            No movements match your filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="max-h-[600px] overflow-y-auto">
              <table className="min-w-full text-left text-xs">
                <thead className="sticky top-0 bg-background-input border-b border-border z-10 rounded-t-2xl">
                  <tr>
                    {columnsToRender.map((col) => (
                      <th
                        key={col.id}
                        className="px-4 py-3 font-semibold text-foreground-muted whitespace-nowrap cursor-pointer hover:text-foreground hover:bg-background-secondary select-none"
                        onClick={() => handleSort(col.id)}
                      >
                        <div className="flex items-center gap-1">
                          {col.label}
                          {sortConfig?.key === col.id && (
                            sortConfig.direction === 'asc' ? (
                              <ArrowUp className="h-3 w-3 text-primary" />
                            ) : (
                              <ArrowDown className="h-3 w-3 text-primary" />
                            )
                          )}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredMovements.map((movement) => (
                    <tr
                      key={movement.id}
                      className="border-b border-border/60 last:border-b-0 hover:bg-background-secondary"
                    >
                      {columnsToRender.map((col) => (
                        <td key={col.id} className="px-4 py-2.5 text-foreground whitespace-nowrap">
                          {col.render(movement)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {isModalOpen && (
        <AddMovementModal
          onClose={() => setIsModalOpen(false)}
          equipmentOptions={equipmentOptions}
        />
      )}
    </div>
  );
}
