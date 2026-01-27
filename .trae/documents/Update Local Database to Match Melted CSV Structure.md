# Plan: Update Local Database circuit_templates Structure

## Context
- **Goal**: Update local database `circuit_templates` table to match `circuit_templates_melted_clean.csv` structure
- **CSV Structure**: 151 rows, one per exercise per circuit (flattened)
- **Current DB Structure**: 27 rows, one per circuit with nested `exercises_json` array
- **Critical Finding**: Frontend and backend heavily depend on `exercises_json` format

---

## Analysis Results

### Current Dependencies on `exercises_json`:
1. **Frontend (5 files)**: All components expect `circuit.exercises_json` array
2. **Backend API**: Endpoints return/enrich `exercises_json`
3. **Session Generation**: Expands circuits from `exercises_json` 
4. **Workout Logging**: Creates session_exercises from `exercises_json`
5. **Foreign Keys**: `sessions.main_circuit_id`, `sessions.finisher_circuit_id`, `session_exercises.circuit_id`

### Structure Comparison:

**Current Schema** (1 row per circuit):
```sql
circuit_templates (
  id, name, description, circuit_type,
  exercises_json JSON [],  -- Contains all exercises
  default_rounds, default_duration_seconds,
  bucket_stress JSON,
  tags JSON [],
  difficulty_tier,
  fatigue_factor, stimulus_factor, min_recovery_hours,
  muscle_volume JSON, muscle_fatigue JSON,
  total_reps, estimated_work_seconds, effective_work_volume
)
```

**Melted CSV Schema** (1 row per exercise):
```sql
circuit_templates (
  id SERIAL PRIMARY KEY,
  circuit_id, circuit_name, circuit_description, circuit_type,
  exercise_sequence, total_exercises,
  movement_id, movement_name, metric_type,
  reps, distance_meters, duration_seconds, calories,
  rest_seconds, notes, rx_weight_male, rx_weight_female,
  default_rounds, default_duration_seconds, difficulty_tier, min_recovery_hours
)
```

---

## Recommended Approach: **Option 2 - Keep Current Structure** ✅

**Rationale**: Changing to melted structure would break entire application:
- ❌ Frontend: 5+ files need updates (types, circuits.tsx, library.tsx, admin pages)
- ❌ Backend: API responses, session generator, workout logging all break
- ❌ Foreign keys need complex migration
- ❌ Risk: Very high, extensive testing required

**Better Solution**: Transform melted CSV back to exercises_json format before importing.

---

## Implementation Plan

### Phase 1: Create CSV Transformation Script
**File**: `scripts/unmelt_circuit_templates.py`

1. Read `circuit_templates_melted_clean.csv` (151 rows)
2. Group by `circuit_id` to reconstruct circuits
3. Aggregate exercises into `exercises_json` array
4. Output `circuit_templates_import.csv` (27 rows, exercises_json format)
5. Preserve all metadata (difficulty_tier, fatigue_factor, etc.) from first row per circuit

### Phase 2: Create Database Migration
**File**: `alembic/versions/update_circuit_templates_for_csv_import.py`

1. **No schema changes** - keep current structure
2. **Add optional columns** if missing (created_at, updated_at for Supabase compatibility)
3. **Verify foreign key constraints** are intact
4. **Add migration documentation**

### Phase 3: Update Import Documentation
**File**: `scripts/supabase_csv_import_guide.md`

1. Update to use `circuit_templates_import.csv` (unmelted version)
2. Add notes about transformation script
3. Verify all 14 CSV files are listed correctly

### Phase 4: Verify Existing Code
**No changes needed** - all code continues to work:
- ✅ Frontend types and components
- ✅ Backend API endpoints
- ✅ Session generation logic
- ✅ Workout logging functionality
- ✅ Foreign key relationships

---

## Alternative: Option 3 - Hybrid (If User Insists)

If user wants normalized structure long-term:

### Phase 1: Create New Table
**File**: `alembic/versions/create_circuit_exercises_table.py`

```sql
CREATE TABLE circuit_exercises (
  id SERIAL PRIMARY KEY,
  circuit_id INTEGER REFERENCES circuit_templates(id) ON DELETE CASCADE,
  movement_id INTEGER REFERENCES movements(id),
  movement_name VARCHAR(255),
  sequence_number INTEGER NOT NULL,
  reps INTEGER,
  distance_meters INTEGER,
  duration_seconds INTEGER,
  calories INTEGER,
  rest_seconds INTEGER,
  notes TEXT,
  rx_weight_male NUMERIC(10,2),
  rx_weight_female NUMERIC(10,2),
  metric_type VARCHAR(50)
);
```

### Phase 2: Backend Transformation
**Files**: 
- `app/api/routes/circuits.py` - Populate exercises_json from circuit_exercises
- `app/models/circuit.py` - Add relationship to circuit_exercises
- `app/services/session_generator.py` - Query circuit_exercises instead of parsing JSON

### Phase 3: Frontend (No Changes)
- Keep exercises_json in API responses
- Backend aggregates circuit_exercises into exercises_json

### Phase 4: Migrate Data
**File**: `scripts/migrate_circuit_exercises_from_csv.py`

1. Read melted CSV
2. Insert into circuit_exercises table
3. Reconstruct exercises_json for each circuit
4. Update circuit_templates.exercises_json

---

## Execution Steps (Option 2 - Recommended)

1. ✅ Create `scripts/unmelt_circuit_templates.py` to transform CSV
2. ✅ Generate `circuit_templates_import.csv` with exercises_json format
3. ✅ Create migration to ensure current schema is ready
4. ✅ Update import guide
5. ✅ Test import locally
6. ✅ Verify application still works
7. ✅ No frontend or backend code changes needed

---

## Questions for User

1. **Do you want Option 2 (keep current structure)** or **Option 3 (hybrid normalized)**?
2. If Option 3, are you comfortable with backend-only changes (no frontend updates needed)?
3. Should I create transformation script to unmelt the CSV for Option 2?
