import { CircuitDisplay, CircuitDisplayCompact } from './CircuitDisplay';
import type { CircuitBlock } from '@/types';

// Example circuit data for different types
const EXAMPLE_CIRCUITS: Record<string, CircuitBlock> = {
  AMRAP: {
    circuit_id: 1,
    name: 'The Filthy Fifty',
    circuit_type: 'AMRAP',
    difficulty_tier: 3,
    estimated_duration_seconds: 960,
    default_rounds: 20,
    primary_region: 'full body',
    primary_muscles: ['quadriceps', 'hamstrings', 'chest', 'shoulders', 'core'],
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
        notes: '',
        rx_weight_male: 24,
        rx_weight_female: 20,
      },
      {
        movement: 'Jumping Pull-ups',
        movement_id: 2,
        sequence: 2,
        metric_type: 'reps',
        reps: 50,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
      {
        movement: 'Kettlebell Swings',
        movement_id: 3,
        sequence: 3,
        metric_type: 'reps',
        reps: 50,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: 24,
        rx_weight_female: 16,
      },
      {
        movement: 'Walking Lunges',
        movement_id: 4,
        sequence: 4,
        metric_type: 'reps',
        reps: 50,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
      {
        movement: 'Knees to Elbows',
        movement_id: 5,
        sequence: 5,
        metric_type: 'reps',
        reps: 50,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
    ],
  },
  EMOM: {
    circuit_id: 2,
    name: 'Power Hour',
    circuit_type: 'EMOM',
    difficulty_tier: 2,
    estimated_duration_seconds: 480,
    default_rounds: 8,
    primary_region: 'full body',
    primary_muscles: ['shoulders', 'quadriceps', 'core'],
    fatigue_factor: 1.3,
    stimulus_factor: 1.5,
    exercises: [
      {
        movement: 'Burpees',
        movement_id: 6,
        sequence: 1,
        metric_type: 'reps',
        reps: 10,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
      {
        movement: 'Power Cleans',
        movement_id: 7,
        sequence: 2,
        metric_type: 'reps',
        reps: 5,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: 61,
        rx_weight_female: 43,
      },
    ],
  },
  RFT: {
    circuit_id: 3,
    name: 'The Chief',
    circuit_type: 'RFT',
    difficulty_tier: 2,
    estimated_duration_seconds: 600,
    default_rounds: 5,
    primary_region: 'full body',
    primary_muscles: ['shoulders', 'triceps', 'chest', 'core'],
    fatigue_factor: 1.4,
    stimulus_factor: 1.6,
    exercises: [
      {
        movement: 'Power Cleans',
        movement_id: 8,
        sequence: 1,
        metric_type: 'reps',
        reps: 3,
        rest_seconds: 60,
        notes: '',
        rx_weight_male: 84,
        rx_weight_female: 57,
      },
      {
        movement: 'Push-ups',
        movement_id: 9,
        sequence: 2,
        metric_type: 'reps',
        reps: 6,
        rest_seconds: 60,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
      {
        movement: 'Air Squats',
        movement_id: 10,
        sequence: 3,
        metric_type: 'reps',
        reps: 9,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
    ],
  },
  LADDER: {
    circuit_id: 4,
    name: 'Ladder Hell',
    circuit_type: 'LADDER',
    difficulty_tier: 3,
    estimated_duration_seconds: 720,
    default_rounds: 7,
    primary_region: 'upper body',
    primary_muscles: ['chest', 'triceps', 'shoulders'],
    fatigue_factor: 1.6,
    stimulus_factor: 1.7,
    exercises: [
      {
        movement: 'Thrusters',
        movement_id: 11,
        sequence: 1,
        metric_type: 'reps',
        reps: 3,
        rest_seconds: 45,
        notes: 'Ladder: 3, 6, 9, 12, 15, 18, 21',
        rx_weight_male: 43,
        rx_weight_female: 30,
      },
      {
        movement: 'Pull-ups',
        movement_id: 12,
        sequence: 2,
        metric_type: 'reps',
        reps: 3,
        rest_seconds: 0,
        notes: 'Ladder: 3, 6, 9, 12, 15, 18, 21',
        rx_weight_male: null,
        rx_weight_female: null,
      },
    ],
  },
  TIME_BASED: {
    circuit_id: 5,
    name: 'Sprint Intervals',
    circuit_type: 'AMRAP',
    difficulty_tier: 2,
    estimated_duration_seconds: 600,
    default_rounds: 10,
    primary_region: 'lower body',
    primary_muscles: ['quadriceps', 'hamstrings', 'calves'],
    fatigue_factor: 1.2,
    stimulus_factor: 1.4,
    exercises: [
      {
        movement: '400m Run',
        movement_id: 13,
        sequence: 1,
        metric_type: 'distance',
        distance_meters: 400,
        rest_seconds: 90,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
      {
        movement: 'Row',
        movement_id: 14,
        sequence: 2,
        metric_type: 'distance',
        distance_meters: 500,
        rest_seconds: 90,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
    ],
  },
  CALORIE_BASED: {
    circuit_id: 6,
    name: 'Rowing WOD',
    circuit_type: 'AMRAP',
    difficulty_tier: 2,
    estimated_duration_seconds: 960,
    default_rounds: 16,
    primary_region: 'full body',
    primary_muscles: ['quadriceps', 'hamstrings', 'back', 'core'],
    fatigue_factor: 1.3,
    stimulus_factor: 1.5,
    exercises: [
      {
        movement: 'Row',
        movement_id: 15,
        sequence: 1,
        metric_type: 'calories',
        calories: 20,
        rest_seconds: 0,
        notes: 'max cals',
        rx_weight_male: null,
        rx_weight_female: null,
      },
      {
        movement: 'Burpees',
        movement_id: 16,
        sequence: 2,
        metric_type: 'reps',
        reps: 20,
        rest_seconds: 0,
        notes: '',
        rx_weight_male: null,
        rx_weight_female: null,
      },
    ],
  },
};

// Example usage component
export function CircuitDisplayExample() {
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">
      <h1 className="text-3xl font-bold text-foreground mb-2">Circuit Display Examples</h1>
      <p className="text-foreground-muted">
        Different circuit types with their respective styling and metrics
      </p>

      {/* AMRAP Example */}
      <section>
        <h2 className="text-xl font-semibold text-foreground mb-4">AMRAP Circuit</h2>
        <CircuitDisplay circuit={EXAMPLE_CIRCUITS.AMRAP} title="Main Circuit" />
      </section>

      {/* EMOM Example */}
      <section>
        <h2 className="text-xl font-semibold text-foreground mb-4">EMOM Circuit</h2>
        <CircuitDisplay circuit={EXAMPLE_CIRCUITS.EMOM} title="Conditioning Circuit" />
      </section>

      {/* RFT Example */}
      <section>
        <h2 className="text-xl font-semibold text-foreground mb-4">RFT Circuit</h2>
        <CircuitDisplay circuit={EXAMPLE_CIRCUITS.RFT} title="Finisher Circuit" />
      </section>

      {/* LADDER Example */}
      <section>
        <h2 className="text-xl font-semibold text-foreground mb-4">Ladder Circuit</h2>
        <CircuitDisplay circuit={EXAMPLE_CIRCUITS.LADDER} title="Strength Circuit" />
      </section>

      {/* Time-based Example */}
      <section>
        <h2 className="text-xl font-semibold text-foreground mb-4">Distance/Time Circuit</h2>
        <CircuitDisplay circuit={EXAMPLE_CIRCUITS.TIME_BASED} title="Cardio Circuit" />
      </section>

      {/* Calorie-based Example */}
      <section>
        <h2 className="text-xl font-semibold text-foreground mb-4">Calorie Circuit</h2>
        <CircuitDisplay circuit={EXAMPLE_CIRCUITS.CALORIE_BASED} title="Metcon Circuit" />
      </section>

      {/* Compact Examples */}
      <section>
        <h2 className="text-xl font-semibold text-foreground mb-4">Compact Display (for lists/cards)</h2>
        <div className="space-y-3">
          {Object.entries(EXAMPLE_CIRCUITS).map(([key, circuit]) => (
            <CircuitDisplayCompact key={key} circuit={circuit} />
          ))}
        </div>
      </section>
    </div>
  );
}

export default CircuitDisplayExample;
