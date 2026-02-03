# Session Generation System - Key Findings & Action Plan

## Quick Summary

**Issue**: Only day 1 and day 10 sessions being created instead of all expected sessions

**Root Cause Analysis**: The system has a known transaction timing issue that has been identified and fixed, but may have residual problems or edge cases.

## System Flow Overview

```
API Request (POST /programs)
    ↓
1. Create Program Object
2. Flush to get ID
    ↓
3. Create Program Disciplines
    ↓
4. Create Microcycles (loop)
    ↓
5. For each microcycle:
   a. Create Microcycle Object
   b. Flush to get ID
   c. Create Sessions (loop) - Creates ALL session "shells"
    ↓
6. COMMIT all changes (program, microcycles, sessions)
    ↓
7. Add Background Task (AFTER commit)
    ↓
8. Background Task Queries Database for Sessions
    ↓
9. Populates Each Session with Exercises (LLM calls)
    ↓
10. Save Exercises to Database
```

## Critical Code Locations

### 1. Program Creation (Sync)
**File**: [app/api/routes/programs.py:56](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py#L56-L220)
- Commits all changes at line 198
- Adds background task AFTER commit at line 209

### 2. Session Shell Creation
**File**: [app/services/program.py:995](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L995-L1003)
- Creates session objects with metadata only (no exercises)
- All sessions created in single transaction

### 3. Background Task Entry
**File**: [app/services/program.py:352](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L352-L379)
- Queries for ALL sessions in active microcycle
- Line 412-416: Critical query that fetches sessions

### 4. Session Population
**File**: [app/services/session_generator.py:263](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L263-L449)
- Each session populated independently
- Uses 3 separate DB sessions per session
- Commits exercises after LLM generation

## Identified Issues

### Issue #1: Transaction Timing (FIXED in code)

**Symptom**: Only first and last sessions visible

**Root Cause**:
- Background task was added BEFORE commit in earlier version
- SQLAlchemy flush sends SQL but doesn't make changes visible to other transactions
- Query in background task could only see flushed sessions

**Evidence**:
Comment at [programs.py:205-208](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py#L205-L208) explicitly states:
```python
# CRITICAL: Add background task AFTER all transactions are committed
# This ensures all sessions are available when the background task queries the database
# If the background task is added before commit, it may query for sessions before they are
# committed, leading to only seeing the first and last sessions that were flushed
```

**Current Status**: Fixed - background task added AFTER commit (line 209)

### Issue #2: Session Population Failures (POSSIBLE)

**Symptom**: Sessions created but not populated with exercises

**Root Cause**:
- Sessions are created as "shells" in Phase 1
- Exercises added in Phase 2 (background task)
- If background task fails or is interrupted, sessions remain empty
- Individual session failures are caught and continue

**Evidence**:
- Each session population wrapped in try/except (line 468)
- Recovery sessions explicitly skipped (line 437)
- Failures don't stop other sessions

### Issue #3: Split Template Edge Cases (POSSIBLE)

**Symptom**: Only specific days have training sessions

**Root Cause**:
- Evenly spaced days algorithm might have edge cases
- Goal-based distribution can convert training days to other types
- Conversions might reduce expected training day count

**Evidence**:
- [program.py:1068](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L1068-L1074): `_build_freeform_split_config`
- [program.py:1153](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L1153-L1333): `_apply_goal_based_cycle_distribution`
- Converts training days to cardio/mobility/conditioning

### Issue #4: Database Isolation (UNLIKELY)

**Symptom**: New DB session doesn't see committed data

**Root Cause**:
- SQLite isolation level or WAL mode configuration
- Transaction visibility rules

**Evidence**:
- WAL mode enabled: [database.py:54-58](file:///Users/shourjosmac/Documents/alloy/app/db/database.py#L54-L58)
- Session factory uses `expire_on_commit=False`: [database.py:25](file:///Users/shourjosmac/Documents/alloy/app/db/database.py#L25)

## Action Plan

### Immediate Actions (Debugging)

1. **Add Comprehensive Logging**
   - Log session count after creation in `_create_microcycle`
   - Log each session created (day_number, session_type)
   - Log sessions fetched in background task
   - Log session population completion/failure

2. **Verify Database State**
   ```sql
   -- Check session count for microcycle
   SELECT COUNT(*) FROM sessions WHERE microcycle_id = X;

   -- Check which sessions have exercises
   SELECT s.id, s.day_number, COUNT(se.id) as exercise_count
   FROM sessions s
   LEFT JOIN session_exercises se ON s.id = se.session_id
   WHERE s.microcycle_id = X
   GROUP BY s.id, s.day_number;
   ```

3. **Monitor Background Task**
   - Check logs for "START" and "COMPLETED" messages
   - Look for "Found X sessions to generate" messages
   - Verify all sessions are being processed

4. **Test Transaction Visibility**
   - Add query immediately after commit in `create_program`
   - Verify all sessions are visible in new DB session
   - Compare with background task query results

### Short-term Fixes

1. **Add Session Count Validation**
   - After creating sessions, verify count matches expected
   - Log warning if count doesn't match split_config.training_days
   - Prevent background task if validation fails

2. **Add Session Population Status Tracking**
   - Add field to Session model: `content_generated_at` timestamp
   - Update timestamp when exercises are saved
   - Query for sessions without content to identify failures

3. **Add Retry Mechanism**
   - Track failed session populations
   - Implement retry logic with exponential backoff
   - Max 3 retries per session

4. **Add Monitoring Dashboard**
   - Track session generation success rate
   - Monitor background task execution time
   - Alert on repeated failures

### Long-term Improvements

1. **Redesign Session Generation Flow**
   - Consider making session creation fully synchronous
   - Or implement proper job queue with visibility guarantees
   - Remove dependency on background task timing

2. **Add Unit Tests**
   - Test split template generation with various inputs
   - Test session creation count validation
   - Test transaction visibility scenarios
   - Test edge cases (odd numbers, boundary values)

3. **Improve Error Handling**
   - Collect all session generation errors
   - Report summary to user
   - Provide option to regenerate failed sessions

4. **Add Circuit Template Support**
   - If using circuits, verify template assignment
   - Check if circuit assignment affects session visibility
   - Add logging for circuit template lookups

## Split Template Analysis

### Evenly Spaced Days Algorithm

**Example**: 4 days/week, 7-day cycle
- Calculation: `target_sessions = round(4 * 7/7) = 4`
- Step: `step = 7 / 4 = 1.75`
- Days: [1, 3, 4, 6]

**Resulting Sessions**:
- Day 1: Training
- Day 2: Rest
- Day 3: Training
- Day 4: Training
- Day 5: Rest
- Day 6: Training
- Day 7: Rest

**Expected**: 4 training sessions per 7-day cycle

### Goal-Based Distribution Impact

The `_apply_goal_based_cycle_distribution` method can:
1. Convert training days to cardio/mobility/conditioning
2. Add finisher preferences to training days
3. Add accessory preferences to training days
4. Change session type based on goals

**Potential Issue**: If too many training days converted, fewer sessions than expected

## Database Transaction Flow

### Program Creation Transaction
```
BEGIN TRANSACTION
  INSERT INTO programs
  COMMIT (flush only) → program.id available
    ↓
  INSERT INTO program_disciplines
    ↓
  LOOP over microcycles:
    INSERT INTO microcycles
    COMMIT (flush only) → microcycle.id available
      ↓
    LOOP over days:
      INSERT INTO sessions
END LOOP
END LOOP
  COMMIT (full) → All changes visible
    ↓
  Add background task
```

### Background Task Transaction
```
BEGIN NEW TRANSACTION
  SELECT sessions WHERE microcycle_id = X
  (Should see all sessions from above commit)
END TRANSACTION

  LOOP over sessions:
    BEGIN NEW TRANSACTION
      SELECT session, program, microcycle
      (Context fetching)
    END TRANSACTION

    GENERATE CONTENT (no DB connection)

    BEGIN NEW TRANSACTION
      SELECT session
      INSERT INTO session_exercises
      UPDATE session.estimated_duration_minutes
      COMMIT
    END TRANSACTION
END LOOP
```

## Debugging Checklist

- [ ] Verify background task is added AFTER commit
- [ ] Check logs for "Successfully committed all changes"
- [ ] Verify background task logs "Found X sessions to generate"
- [ ] Check if X matches expected session count
- [ ] Look for errors in session population
- [ ] Verify all sessions have exercises in database
- [ ] Test with fresh database to rule out corruption
- [ ] Check for any caching issues
- [ ] Verify split template configuration
- [ ] Test with different days_per_week values

## References

- **Complete Flow Analysis**: [SESSION_GENERATION_KNOWLEDGE.md](file:///Users/shourjosmac/Documents/alloy/SESSION_GENERATION_KNOWLEDGE.md)
- **Program Service**: [app/services/program.py](file:///Users/shourjosmac/Documents/alloy/app/services/program.py)
- **Session Generator**: [app/services/session_generator.py](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py)
- **API Routes**: [app/api/routes/programs.py](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py)
- **Data Models**: [app/models/program.py](file:///Users/shourjosmac/Documents/alloy/app/models/program.py)
- **Database Config**: [app/db/database.py](file:///Users/shourjosmac/Documents/alloy/app/db/database.py)

## Conclusion

The most likely cause of partial session visibility is the transaction timing issue that has been identified and fixed. However, residual issues may exist due to:

1. **Edge cases in split template configuration** - Testing needed with various inputs
2. **Silent failures in session population** - Better error handling needed
3. **Incomplete implementation of timing fix** - Verify fix is working in all code paths

**Recommended immediate action**: Add comprehensive logging to identify exactly where the issue occurs, then implement targeted fixes based on findings.
