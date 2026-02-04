import { useState } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ArrowLeft, Save, Plus, X, Search, Flame } from 'lucide-react';
import { useMovements } from '@/api/settings';
import { useCircuits } from '@/api/circuits';
import { useLogCustomWorkout } from '@/api/logs';
import { Spinner } from '@/components/common/Spinner';
import { SorenessTracker } from '@/components/visuals';
import { 
  MetricType, 
  ExerciseRole,
  CircuitType,
  type Movement, 
  type CircuitTemplate,
  type CustomExerciseCreate,
  type CustomWorkoutCreate 
} from '@/types';

export const Route = createFileRoute('/log/workout')({
  component: LogWorkoutPage,
});

// Sections definition
const SECTIONS = [
  { id: 'warmup', label: 'Warm Up', role: ExerciseRole.WARMUP },
  { id: 'main', label: 'Main Lifts', role: ExerciseRole.MAIN },
  { id: 'accessory', label: 'Accessories', role: ExerciseRole.ACCESSORY },
  { id: 'finisher', label: 'Finisher', role: ExerciseRole.FINISHER },
  { id: 'circuit', label: 'Circuit', role: ExerciseRole.MAIN }, // Mapping to Main for now, special handling
  { id: 'cooldown', label: 'Cool Down', role: ExerciseRole.COOLDOWN },
] as const;

type SectionId = typeof SECTIONS[number]['id'];

interface WorkoutItem {
  id: string; // temp id
  movement?: Movement;
  circuit?: CircuitTemplate;
  type: 'movement' | 'circuit';
  // exercise data
  sets: number;
  reps?: number;
  weight?: number;
  distance?: number;
  duration?: number;
  notes?: string;
}

function LogWorkoutPage() {
  const navigate = useNavigate();
  const { mutate: logWorkout, isPending: isSubmitting } = useLogCustomWorkout();

  // State
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [activeSection, setActiveSection] = useState<SectionId | null>(null);
  const [workoutData, setWorkoutData] = useState<Record<SectionId, WorkoutItem[]>>({
    warmup: [],
    main: [],
    accessory: [],
    finisher: [],
    circuit: [],
    cooldown: [],
  });
  
  // Meta
  const [workoutName, setWorkoutName] = useState('');
  const [notes, setNotes] = useState('');
  const [difficulty, setDifficulty] = useState(5);
  const [enjoyment, setEnjoyment] = useState(3);
  const [duration, setDuration] = useState(60);
  const [showSorenessTracker, setShowSorenessTracker] = useState(false);

  // Selector State
  const [selectorOpen, setSelectorOpen] = useState<{ section: SectionId, type: 'movement' | 'circuit' } | null>(null);

  // Handlers
  const toggleSection = (id: SectionId) => {
    setActiveSection(prev => prev === id ? null : id);
  };

  const addItem = (section: SectionId, item: WorkoutItem) => {
    // Set smart defaults based on movement metric type
    if (item.type === 'movement' && item.movement) {
      const metric = item.movement.metric_type || MetricType.REPS;
      
      // Defaults
      item.sets = 3;
      
      if (metric === MetricType.REPS) {
        item.reps = 10;
        item.weight = 0;
      } else if (metric === MetricType.DISTANCE) {
        item.distance = 1000; // meters
      } else if (metric === MetricType.TIME) {
        item.duration = 60; // seconds
      }
    }

    setWorkoutData(prev => ({
      ...prev,
      [section]: [...prev[section], item]
    }));
    setSelectorOpen(null);
  };

  const updateItem = (section: SectionId, itemId: string, updates: Partial<WorkoutItem>) => {
    setWorkoutData(prev => ({
      ...prev,
      [section]: prev[section].map(i => i.id === itemId ? { ...i, ...updates } : i)
    }));
  };

  const removeItem = (section: SectionId, itemId: string) => {
    setWorkoutData(prev => ({
      ...prev,
      [section]: prev[section].filter(i => i.id !== itemId)
    }));
  };

  const handleSubmit = () => {
    // Transform to API payload
    const payload: CustomWorkoutCreate = {
      log_date: date,
      duration_minutes: duration,
      notes: notes || undefined,
      perceived_difficulty: difficulty,
      enjoyment_rating: enjoyment,
      
      warmup: workoutData.warmup.map(toApiExercise),
      main: workoutData.main.map(toApiExercise),
      accessory: workoutData.accessory.map(toApiExercise),
      finisher: workoutData.finisher.filter(i => i.type === 'movement').map(toApiExercise),
      cooldown: workoutData.cooldown.map(toApiExercise),
      
      finisher_circuit_id: workoutData.finisher.find(i => i.type === 'circuit')?.circuit?.id,
    };

    logWorkout(payload, {
      onSuccess: () => navigate({ to: '/' }),
    });
  };

  const toApiExercise = (item: WorkoutItem): CustomExerciseCreate => ({
    movement_id: item.movement!.id,
    sets: item.sets,
    reps: item.reps,
    weight: item.weight,
    distance_meters: item.distance,
    duration_seconds: item.duration,
    notes: item.notes,
  });

  return (
    <div className="container-app py-6 space-y-6 animate-fade-in relative min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between sticky top-0 bg-background z-10 py-2 border-b">
        <div className="flex items-center space-x-4">
          <Button variant="ghost" size="icon" onClick={() => window.history.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-xl font-semibold">Log Custom Workout</h1>
        </div>
        <Button onClick={handleSubmit} disabled={isSubmitting}>
          {isSubmitting ? <Spinner className="mr-2 h-4 w-4" /> : <Save className="mr-2 h-4 w-4" />}
          Save
        </Button>
      </div>

      {/* Meta Fields */}
      <Card className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="col-span-1 md:col-span-2">
          <label className="text-xs font-medium text-foreground-muted">Workout Name (Optional)</label>
          <input 
            type="text" 
            value={workoutName} 
            onChange={e => setWorkoutName(e.target.value)}
            maxLength={50}
            placeholder="e.g. Leg Day Destruction"
            className="w-full bg-transparent border-b border-border focus:outline-none focus:border-primary py-1"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-foreground-muted">Date</label>
          <input 
            type="date" 
            value={date} 
            onChange={e => setDate(e.target.value)}
            className="w-full bg-transparent border-b border-border focus:outline-none focus:border-primary py-1"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-foreground-muted">Duration (min)</label>
          <input 
            type="number" 
            value={duration} 
            onChange={e => setDuration(Number(e.target.value))}
            className="w-full bg-transparent border-b border-border focus:outline-none focus:border-primary py-1"
          />
        </div>
      </Card>

      {/* Sections */}
      <div className="space-y-2">
        {SECTIONS.map(section => (
          <div key={section.id} className="border rounded-lg overflow-hidden bg-background-elevated">
            {/* Section Header */}
            <div 
              className="p-3 font-semibold flex justify-between items-center cursor-pointer hover:bg-background-secondary transition-colors"
              onClick={() => toggleSection(section.id)}
            >
              <span>{section.label}</span>
              <span className="text-xs text-foreground-muted">
                {workoutData[section.id].length} items
              </span>
            </div>

            {/* Section Content */}
            {activeSection === section.id && (
              <div className="p-3 pt-0 space-y-3 animate-slide-down">
                {/* Items List */}
                {workoutData[section.id].map(item => (
                  <div key={item.id} className="bg-background p-3 rounded border space-y-2">
                    <div className="flex justify-between items-start">
                      <span className="font-medium">
                        {item.type === 'movement' ? item.movement?.name : `Circuit: ${item.circuit?.name}`}
                      </span>
                      <button onClick={() => removeItem(section.id, item.id)}>
                        <X className="h-4 w-4 text-foreground-muted hover:text-destructive" />
                      </button>
                    </div>

                    {item.type === 'movement' && (
                      <div className="grid grid-cols-3 gap-2 text-sm">
                        <div>
                          <label className="text-[10px] text-foreground-muted block">Sets</label>
                          <input 
                            type="number" 
                            value={item.sets} 
                            onChange={e => updateItem(section.id, item.id, { sets: Number(e.target.value) })}
                            className="w-full bg-transparent border-b border-border py-0.5"
                          />
                        </div>
                        {/* Dynamic Fields based on Metric Type */}
                        {(item.movement?.metric_type === MetricType.REPS || !item.movement?.metric_type) && (
                          <>
                            <div>
                              <label className="text-[10px] text-foreground-muted block">Reps</label>
                              <input 
                                type="number" 
                                value={item.reps || ''} 
                                onChange={e => updateItem(section.id, item.id, { reps: Number(e.target.value) })}
                                className="w-full bg-transparent border-b border-border py-0.5"
                              />
                            </div>
                            <div>
                              <label className="text-[10px] text-foreground-muted block">Weight (kg)</label>
                              <input 
                                type="number" 
                                value={item.weight || ''} 
                                onChange={e => updateItem(section.id, item.id, { weight: Number(e.target.value) })}
                                className="w-full bg-transparent border-b border-border py-0.5"
                              />
                            </div>
                          </>
                        )}
                        {item.movement?.metric_type === MetricType.DISTANCE && (
                          <div className="col-span-2">
                            <label className="text-[10px] text-foreground-muted block">Distance (m)</label>
                            <input 
                              type="number" 
                              value={item.distance || ''} 
                              onChange={e => updateItem(section.id, item.id, { distance: Number(e.target.value) })}
                              className="w-full bg-transparent border-b border-border py-0.5"
                            />
                          </div>
                        )}
                        {item.movement?.metric_type === MetricType.TIME && (
                          <div className="col-span-2">
                            <label className="text-[10px] text-foreground-muted block">Duration (s)</label>
                            <input 
                              type="number" 
                              value={item.duration || ''} 
                              onChange={e => updateItem(section.id, item.id, { duration: Number(e.target.value) })}
                              className="w-full bg-transparent border-b border-border py-0.5"
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}

                {/* Add Actions */}
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="flex-1 border-dashed"
                    onClick={() => setSelectorOpen({ section: section.id, type: 'movement' })}
                  >
                    <Plus className="h-3 w-3 mr-2" />
                    Add Movement
                  </Button>
                  
                  {/* Show Circuit Option for Finisher and Circuit sections */}
                  {(section.id === 'finisher' || section.id === 'circuit') && (
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="flex-1 border-dashed"
                      onClick={() => setSelectorOpen({ section: section.id, type: 'circuit' })}
                    >
                      <Flame className="h-3 w-3 mr-2" />
                      Add Circuit
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Soreness Tracker Toggle */}
      {!showSorenessTracker ? (
        <Button
          type="button"
          variant="outline"
          onClick={() => setShowSorenessTracker(true)}
          className="w-full border-dashed"
        >
          <Plus className="h-4 w-4 mr-2" />
          Log Muscle Soreness
        </Button>
      ) : (
        <SorenessTracker
          logDate={date}
          onSuccess={() => setShowSorenessTracker(false)}
          onCancel={() => setShowSorenessTracker(false)}
        />
      )}

      {/* Footer Meta */}
      <Card className="p-4 space-y-4">
        <div>
          <label className="text-sm font-medium block mb-2">Notes</label>
          <textarea 
            value={notes} 
            onChange={e => setNotes(e.target.value)}
            className="w-full bg-background border rounded p-2 text-sm"
            rows={3}
            placeholder="Workout notes..."
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium block mb-2">Difficulty: {difficulty}</label>
            <input 
              type="range" min="1" max="10" 
              value={difficulty} onChange={e => setDifficulty(Number(e.target.value))}
              className="w-full"
            />
          </div>
          <div>
            <label className="text-sm font-medium block mb-2">Enjoyment: {enjoyment}</label>
            <input 
              type="range" min="1" max="5" 
              value={enjoyment} onChange={e => setEnjoyment(Number(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      </Card>

      {/* Selectors */}
      {selectorOpen && (
        <div className="fixed inset-0 bg-background z-50 flex flex-col animate-in slide-in-from-bottom-10">
          <div className="p-4 border-b flex items-center gap-2">
            <Search className="h-4 w-4 text-foreground-muted" />
            <input 
              autoFocus
              placeholder={`Search ${selectorOpen.type}s...`}
              className="flex-1 bg-transparent focus:outline-none text-lg"
              onChange={(e) => {
                // We'll handle search in the list component
                const event = new CustomEvent('search-change', { detail: e.target.value });
                window.dispatchEvent(event);
              }}
            />
            <Button variant="ghost" size="icon" onClick={() => setSelectorOpen(null)}>
              <X className="h-5 w-5" />
            </Button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4">
            {selectorOpen.type === 'movement' ? (
              <MovementList onSelect={(m) => addItem(selectorOpen.section, {
                id: Math.random().toString(36).substr(2, 9),
                type: 'movement',
                movement: m,
                sets: 3, // default
                reps: 10,
              })} />
            ) : (
              <CircuitList onSelect={(c) => addItem(selectorOpen.section, {
                id: Math.random().toString(36).substr(2, 9),
                type: 'circuit',
                circuit: c,
                sets: 1,
              })} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Sub-components for lists

function MovementList({ onSelect }: { onSelect: (m: Movement) => void }) {
  const [search, setSearch] = useState('');
  const { data, isLoading } = useMovements({ search, limit: 50 });

  if (isLoading) return <Spinner />;

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="absolute left-2 top-2.5 h-4 w-4 text-foreground-muted" />
        <input
          type="text"
          placeholder="Search movements..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-background border rounded pl-8 p-2 text-sm focus:outline-none focus:border-primary"
          autoFocus
        />
      </div>
      
      <div className="max-h-[300px] overflow-y-auto space-y-2">
        {data?.movements.map(m => (
          <div 
            key={m.id} 
            className="p-3 border rounded hover:bg-background-elevated cursor-pointer flex justify-between items-center"
            onClick={() => onSelect(m)}
          >
            <div>
              <div className="font-medium">{m.name}</div>
              <div className="text-xs text-foreground-muted capitalize">
                {m.primary_muscles?.[0] || 'General'} • {m.default_equipment || 'No Eq'}
              </div>
            </div>
            <Plus className="h-4 w-4 text-foreground-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}

function CircuitList({ onSelect }: { onSelect: (c: CircuitTemplate) => void }) {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<CircuitType | 'all'>('all');
  const { data: circuits, isLoading } = useCircuits(typeFilter);

  const CIRCUIT_FILTERS: { key: CircuitType | 'all'; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: CircuitType.ROUNDS_FOR_TIME, label: 'RFT' },
    { key: CircuitType.AMRAP, label: 'AMRAP' },
    { key: CircuitType.EMOM, label: 'EMOM' },
    { key: CircuitType.CHIPPER, label: 'Chipper' },
    { key: CircuitType.LADDER, label: 'Ladder' },
    { key: CircuitType.TABATA, label: 'Tabata' },
  ];

  if (isLoading) return <Spinner />;

  const filtered = circuits?.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-2 top-2.5 h-4 w-4 text-foreground-muted" />
        <input
          type="text"
          placeholder="Search circuits..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-background border rounded pl-8 p-2 text-sm focus:outline-none focus:border-primary"
          autoFocus
        />
      </div>

      <div className="flex gap-2 overflow-x-auto pb-2 -mx-2 px-2 scrollbar-hide">
        {CIRCUIT_FILTERS.map((f) => (
          <Button
            key={f.key}
            size="sm"
            variant={typeFilter === f.key ? 'cta' : 'outline'}
            onClick={() => setTypeFilter(f.key)}
            className="whitespace-nowrap h-7 text-xs px-3"
          >
            {f.label}
          </Button>
        ))}
      </div>

      <div className="space-y-2 max-h-[300px] overflow-y-auto">
        {filtered?.length === 0 ? (
          <div className="text-center py-4 text-foreground-muted text-sm">
            No circuits found.
          </div>
        ) : (
          filtered?.map(c => (
            <div 
              key={c.id} 
              className="p-3 border rounded hover:bg-background-elevated cursor-pointer flex justify-between items-center group"
              onClick={() => onSelect(c)}
            >
              <div>
                <div className="font-medium group-hover:text-primary transition-colors">{c.name}</div>
                <div className="text-xs text-foreground-muted capitalize">
                  {c.circuit_type.replace('_', ' ')} • {c.difficulty_tier}/5
                </div>
              </div>
              <Plus className="h-4 w-4 text-foreground-muted group-hover:text-primary" />
            </div>
          ))
        )}
      </div>
    </div>
  );
}
