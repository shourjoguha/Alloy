# Phase 1 Implementation Plan: Heuristics to Code Configuration

## Summary
Move all heuristic configurations from database to Python module (4-6 hours effort), then delete all failed Supabase migration artifacts.

---

## Part A: Move Heuristics to Code Configuration

### Step 1: Create Heuristics Config Module
**File**: `app/config/heuristics.py` (NEW)

Create TypedDict-based configuration module with all 10 heuristics from `seed_data/heuristic_configs.json`:
- `GOAL_DOSE_HEURISTICS` - Training parameters by goal
- `INTERFERENCE_RULES` - Activity & training interference rules
- `TIME_ESTIMATION` - Session time estimation defaults
- `CNS_LOAD_BUDGET` - CNS load budgeting parameters
- `DELOAD_POLICY` - Deload timing and intensity rules
- `PSI_CALCULATION` - PSI calculation parameters
- `SPLIT_TEMPLATES` - Predefined split structures
- `PROGRESSION_RULES` - Progression style rules
- `PERSONA_DEFINITIONS` - Coach persona tones & aggression levels
- `DOMS_ATTRIBUTION` - DOMS attribution rules

**Type Safety**: Use TypedDict for compile-time validation
**Pattern**: Follow existing `app/config/activity_distribution.py`

### Step 2: Update InterferenceService
**File**: `app/services/interference.py`

Changes:
- Import from `app.config.heuristics` instead of loading from DB
- Remove `_load_interference_rules()` method (no longer needed)
- Remove `self._interference_rules` cache (no longer needed)
- Remove `clear_cache()` method (no longer needed)
- Direct return of `INTERFERENCE_RULES` constant

### Step 3: Update DeloadService
**File**: `app/services/deload.py`

Changes:
- Import `DELOAD_POLICY` from `app.config.heuristics`
- Replace hardcoded values (line 72: `time_since_deload > 28`) with config-driven value
- Use `DELOAD_POLICY["default_deload_every_microcycles"]` and `DELOAD_POLICY["deload_intensity_reduction"]`

### Step 4: Update ProgramService
**File**: `app/services/program.py`

Changes:
- Import `SPLIT_TEMPLATES` from `app.config.heuristics`
- Update `_load_split_template()` to return from code config instead of DB query
- Remove HeuristicConfig import (line 20)
- Update `_get_default_split_template()` to use `SPLIT_TEMPLATES` constant

### Step 5: Update API Endpoints
**File**: `app/api/routes/settings.py`

Changes:
- Import all heuristics from `app.config.heuristics`
- Update `list_heuristic_configs()` to return in-memory data
- Update `get_heuristic_config()` to return from in-memory dict
- Keep same response format (HeuristicConfigResponse) - backward compatible

### Step 6: Update Tests
**Files**: `tests/test_interference_service.py`, `tests/test_deload_service.py`, etc.

Changes:
- Remove DB fixture setup for heuristics
- Add mock config tests
- Verify services work with in-memory configs

### Step 7: Remove DB Dependency (Optional)
**File**: `app/db/seed.py`

Changes:
- Keep `seed_heuristic_configs()` function for backward compatibility
- Mark as deprecated with comment
- Can be removed entirely in future cleanup

### Step 8: Update Model Exports (Optional)
**File**: `app/models/__init__.py`

Changes:
- Keep HeuristicConfig import for backward compatibility
- Add deprecation comment: "Deprecated: Use app.config.heuristics instead"

---

## Part B: Delete Failed Supabase Migration Artifacts

### Root Directory Files to Delete (10 Python scripts):

**Import Scripts:**
1. `orchestrated_import.py` - Failed orchestration import
2. `clear_and_import_simple.py` - Failed simple import
3. `reset_and_import_simple.py` - Failed reset import

**Conversion Scripts:**
4. `convert_sql_to_csv.py` - SQL to CSV conversion
5. `convert_sql_to_csv_fixed.py` - Fixed conversion script
6. `convert_sql_to_csv_v2.py` - V2 conversion script

**Constraint Management:**
7. `constraint_manager.py` - Constraint management for failed import
8. `test_constraint_manager.py` - Test script
9. `example_constraint_workflow.py` - Example workflow
10. `demo_constraint_strategy.py` - Demo strategy

### Root Directory Files to Delete (7 Markdown files):

1. `IMPORT_FAILURE_ANALYSIS.md` - Import failure analysis
2. `CONSTRAINT_RELAXATION_STRATEGY.md` - Constraint relaxation strategy
3. `CONSTRAINT_RELAXATION_README.md` - Constraint relaxation README
4. `CONSTRAINT_IMPLEMENTATION_SUMMARY.md` - Implementation summary
5. `DUMP_ANALYSIS_REPORT.md` - Dump analysis report
6. `DUPLICATE_KEY_ANALYSIS_REPORT.md` - Duplicate key analysis
7. `cleaned_dump.sql` - Cleaned SQL dump

### Root Directory Files to Delete (2 SQL files):

1. `cleaned_dump.sql` - Cleaned dump (already listed above, included for completeness)

### .trae/documents Directory Files to Delete (2 markdown files):

1. `Direct Supabase Migration Using pg_dump with session_replication_role.md`
2. `Optimized Supabase Import with Constraint Management and Orchestration.md`

### Keep These Files (Documentation):

**Keep in Root Directory:**
- `AI_CONTEXT_ARCHITECTURE_GUIDE.md` - System architecture (relevant)
- `API_REFERENCE.md` - API documentation (relevant)
- `DATABASE_OVERVIEW.md` - Database schema (relevant)
- `README.md` - Project README (relevant)
- `SESSION_LOG.md` - Development log (relevant)

**Keep Entire Directory:**
- `Manual-CSV Upload/` - Contains working CSV export (may need later)

**Keep in Backups:**
- `backups/refactor_phase_2_20260123_181125/` - Refactor backup (relevant)

---

## Success Criteria

### Heuristics Migration:
✅ Zero DB queries for heuristic config access
✅ All services import from `app.config.heuristics`
✅ API endpoints return same data format
✅ All tests passing with in-memory configs
✅ Performance improvement verified (<0.01ms access vs 2-6ms)

### Cleanup:
✅ All 21 failed migration files deleted
✅ No broken imports or references
✅ Clean root directory structure
✅ Git status shows only new heuristics module

---

## Estimated Effort

**Heuristics Migration:**
- Create config module: 2 hours
- Update services (3 files): 2 hours
- Update API: 0.5 hours
- Update tests: 1-2 hours
- Total: 4-6 hours

**Cleanup:**
- Delete files: 0.25 hours (15 minutes)
- Verify no broken references: 0.25 hours
- Total: 0.5 hours

**Total Effort: 4.5-6.5 hours**

---

## Risk Assessment

**Risk Level: LOW** ✅

**Mitigation:**
- Incremental changes (one service at a time)
- Tests can run after each change
- Easy rollback (git revert)
- No frontend changes required
- Backward compatible API responses

**No User Impact:**
- No API contract changes
- Same data returned
- No deployment downtime needed