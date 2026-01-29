# Implementation Plan: Circuit Melted and Macro Tables

## Overview
Create two new database tables to improve circuit data indexing, querying, and comparability with the movements table:
1. **circuits_melted** - One row per exercise (similar to CSV format)
2. **circuits_macro** - Circuit-level aggregated metrics with 50% normalization

---

## Phase 1: Database Schema Design

### Create `circuits_melted` Table
- Foreign keys to `circuit_templates.id` (CASCADE) and `movements.id` (RESTRICT)
- Exercise sequence and positioning
- Movement metrics: reps, distance_meters, duration_seconds, calories
- Rest periods, notes, RX weights
- Indexes on: circuit_id, movement_id, exercise_sequence, metric_type
- Unique constraint: (circuit_id, exercise_sequence)

### Create `circuits_macro` Table
- 1:1 relationship with circuit_templates (circuit_id as PK)
- Exercise count: total_exercises, unique_movements
- Primary metrics: total_reps, total_work_seconds, total_rest_seconds, estimated_duration_seconds
- Difficulty: difficulty_tier, min_recovery_hours
- Muscle engagement: primary_muscles (JSON), muscle_engagement_score
- Equipment: required_equipment (JSON), equipment_complexity
- Movement patterns: movement_pattern_counts (JSON), pattern_diversity_score
- Metabolic profile: metabolic_profile (JSON), estimated_calories_per_hour
- Circuit-specific: default_rounds, circuit_type_intensity
- Quality metrics: data_completeness_score, validation_errors

### Update CircuitTemplate Model
- Add back-references to both tables
- Keep exercises_json for backward compatibility (deprecated)

---

## Phase 2: 50% Normalization Implementation

### Calculate Main Lift Baseline
```python
# Query programs with MAIN section movements
# Filter: compound AND (fatigue_factor > 0.6 OR is_complex_lift)
# Calculate average: fatigue_factor, stimulus_factor, work_volume
```

### Normalization Formula
```python
NORMALIZATION_TARGET = 0.5

# Factors:
# - Volume factor: min(1.0, circuit_volume / avg_main_volume)
# - Circuit type: RFT(0.9), AMRAP(0.85), LADDER(0.88), EMOM(0.92)
# - Rep efficiency: 0.5 (high-rep, low-weight)

normalization_factor = NORMALIZATION_TARGET × volume_factor × type_factor × rep_efficiency

# Apply to:
# - fatigue_factor
# - stimulus_factor
# - muscle_volume (per muscle)
# - muscle_fatigue (per muscle)
```

### Validation
- Ensure normalized values are 40-60% of main lift baseline
- Apply adjustment factor if deviation > 20%

---

## Phase 3: Population Script

### Script: `scripts/populate_circuit_tables.py`

**Step 1: Calculate Main Lift Baseline**
- Query all programs with main_json
- Identify main lift movements (compound + fatigue_factor > 0.6 or is_complex_lift)
- Calculate averages: avg_main_fatigue, avg_main_stimulus, avg_main_volume

**Step 2: Populate circuits_melted**
- Parse circuit_templates.exercises_json
- Insert one row per exercise
- Map to original circuit_templates.id

**Step 3: Populate circuits_macro**
- For each circuit:
  - Aggregate metrics from melted data
  - Calculate muscle engagement (sum from movements)
  - Extract movement patterns from exercises
  - Build equipment requirements list
  - Calculate pattern diversity score (Simpson's index)
  - Compute metabolic profile breakdown
  - **Apply 50% normalization** to fatigue_factor, stimulus_factor, muscle_volume, muscle_fatigue
  - Estimate calories, duration, space requirements
  - Calculate data completeness score

**Step 4: Validation**
- Check all circuits have macro records
- Verify normalization targets met (40-60% range)
- Generate validation errors report

---

## Phase 4: Circuit Comparability Enhancements

### Extract Missing Fields for Circuits
- **pattern**: Analyze exercises to determine dominant pattern(s)
  - squat, hinge, lunge, horizontal_push, horizontal_pull, vertical_push, vertical_pull, conditioning
- **primary_region**: Derive from exercise composition (upper/lower/full_body)
- **compound**: False for circuits (multi-movement)
- **is_complex_lift**: Based on complexity of constituent movements

### Add to circuits_macro
- `dominant_pattern` (string)
- `primary_region` (enum)
- `pattern_distribution` (JSON: {"squat": 2, "hinge": 1, ...})
- `contains_complex_movements` (boolean)

---

## Phase 5: API Integration Updates

### Update Circuit API (`app/api/routes/circuits.py`)
- Use relationships instead of exercises_json parsing
- Load exercises with `selectinload(CircuitTemplate.melted_exercises)`
- Remove manual movement_id collection and batch queries
- Add endpoint for circuit macro metrics

### Update Session Generator (`app/services/session_generator.py`)
- Modify `_load_all_circuits()` to use junction tables
- Update volume calculation to aggregate from circuits_macro
- Enable circuit-type filtering (METABOLIC, STRENGTH, ENDURANCE)
- Add pattern/region filtering for circuits
- Implement difficulty-based filtering (difficulty_tier)
- Enhance objective scoring with circuit-type-specific bonuses

### Update Optimization Service (`app/services/optimization.py`)
- Extend SolverCircuit with exercise composition data
- Add circuit macro metrics to optimization objectives
- Update circuit volume constraints using circuits_macro

---

## Phase 6: Documentation and Testing

### Update Documentation
- Update `DATABASE_OVERVIEW.md` with new tables
- Document normalization formula and rationale
- Add schema diagrams

### Testing
- Verify all circuits populated correctly
- Check normalization values in 40-60% range
- Test query performance with new indexes
- Validate backward compatibility with exercises_json
- Test circuit filtering and comparison logic

---

## Key Decisions

### Why Two Tables?
- **circuits_melted**: Exercise-level detail, easier to query by movement
- **circuits_macro**: Pre-computed aggregates for fast circuit comparison
- Similar to movements + movement_muscle_map pattern

### 50% Normalization Rationale
- Circuits are high-rep, low-weight → less stimulus per rep
- Should complement, not replace, main lifts
- Maintains programming hierarchy while allowing meaningful contribution
- Accounts for metabolic demand and time pressure

### Backward Compatibility
- Keep exercises_json during migration
- Dual-write pattern during transition
- Future: deprecate exercises_json after verification

---

## Success Criteria
✅ Both tables created with proper indexes and constraints
✅ All circuits populated with melted and macro data
✅ Normalization values in 40-60% of main lift baseline
✅ Query performance improved (5-10x faster movement filtering)
✅ Circuits comparable to movements via pattern/region/difficulty
✅ API integration complete and tested
✅ Backward compatibility maintained