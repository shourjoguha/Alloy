# Program Creation Architecture

This document provides an overview of the intended business logic and implementation of the program creation wizard, including how constraints, marked movements, and user preferences flow through the system to build programs with microcycles and sessions.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         Frontend Program Wizard                              │
│                   (frontend/src/stores/program-wizard-store.ts)              │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              │ POST /programs
                              │ ProgramCreate schema
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    API Route Layer (programs.py)                             │
│              - Validate request                                              │
│              - Call interference_service.validate_goals()                           │
│              - Call program_service.create_program()                             │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     ProgramService (program.py)                                 │
│  - Create Program model                                                    │
│  - Generate microcycles with split config                                     │
│  - Create session shells (type, intent_tags)                                │
│  - Commit transaction                                                       │
│  - Queue background task: generate_active_microcycle_sessions()                    │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              │ Background Task
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│              Session Generator (session_generator.py)                              │
│  - For each session:                                                        │
│    1. Load context (movements, rules, preferences)                              │
│    2. Generate exercise content via LLM                                        │
│    3. Solve constraints via ConstraintSolver                                      │
│    4. Save exercises to database                                              │
│  - Track cross-session state (used movements, fatigued muscles)                      │
│  - Generate batched coach notes (Jerome)                                      │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                              │
                              │ Optional: assign circuit
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│            Circuit Assignment Service (circuit_assignment.py)                        │
│  - Atomic circuit assignment to sessions                                       │
│  - Enforce mutual exclusivity (circuits OR accessories, not both)                │
│  - Update session duration estimates                                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Schema References

### Core Models

| Model/Table | File | Purpose | Key Fields |
|-------------|-------|-----------|-------------|
| `Program` | `app/models/program.py` | Top-level program container | goals (goal_1, goal_2, goal_3), split_template, days_per_week, max_session_duration, deload_every_n_microcycles, progression_style |
| `Microcycle` | `app/models/program.py` | Time-bound program phase | program_id, sequence_number, start_date, length_days, status (ACTIVE/PLANNED), is_deload |
| `Session` | `app/models/program.py` | Single workout day | microcycle_id, date, day_number, session_type, intent_tags, finisher_circuit_id, duration fields |
| `SessionExercise` | `app/models/program.py` | Individual exercise in session | session_id, movement_id, exercise_role (MAIN/ACCESSORY/FINISHER), target_sets, target_rep_range |
| `ProgramDiscipline` | `app/models/program.py` | Junction table for program-level disciplines | program_id, discipline_type, weight |

### User Preferences

| Model/Table | File | Purpose | Key Fields |
|-------------|-------|-----------|-------------|
| `UserProfile` | `app/models/user.py` | User settings and preferences | skill_level, discipline_preferences (dict), scheduling_preferences (dict), persona_tone, persona_aggression |
| `UserMovementRule` | `app/models/user.py` | Movement-level preferences | user_id, movement_id, rule_type (HARD_NO/HARD_YES/PREFERRED), cadence, notes |
| `UserEnjoyableActivity` | `app/models/user.py` | User's favorite activities | user_id, activity_type, custom_name, recommend_every_days, enabled |

### Movement & Circuit Data

| Model/Table | File | Purpose | Key Fields |
|-------------|-------|-----------|-------------|
| `Movement` | `app/models/movement.py` | Exercise catalog | name, primary_discipline, primary_muscle, substitution_group, tags, muscle_roles |
| `CircuitTemplate` | `app/models/circuit.py` | Pre-built circuit templates | name, circuit_type, default_rounds, difficulty_tier |
| `CircuitMelted` | `app/models/circuit_extended.py` | Flattened circuit exercises | circuit_id, movement_id, exercise_sequence, reps, duration_seconds, rest_seconds |
| `CircuitMacro` | `app/models/circuit_extended.py` | Circuit aggregate metrics | circuit_id, primary_muscles, primary_region, estimated_duration_seconds, muscle_engagement_score |

### Recovery Signals

| Model/Table | File | Purpose | Key Fields |
|-------------|-------|-----------|-------------|
| `RecoverySignal` | `app/models/recovery.py` | User-reported recovery metrics | user_id, date, sleep_hours, hrv, readiness |

## Frontend Program Wizard

**File:** `frontend/src/stores/program-wizard-store.ts`

The wizard collects user input through a multi-step interface using Zustand state management:

### Wizard Steps and Data Collection

| Step | Purpose | State Fields | API Mapping |
|-------|-----------|---------------|--------------|
| **1. Goals** | User selects 1-3 goals with weights summing to 10 | `goals: GoalWeight[]` | `ProgramCreate.goals` |
| **2. Split** | Training frequency and duration | `daysPerWeek`, `maxDuration`, `splitPreference` | `ProgramCreate.days_per_week`, `max_session_duration`, `split_template` |
| **3. Disciplines** | Discipline priority weights | `disciplines: DisciplineWeight[]` | `ProgramCreate.disciplines` |
| **4. Progression** | Overload strategy | `progressionStyle` | `ProgramCreate.progression_style` |
| **5. Movements** | Mark movements as AVOID/MUST_INCLUDE/PREFER | `movementRules: MovementRuleCreate[]` | `ProgramCreate.movement_rules` |
| **6. Activities** | Enjoyable activities to schedule | `enjoyableActivities: EnjoyableActivityCreate[]` | `ProgramCreate.enjoyable_activities` |
| **7. Coach Persona** | Communication style and intensity | `communicationStyle`, `pushIntensity` | Mapped to `persona_tone`, `persona_aggression` |
| **8. Duration** | Program length in weeks | `durationWeeks` | `ProgramCreate.duration_weeks` |

### Movement Rules

Movement rules are collected in step 5 and sent to the backend:

```typescript
interface MovementRuleCreate {
  movement_id: number;
  rule_type: MovementRuleType;  // "HARD_NO" | "HARD_YES" | "PREFERRED"
  cadence: string | null;         // e.g., "once_per_week"
  notes: string | null;
}
```

**Backend Storage:** Rules are persisted to `UserMovementRule` table after program creation (see `programs.py` lines 131-159).

## API Layer

**File:** `app/api/routes/programs.py`

### POST /programs Endpoint Flow

```python
@router.post("", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(program_data: ProgramCreate, ...)
```

**Execution Sequence:**

1. **Fetch User** (lines 81-89) - Verify user exists
2. **Validate Goals** (lines 92-108) - Call `interference_service.validate_goals()` to detect conflicts
3. **Call ProgramService** (line 112) - `program_service.create_program(db, user_id, program_data)`
4. **Load Program Disciplines** (lines 120-128) - Eager load relationship for serialization
5. **Persist Movement Rules** (lines 131-159) - Create/update `UserMovementRule` records
6. **Persist Enjoyable Activities** (lines 161-193) - Create/update `UserEnjoyableActivity` records
7. **Commit Transaction** (lines 198-205) - All program/microcycle/session data committed
8. **Queue Background Task** (lines 213-216) - `program_service.generate_active_microcycle_sessions(program_id)`

### GET /programs/{program_id}

Returns `ProgramWithMicrocycleResponse` including:
- Active microcycle with sessions
- Upcoming sessions (from today to microcycle end)
- All microcycles with their sessions
- Duration estimates calculated via `TimeEstimationService`

### POST /programs/{program_id}/microcycles/generate-next

Generates next microcycle in sequence:
1. Mark current active microcycle as COMPLETE
2. Create new microcycle with split config
3. Generate sessions (shells only)
4. Queue background task for session content generation

## ProgramService

**File:** `app/services/program.py`

### Core Responsibility

The `ProgramService` is responsible for orchestrating program creation and microcycle structure. It **does not** generate exercise content - that's delegated to `SessionGeneratorService` in a background task.

### create_program() Method

**Lines:** 46-324

**Input Processing:**

1. **Validate Duration** (lines 70-75) - Must be 8-12 weeks, even number
2. **Process Goals** (lines 77-90) - Pad to 3 goals with 0-weight dummy if needed
3. **Validate Interference** (lines 93-106) - Call `InterferenceService.validate_goals()` for conflict detection
4. **Fetch User Profile** (lines 108-114) - Get discipline_preferences, scheduling_preferences
5. **Resolve Split Template** (lines 116-126) - From request or user preference, default HYBRID
6. **Resolve Microcycle Length** (lines 128-129) - From scheduling_preferences or default (7 days)
7. **Fetch User** (lines 132-133) - For experience_level and persona defaults

**Program Creation:**

8. **Create Program Model** (lines 163-182) - Store all core program data
9. **Deactivate Other Programs** (lines 184-195) - Single active program per user
10. **Create Program Disciplines** (lines 201-258) - From request, user preferences, or experience-level fallbacks

**Microcycle Generation Loop** (lines 268-313):

For each microcycle (calculated via `_partition_microcycle_lengths()`):

```python
for mc_idx, cycle_length_days in enumerate(microcycle_lengths):
    is_deload = ((mc_idx + 1) % deload_frequency == 0)  # Line 270
    
    split_config = self._build_freeform_split_config(...)      # Line 273
    split_config = self._apply_goal_based_cycle_distribution(...)  # Line 279
    split_config = self._assign_freeform_day_types_and_focus(...)  # Line 290
    
    microcycle = await self._create_microcycle(...)        # Line 302
    current_date += timedelta(days=cycle_length_days)
```

**Key Method:** `_create_microcycle()` (lines 997-1070)

- Creates `Microcycle` model with `is_deload` flag
- Creates `Session` models for each day in split config
- First microcycle is `ACTIVE`, others are `PLANNED`
- Maps day type to `SessionType` enum (line 1889)

### Deload Determination

**Line 270:** `is_deload = ((mc_idx + 1) % deload_frequency == 0)`

Deloads are scheduled every N microcycles (default: 4) based on:
- `program.deload_every_n_microcycles` - User-configurable frequency
- Zero-indexed microcycle index + 1 (1-indexed)

**Note:** The `DeloadService` (`app/services/deload.py`) exists but is **not actively used** during program generation. It provides:
- `should_trigger_deload()` - Checks recovery signals and time since last deload
- `_get_recovery_status()` - Aggregates sleep, HRV, readiness from last 7 days

### Split Configuration Methods

#### _build_freeform_split_config()

**Lines:** 1127-1147

Generates a base structure with:
- Evenly spaced training days based on `days_per_week`
- All days initially set to `full_body` or `rest`
- Returns `split_config` dict with `structure` array

#### _apply_goal_based_cycle_distribution()

**Lines:** 1238-1423

**Intended Behavior:** Apply goal-based bias to split configuration:

1. Calculate bucket scores (cardio, finisher, mobility, lifting) from goal weights
2. Convert rest days to cardio/mobility/conditioning based on goals
3. Insert `prefer_finisher` or `prefer_accessory` tags into focus arrays

**Key Parameters:**
- `scheduling_prefs["cardio_preference"]` - "finisher" | "dedicated_day" | "mixed"
- `scheduling_prefs["avoid_cardio_days"]` - Inferred from movement rules (line 113)
- `goal_weights` - From program goals

#### _assign_freeform_day_types_and_focus()

**Lines:** 1149-1236

**Intended Behavior:** Assign specific day types (upper/lower/push/pull/legs/full_body) and focus patterns:

Based on `days_per_week`:
- ≤3 days: Full body rotations
- 4 days: Upper/Lower/Upper/Lower/Full Body
- 5 days: Upper/Lower/Full Body/Upper/Lower
- ≥6 days: Push/Pull/Legs/Upper/Lower/Full Body

Pattern rotation cycles:
- Lower: squat → hinge → lunge
- Push: horizontal_push → vertical_push
- Pull: horizontal_pull → vertical_pull

**Pattern Conflict Resolution (lines 1210-1225):**
- Detects if both horizontal AND vertical patterns exist → upgrades to `full_body`
- Detects if both upper AND lower patterns exist → upgrades to `full_body`

## Session Generator

**File:** `app/services/session_generator.py`

### Core Responsibility

Generates exercise content for session shells using LLM, with constraint satisfaction via OR-Tools.

### Background Task Flow

**Entry Point:** `generate_active_microcycle_sessions()` (lines 353-393)

**Sequence:**

1. **Create New DB Session** - Independent from request transaction
2. **Fetch Active Microcycle** - Get all sessions for active microcycle
3. **Call Content Generation** - `_generate_session_content_async()` with all sessions
4. **Track State** - Used movements, movement groups, main patterns, accessory movements
5. **Generate Jerome Notes** - Batched LLM call for coach notes

### _generate_session_content_async()

**Lines:** 395-570

**For Each Session:**

#### 1. Apply Pattern Interference Rules

**Lines:** 461-474 → `_apply_pattern_interference_rules()` (lines 620-697)

**Intended Behavior:** Prevent muscle pattern overlap between consecutive sessions

**Rules Enforced:**
- No same main pattern on consecutive days (even with rest between)
- No same main pattern within 2 days
- Limit pattern usage to max 2 times per week
- Pattern alternatives: squat → hinge/lunge, horizontal_push → vertical_push

**Pattern Alternatives Mapping** (lines 656-667):
```python
pattern_alternatives = {
    "squat": ["hinge", "lunge"],
    "hinge": ["squat", "lunge"],
    "horizontal_push": ["vertical_push"],
    "vertical_push": ["horizontal_push"],
    # ... etc
}
```

**Deviation:** Pattern interference is applied **before** session content generation, modifying `session.intent_tags`. This means the LLM may receive already-modified patterns.

#### 2. Generate Session Content

**Lines:** 476-489 → `populate_session_by_id()` (lines 344-539)

**Three-Phase Approach:**

**Phase 1: Load Context** (lines 372-443)

- Fetch session, program, microcycle models
- Load `movements_by_pattern` - Organized by movement patterns
- Load `movement_rules` via `_load_user_movement_rules_dict()` (lines 1008-1041)
- Fetch `UserProfile` for skill_level, discipline_preferences, scheduling_preferences
- Load `all_movements` for constraint solving

**Movement Rules Structure:**
```python
{
    "avoid": ["movement_name", ...],      # HARD_NO rules
    "must_include": ["movement_name", ...], # HARD_YES rules
    "prefer": ["movement_name", ...]       # PREFERRED rules
}
```

**Phase 2: Generate Content Offline** (lines 446-484)

- Calls `generate_session_exercises_offline()` - No DB connection held
- Passes context data (movements, rules, preferences) to offline generator
- Determines `fatigued_muscles` from `previous_day_volume`

**Phase 3: Save Results** (lines 485-536)

- Save `Session.estimated_duration_minutes`
- Call `_save_session_exercises()` to persist `SessionExercise` records
- Calculate session volume via `_calculate_session_volume()`

**Duplicate Removal** (lines 469-483):

- Uses `DuplicateRemover.remove_cross_session_accessory_duplicates()`
- Prevents same accessory appearing on consecutive days
- Compares current session accessories with previous day's accessories

#### 3. Update Cross-Session State

**Lines:** 516-558

After each session is generated:
- Add movements to `used_movements` set
- Track main patterns in `used_main_patterns[day_number]`
- Track accessory movements in `used_accessory_movements[day_number]`
- Update `used_movement_groups` via `_update_movement_group_usage()`

### generate_session_exercises_offline()

**Lines:** 580-953

**Intended Behavior:** Generate exercise content without DB connection using LLM and constraint solving.

**Template Detection** (line 245): `_detect_session_template(session)` returns:
- `"normal"` - Standard lifting session
- `"cardio"` - Cardio-only session
- `"mobility"` - Mobility-only session

**Block Generation Flow:**

1. **Load Movements** (lines 896-964):
   - Filter by pattern (session.intent_tags)
   - Apply movement rules (avoid, must_include, prefer)
   - Convert to `SolverMovement` format for constraint solver

2. **Generate Blocks** (lines 968-1002):
   - Call `_generate_blocks_by_template()` based on detected template
   - Returns warmup, main, accessory, finisher, cooldown blocks

3. **Fill to Target Duration** (line 271):
   - Call `_fill_to_target_duration()` - Adds/removes exercises to hit target ±5%
   - Uses `TimeEstimationService.estimate_session_time_with_transitions()`

4. **Apply Constraints** (lines 954-995):
   - Build `OptimizationRequest` with:
     - `available_movements` - Filtered by rules and patterns
     - `excluded_movement_ids` - HARD_NO rules
     - `required_movement_ids` - HARD_YES rules
     - `preferred_movement_ids` - PREFERRED rules
     - `target_muscle_volumes` - From intent_tags
     - `max_fatigue` - From previous day volume
     - `session_duration_minutes` - From program config
   - Call `ConstraintSolver.solve_session_with_progressive_relaxation()`

5. **Normalize Content** (line 299):
   - Call `_normalize_session_content()` - Ensures proper structure and role assignments

### Constraint Solver (OR-Tools)

**File:** `app/services/optimization.py`

### Core Responsibility

Implements a Constraint Satisfaction Problem (CSP) solver using Google OR-Tools to select optimal exercises for a session.

### Progressive Constraint Relaxation

**Method:** `solve_session_with_progressive_relaxation()` (lines 73-154)

**Intended Behavior:** Try 5 passes with progressively relaxed constraints, returning first feasible solution:

| Pass | Fatigue Multiplier | Volume Reduction | Min Compound | Min Isolation | Description |
|------|-------------------|-------------------|----------------|------------------|-------------|
| 1 | 1.0x | Default (20%) | 2 | 2 | Original strict constraints |
| 2 | 1.5x | Default | 2 | 2 | Relax fatigue by 50% |
| 3 | 1.5x | 30% | 2 | 2 | Relax volume by 30% |
| 4 | 1.5x | 30% | 1 | 1 | Relax compound requirement |
| 5 | 2.0x | 50% | 0 | 0 | Minimum constraints (2+ movements) |

**Deviation:** The pass configs reference `activity_distribution_config.or_tools_volume_target_reduction_pct` which may be defined elsewhere.

### Internal Solver

**Method:** `_solve_session_internal()` (lines 189-...)

**Intended Behavior:** Create OR-Tools CP model with constraints:

**Variables:**
- `selected_movements[i]` - Boolean: whether movement i is selected
- `movement_order[i]` - Integer: order of movement i in session
- `selected_circuits[i]` - Boolean: whether circuit i is selected

**Constraints:**
1. **Duration Constraint:** Sum of exercise durations ≤ target_duration_minutes
2. **Fatigue Constraint:** Total fatigue ≤ max_fatigue (adjusted by pass multiplier)
3. **Stimulus Constraint:** Total stimulus ≥ min_stimulus
4. **Volume Constraint:** Target muscle volumes ± tolerance
5. **Compound Requirement:** Minimum compound exercises (varies by pass)
6. **Exclusion:** HARD_NO movements cannot be selected
7. **Requirement:** HARD_YES movements must be selected
8. **Preference:** Maximize score for PREFERRED movements

### OptimizationResult

**Fields** (lines 59-67):
```python
@dataclass
class OptimizationResult:
    selected_movements: List[SolverMovement]
    selected_circuits: List[SolverCircuit]
    total_fatigue: float
    total_stimulus: float
    estimated_duration: int
    status: str  # "OPTIMAL", "FEASIBLE", "INFEASIBLE"
    pass_number: int  # Which pass succeeded
    pass_config: str  # Config description
```

## Circuit Assignment

**File:** `app/services/circuit_assignment.py`

### Core Responsibility

Atomic assignment of circuit templates to sessions with mutual exclusivity enforcement.

### assign_circuit_to_session()

**Lines:** 34-254

**Intended Behavior:** Atomically assign all circuit exercises to a session.

**Transaction Flow:**

1. **Validate Session Exists** (lines 72-78) - With row lock (`with_for_update()`)
2. **Validate Circuit Exists** (lines 80-86)
3. **Load Circuit Exercises** (lines 88-97) - From `CircuitMelted` table
4. **Load Circuit Macro** (lines 99-103) - From `CircuitMacro` table
5. **Check Mutual Exclusivity** (lines 105-120):
   - If session has `ACCESSORY` role exercises → raise error unless `replace_existing=True`
   - Enforces: Sessions can have circuits OR accessories, never both
6. **Remove Conflicting Accessories** (lines 122-140) - If `replace_existing=True`
7. **Calculate Order** (lines 142-148) - Existing exercise count determines start order
8. **Create SessionExercise Records** (lines 150-168):
   - One record per melted exercise
   - `exercise_role` = `FINISHER` (line 158)
   - `substitution_allowed` = False (line 165)
9. **Update Session** (lines 170-198):
   - Set `session.finisher_circuit_id`
   - Set `session.has_circuits = True`
   - Update `finisher_duration_minutes`
   - Recalculate `estimated_duration_minutes` via `TimeEstimationService`
10. **Commit Transaction** (lines 210-211)

### get_available_circuits_for_session()

**Lines:** 256-402

**Intended Behavior:** Recommend circuits compatible with a session.

**Filtering Logic:**
- Exclude circuits with movements already in session
- Filter by circuit_type, difficulty_tier, primary_region
- Filter by max_duration_minutes

**Scoring:** Uses `CircuitComparisonService.calculate_circuit_similarity_score()` (line 348)

### Mutual Exclusivity Constraint

**Intended Behavior:** A session cannot have both circuits and accessory exercises.

**Implementation:** Lines 105-120 check for existing `ACCESSORY` role exercises before circuit assignment.

**Deviation:** The constraint is only checked at circuit assignment time. If a session is generated with accessories via `SessionGeneratorService`, and then a circuit is assigned, the accessories are only removed if `replace_existing=True`. Otherwise, an error is raised.

## Interference Service

**File:** `app/services/interference.py`

### Core Responsibility

Validates goal conflicts and provides adjustment recommendations based on interference rules.

### validate_goals()

**Lines:** 35-81

**Intended Behavior:** Check if selected goals have disqualifying conflicts.

**Input:** 3 goals (may include duplicates for padding)

**Process:**
1. **Extract Unique Goals** (lines 58-59) - Remove duplicates while preserving order
2. **Single Goal Fast Path** (lines 61-63) - No conflicts possible
3. **Pairwise Conflict Check** (lines 66-79):
   - For each unique goal pair, check `INTERFERENCE_RULES` config
   - If severity > 0.8 → **Hard conflict** → return `False`
   - If severity > 0.0 → **Soft conflict** → add warning
4. **Return** `(is_valid, warnings)`

**Interference Rules Config:** From `app/config/heuristics.py` → `INTERFERENCE_RULES`

### get_conflicts()

**Lines:** 83-120

**Intended Behavior:** Return detailed conflict information for all goal pairs.

**Returns:** `List[GoalConflict]` with:
- `goal_1`, `goal_2` - Conflicting goals
- `conflict_type` - e.g., "volume_conflict", "frequency_conflict"
- `severity` - 0-1 scale
- `adjustment` - Dict of adjustments to apply
- `recommendation` - Human-readable explanation

### apply_dose_adjustments()

**Lines:** 122-149

**Intended Behavior:** Adjust base session frequencies based on goal conflicts.

**Process:**
1. Get conflicts for all goal pairs
2. For each conflict with adjustments:
   - Apply frequency reduction factor to affected patterns
3. Return adjusted frequency dict

**Note:** This method exists but appears **unused** in the current implementation.

## Deload Service

**File:** `app/services/deload.py`

### Core Responsibility

Manage deload scheduling based on time and recovery signals.

### should_trigger_deload()

**Lines:** 34-74

**Intended Behavior:** Determine if deload should be triggered for current program.

**Checks:**
1. **Recovery Signals** (lines 58-62):
   - Average sleep < 6 hours → trigger
   - Average readiness < 40 → trigger
2. **Time Since Last Deload** (lines 65-69):
   - If > 4 weeks (28 days) → trigger

**Returns:** `(should_deload: bool, reason: str)`

### _get_recovery_status()

**Lines:** 77-112

**Intended Behavior:** Aggregate recovery signal averages from last 7 days.

**Returns:**
```python
{
    "sleep_avg": float,      # Average sleep_hours
    "readiness_avg": float,  # Average readiness score
    "hrv_avg": float,       # Average HRV
}
```

### _days_since_last_deload()

**Lines:** 114-151

**Intended Behavior:** Calculate days since last deload microcycle.

**Logic:**
- Query `Microcycle` table for `is_deload=True`
- If found → return days since `start_date`
- If not found → return days since `program.start_date`

### Usage Status

**Intended:** Deload microcycles should be scheduled based on recovery signals.

**Actual Implementation:** Deloads are scheduled **deterministically** during program creation (`ProgramService.create_program()` line 270):
```python
is_deload = ((mc_idx + 1) % deload_frequency == 0)
```

The `DeloadService` exists but is **not called** during program generation or session generation.

## Data Flow Diagrams

### Program Creation Flow

```
User completes wizard
        │
        ▼
POST /programs
        │
        ▼
┌─────────────────────────────────────┐
│  Validate goals via              │
│  InterferenceService              │
└────────────┬────────────────────┘
             │
             ▼ (if valid)
┌─────────────────────────────────────┐
│  ProgramService.create_program()   │
│  - Create Program model           │
│  - Partition microcycle lengths    │
│  - For each microcycle:          │
│    - Build split config          │
│    - Apply goal distribution     │
│    - Assign day types/focus    │
│    - Create Microcycle model     │
│    - Create Session shells        │
└────────────┬────────────────────┘
             │
             ▼
      Commit transaction
        │
        ▼
┌─────────────────────────────────────┐
│  Persist UserMovementRule         │
│  Persist UserEnjoyableActivity    │
└────────────┬────────────────────┘
             │
             ▼
      Queue background task:
      generate_active_microcycle_sessions()
```

### Session Generation Flow

```
generate_active_microcycle_sessions()
        │
        ▼
┌─────────────────────────────────────┐
│  Fetch active microcycle         │
│  Fetch all sessions             │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  For each session:              │
│  - Apply pattern interference     │
│  - populate_session_by_id()     │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  populate_session_by_id():       │
│  1. Load context:             │
│     - Session, program,        │
│       microcycle               │
│     - movements_by_pattern       │
│     - movement_rules            │
│     - user_profile             │
│  2. Generate offline:          │
│     - generate_session_exercises_offline()   │
│     - Detect template          │
│     - Generate blocks          │
│     - Solve constraints        │
│     - Fill to target duration │
│  3. Save results:              │
│     - SessionExercise records   │
│     - Calculate volume        │
│  4. Update tracking state:      │
│     - used_movements         │
│     - used_main_patterns      │
│     - used_accessory_movements│
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  After all sessions:            │
│  - Generate batched Jerome notes │
│    via _generate_microcycle_    │
│    jerome_notes()              │
└─────────────────────────────────────┘
```

### Constraint Solving Flow

```
generate_session_exercises_offline()
        │
        ▼
┌─────────────────────────────────────┐
│  Load movements by pattern       │
│  Apply movement rules:            │
│  - Filter out HARD_NO           │
│  - Include HARD_YES             │
│  - Boost PREFERRED scores        │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Build OptimizationRequest:       │
│  - available_movements           │
│  - excluded_movement_ids        │
│  - required_movement_ids         │
│  - preferred_movement_ids        │
│  - target_muscle_volumes       │
│  - max_fatigue                │
│  - session_duration_minutes      │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  ConstraintSolver.              │
│  solve_with_progressive_         │
│  relaxation():                  │
│  For pass 1-5:                │
│  - Try with config            │
│  - If feasible → return       │
│  - If infeasible → next pass │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  OptimizationResult:             │
│  - selected_movements           │
│  - selected_circuits           │
│  - pass_number (which succeeded)│
│  - estimated_duration          │
└─────────────────────────────────────┘
```

## Deviations from Intended Behavior

### 1. DeloadService Not Used During Generation

**Intended:** Deload microcycles should be scheduled based on recovery signals (sleep, HRV, readiness) via `DeloadService.should_trigger_deload()`.

**Actual:** Deloads are scheduled deterministically by sequence number:
```python
# ProgramService.create_program() line 270
is_deload = ((mc_idx + 1) % deload_frequency == 0)
```

**Impact:** Recovery-based deload scheduling is not implemented despite service availability.

### 2. Pattern Interference Applied Before LLM Generation

**Intended:** LLM should receive original intent tags and generate content, then interference rules should be applied to the generated content.

**Actual:** Pattern interference is applied to `session.intent_tags` **before** content generation (line 465-467 in `program.py`). The LLM receives already-modified patterns.

**Impact:** LLM may generate content that doesn't align with original user intent, as patterns have been pre-modified.

### 3. Interference Service Dose Adjustments Not Used

**Intended:** `InterferenceService.apply_dose_adjustments()` should modify base session frequencies based on goal conflicts.

**Actual:** The method exists but is not called during program or session generation.

**Impact:** Conflicting goals do not receive automatic frequency adjustments.

### 4. Movement Rules Persisted Separately from Program

**Intended:** Movement rules sent in `ProgramCreate.movement_rules` should be associated with the program or microcycle.

**Actual:** Movement rules are persisted to `UserMovementRule` table **after** program creation (lines 131-159 in `programs.py`). They are not directly linked to the program - they are global user preferences.

**Impact:** Movement rules apply across all programs for a user, not per-program preferences.

### 5. Circuit Mutual Exclusivity Check Timing

**Intended:** Sessions should prevent having both circuits and accessories at any time.

**Actual:** Mutual exclusivity is only checked during circuit assignment (`CircuitAssignmentService.assign_circuit_to_session()` line 105-120). If a session is generated with accessories via `SessionGeneratorService`, it can coexist until a circuit is assigned.

**Impact:** Potential state inconsistency if circuits are assigned to sessions with existing accessories without `replace_existing=True`.

### 6. UserMovementRule Cadence Field Not Used

**Intended:** Rules should respect cadence (PER_MICROCYCLE, WEEKLY, BIWEEKLY) to control how often movements appear.

**Actual:** The `cadence` field in `UserMovementRule` is stored but never used in the optimization solver. All rules apply globally without cadence-based filtering.

**Impact:** Movement frequency cannot be controlled at the desired granularity.

### 7. Background Task Race Conditions

**Intended:** Background task should reliably generate session content after program commit.

**Actual:** FastAPI `BackgroundTasks.add_task()` is used without proper transaction isolation ([`programs.py:213-216`](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py#L213-L216)). The background task may not see committed data, and there's no error handling or retry mechanism.

**Impact:** Session generation can fail silently, leaving programs with empty sessions.

### 8. CircuitAssignmentService Not Integrated

**Intended:** Circuit assignment should use atomic transaction guarantees via `CircuitAssignmentService`.

**Actual:** Circuits are assigned directly in `SessionGeneratorService._build_goal_finisher_with_db()` without using `CircuitAssignmentService`. The service exists but is never called during program or session generation.

**Impact:** No atomic transaction guarantees for circuit assignment during program generation.

### 9. Unused Disciplines Field

**Intended:** Discipline priorities should be set in the wizard and sent to backend.

**Actual:** Frontend store implements `disciplines` management ([`program-wizard-store.ts:69-71`](file:///Users/shourjosmac/Documents/alloy/frontend/src/stores/program-wizard-store.ts#L69-L71)), but it's never:
- Exposed in any wizard step component
- Sent to backend in API payload
- Used in validation

**Impact:** Dead code that should be removed or implemented.

### 10. Custom Movement Handling Bug

**Intended:** Users should be able to add custom movement preferences.

**Actual:** Custom movements use `movement_id: 0` ([`ActivitiesAndMovementsStep.tsx:154-162`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/wizard/ActivitiesAndMovementsStep.tsx#L154-L162)), which won't match any actual movement in the database. The custom name is not stored anywhere.

**Impact:** Custom movement preferences don't work.

## Areas for Improvement

### 1. Consolidate Goal Validation

**Current:** Goal validation happens in both API layer (`programs.py` lines 92-108) and `ProgramService` (`program.py` lines 93-106).

**Recommendation:** Move all goal validation to `ProgramService.create_program()` to avoid duplication and ensure single source of truth.

### 2. Extract Microcycle Generation Logic

**Current:** Microcycle generation loop (lines 268-313) is embedded in `create_program()`.

**Recommendation:** Extract to separate method `_generate_microcycle_structure()` for:
- Better testability
- Reusability for next microcycle generation
- Clearer separation of concerns

### 3. Standardize Constraint Relaxation Configuration

**Current:** Pass configs reference `activity_distribution_config.or_tools_volume_target_reduction_pct` which may not be clearly defined.

**Recommendation:** Define all relaxation parameters in a single configuration file with clear documentation of each pass's purpose.

### 4. Integrate DeloadService into Program Generation

**Current:** Deloads scheduled deterministically; `DeloadService` unused.

**Recommendation:**
- Call `DeloadService.should_trigger_deload()` for each microcycle during generation
- Combine time-based and recovery-based deload triggers
- Allow override for recovery-based deloads

### 5. Separate Pattern Interference from Session Generation

**Current:** Pattern interference modifies `session.intent_tags` before LLM generation.

**Recommendation:**
- Pass original intent tags to LLM
- Apply interference rules to **generated content** (exercise selection)
- This allows LLM to maintain original intent while ensuring constraints

### 6. Add Circuit Validation to Session Generation

**Current:** Sessions can have both accessories and circuits until circuit assignment.

**Recommendation:** Add validation in `SessionGeneratorService` to ensure sessions don't generate both accessories and finisher circuits simultaneously.

### 7. Consolidate Movement Rule Application

**Current:** Movement rules are applied in multiple places:
- `_load_user_movement_rules_dict()` loads them
- `_generate_blocks_by_template()` applies them
- `ConstraintSolver` receives them via `OptimizationRequest`

**Recommendation:** Create a single `MovementRuleFilter` service that:
- Loads rules once per session
- Provides filtered movement sets
- Centralizes rule application logic

### 8. Improve Cross-Session State Management

**Current:** Cross-session state (used_movements, used_main_patterns, etc.) is passed as arguments through the generation loop.

**Recommendation:** Create a `MicrocycleContext` class that:
- Encapsulates all cross-session state
- Provides methods for updates and queries
- Improves type safety and reduces argument passing

### 9. Extract Jerome Notes Generation

**Current:** Batched Jerome notes generation (`_generate_microcycle_jerome_notes()`) is embedded in `ProgramService`.

**Recommendation:** Extract to `CoachNotesService` for:
- Better separation of concerns
- Reusability for individual session note updates
- Clearer testing boundaries

### 10. Add Circuit Selection to Constraint Solver

**Current:** Circuits are assigned post-generation via `CircuitAssignmentService`, not integrated with exercise selection.

**Recommendation:** Extend `ConstraintSolver` to:
- Include circuits in optimization alongside movements
- Select optimal combination of movements AND circuits
- Unify finisher selection logic

### 11. Implement Message Queue for Background Tasks

**Current:** FastAPI `BackgroundTasks` used with race conditions and no error handling.

**Recommendation:** Replace with task queue (Celery/Redis) or implement:
- Explicit transaction isolation
- Error handling with retry mechanism
- Task status tracking
- Dead letter queue for failed tasks

### 12. Implement Saga Pattern for Long-Running Transactions

**Current:** No distributed transaction pattern. If LLM fails after optimization succeeds, system is in inconsistent state.

**Recommendation:** Implement Saga pattern:
1. `OptimizeSession` → record "optimized"
2. `GenerateContent` → record "generated"
3. `ValidateSession` → record "validated"
4. Compensation actions on failure (rollback to previous state)

### 13. Extract ProgramOrchestrator Service

**Current:** `ProgramService` contains mixed responsibilities:
- Program creation
- Microcycle orchestration
- Session generation orchestration
- Background task management

**Recommendation:** Extract to `ProgramOrchestrator` that:
- Coordinates between services
- Delegates specific operations
- Improves testability and separation of concerns

### 14. Implement Repository Pattern Explicitly

**Current:** Services directly access ORM models without abstraction.

**Recommendation:** Create explicit repository interfaces:
```python
class ProgramRepository(ABC):
    @abstractmethod
    async def create(self, program: Program) -> Program: pass
    
    @abstractmethod
    async def get_active_microcycle(self, program_id: int) -> Microcycle: pass
```

### 15. Consolidate Configuration

**Current:** Configuration scattered across:
- `activity_distribution.py`
- `heuristics.py`
- `settings.py`

**Recommendation:** Single configuration hierarchy:
```python
@dataclass
class TrainingConfig:
    distribution: DistributionConfig
    heuristics: HeuristicConfig
    optimization: OptimizationConfig
    time_estimation: TimeEstimationConfig
```

### 16. Reduce LLM Token Usage

**Current:** Verbose prompts with full movement lists ([`prompts.py:29-73`](file:///Users/shourjosmac/Documents/alloy/app/llm/prompts.py#L29-L73)).

**Recommendation:** Use structured prompting with token optimization:
- Pre-filter movements before prompting
- Use top-k ranked movements
- Implement response caching for similar contexts

### 17. Optimize Database Queries with Bulk Operations

**Current:** Individual session updates in loop ([`program.py:500-600`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L500-L600)).

**Recommendation:** Use bulk operations:
```python
# Instead of individual updates
await db.execute(
    update(Session)
    .where(Session.id.in_(session_ids))
    .values(warmup_json=content)
)
```

### 18. Add Circuit Validation to Session Generation

**Current:** Sessions can generate both accessories and circuits simultaneously.

**Recommendation:** Add validation in `SessionGeneratorService._validate_mutual_exclusivity()` (existing method at [`session_generator.py:1216-1233`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L1216-L1233)) to prevent this during generation, not just during circuit assignment.

### 19. Fix Frontend State Reset Timing

**Current:** Wizard resets state on every mount ([`program.wizard.tsx:74-86`](file:///Users/shourjosmac/Documents/alloy/frontend/src/routes/program.wizard.tsx#L74-L86)), causing progress loss on navigation.

**Recommendation:** Implement proper persistence layer:
- Save wizard state to localStorage
- Restore state on mount
- Only reset on explicit user action

### 20. Fetch Activity Categories from Backend

**Current:** Activities hard-coded in frontend ([`ActivitiesAndMovementsStep.tsx:9-44`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/wizard/ActivitiesAndMovementsStep.tsx#L9-L44)).

**Recommendation:** Fetch from backend to:
- Enable dynamic activity management
- Ensure backend validation
- Maintain consistency with movements handling

## File Reference Summary

### Core Services

| File | Primary Responsibility | Key Classes/Methods |
|-------|---------------------|----------------------|
| `app/api/routes/programs.py` | API endpoints for program CRUD | `create_program()`, `get_program()`, `generate_next_microcycle()` |
| `app/services/program.py` | Program and microcycle structure generation | `ProgramService.create_program()`, `_create_microcycle()`, `_build_freeform_split_config()` |
| `app/services/session_generator.py` | Exercise content generation via LLM | `SessionGeneratorService.populate_session_by_id()`, `generate_session_exercises_offline()` |
| `app/services/optimization.py` | Constraint satisfaction solver | `ConstraintSolver.solve_session_with_progressive_relaxation()` |
| `app/services/circuit_assignment.py` | Circuit assignment to sessions | `CircuitAssignmentService.assign_circuit_to_session()` |
| `app/services/deload.py` | Deload scheduling | `DeloadService.should_trigger_deload()` |
| `app/services/interference.py` | Goal conflict validation | `InterferenceService.validate_goals()`, `get_conflicts()` |

### Supporting Services

| File | Purpose |
|-------|-----------|
| `app/services/time_estimation.py` | Duration calculation for sessions and exercises |
| `app/services/circuit_comparison.py` | Circuit similarity scoring |
| `app/services/circuit_metrics_normalization.py` | Circuit metric normalization |

### Models

| File | Key Models |
|-------|-------------|
| `app/models/program.py` | `Program`, `Microcycle`, `Session`, `SessionExercise`, `ProgramDiscipline` |
| `app/models/user.py` | `User`, `UserProfile`, `UserMovementRule`, `UserEnjoyableActivity` |
| `app/models/movement.py` | `Movement` |
| `app/models/circuit.py` | `CircuitTemplate` |
| `app/models/circuit_extended.py` | `CircuitMelted`, `CircuitMacro` |

### Frontend

| File | Purpose |
|-------|-----------|
| `frontend/src/stores/program-wizard-store.ts` | Wizard state management |
| `frontend/src/components/wizard/` | Wizard step components |

### Configuration

| File | Purpose |
|-------|-----------|
| `app/config/heuristics.py` | Heuristic configs (INTERFERENCE_RULES, DELOAD_POLICY, TIME_ESTIMATION) |
| `app/config/activity_distribution.py` | Goal-to-bucket weight mappings |

## Architectural Patterns

### Implemented Patterns

| Pattern | Location | Quality | Notes |
|----------|-----------|----------|--------|
| **Service Layer** | `app/services/` | ✅ Good | Clear separation between API and business logic |
| **Repository Pattern** | Partial | ⚠️ Needs improvement | Direct ORM access, no explicit repository interfaces |
| **Dependency Injection** | FastAPI dependencies | ✅ Good | Proper use of FastAPI dependency injection |
| **Singleton** | Service instances | ✅ Appropriate | Stateless services instantiated once |
| **Strategy Pattern** | Optimization passes ([`optimization.py:85-154`](file:///Users/shourjosmac/Documents/alloy/app/services/optimization.py#L85-L154)) | ✅ Excellent | Progressive constraint relaxation is well-designed |
| **Background Tasks** | FastAPI BackgroundTasks | ⚠️ Limited reliability | No error handling, race conditions possible |
| **Factory Pattern** | Session content generation | ⚠️ Implicit | Could be more explicit |

### Recommended Additions

**1. Command Pattern (For Long Operations)**

```python
@dataclass
class CreateProgramCommand:
    user_id: int
    goals: list[Goal]
    duration_weeks: int
    # ... other fields

class CommandHandler:
    async def handle(self, command: CreateProgramCommand):
        # Handle with transaction and compensation
        pass
```

**2. Event-Driven Architecture**

```python
# Instead of direct service calls
class ProgramCreatedEvent:
    program_id: int
    user_id: int

# Subscribers react to events
@subscribe(ProgramCreatedEvent)
async def generate_sessions(event: ProgramCreatedEvent):
    # Async processing
    pass
```

**3. CQRS (Command Query Responsibility Segregation)**

Separate read/write models:
- **Write model:** ProgramWriteModel - creates programs, microcycles, sessions
- **Read model:** ProgramReadModel - optimized queries for frontend

**4. Pipeline Pattern for Session Generation**

Extract session generation into discrete stages:
```python
class SessionGenerationPipeline:
    stages = [
        SelectionStage(),      # OR-Tools optimization
        ContentStage(),        # LLM content generation
        ValidationStage(),     # Constraint verification
        PersistenceStage()     # Save to database
    ]
```

### Architectural Concerns

**Coupling Issues:**
- High service-to-service coupling (ProgramService directly depends on 5+ services)
- LLM-specific logic mixed with business logic in SessionGenerator
- Database schema exposed to services (no DTOs)

**Transaction Boundaries:**
- Split transaction pattern with background task race conditions
- No distributed transaction pattern for multi-service operations
- Circuit assignment lacks proper isolation in session generation

**Cohesion Issues:**
- ProgramService has mixed responsibilities (creation, orchestration, task management)
- Movement rule application scattered across multiple services
- Configuration fragmented across multiple files

---

**Document Version:** 1.1  
**Last Updated:** 2026-02-05  
**Purpose:** Expert architectural review of program creation business logic
