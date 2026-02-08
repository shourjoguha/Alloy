# Program 228 Session Generation Failures - Investigation Summary

## Date
2026-02-06

## Executive Summary

**Root Cause**: Type safety bug in `session_generator.py` caused ALL training sessions (Days 1-12) to fail with error: `object of type 'NoneType' has no len()`

**Impact**: Only 1 of 12 training sessions in first microcycle was successfully generated (Day 13). Days 1-10 appear "normal" due to fallback notes overwriting error messages, while Days 11-12 show explicit error notes due to a transaction rollback.

**Resolution**: Three critical bugs fixed:
1. Type safety bug - Added `isinstance()` checks before calling `len()`
2. Fallback movement query bug - Changed from pattern match to exact match with `.limit(1)`
3. Multi-layered fallback mechanism - Replaced silent fallbacks with comprehensive structured error logging

---

## Investigation Process

### 1. Initial Misdiagnosis
Initially suspected duplicate session creation bug due to seeing 6 sessions per day in database queries. However, systematic investigation by specialized agents revealed:
- 6 microcycles × 14 days each = 84 sessions (expected, not a bug)
- Each microcycle has unique `microcycle_id` and different dates
- Session shells are created correctly during program creation

### 2. Root Cause Discovery

#### Database Evidence
| Day | Session ID | Exercises | Coach Notes | Status |
|------|-------------|------------|--------------|--------|
| 1 | 15163 | 0 | "Optimization-first session aligned..." | Failed (hidden) |
| 2 | 15164 | 0 | "Optimization-first session aligned..." | Failed (hidden) |
| ... | ... | ... | ... | ... |
| 11 | 15173 | 0 | "Generation failed: object of type 'NoneType' has no len()" | Failed (visible) |
| 12 | 15174 | 0 | "Generation failed: object of type 'NoneType' has no len()" | Failed (visible) |
| 13 | 15175 | 9 | (null) | **SUCCESS** |

#### Error Timeline
1. **16:51:40-16:51:42** - Session generation loop processes all 14 sessions
2. **16:51:40.753 - 16:51:42.272** - `_apply_session_fallback` called for sessions 15163-15174
3. **16:52:16.980** - Batch 1 notes (Days 1-3) - fallback notes applied successfully
4. **16:52:49.640** - Batch 2 notes (Days 4-6) - fallback notes applied successfully
5. **16:53:21.297** - Batch 3 notes (Days 8-10) - fallback notes applied successfully
6. **16:53:21.324** - Batch 4 notes (Days 11-12) - **ROLLBACK** occurred

### 3. Why Error Messages "Disappeared Progressively"

**Not actually disappearing** - Days 1-10 error notes were **overwritten** by successful fallback notes transactions. Days 11-12 error notes **remained** because Batch 4 transaction was rolled back.

---

## Bugs Fixed

### Bug #1: Type Safety in _normalize_session_content

**File**: `app/services/session_generator.py`

**Location**: Lines 1091, 1208

**Problem**:
```python
has_accessory = bool(normalized.get("accessory")) and len(normalized.get("accessory", [])) > 0
```

`bool()` returns `True` for non-empty strings, dicts, sets, etc. Then `len()` fails with TypeError on non-list types.

**Fix**:
```python
accessory = normalized.get("accessory")
if accessory is not None and not isinstance(accessory, list):
    logger.error(f"Invalid type for 'accessory' field: {type(accessory).__name__}. Expected list or None. Value: {accessory}")
    has_accessory = False
else:
    has_accessory = bool(accessory) and len(accessory) > 0
```

**Diagnostic File**: `/Users/shourjosmac/Documents/alloy/TYPE_SAFETY_FIX_DIAGNOSTIC.md`

---

### Bug #2: Fallback Movement Query Returns Multiple Rows

**File**: `app/services/program.py`

**Location**: Line 675

**Problem**:
```python
fallback_movement = await db.execute(
    select(Movement).where(Movement.name.ilike("%air%"))
)
fallback_movement = fallback_movement.scalar_one_or_none()
```

Multiple movements contain "air" in their names (Air Squat, Air Bike, Air Lunge, etc.), causing `scalar_one_or_none()` to fail.

**Fix**:
```python
fallback_movement = await db.execute(
    select(Movement).where(Movement.name == "Back Squat").limit(1)
)
fallback_movement = fallback_movement.scalar_one_or_none()
```

**Diagnostic File**: `/Users/shourjosmac/Documents/alloy/FALLBACK_MOVEMENT_FIX.md`

---

### Bug #3: Multi-Layered Fallback Mechanisms Masking Real Issues

**Files**: `app/services/session_generator.py`, `app/services/program.py`

**Problem**: 7+ fallback mechanisms in session_generator.py and 5+ in program.py silently caught exceptions without logging why they failed, making debugging extremely difficult.

**Fix**: Replaced silent fallbacks with comprehensive structured error logging:
- **Input state** captured (session_id, type, duration, constraints)
- **Failure context** documented (what failed, why failed, exception type)
- **Stack traces** included for debugging
- **Fallbacks documented** with clear logging when they're used

**Diagnostic Files**:
- `/Users/shourjosmac/Documents/alloy/FALLBACK_DIAGNOSTIC_REPORT.md`
- `/Users/shourjosmac/Documents/alloy/FALLBACK_CHANGES_SUMMARY.md`

---

## Files Modified

### Core Fixes
1. `app/services/session_generator.py` - Lines 1091-1096, 1208-1214
2. `app/services/program.py` - Lines 675, 697

### Logging Enhancements
1. `app/services/session_generator.py` - 7 locations enhanced with structured logging
2. `app/services/program.py` - 5 locations enhanced with structured logging

### Diagnostic Documentation
1. `TYPE_SAFETY_FIX_DIAGNOSTIC.md`
2. `FALLBACK_MOVEMENT_FIX.md`
3. `FALLBACK_DIAGNOSTIC_REPORT.md`
4. `FALLBACK_CHANGES_SUMMARY.md`
5. `PROGRAM_228_INVESTIGATION_SUMMARY.md` (this file)

---

## Expected Outcomes

### After Fixes

1. **Type safety**: `len()` will never be called on non-list values
2. **Fallback movement**: Query will return exactly 0 or 1 rows
3. **Visibility**: All failures will have detailed error context with stack traces
4. **Debugging**: Structured logging format enables automated parsing and alerting
5. **MTTR**: Root causes visible immediately, no need to dig through nested fallbacks

### When Program 228 is Regenerated

1. All 12 training sessions should generate successfully
2. OR-Tools optimization should find solutions for all session types
3. If failures occur, detailed error logs will show exactly why
4. No more "NoneType has no len()" errors
5. Fallback mechanism should rarely be triggered

---

## Key Learnings

### 1. OR-Tools vs LLM Architecture Confirmed
- **OR-Tools**: Primary movement selection (ConstraintSolver)
- **LLM**: ONLY generates coach notes (batched after session creation)
- **Fallbacks**: Rule-based logic, not LLM

### 2. Scheduling Preferences Integration
- Scheduling preferences are used during **program creation** to set session structure (day types, intent_tags)
- Session generation uses **intent_tags** from program creation, not raw scheduling preferences
- Disconnect exists but doesn't cause this issue

### 3. Multi-Layered Fallbacks Are Harmful
- Silent fallbacks mask root causes
- Users see generic errors or "normal" sessions that are actually broken
- Debugging requires tracing through multiple fallback layers
- Better to fail loudly with detailed context

---

## Next Steps

1. **Test fixes** by regenerating program 228 sessions
2. **Monitor logs** for structured error output
3. **Set up alerts** for:
   - CRITICAL level logs from fallback mechanisms
   - High frequency of same failure type
   - Missing movements in database
4. **Review production logs** after fixes to identify any remaining issues
5. **Consider** adding health checks for external dependencies (LLM, database)

---

## Credits

Investigation completed using systematic debugging approach with multiple specialized agents:
- error-detective: Traced failure timeline and error messages
- debugger: Analyzed session generation flow and code paths
- code-reviewer: Verified OR-Tools vs LLM architecture
- backend-developer: Fixed type safety and query bugs
- error-coordinator: Replaced silent fallbacks with structured logging

All temporary diagnostic files preserved for reference.
