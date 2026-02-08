# Fallback Movement Query Bug Fix

## Date
2026-02-06

## Issue
The `_apply_session_fallback` function in `app/services/program.py` around line 675 was using `ilike("%air%")` to search for fallback movements, which could return multiple rows. This caused `scalar_one_or_none()` to fail when multiple movements containing "air" existed in the database.

## Root Cause
- `ilike("%air%")` is a pattern match that returns any movement with "air" in its name
- This could match multiple movements (e.g., "Air Squat", "Fair", "Airplane", etc.)
- `scalar_one_or_none()` expects exactly 0 or 1 rows, throwing an exception if multiple rows are returned

## Fix Applied
**File**: `/Users/shourjosmac/Documents/alloy/app/services/program.py`

**Line 675**: Changed from:
```python
select(Movement).where(Movement.name.ilike("%air%"))
```

To:
```python
select(Movement).where(Movement.name == "Back Squat").limit(1)
```

**Line 697**: Changed log level from `logger.warning` to `logger.error` when no fallback movement is found.

## Changes Summary
1. Replaced `ilike("%air%")` with exact match `== "Back Squat"`
2. Added `.limit(1)` to ensure query returns at most 1 row
3. Changed warning log to error log for missing fallback movement

## Rationale
- "Back Squat" is a core movement guaranteed to exist in the seed data
- Exact match ensures deterministic behavior
- `.limit(1)` provides additional safety even though exact match should return 0 or 1 rows
- Error log level better reflects severity of missing fallback (session will have no exercises)

## Testing
The fix ensures:
- Query returns exactly 0 or 1 rows
- No exception thrown when fallback movement exists
- No exception thrown when fallback movement doesn't exist
- Proper error logging when fallback is unavailable

## Files Modified
- `/Users/shourjosmac/Documents/alloy/app/services/program.py` (lines 675, 697)
