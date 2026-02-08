# Fallback Error Logging Changes Summary

## Date: 2026-02-06

## Overview
This document summarizes the changes made to replace multi-layered fallback mechanisms with comprehensive error logging in session_generator.py and program.py.

---

## Changes Made

### app/services/session_generator.py

#### 1. _call_llm_with_retry (Lines 137-158, 165-181)
**Before:** Simple warning log on exception
**After:** Structured error log with input state, failure context, and stack trace

**Changes:**
- Added structured logging with `input_state` (session_id, session_type, attempt, max_retries, delay, provider_base_url)
- Added `failure_context` (what_failed, why_failed, exception_type, exception_message)
- Added `exc_info=True` for full stack traces
- Changed from logger.warning to logger.error for better visibility
- Enhanced final retry exhaustion message with structured context

#### 2. generate_session_exercises_offline (Lines 590-607)
**Before:** Generic error log with exception details
**After:** Structured error log separating input state from failure context

**Changes:**
- Reorganized logging to separate `input_state` and `failure_context`
- Added all input parameters (session_id, session_type, intent_tags, movements counts, goal_weights, movement rules, duration, movement_groups, fatigued_muscles)
- Clearly identified what failed (OR-Tools draft generation)
- Maintained exception details with stack trace

#### 3. _validate_and_complete_session (Lines 1065-1079)
**Before:** Simple error log about missing main section
**After:** Structured error log with context

**Changes:**
- Added structured logging with `input_state` (session_type, has_main, main_count)
- Added `failure_context` (what_failed, why_failed)
- Maintained fallback behavior (critical fallback kept)

#### 4. _build_goal_finisher_with_db (Lines 1480-1507)
**Before:** Simple error log with exception
**After:** Structured error log + structured warning for fallback

**Changes:**
- Added structured error log with `input_state` (session_type, intent_tags, fat_loss_weight, endurance_weight, available_circuits_count)
- Added `failure_context` (what_failed, why_failed, exception details)
- Added structured warning log when falling back to preset finisher
- Clearly documented that preset fallback is being used

#### 5. _generate_circuit_block_with_db (Lines 1674-1690)
**Before:** Simple error log with exception
**After:** Structured error log with context

**Changes:**
- Added structured logging with `input_state` (session_type, intent_tags, goal_weights, primary_region)
- Added `failure_context` (what_failed, why_failed, exception details)
- Maintained None return behavior

#### 6. _get_circuit_melted_exercises (Lines 1723-1741)
**Before:** Simple error log
**After:** Structured error log with context

**Changes:**
- Added structured logging with `input_state` (circuit_id)
- Added `failure_context` (what_failed, why_failed, exception details)
- Maintained empty list return behavior

#### 7. _get_smart_fallback_session_content (Lines 2002-2018)
**Before:** Silent fallback when main exercises cannot be built
**After:** Error log before falling back to hardcoded content

**Changes:**
- Added structured error log when pattern matching fails for all intent tags
- Added `input_state` (session_type, intent_tags, movements_by_pattern_keys, used_movements_count, max_session_duration)
- Added `failure_context` (what_failed, why_failed)
- Clearly documents that fallback is being used

### app/services/program.py

#### 1. _infer_avoid_cardio_days (Lines 347-379)
**Before:** Silent exception with empty catch blocks
**After:** Structured error logging for both main exception and rollback failure

**Changes:**
- Added structured error log with `input_state` (user_id)
- Added `failure_context` (what_failed, why_failed, exception details)
- Added structured error log for rollback failure
- Maintained False return behavior (critical fallback kept)

#### 2. _generate_session_content_async (Lines 491-595)
**Before:** Simple error logs with basic session info
**After:** Structured error logs for both ValueError and Exception cases, plus fallback failures

**Changes:**
- Added structured error log for ValueError with `input_state` (session_id, day_number, session_type, microcycle_id, is_deload)
- Added `failure_context` (what_failed, why_failed, exception details)
- Added structured CRITICAL error log when fallback application fails
- Added structured error log for general Exception case
- Added structured CRITICAL error log for general exception fallback failure
- All errors include stack traces via `exc_info=True`

#### 3. _apply_session_fallback (Lines 751-810)
**Before:** Simple info/error logs
**After:** Structured logging for all scenarios

**Changes:**
- Added structured INFO log when applying fallback placeholder exercise
- Added `input_state` (session_id, session_type, fallback_movement_id, fallback_movement_name, original_error)
- Added `failure_context` (what_failed, why_failed)
- Added structured ERROR log when fallback movement not found
- Added structured ERROR log when fallback movement query fails
- All error logs include exception details

#### 4. _generate_microcycle_jerome_notes (Lines 1135-1172)
**Before:** Simple warning/error logs
**After:** Structured logging for LLM response parsing failure and generation failure

**Changes:**
- Added structured WARNING log when LLM response parsing fails
- Added `input_state` (batch_size, response_type, batch_start_index)
- Added `failure_context` (what_failed, why_failed)
- Added structured ERROR log when LLM batch notes generation fails
- Added `input_state` (batch_size, batch_start_index, batch_index, total_sessions)
- Added `failure_context` (what_failed, why_failed, exception details)
- Maintained fallback to default notes (critical fallback kept)

#### 5. _apply_fallback_notes (Lines 1176-1207)
**Before:** No logging
**After:** Structured INFO log documenting fallback usage

**Changes:**
- Added structured INFO log when applying fallback coach notes
- Added `input_state` (sessions_count, is_deload)
- Added `failure_context` (what_failed, why_failed)
- Clearly documents that generic fallback notes are being used

---

## Structured Logging Format

All error logging now follows this consistent format:

```python
logger.error(
    "[FUNCTION_NAME] ERROR - Brief description",
    extra={
        "input_state": {
            # Key-value pairs describing the state when the error occurred
            "session_id": ...,
            "session_type": ...,
            "duration": ...,
            "constraints": ...,
        },
        "failure_context": {
            # Key-value pairs describing the failure
            "what_failed": "Component/operation that failed",
            "why_failed": "Reason for failure",
            "exception_type": "Exception class name",
            "exception_message": "Exception message",
        },
    },
    exc_info=True,  # Full stack trace
)
```

---

## Critical Fallbacks Kept

The following fallbacks are preserved because they prevent complete system failure:

1. **_get_fallback_session_content** - Prevents empty sessions when all other methods fail
2. **_apply_session_fallback** - Prevents program creation failure when session generation fails
3. **_apply_fallback_notes** - Prevents missing coach notes when LLM generation fails

These critical fallbacks now have enhanced logging to make their usage visible and actionable.

---

## Expected Benefits

1. **Faster debugging**: Stack traces and context available for all failures
2. **Better data quality**: Silent fallbacks that mask data issues are eliminated
3. **Actionable alerts**: Structured logging enables automated parsing and alerting
4. **Pattern detection**: Consistent error format allows automated analysis
5. **Reduced MTTR**: Root cause visible immediately, no need to dig through nested fallbacks

---

## Monitoring Recommendations

1. Set up alerts for:
   - "CRITICAL" level logs from fallback mechanisms
   - High frequency of same fallback type
   - Missing movements in database (threshold exceeded)

2. Monitor metrics:
   - Fallback rate per session type
   - LLM failure rate
   - OR-Tools failure rate
   - Database query failure rate

3. Create dashboards for:
   - Top failure reasons by session type
   - Pattern of fallback usage over time
   - Most common missing movements

---

## Next Steps

1. Review logs from production to identify common failure patterns
2. Address root causes of frequent fallbacks (data quality, service availability)
3. Consider implementing circuit breaker patterns for repeated failures
4. Add health checks for external dependencies (LLM, OR-Tools, database)
