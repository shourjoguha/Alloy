# Implementation Plan: Fix 75-minute Sessions Generating at 42-51 Minutes

## Root Causes Identified

### 1. Hardcoded Exercise Count Limits (CRITICAL)
- Cardio: 1-3 exercises max (line 2891)
- Conditioning: 4-6 exercises max (line 2911)
- Mobility: 8-12 exercises max (line 2933)
- Cooldown: 2-3 stretches max (line 2956)
- Warmup: 3 exercises max (line 2770)
- Main (fallback): 3 exercises max (line 2840)

**Impact**: These hardcoded caps prevent system from adding more exercises to reach 75-minute target.

### 2. Fixed Per-Exercise Durations
- Mobility: 60 seconds per exercise (fixed)
- Cooldown: 60 seconds per stretch (fixed)
- **Impact**: Creates rigid time ranges that can't adapt to 75-minute targets

### 3. ConstraintSolver Time Calculation Overestimation
- Calculates ~14 minutes per movement using formula
- TimeEstimationService calculates ~8-10 minutes for same content
- **Impact**: Solver selects FEWER movements than actually possible

### 4. 10-Minute Warmup/Cooldown Deduction
- `_get_fast_special_session_content`: `max(600, (total_minutes - 10) * 60)`
- `_get_fast_conditioning_session_content`: `max(30, total_minutes - 10)`
- **Impact**: Reduces available time by 10 minutes before main block generation

### 5. Integer Division Truncation
- Cardio: `duration_seconds = (max_session_duration * 60) // num_exercises`
- **Impact**: Loses remainder seconds, further reducing time

### 6. 5% Tolerance Allows Too Low
- 75-minute target accepts 71.25-78.75 minute range
- **Impact**: Even 42-minute sessions would be rejected, but system never reaches 71+ minutes

## Implementation Tasks

### Task 6.1: Remove Hardcoded Exercise Count Limits (HIGH PRIORITY)
**Files**: session_generator.py

**Changes**:
1. `_generate_cardio_main_block` (line 2891): Remove `min(3, max(1, ...))` limit
2. `_generate_conditioning_main_block` (line 2911): Remove `min(6, max(4, ...))` limit
3. `_generate_mobility_main_block` (line 2933): Remove `min(12, max(8, ...))` limit
4. `_generate_cooldown_block` (line 2956): Remove `min(3, ...)` limit
5. `_generate_warmup_block` (line 2770): Remove `len(warmup_exercises) < 3` limit

**New Logic**: Calculate exercise count based on `max_session_duration` and per-exercise time.

### Task 6.2: Fix Fixed Per-Exercise Durations (HIGH PRIORITY)
**Files**: session_generator.py

**Changes**:
1. `_generate_mobility_main_block` (line 2931): Calculate mobility exercise duration based on `max_session_duration / target_count` instead of fixed 60s
2. `_generate_cooldown_block` (line 2965): Calculate stretch duration based on `max_session_duration / target_count` instead of fixed 60s

**New Logic**: Distribute available time proportionally across exercises.

### Task 6.3: Fix ConstraintSolver Time Calculation (HIGH PRIORITY)
**Files**: optimization.py

**Changes**:
1. Remove inline time calculation (lines 325-329)
2. Use `TimeEstimationService.estimate_exercise_time()` for accurate per-movement duration
3. Adjust constraint to use accurate duration instead of overestimated value

**Expected Impact**: Solver can now select more movements within time budget.

### Task 6.4: Remove 10-Minute Warmup/Cooldown Deduction (HIGH PRIORITY)
**Files**: session_generator.py

**Changes**:
1. `_get_fast_special_session_content` (line 1702): Remove `- 10` from `max(600, (total_minutes - 10) * 60)`
2. `_get_fast_conditioning_session_content` (line 1730): Remove `- 10` from `max(30, total_minutes - 10)`

**New Logic**: Use full `max_session_duration` for time budgeting.

### Task 6.5: Fix Integer Division Truncation (MEDIUM PRIORITY)
**Files**: session_generator.py

**Changes**:
1. `_generate_cardio_main_block` (line 2899): Use float division then round instead of `//`
2. Preserve remainder seconds in duration calculation

**New Logic**: `duration_seconds = int((max_session_duration * 60) / num_exercises)`

### Task 6.6: Reduce 5% Tolerance or Make Configurable (MEDIUM PRIORITY)
**Files**: session_generator.py, heuristics.py

**Option A**: Reduce tolerance from 5% to 3% for stricter validation
**Option B**: Make tolerance proportional to duration (e.g., shorter sessions = tighter tolerance)
**Option C**: Allow tolerance to be configurable per program

### Task 6.7: Refactor session_generator.py to Reduce Bloat (LOW PRIORITY)
**Files**: session_generator.py

**Major Refactoring**:
1. Consolidate 6 different warmup/cooldown generation methods into 1
2. Unify goal weights extraction (2 functions → 1)
3. Remove duplicate session generation paths (keep only block-based)
4. Extract duplicate removal logic into separate service
5. Move hardcoded data to configuration files

**Expected Reduction**: 3,606 lines → ~2,000-2,200 lines (30-40% reduction)

## Expected Outcome

After implementing these changes:
- 75-minute target sessions will generate in 71-79 minute range
- Exercise counts will scale with session duration (more time = more exercises)
- No hardcoded limits will prevent reaching target duration
- ConstraintSolver will use accurate time estimation
- All block types will respect `max_session_duration`

## Files to Modify

1. `app/services/session_generator.py` - Block generation, time calculations
2. `app/services/optimization.py` - Constraint solver time estimation
3. `app/config/heuristics.py` - Tolerance configuration
4. `app/services/time_estimation.py` - Ensure consistent calculations