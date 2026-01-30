/**
 * CircuitDisplay Component - Type and Data Validation Tests
 * 
 * This file contains test data and validation examples to ensure
 * the CircuitDisplay component works correctly with the existing
 * Gainsly type system and data structures.
 */

import type { CircuitBlock, CircuitExercise, CircuitType } from '@/types';

// ============================================================================
// TEST DATA: Valid Circuit Block Examples
// ============================================================================

const TEST_CIRCUITS: Record<string, CircuitBlock> = {
  // AMRAP with reps
  AMRAP_WITH_REPS: {
    circuit_id: 1,
    name: 'AMRAP Test',
    circuit_type: 'AMRAP',
    difficulty_tier: 2,
    estimated_duration_seconds: 600,
    default_rounds: 10,
    primary_region: 'full body',
    primary_muscles: ['quadriceps', 'chest'],
    fatigue_factor: 1.3,
    stimulus_factor: 1.5,
    exercises: [
      {
        movement: 'Burpees',
        movement_id: 1,
        sequence: 1,
        metric_type: 'reps',
        reps: 10,
        rest_seconds: 0,
      },
      {
        movement: 'Push-ups',
        movement_id: 2,
        sequence: 2,
        metric_type: 'reps',
        reps: 15,
        rest_seconds: 0,
      },
    ],
  },

  // EMOM with time intervals
  EMOM_WITH_TIME: {
    circuit_id: 2,
    name: 'EMOM Test',
    circuit_type: 'EMOM',
    difficulty_tier: 2,
    estimated_duration_seconds: 480,
    default_rounds: 8,
    primary_region: 'upper body',
    primary_muscles: ['shoulders', 'triceps'],
    fatigue_factor: 1.2,
    stimulus_factor: 1.4,
    exercises: [
      {
        movement: 'Thrusters',
        movement_id: 3,
        sequence: 1,
        metric_type: 'reps',
        reps: 5,
        duration_seconds: 40,
        rest_seconds: 20,
        rx_weight_male: 43,
        rx_weight_female: 30,
      },
      {
        movement: 'Pull-ups',
        movement_id: 4,
        sequence: 2,
        metric_type: 'reps',
        reps: 7,
        duration_seconds: 40,
        rest_seconds: 20,
      },
    ],
  },

  // RFT with prescribed weights
  RFT_WITH_WEIGHTS: {
    circuit_id: 3,
    name: 'RFT Test',
    circuit_type: 'rounds_for_time',
    difficulty_tier: 3,
    estimated_duration_seconds: 900,
    default_rounds: 5,
    primary_region: 'full body',
    primary_muscles: ['quadriceps', 'shoulders', 'core'],
    fatigue_factor: 1.5,
    stimulus_factor: 1.7,
    exercises: [
      {
        movement: 'Deadlifts',
        movement_id: 5,
        sequence: 1,
        metric_type: 'reps',
        reps: 5,
        rest_seconds: 60,
        rx_weight_male: 84,
        rx_weight_female: 57,
      },
      {
        movement: 'Handstand Push-ups',
        movement_id: 6,
        sequence: 2,
        metric_type: 'reps',
        reps: 5,
        rest_seconds: 60,
      },
    ],
  },

  // LADDER with notes
  LADDER_WITH_NOTES: {
    circuit_id: 4,
    name: 'Ladder Test',
    circuit_type: 'ladder',
    difficulty_tier: 3,
    estimated_duration_seconds: 720,
    default_rounds: 6,
    primary_region: 'upper body',
    primary_muscles: ['chest', 'triceps'],
    fatigue_factor: 1.6,
    stimulus_factor: 1.8,
    exercises: [
      {
        movement: 'Thrusters',
        movement_id: 7,
        sequence: 1,
        metric_type: 'reps',
        reps: 3,
        rest_seconds: 45,
        notes: 'Ladder: 3, 6, 9, 12, 15, 18',
        rx_weight_male: 43,
        rx_weight_female: 30,
      },
      {
        movement: 'Chest-to-Bar Pull-ups',
        movement_id: 8,
        sequence: 2,
        metric_type: 'reps',
        reps: 3,
        rest_seconds: 45,
        notes: 'Ladder: 3, 6, 9, 12, 15, 18',
      },
    ],
  },

  // Distance-based exercises
  DISTANCE_BASED: {
    circuit_id: 5,
    name: 'Distance Test',
    circuit_type: 'AMRAP',
    difficulty_tier: 2,
    estimated_duration_seconds: 960,
    default_rounds: 16,
    primary_region: 'lower body',
    primary_muscles: ['quadriceps', 'hamstrings', 'calves'],
    fatigue_factor: 1.3,
    stimulus_factor: 1.5,
    exercises: [
      {
        movement: '400m Run',
        movement_id: 9,
        sequence: 1,
        metric_type: 'distance',
        distance_meters: 400,
        rest_seconds: 90,
      },
      {
        movement: '500m Row',
        movement_id: 10,
        sequence: 2,
        metric_type: 'distance',
        distance_meters: 500,
        rest_seconds: 90,
      },
    ],
  },

  // Calorie-based exercises with max
  CALORIE_WITH_MAX: {
    circuit_id: 6,
    name: 'Calorie Test',
    circuit_type: 'AMRAP',
    difficulty_tier: 2,
    estimated_duration_seconds: 600,
    default_rounds: 10,
    primary_region: 'full body',
    primary_muscles: ['quadriceps', 'back', 'core'],
    fatigue_factor: 1.4,
    stimulus_factor: 1.6,
    exercises: [
      {
        movement: 'Row',
        movement_id: 11,
        sequence: 1,
        metric_type: 'calories',
        calories: 999,
        reps: 999,
        rest_seconds: 0,
        notes: 'max cals',
      },
      {
        movement: 'Burpees',
        movement_id: 12,
        sequence: 2,
        metric_type: 'reps',
        reps: 20,
        rest_seconds: 0,
      },
    ],
  },

  // Time-based exercises
  TIME_BASED: {
    circuit_id: 7,
    name: 'Time Test',
    circuit_type: 'AMRAP',
    difficulty_tier: 1,
    estimated_duration_seconds: 480,
    default_rounds: 8,
    primary_region: 'full body',
    primary_muscles: ['core', 'shoulders'],
    fatigue_factor: 1.1,
    stimulus_factor: 1.3,
    exercises: [
      {
        movement: 'Plank Hold',
        movement_id: 13,
        sequence: 1,
        metric_type: 'time',
        duration_seconds: 60,
        rest_seconds: 30,
      },
      {
        movement: 'L-Sit Hold',
        movement_id: 14,
        sequence: 2,
        metric_type: 'time',
        duration_seconds: 30,
        rest_seconds: 30,
      },
    ],
  },

  // Mixed metric types
  MIXED_METRICS: {
    circuit_id: 8,
    name: 'Mixed Metrics Test',
    circuit_type: 'AMRAP',
    difficulty_tier: 2,
    estimated_duration_seconds: 720,
    default_rounds: 12,
    primary_region: 'full body',
    primary_muscles: ['quadriceps', 'shoulders', 'back'],
    fatigue_factor: 1.3,
    stimulus_factor: 1.5,
    exercises: [
      {
        movement: '200m Run',
        movement_id: 15,
        sequence: 1,
        metric_type: 'distance',
        distance_meters: 200,
        rest_seconds: 30,
      },
      {
        movement: '10 Push-ups',
        movement_id: 16,
        sequence: 2,
        metric_type: 'reps',
        reps: 10,
        rest_seconds: 0,
      },
      {
        movement: '30s Plank',
        movement_id: 17,
        sequence: 3,
        metric_type: 'time',
        duration_seconds: 30,
        rest_seconds: 0,
      },
    ],
  },

  // All circuit types
  ALL_TYPES: Object.values({
    AMRAP: 'amrap',
    EMOM: 'emom',
    RFT: 'rounds_for_time',
    LADDER: 'ladder',
    CHIPPER: 'chipper',
    TABATA: 'tabata',
    STATION: 'station',
  }).reduce((acc, type) => {
    acc[type.toUpperCase()] = {
      circuit_id: 100 + Math.floor(Math.random() * 1000),
      name: `${type.toUpperCase()} Circuit`,
      circuit_type: type as CircuitType,
      difficulty_tier: 2,
      estimated_duration_seconds: 600,
      default_rounds: 5,
      primary_region: 'full body',
      primary_muscles: ['quadriceps', 'chest'],
      fatigue_factor: 1.3,
      stimulus_factor: 1.5,
      exercises: [
        {
          movement: 'Burpees',
          movement_id: 1,
          sequence: 1,
          metric_type: 'reps',
          reps: 10,
          rest_seconds: 0,
        },
      ],
    };
    return acc;
  }, {} as Record<string, CircuitBlock>),
};

// ============================================================================
// TYPE VALIDATION TESTS
// ============================================================================

/**
 * Test 1: Validate CircuitBlock type structure
 */
function validateCircuitBlockStructure(circuit: CircuitBlock): boolean {
  const requiredFields: (keyof CircuitBlock)[] = [
    'circuit_id',
    'name',
    'circuit_type',
    'difficulty_tier',
    'estimated_duration_seconds',
    'default_rounds',
    'primary_region',
    'primary_muscles',
    'fatigue_factor',
    'stimulus_factor',
    'exercises',
  ];

  return requiredFields.every(field => field in circuit);
}

/**
 * Test 2: Validate CircuitExercise type structure
 */
function validateCircuitExerciseStructure(exercise: CircuitExercise): boolean {
  const requiredFields: (keyof CircuitExercise)[] = [
    'movement',
    'movement_id',
    'sequence',
    'metric_type',
  ];

  return requiredFields.every(field => field in exercise);
}

/**
 * Test 3: Validate metric type values
 */
function validateMetricType(metricType: string): boolean {
  const validTypes = ['reps', 'time', 'distance', 'calories'];
  return validTypes.includes(metricType.toLowerCase());
}

/**
 * Test 4: Validate circuit type values
 */
function validateCircuitType(circuitType: string): boolean {
  const validTypes: CircuitType[] = [
    'rounds_for_time',
    'amrap',
    'emom',
    'ladder',
    'tabata',
    'chipper',
    'station',
  ];
  return validTypes.includes(circuitType.toLowerCase() as CircuitType);
}

/**
 * Test 5: Validate exercise has at least one metric
 */
function validateExerciseHasMetric(exercise: CircuitExercise): boolean {
  return !!(
    exercise.reps ||
    exercise.duration_seconds ||
    exercise.distance_meters ||
    exercise.calories
  );
}

/**
 * Test 6: Validate exercise sequence is unique
 */
function validateExerciseSequences(circuit: CircuitBlock): boolean {
  const sequences = circuit.exercises.map(ex => ex.sequence);
  const uniqueSequences = new Set(sequences);
  return sequences.length === uniqueSequences.size;
}

/**
 * Test 7: Validate estimated duration is reasonable
 */
function validateDuration(durationSeconds: number): boolean {
  return durationSeconds > 0 && durationSeconds <= 3600; // Max 1 hour
}

/**
 * Test 8: Validate default rounds is reasonable
 */
function validateRounds(rounds: number): boolean {
  return rounds > 0 && rounds <= 50;
}

/**
 * Test 9: Validate muscle list
 */
function validateMuscles(muscles: string[]): boolean {
  const validMuscles = [
    'quadriceps', 'hamstrings', 'glutes', 'calves',
    'chest', 'lats', 'upper_back', 'rear_delts', 'front_delts', 'side_delts',
    'biceps', 'triceps', 'forearms', 'core', 'obliques', 'lower_back',
    'hip_flexors', 'adductors', 'abductors', 'full_body'
  ];
  return muscles.every(muscle => validMuscles.includes(muscle.toLowerCase()));
}

/**
 * Test 10: Validate fatigue and stimulus factors
 */
function validateFactors(fatigue: number, stimulus: number): boolean {
  return fatigue > 0 && fatigue <= 3 && stimulus > 0 && stimulus <= 3;
}

// ============================================================================
// RUN ALL TESTS
// ============================================================================

export function runCircuitDisplayTests(): {
  passed: number;
  failed: number;
  results: Array<{ test: string; passed: boolean; message?: string }>;
} {
  const results: Array<{ test: string; passed: boolean; message?: string }> = [];
  let passed = 0;
  let failed = 0;

  // Test all circuit data
  Object.entries(TEST_CIRCUITS).forEach(([name, circuit]) => {
    // Test 1: Circuit structure
    if (validateCircuitBlockStructure(circuit)) {
      results.push({ test: `${name}: Circuit structure`, passed: true });
      passed++;
    } else {
      results.push({ test: `${name}: Circuit structure`, passed: false, message: 'Missing required fields' });
      failed++;
    }

    // Test 4: Circuit type
    if (validateCircuitType(circuit.circuit_type)) {
      results.push({ test: `${name}: Circuit type`, passed: true });
      passed++;
    } else {
      results.push({ test: `${name}: Circuit type`, passed: false, message: 'Invalid circuit type' });
      failed++;
    }

    // Test 7: Duration
    if (validateDuration(circuit.estimated_duration_seconds)) {
      results.push({ test: `${name}: Duration`, passed: true });
      passed++;
    } else {
      results.push({ test: `${name}: Duration`, passed: false, message: 'Invalid duration' });
      failed++;
    }

    // Test 8: Rounds
    if (validateRounds(circuit.default_rounds)) {
      results.push({ test: `${name}: Rounds`, passed: true });
      passed++;
    } else {
      results.push({ test: `${name}: Rounds`, passed: false, message: 'Invalid rounds' });
      failed++;
    }

    // Test 9: Muscles
    if (validateMuscles(circuit.primary_muscles)) {
      results.push({ test: `${name}: Muscles`, passed: true });
      passed++;
    } else {
      results.push({ test: `${name}: Muscles`, passed: false, message: 'Invalid muscles' });
      failed++;
    }

    // Test 10: Factors
    if (validateFactors(circuit.fatigue_factor, circuit.stimulus_factor)) {
      results.push({ test: `${name}: Factors`, passed: true });
      passed++;
    } else {
      results.push({ test: `${name}: Factors`, passed: false, message: 'Invalid factors' });
      failed++;
    }

    // Test exercises
    circuit.exercises.forEach((exercise, idx) => {
      // Test 2: Exercise structure
      if (validateCircuitExerciseStructure(exercise)) {
        results.push({ test: `${name}: Exercise ${idx + 1} structure`, passed: true });
        passed++;
      } else {
        results.push({ test: `${name}: Exercise ${idx + 1} structure`, passed: false, message: 'Missing required fields' });
        failed++;
      }

      // Test 3: Metric type
      if (validateMetricType(exercise.metric_type)) {
        results.push({ test: `${name}: Exercise ${idx + 1} metric type`, passed: true });
        passed++;
      } else {
        results.push({ test: `${name}: Exercise ${idx + 1} metric type`, passed: false, message: 'Invalid metric type' });
        failed++;
      }

      // Test 5: Exercise has metric
      if (validateExerciseHasMetric(exercise)) {
        results.push({ test: `${name}: Exercise ${idx + 1} has metric`, passed: true });
        passed++;
      } else {
        results.push({ test: `${name}: Exercise ${idx + 1} has metric`, passed: false, message: 'No metric value' });
        failed++;
      }
    });

    // Test 6: Exercise sequences
    if (validateExerciseSequences(circuit)) {
      results.push({ test: `${name}: Exercise sequences unique`, passed: true });
      passed++;
    } else {
      results.push({ test: `${name}: Exercise sequences unique`, passed: false, message: 'Duplicate sequences' });
      failed++;
    }
  });

  return {
    passed,
    failed,
    results,
  };
}

// ============================================================================
// EXPORT TEST DATA
// ============================================================================

export { TEST_CIRCUITS };
export type {
  CircuitBlock,
  CircuitExercise,
  CircuitType,
};
