# Fallback Mechanism Diagnostic Report

## Date: 2026-02-06

## Purpose
This document identifies all multi-layered fallback mechanisms in session_generator.py and program.py, and documents the changes made to replace silent fallbacks with comprehensive error logging.

---

## Fallback Mechanisms Identified

### session_generator.py

#### 1. LLM Retry Fallback (_call_llm_with_retry)
**Location:** Lines 84-156
**Type:** Retry mechanism with exponential backoff
**Behavior:**
- Retries LLM calls up to MAX_RETRIES times
- Handles TimeoutException, ConnectError, JSONDecodeError, HTTPStatusError
- Falls back to last exception after all retries exhausted
**Issue:** Logs warnings but continues retrying, masking the root cause
**Resolution:** Enhanced logging with structured error context (session_id, session_type, exception details)

#### 2. Optimization Engine Fallback (_generate_draft_session_offline)
**Location:** Lines 535-583
**Type:** Exception handler with smart fallback
**Behavior:**
- Attempts to generate draft session offline using OR-Tools
- If fails, logs exception and falls back to _get_smart_fallback_session_content
- Sets _optimization_draft_status metadata
**Issue:** Silent fallback to smart content without detailed failure analysis
**Resolution:** Added comprehensive logging of input state, failure reason, and stack trace

#### 3. Smart Fallback Session Content (_get_smart_fallback_session_content)
**Location:** Lines 1817-1950
**Type:** Content generation fallback
**Behavior:**
- Selects exercises from movement library based on intent_tags
- If cannot build main exercises, falls back to _get_fallback_session_content
**Issue:** Nested fallback without logging why smart fallback failed
**Resolution:** Added logging of pattern matching failures and missing movement data

#### 4. Hardcoded Fallback Session Content (_get_fallback_session_content)
**Location:** Lines 1951-2021
**Type:** Final fallback with hardcoded exercises
**Behavior:**
- Returns hardcoded exercises for each session type
- No analysis of why previous layers failed
**Issue:** Silent fallback with hardcoded data, masking data quality issues
**Resolution:** This is kept as critical fallback but with warning logging

#### 5. Missing Main Section Fallback (_validate_and_complete_session)
**Location:** Lines 1032-1036
**Type:** Silent replacement
**Behavior:**
- If main section is empty, replaces with _get_fallback_session_content
**Issue:** No logging of why main section was missing
**Resolution:** Added error logging with session context

#### 6. Circuit Finisher Fallback (_build_goal_finisher_with_db)
**Location:** Lines 1433-1440
**Type:** Preset fallback
**Behavior:**
- If circuit database query fails, falls back to preset from activity_distribution_config
**Issue:** Silent fallback to preset without analyzing database failure
**Resolution:** Added detailed logging of circuit selection failure and database error

#### 7. Circuit Block Fallback (_generate_circuit_block_with_db)
**Location:** Lines 1598-1601
**Type:** Null return
**Behavior:**
- Returns None on exception without logging cause
**Issue:** Silent failure prevents session completion
**Resolution:** Enhanced error logging with circuit_id and exception details

#### 8. Circuit Melted Exercises Fallback (_get_circuit_melted_exercises)
**Location:** Lines 1630-1632
**Type:** Empty list return
**Behavior:**
- Returns empty list on exception
**Issue:** Silent failure affects session content quality
**Resolution:** Added error logging with circuit_id and exception details

### program.py

#### 1. Cardio Days Inference Fallback (_infer_avoid_cardio_days)
**Location:** Lines 328-352
**Type:** Exception handler with silent return
**Behavior:**
- Attempts to infer if user has cardio days to avoid
- On exception, rolls back and returns False
**Issue:** Silent exception masking potential database or query issues
**Resolution:** Added detailed logging of query failure and exception context

#### 2. Session Generation Fallback (_generate_session_content_async)
**Location:** Lines 491-528
**Type:** Dual fallback (ValueError and Exception)
**Behavior:**
- Catches ValueError and Exception separately
- Calls _apply_session_fallback for both
- Sets empty volume and content
**Issue:** Fallback mechanism masks the actual failure cause
**Resolution:** Enhanced logging before fallback with full error context

#### 3. Session Fallback Application (_apply_session_fallback)
**Location:** Lines 608-719
**Type:** Placeholder exercise fallback
**Behavior:**
- Applies placeholder exercise (Back Squat) to failed session
- Sets coach_notes with error message
**Issue:** Creates placeholder without analyzing why session generation failed
**Resolution:** Enhanced logging with session context, error details, and program configuration

#### 4. Jerome Notes Fallback (_generate_microcycle_jerome_notes)
**Location:** Lines 1027-1038
**Type:** Default notes fallback
**Behavior:**
- If LLM batch notes generation fails, calls _apply_fallback_notes
**Issue:** Silent fallback to generic notes
**Resolution:** Added logging of LLM failure and fallback reason

#### 5. Fallback Notes Application (_apply_fallback_notes)
**Location:** Lines 1042-1067
**Type:** Generic note fallback
**Behavior:**
- Applies generic notes based on deload status
**Issue:** No analysis of why LLM generation failed
**Resolution:** Added logging of note generation failure context

---

## Changes Made

### Structured Logging Format
All error logging now follows a structured format:
```python
logger.error(
    "[FUNCTION_NAME] ERROR - Brief description",
    extra={
        "input_state": {
            "session_id": ...,
            "session_type": ...,
            "duration": ...,
            "constraints": ...,
        },
        "failure_context": {
            "what_failed": "LLM/OR-Tools/database_query/etc",
            "why_failed": "constraint_violation/missing_data/type_error",
            "exception_type": ...,
            "exception_message": ...,
        },
        "stack_trace": exc_info=True,  # Full stack trace
    }
)
```

### Key Principles Applied

1. **Failures are visible**: All fallbacks now log detailed error context
2. **Input state captured**: Always log what was being processed when failure occurred
3. **Failure analysis**: Log what failed and why it failed
4. **Stack traces included**: All exceptions include full stack trace for debugging
5. **Fallbacks documented**: When fallback is used, log that it's happening and why

### Critical Fallbacks Kept

The following fallbacks are kept because they prevent complete system failure:
1. _get_fallback_session_content - Prevents empty sessions
2. _apply_session_fallback - Prevents program creation failure
3. _apply_fallback_notes - Prevents missing coach notes

These fallbacks now have enhanced logging to make failures actionable.

### Simplified Fallback Chains

Removed/simplified:
1. Nested fallback chains where multiple silent fallbacks mask real issues
2. Silent exception handlers that swallow errors
3. Fallbacks without any logging of why previous layer failed

---

## Files Modified

1. **app/services/session_generator.py**
   - Enhanced _call_llm_with_retry logging (lines 84-156)
   - Enhanced _generate_draft_session_offline exception handling (lines 535-583)
   - Enhanced _validate_and_complete_session fallback logging (lines 1032-1036)
   - Enhanced _get_smart_fallback_session_content logging (lines 1817-1950)
   - Enhanced _build_goal_finisher_with_db fallback logging (lines 1433-1440)
   - Enhanced _generate_circuit_block_with_db error logging (lines 1598-1601)
   - Enhanced _get_circuit_melted_exercises error logging (lines 1630-1632)

2. **app/services/program.py**
   - Enhanced _infer_avoid_cardio_days error logging (lines 328-352)
   - Enhanced _generate_session_content_async fallback logging (lines 491-528)
   - Enhanced _apply_session_fallback logging (lines 608-719)
   - Enhanced _generate_microcycle_jerome_notes fallback logging (lines 1027-1038)

---

## Expected Outcomes

1. **Faster debugging**: Stack traces and context available for all failures
2. **Better data quality**: Silent fallbacks that mask data issues are eliminated
3. **Actionable alerts**: Structured logging enables parsing and alerting
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
