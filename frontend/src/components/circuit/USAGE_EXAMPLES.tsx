/**
 * CircuitDisplay Component - Usage Examples
 * 
 * This file provides practical examples of how to use the CircuitDisplay component
 * in different scenarios throughout the Gainsly application.
 */

import { CircuitDisplay, CircuitDisplayCompact } from '@/components/circuit';
import type { CircuitBlock } from '@/types';

// ============================================================================
// EXAMPLE 1: Basic Usage
// ============================================================================

function BasicUsageExample() {
  const circuit: CircuitBlock = {
    circuit_id: 1,
    name: 'The Filthy Fifty',
    circuit_type: 'AMRAP',
    difficulty_tier: 3,
    estimated_duration_seconds: 960,
    default_rounds: 20,
    primary_region: 'full body',
    primary_muscles: ['quadriceps', 'hamstrings', 'chest'],
    fatigue_factor: 1.5,
    stimulus_factor: 1.8,
    exercises: [
      {
        movement: 'Box Jumps',
        movement_id: 1,
        sequence: 1,
        metric_type: 'reps',
        reps: 50,
        rest_seconds: 0,
      },
      {
        movement: 'Jumping Pull-ups',
        movement_id: 2,
        sequence: 2,
        metric_type: 'reps',
        reps: 50,
        rest_seconds: 0,
      },
    ],
  };

  return (
    <CircuitDisplay 
      circuit={circuit} 
      title="Circuit Block"
    />
  );
}

// ============================================================================
// EXAMPLE 2: Hide Circuit Metrics
// ============================================================================

function HideMetricsExample() {
  const circuit: CircuitBlock = {
    // ... circuit data
    circuit_id: 1,
    name: 'Simple Circuit',
    circuit_type: 'AMRAP',
    difficulty_tier: 1,
    estimated_duration_seconds: 300,
    default_rounds: 5,
    primary_region: 'upper body',
    primary_muscles: ['chest', 'shoulders'],
    fatigue_factor: 1.0,
    stimulus_factor: 1.2,
    exercises: [],
  };

  return (
    <CircuitDisplay 
      circuit={circuit} 
      title="Quick Circuit"
      showMetrics={false}  // Hide circuit-level metrics
    />
  );
}

// ============================================================================
// EXAMPLE 3: Compact Display for Lists
// ============================================================================

function CompactDisplayExample({ circuits }: { circuits: CircuitBlock[] }) {
  return (
    <div className="space-y-3">
      {circuits.map((circuit) => (
        <CircuitDisplayCompact 
          key={circuit.circuit_id} 
          circuit={circuit} 
        />
      ))}
    </div>
  );
}

// ============================================================================
// EXAMPLE 4: Integration with SessionCard
// ============================================================================

import type { Session } from '@/types';

interface SessionCardProps {
  session: Session;
}

function SessionCardWithCircuit({ session }: SessionCardProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-border/30 overflow-hidden">
      {/* Session header */}
      <div className="p-4 border-b border-border/30">
        <h3 className="font-semibold text-lg">{session.session_type}</h3>
        <p className="text-sm text-foreground-muted">Day {session.day_number}</p>
      </div>

      {/* Circuit block */}
      {session.circuit && (
        <CircuitDisplay 
          circuit={session.circuit} 
          title="Circuit Block" 
        />
      )}

      {/* Finisher circuit */}
      {session.finisher_circuit && (
        <CircuitDisplay 
          circuit={session.finisher_circuit} 
          title="Finisher" 
        />
      )}
    </div>
  );
}

// ============================================================================
// EXAMPLE 5: Conditional Rendering
// ============================================================================

function ConditionalCircuitDisplay({ session }: SessionCardProps) {
  return (
    <div>
      {/* Only show if circuit exists */}
      {session.circuit && (
        <CircuitDisplay 
          circuit={session.circuit} 
          title="Circuit Block" 
        />
      )}

      {/* Show alternative if no circuit */}
      {!session.circuit && session.accessory && (
        <div className="mt-3">
          <h4 className="text-xs font-medium text-foreground-muted uppercase tracking-wide mb-2">
            Accessory
          </h4>
          {/* Render accessory exercises */}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// EXAMPLE 6: Circuit Library/Grid Display
// ============================================================================

function CircuitLibraryGrid({ circuits }: { circuits: CircuitBlock[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {circuits.map((circuit) => (
        <div key={circuit.circuit_id} className="bg-white rounded-lg shadow-sm">
          <CircuitDisplayCompact circuit={circuit} />
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// EXAMPLE 7: Circuit Type Filter
// ============================================================================

function FilteredCircuitDisplay({ 
  circuits, 
  filterType 
}: { 
  circuits: CircuitBlock[]; 
  filterType?: string; 
}) {
  const filteredCircuits = filterType
    ? circuits.filter(c => c.circuit_type === filterType)
    : circuits;

  return (
    <div className="space-y-4">
      {filteredCircuits.map((circuit) => (
        <CircuitDisplay 
          key={circuit.circuit_id} 
          circuit={circuit} 
          title={`${circuit.circuit_type} Circuit`}
        />
      ))}
    </div>
  );
}

// ============================================================================
// EXAMPLE 8: Circuit Detail Page
// ============================================================================

function CircuitDetailPage({ circuit }: { circuit: CircuitBlock }) {
  return (
    <div className="container-app py-8">
      {/* Circuit display */}
      <CircuitDisplay 
        circuit={circuit} 
        title="Workout Details"
        showMetrics={true}
      />

      {/* Additional information */}
      <div className="mt-6 p-4 bg-background-secondary rounded-lg">
        <h3 className="font-semibold mb-2">Circuit Info</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-foreground-muted">Difficulty:</span>
            <span className="font-medium">{circuit.difficulty_tier}/5</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Fatigue Factor:</span>
            <span className="font-medium">{circuit.fatigue_factor}x</span>
          </div>
          <div className="flex justify-between">
            <span className="text-foreground-muted">Stimulus Factor:</span>
            <span className="font-medium">{circuit.stimulus_factor}x</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// EXAMPLE 9: Loading State
// ============================================================================

function CircuitDisplayWithLoading({ circuit, isLoading }: { 
  circuit?: CircuitBlock; 
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <div className="p-6 bg-background-secondary rounded-xl animate-pulse">
        <div className="h-6 bg-background-input rounded mb-3 w-1/2"></div>
        <div className="h-4 bg-background-input rounded mb-2 w-1/3"></div>
        <div className="space-y-2 mt-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-background-input rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  return circuit ? (
    <CircuitDisplay circuit={circuit} title="Circuit Block" />
  ) : (
    <div className="p-6 text-center text-foreground-muted">
      No circuit available
    </div>
  );
}

// ============================================================================
// EXAMPLE 10: Error State
// ============================================================================

function CircuitDisplayWithError({ circuit, error }: { 
  circuit?: CircuitBlock; 
  error?: string;
}) {
  if (error) {
    return (
      <div className="p-4 bg-error/10 border border-error/20 rounded-lg">
        <p className="text-error text-sm font-medium">
          Failed to load circuit: {error}
        </p>
      </div>
    );
  }

  return circuit ? (
    <CircuitDisplay circuit={circuit} title="Circuit Block" />
  ) : null;
}

// ============================================================================
// EXAMPLE 11: Custom Section Title
// ============================================================================

function CustomTitleExample({ circuit }: { circuit: CircuitBlock }) {
  const customTitle = `${circuit.circuit_type} Challenge`;
  
  return (
    <CircuitDisplay 
      circuit={circuit} 
      title={customTitle}
    />
  );
}

// ============================================================================
// EXAMPLE 12: Multiple Circuits in One Session
// ============================================================================

function MultiCircuitSession({ session }: { session: Session }) {
  return (
    <div className="space-y-6">
      {/* Main circuit */}
      {session.circuit && (
        <section>
          <CircuitDisplay 
            circuit={session.circuit} 
            title="Main Circuit"
          />
        </section>
      )}

      {/* Finisher circuit */}
      {session.finisher_circuit && (
        <section>
          <CircuitDisplay 
            circuit={session.finisher_circuit} 
            title="Finisher"
          />
        </section>
      )}
    </div>
  );
}

// ============================================================================
// EXAMPLE 13: Circuit Comparison
// ============================================================================

function CircuitComparison({ 
  circuit1, 
  circuit2 
}: { 
  circuit1: CircuitBlock; 
  circuit2: CircuitBlock;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <h3 className="text-sm font-medium text-foreground-muted mb-2">Option A</h3>
        <CircuitDisplay 
          circuit={circuit1} 
          title="Circuit A"
          showMetrics={true}
        />
      </div>
      <div>
        <h3 className="text-sm font-medium text-foreground-muted mb-2">Option B</h3>
        <CircuitDisplay 
          circuit={circuit2} 
          title="Circuit B"
          showMetrics={true}
        />
      </div>
    </div>
  );
}

// ============================================================================
// EXAMPLE 14: Responsive Layout
// ============================================================================

function ResponsiveCircuitList({ circuits }: { circuits: CircuitBlock[] }) {
  return (
    <div className="space-y-3">
      {circuits.map((circuit) => (
        <div key={circuit.circuit_id}>
          {/* Full display on mobile */}
          <div className="md:hidden">
            <CircuitDisplay 
              circuit={circuit} 
              title="Circuit"
            />
          </div>
          
          {/* Compact display on desktop */}
          <div className="hidden md:block">
            <CircuitDisplayCompact circuit={circuit} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// EXAMPLE 15: Circuit with Callback
// ============================================================================

function CircuitDisplayWithCallback({ 
  circuit, 
  onCircuitClick 
}: { 
  circuit: CircuitBlock; 
  onCircuitClick: (circuitId: number) => void;
}) {
  return (
    <div 
      className="cursor-pointer"
      onClick={() => onCircuitClick(circuit.circuit_id)}
    >
      <CircuitDisplay 
        circuit={circuit} 
        title="Circuit Block"
      />
    </div>
  );
}

// Export all examples
export {
  BasicUsageExample,
  HideMetricsExample,
  CompactDisplayExample,
  SessionCardWithCircuit,
  ConditionalCircuitDisplay,
  CircuitLibraryGrid,
  FilteredCircuitDisplay,
  CircuitDetailPage,
  CircuitDisplayWithLoading,
  CircuitDisplayWithError,
  CustomTitleExample,
  MultiCircuitSession,
  CircuitComparison,
  ResponsiveCircuitList,
  CircuitDisplayWithCallback,
};
