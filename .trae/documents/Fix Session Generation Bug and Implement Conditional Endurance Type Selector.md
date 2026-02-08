## Overview
This plan addresses two critical issues:
1. **Session Generation Bug**: All sessions stop generating after day 2-3 when dedicated CARDIO/CONDITIONING sessions fail
2. **Conditional Endurance Type Selector**: Make "Endurance-Heavy Cardio Day" conditional and add "Endurance only" vs "Cardio only" selector

---

## Issue 1: Fix Session Generation Bug (Critical)

### Root Cause
In [`program.py#L611`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L611), `_apply_session_fallback()` accesses `failed_session.program_id` which **doesn't exist** on Session model (Session only has `microcycle_id`). When a dedicated CARDIO/CONDITIONING session fails, the fallback crashes, terminating all remaining session generation.

### Confirmed Trigger
Bug ONLY occurs when `cardio_preference` is NOT `"finisher"` (i.e., `"dedicated_day"` or `"mixed"`), because only then are dedicated CARDIO sessions created which can fail and trigger the buggy fallback.

### Solution
**File: [`app/services/program.py`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py)**
- Line 611: Replace `failed_session.program_id` with `failed_session.microcycle.program_id`
- Add better error handling around fallback calls
- Add detailed logging to identify which session fails

**Files Modified:**
- [`app/services/program.py`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py) (~5 lines)

---

## Issue 2: Conditional Endurance Type Selector

### 2a. Make "Endurance-Heavy Cardio Day" Conditional

**Backend Changes:**
**File: [`app/services/program.py`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py)**
- Lines 1315-1327: Modify `force_endurance_cardio_day` logic to only apply when `cardio_preference in {"dedicated_day", "mixed"}`
- Add logging when `endurance_dedicated_cardio_day_policy` is ignored due to `cardio_preference = "finisher"`

**Frontend Changes:**
**File: [`frontend/src/components/settings/ProfileTab.tsx`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/settings/ProfileTab.tsx)**
- Lines 379-392: Wrap "Endurance-Heavy Cardio Day" selector in conditional rendering
- Only show when `watch('scheduling_preferences.cardio_preference') !== "none"`

### 2b. Add "Endurance Type" Selector

**Storage Design:**
Add `endurance_type` field to `scheduling_preferences` JSON:
```json
{
  "endurance_type": "auto" | "endurance_only" | "cardio_only"
}
```

**Session Type Mapping (for dedicated sessions only):**
- `"endurance_only"` → `SessionType.CUSTOM` with `"conditioning"` intent (circuit-based conditioning)
- `"cardio_only"` → `SessionType.CARDIO` with traditional cardio movements (steady-state, intervals, running, cycling)
- `"auto"` → Existing goal-based logic: `endurance >= fat_loss → conditioning`, else `cardio`

**IMPORTANT**: `endurance_type` ONLY affects dedicated session types when `cardio_preference` is `"dedicated_day"` or `"mixed"`. When `cardio_preference = "finisher"`, it has no effect (finishers are always circuit-based).

**Backend Changes:**

1. **File: [`app/schemas/settings.py`](file:///Users/shourjosmac/Documents/alloy/app/schemas/settings.py)**
   - Add `SchedulingPreferencesValidator` with `endurance_type` validation
   - Add validator to `UserProfileUpdate` schema

2. **File: [`app/services/program.py`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py)**
   - Lines 1310-1315: Read and validate `endurance_type` from scheduling preferences
   - Modify `preferred_dedicated_type` calculation based on `endurance_type`
   - Ensure `force_endurance_dedicated_type` respects user selection

**Frontend Changes:**

1. **File: [`frontend/src/types/index.ts`](file:///Users/shourjosmac/Documents/alloy/frontend/src/types/index.ts)**
   - Add `endurance_type?: 'auto' | 'endurance_only' | 'cardio_only'` to `SchedulingPreferences`

2. **File: [`frontend/src/components/settings/ProfileTab.tsx`](file:///Users/shourjosmac/Documents/alloy/frontend/src/components/settings/ProfileTab.tsx)**
   - Add new "Endurance Type" selector (lines ~394-406)
   - Options: "Auto (based on goals)", "Endurance only (circuits & conditioning)", "Cardio only (steady-state & intervals)"
   - Conditional rendering: only show when `watch('scheduling_preferences.cardio_preference') in {"dedicated_day", "mixed"}`
   - Add tooltip explaining difference

**Test Updates:**

**File: [`tests/test_goal_distribution_and_structure.py`](file:///Users/shourjosmac/Documents/alloy/tests/test_goal_distribution_and_structure.py)**
   - Update `test_endurance_heavy_adds_dedicated_cardio_day_by_default()` to only trigger when `cardio_preference in {"dedicated_day", "mixed"}`
   - Add new test for `endurance_type = "endurance_only"` creating conditioning sessions
   - Add new test for `endurance_type = "cardio_only"` creating cardio sessions

---

## Files Summary

| File | Changes | Lines |
|-------|-----------|--------|
| `app/services/program.py` | Fix program_id bug + conditional endurance logic + endurance_type | ~20 |
| `app/schemas/settings.py` | Add SchedulingPreferencesValidator | ~30 |
| `frontend/src/types/index.ts` | Add endurance_type to interface | ~1 |
| `frontend/src/components/settings/ProfileTab.tsx` | Conditional rendering + new selector | ~30 |
| `tests/test_goal_distribution_and_structure.py` | Update/add tests | ~50 |

---

## Backward Compatibility
- `endurance_type` defaults to `"auto"` (existing behavior preserved)
- No database migration needed (JSON field addition)
- Existing users unaffected until they change settings
- Bug fix for `program_id` is backward compatible