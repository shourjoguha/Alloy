## Fix Session Building: Progressive Constraint Relaxation & Block Templates

### Confirmed Understanding

**Phase 1 (Constraint Relaxation):**
- Pass 1: Original strict constraints
- Pass 2: Relax fatigue by 50%
- Pass 3: Relax volume by 30%
- Pass 4+: Further relaxation if needed
- Save pass success data for manual review (no auto-tuning)

**Phase 5 (Block Templates):**
- Warmup: mobility OR plyometric + short cardio
- Template 1 (Normal lifting): warmup → main lifts → circuits (replaces accessories) → cooldown
- Template 2 (Cardio day): warmup → 1-3 cardio movements → (empty) → cooldown
- Template 3 (Conditioning day): warmup → 4-6 conditioning movements → (empty) → cooldown
- Template 4 (Mobility day): warmup → 8-12 mobility movements → (empty) → cooldown

**Phase 6 (Time Utilization):**
- If underfilled: add accessories or main lifts
- If overfilled: reduce cooldown (min 5 min) → reduce accessory sets (to 2) → reduce main sets (to 3)
- Add 2 min transition time between blocks
- Warmup base time includes cardio time
- Cooldown is flexible (can be reduced)
- **5% buffer applies to ANY duration selected in program creation flow** (e.g., 30 min → 28.5-31.5 min, 45 min → 42.75-47.25 min, 60 min → 57-63 min)

**Frontend UI:** Session cards should not show empty sections

---

## Task Breakdown with Agent Assignments

### TASK 1: Implement Progressive Constraint Relaxation
**Agents:** `backend-developer` + `typescript-pro` (for type definitions if needed)

**Subtasks:**
1.1 Modify `optimization.py` to support multi-pass solving
1.2 Add pass-specific constraint values (fatigue_relax_pct, volume_relax_pct)
1.3 Add logging to track which pass succeeded
1.4 Save pass success data to database or log file for review

**Files:** `app/services/optimization.py`

---

### TASK 2: Define Section Pattern Filters
**Agents:** `python-pro` + `api-designer` (for config structure)

**Subtasks:**
2.1 Create `SECTION_PATTERN_FILTERS` config in `heuristics.py`
2.2 Add plyometric to warmup include patterns
2.3 Define exclude patterns for main lifts (mobility, stretch, cardio, conditioning, isolation)
2.4 Define include patterns for accessories (isolation)
2.5 Define include patterns for cooldown (stretch, mobility)

**Files:** `app/config/heuristics.py`

---

### TASK 3: Implement Block Template Detection
**Agents:** `backend-developer` + `python-pro`

**Subtasks:**
3.1 Create `_detect_session_template()` method in `session_generator.py`
3.2 Detect: Normal lifting, Cardio day, Conditioning day, Mobility only day
3.3 Add helper: `_has_circuit_or_finisher()` to check if template 1 should be used
3.4 Return template type and corresponding block structure

**Files:** `app/services/session_generator.py`

---

### TASK 4: Implement Block-Based Session Generation
**Agents:** `backend-developer` + `python-pro`

**Subtasks:**
4.1 Create `_generate_blocks_by_template()` method
4.2 Implement Template 1: warmup → main lifts → circuits → cooldown
4.3 Implement Template 2: warmup → cardio movements → cooldown
4.4 Implement Template 3: warmup → conditioning movements → cooldown
4.5 Implement Template 4: warmup → mobility movements → cooldown
4.6 Add pattern filtering per block using `SECTION_PATTERN_FILTERS`

**Files:** `app/services/session_generator.py`

---

### TASK 5: Implement Circuit Population
**Agents:** `backend-developer` + `database-optimiser` (for circuit queries)

**Subtasks:**
5.1 Load circuits from `circuits_melted` and `circuits_macro` tables
5.2 Create `_load_all_circuits()` method with proper DTOs
5.3 Add `_populate_circuit_block()` that loads ALL circuit movements in order
5.4 Update `has_circuits` flag and circuit IDs when saving

**Files:** `app/services/session_generator.py`, `app/models/` (if models need updates)

---

### TASK 6: Implement Time Calculation with Transitions
**Agents:** `performance-engineer` + `python-pro`

**Subtasks:**
6.1 Update `TimeEstimationService.estimate_block_time()` to handle different block types
6.2 Add 2 min transition time between blocks in duration calculation
6.3 Ensure warmup base time includes cardio time
6.4 Make cooldown flexible (can be reduced below 5 min if needed)

**Files:** `app/services/time_estimation.py`

---

### TASK 7: Implement Time-Filling Logic (Phase 6.2)
**Agents:** `backend-developer` + `python-pro`

**Subtasks:**
7.1 Create `_fill_to_target_duration()` method
7.2 Implement underfill logic: add accessories → add main lifts
7.3 Implement overfill logic: reduce cooldown (to 5 min) → reduce accessory sets (to 2) → reduce main sets (to 3)
7.4 Calculate 5% buffer: [target * 0.95, target * 1.05] for ANY duration selected
7.5 Ensure final duration is within buffer

**Files:** `app/services/session_generator.py`

---

### TASK 8: Update Content Generation Flow
**Agents:** `backend-developer` + `architect-reviewer`

**Subtasks:**
8.1 Modify `generate_session_exercises_offline()` to use block-based generation
8.2 Call `_detect_session_template()` first
8.3 Call `_generate_blocks_by_template()` with template type
8.4 Apply progressive constraint relaxation for Template 1 (main lifts)
8.5 Call `_fill_to_target_duration()` after block generation
8.6 Ensure all sessions have movements populated

**Files:** `app/services/session_generator.py`

---

### TASK 9: Add Validation and Logging
**Agents:** `code-reviewer` + `technical-writer`

**Subtasks:**
9.1 Validate: at least N exercises in each session
9.2 Validate: duration within 5% buffer of target (for ANY duration selected)
9.3 Log: which optimization pass succeeded
9.4 Log: template type used per session
9.5 Log: time distribution (underfilled/on target/overfilled)
9.6 Log: actual duration vs target duration (e.g., "Target: 45 min, Actual: 43.2 min, Within buffer: Yes")
9.7 Create documentation for pass success data format

**Files:** `app/services/session_generator.py`, new `docs/session_generation_metrics.md`

---

### TASK 10: Frontend UI - Hide Empty Sections in Session Cards
**Agents:** `frontenddeveloper` + `react-pro`

**Subtasks:**
10.1 Find session card components in frontend codebase
10.2 Identify where sections are rendered (warmup, main, accessory, finisher, cooldown, circuits)
10.3 Add conditional rendering to skip empty sections
10.4 Add checks: `exercises && exercises.length > 0` before rendering
10.5 Handle circuits block specifically (check if circuit data exists)
10.6 Test: ensure UI looks correct when sections are empty
10.7 Add placeholder state if ALL sections are empty (shouldn't happen after backend fixes)

**Files:** `frontend/src/components/` (session card components), `frontend/src/types/` (if type updates needed)

---

### TASK 11: Integration Testing
**Agents:** `fullstack-developer` + `error-detective` (for troubleshooting)

**Subtasks:**
11.1 Create test programs with various durations (30, 45, 60, 90 min)
11.2 Test all 4 templates
11.3 Verify: all sessions have movements
11.4 Verify: durations within 5% buffer of target (e.g., 30 min → 28.5-31.5, 45 min → 42.75-47.25, 60 min → 57-63, 90 min → 85.5-94.5)
11.5 Verify: pattern filtering works (wrong patterns excluded)
11.6 Verify: circuits load with all movements in order
11.7 Verify: constraint relaxation logs for review
11.8 Verify: time-filling logic respects hierarchy
11.9 Verify: frontend UI hides empty sections
11.10 Verify: 5% buffer works correctly across all duration options in create program flow

**Files:** `tests/test_session_generation_templates.py`, `frontend/src/` (manual testing)

---

## Service Interdependencies & Design Order

### Critical Path (Order Matters):

```
1. SECTION_PATTERN_FILTERS (Task 2) 
   ↓ Required by: Task 4 (pattern filtering), Task 3 (template detection)
   
2. Circuit Loading (Task 5)
   ↓ Required by: Task 4 (Template 1 circuits)

3. Time Calculation with Transitions (Task 6)
   ↓ Required by: Task 7 (time filling), Task 4 (duration estimation)

4. Progressive Constraint Relaxation (Task 1)
   ↓ Required by: Task 4 (Template 1 main lifts)

5. Block Template Detection (Task 3)
   ↓ Required by: Task 8 (main flow)

6. Block-Based Generation (Task 4)
   ↓ Required by: Task 8 (main flow)

7. Time-Filling Logic (Task 7)
   ↓ Required by: Task 8 (main flow)

8. Content Generation Flow Update (Task 8)
   ↓ Required by: Task 10 (frontend), Task 11 (testing)

9. Frontend UI Fix (Task 10)
   ↓ Can run parallel to Task 9

10. Validation and Logging (Task 9)
   ↓ Required by: Task 11 (testing)

11. Integration Testing (Task 11)
```

### 2nd & 3rd Order Effects:

**Task 2 affects:**
- Task 4: Must have correct pattern filters before generating blocks
- Task 3: Template detection depends on pattern availability

**Task 5 affects:**
- Task 4: Template 1 needs circuits loaded before use
- Task 8: Circuit IDs must be set correctly during save

**Task 6 affects:**
- Task 7: Time filling needs accurate per-block timing
- Task 4: Block generation needs duration awareness

**Task 1 affects:**
- Task 4: Main lift generation depends on constraint relaxation
- Task 9: Pass success logging needs pass tracking

**Task 10 (Frontend) affects:**
- Task 11: Testing must verify UI behavior with various empty section scenarios
- No backend dependencies (can be done in parallel)

### Design Considerations for Beginning:

1. **Config-First Design**: Start with `SECTION_PATTERN_FILTERS` (Task 2) to establish pattern rules before any generation logic
2. **Database Schema First**: Verify circuits_melted and circuits_macro tables have required fields before Task 5
3. **Interface Contracts**: Define clear interfaces between blocks and time estimation before Task 6
4. **Fallback Strategy**: Ensure each template has a fallback to pattern-based selection if circuits fail
5. **Frontend Resilience**: UI should handle empty sections gracefully even if backend has issues
6. **Duration Agnostic**: Ensure 5% buffer calculation works for ANY duration selected in create program flow (30, 45, 60, 90, etc.)

---

## File Change Summary

| File | Tasks | Purpose |
|-------|--------|---------|
| `app/config/heuristics.py` | 2 | SECTION_PATTERN_FILTERS config |
| `app/services/optimization.py` | 1 | Multi-pass constraint relaxation |
| `app/services/session_generator.py` | 3, 4, 5, 7, 8 | Core generation logic |
| `app/services/time_estimation.py` | 6 | Block time + transitions |
| `app/models/` | 5 | Circuit models if needed |
| `docs/session_generation_metrics.md` | 9 | Metrics documentation |
| `frontend/src/components/` | 10 | Hide empty sections in session cards |
| `tests/test_session_generation_templates.py` | 11 | Integration tests |

---

## Success Criteria

1. ✅ All sessions have movements populated (no empty sessions)
2. ✅ Sessions use 5% buffer for ANY duration selected in program creation flow (e.g., 30 min → 28.5-31.5, 45 min → 42.75-47.25, 60 min → 57-63, 90 min → 85.5-94.5)
3. ✅ Pattern filtering excludes wrong movements per section
4. ✅ 4 templates work correctly (normal, cardio, conditioning, mobility)
5. ✅ Circuits load with all movements in correct order
6. ✅ Constraint relaxation logs pass success for manual review
7. ✅ Time-filling respects hierarchy (cooldown → accessories → main lifts)
8. ✅ 2 min transitions accounted for between blocks
9. ✅ Frontend UI session cards do not show empty sections
10. ✅ Frontend UI handles gracefully if all sections are empty (edge case)
11. ✅ 5% buffer calculation is dynamic based on user's duration selection in create program flow