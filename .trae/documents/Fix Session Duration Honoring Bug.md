# Updated Investigation & Fix Plan for Session Duration Bug

## Summary
Root cause: Multiple code paths don't respect `max_session_duration`, causing sessions to default to 45-60 minutes regardless of user settings (30, 45, 90, 120 min programs all generating 41-51 min sessions).

---

## Phase 1: Fix Critical Bugs

### 1. Fix `_generate_conditioning_main_block()` (session_generator.py:2443-2463)
**Current Issue:** Receives `max_session_duration` but never uses it. Always generates 4-8 exercises with fixed sets/reps.

**Fix Approach:**
- Keep number of movements within 4-8 range
- Calculate time budget per exercise: `max_session_duration / num_exercises`
- Adjust sets/reps proportionally to fit within time budget
- Add note: "Break reps and sets into as many rounds as needed to complete within target duration"

### 2. Update `circuit_assignment.py:474` warning threshold
**Current Issue:** Hardcoded 60-minute warning, ignores program's `max_session_duration`.

**Fix Approach:**
- Pass program.max_session_duration as threshold parameter
- Compare against actual program setting, not hardcoded 60

---

## Phase 2: Fix Hardcoded Defaults

### 3. Update `time_estimation.py` finisher defaults
**Current Issue:** Fixed 8-minute and 5-minute defaults regardless of session duration.

**Fix Approach:**
- Keep finisher duration as-is (per your feedback)
- Increase movements, sets, and reps in warmup/main/cooldown sections to fill time budget
- Use TimeEstimationService to calculate what's needed

### 4. Update `days.py:363` fallback
**Current Issue:** Hardcoded 60-minute fallback when estimated_duration missing.

**Fix Approach:**
- Replace hardcoded 60 with `get_default_session_duration()`
- Already imported, just change constant

---

## Phase 3: Clean Up Legacy Code (Thorough)

### 5. Remove and deprecate `LLMOptimizer.duration_targets`
**Current Issue:** Hardcoded duration_targets dict (45-60 min) not used in active flow.

**Cleanup Approach:**
- Mark as deprecated with clear docstring comment
- Search all services for references (backend, API routes)
- Remove any imports or usage across layers
- Check frontend for any references
- Add deprecation warning if accessed
- Document why it's deprecated (OR-Tools now handles duration)

**Search scope:**
- All files in `app/services/`
- All files in `app/api/routes/`
- All files in `app/llm/`
- Frontend stores (if applicable)

---

## Phase 4: Validate with Tests

### 6. Add integration tests for session duration validation
**Test cases:**
- 30 min program → generates 28-32 min sessions (±5%)
- 45 min program → generates 42-48 min sessions (±5%)
- 90 min program → generates 85-95 min sessions (±5%)
- 120 min program → generates 114-126 min sessions (±5%)

### 7. Run existing test suite
- Ensure no regressions from changes
- Fix any test failures

---

## Net Code Impact
- **Subtraction:** Remove ~20 hardcoded duration references and orphaned code blocks
- **Addition:** Add ~80 lines of proportional duration calculation logic
- **Net change:** ~+60 lines (focused, compact changes per your subtraction preference)

## Execution Order
1. Phase 1: Fix critical conditioning and circuit assignment bugs
2. Phase 2: Fix hardcoded defaults in time_estimation and API routes
3. Phase 3: Thorough cleanup of legacy LLMOptimizer code
4. Phase 4: Add tests and validate