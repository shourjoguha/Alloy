## Root Causes Identified

**Issue 1: Sessions Not Producing Movements**
- Draft optimization fails silently
- Smart fallback encounters missing movements
- Basic fallback succeeds but movement names don't exist in database
- Empty exercise lists save without validation
- Frontend stuck in "Generating…" state

**Issue 2: Identical First Sessions Across Programs**
- Basic fallback uses hardcoded exercise names based ONLY on session type (UPPER/LOWER/FULL_BODY)
- Ignores goals, intent_tags, user preferences
- Different programs with same split → identical first session

## Implementation Plan

### Priority 1: Critical - Prevent Empty Session Persistence
**File:** `app/services/session_generator.py` (line 676-766)
- Add validation to raise error if no exercises are saved
- Log detailed context when save is empty

### Priority 2: Critical - Verify Movement Names in Fallbacks
**File:** `app/services/session_generator.py` (lines 2274-2349)
- Replace hardcoded movement names with dynamic selection from available movements
- Use movement patterns instead of specific names
- Raise error if no movements available

### Priority 3: High - Improve Error Handling and Logging
**File:** `app/services/session_generator.py` (lines 554-574)
- Add structured error logging with full context
- Log session_type, intent_tags, movement counts

### Priority 4: High - Relax Validation Threshold
**File:** `app/services/session_generator.py` (line 761)
- Increase tolerance from 25% to 50% for missing movements
- Add warning log for missing movements under threshold

### Priority 5: Medium - Investigate ConstraintSolver
**File:** `app/services/optimization.py`
- Add unit tests for `solve_session()`
- Add logging to track optimization status

### Priority 6: Medium - Add Frontend Error State
**File:** `frontend/src/components/program/SessionCard.tsx`
- Detect failed generation state
- Display error message to user

### Priority 7: Low - Optimize Database Queries
**File:** `app/api/routes/programs.py` (lines 235-296)
- Use `selectinload` to preload exercises and movements
- Eliminate N+1 query pattern