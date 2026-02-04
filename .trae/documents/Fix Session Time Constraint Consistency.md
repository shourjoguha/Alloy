# Implementation Plan: Fix Session Time Constraint Consistency

## Problem Summary

Sessions use inconsistent time parameters to determine movements/circuits. While the **5% tolerance exists in heuristics.py** and **flows correctly through the system**, there are critical architectural issues:

1. **ConstraintSolver overestimates duration** (~14 min/movement) vs TimeEstimationService (~8-10 min/movement)
2. **Multiple duplicate time calculation logic** across 6+ files
3. **Silent failures** - sessions saved outside 5% tolerance
4. **Fallback hardcodes 45 minutes** - ignores user's `max_session_duration`
5. **Template info lost** - causes incorrect block ordering during time filling

## Key Finding: 5% Tolerance Already Exists

The 5% deviation parameter **IS** in [`heuristics.py#L12`](file:///Users/shourjosmac/Documents/alloy/app/config/heuristics.py#L12):
```python
TIME_CONSTRAINT_TOLERANCE_PERCENT = 5
```

It flows through the system but validation is **inconsistent and not enforced**.

## Implementation Tasks

### Phase 1: Consolidate Time Calculation (Critical)

**Task 1.1: Fix ConstraintSolver time estimation** in [`optimization.py#L319-345`](file:///Users/shourjosmac/Documents/alloy/app/services/optimization.py#L319-L345)
- Remove inline time calculation
- Call `TimeEstimationService.estimate_session_time_with_transitions()` for accurate duration
- This fixes the ~14 min/movement overestimation

**Task 1.2: Remove duplicate time logic** in [`circuit_assignment.py#L187-193`](file:///Users/shourjosmac/Documents/alloy/app/services/circuit_assignment.py#L187-L193)
- Replace manual duration summation with `TimeEstimationService.estimate_session_time()`

**Task 1.3: Remove API fallback calculation** in [`programs.py#L350-351`](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py#L350-L351)
- Delete inline `10 + (exercise_count * 4)` calculation
- Use `TimeEstimationService.calculate_session_duration()`

### Phase 2: Fix Fallback Logic (Critical)

**Task 2.1: Use user's max_session_duration** in [`program.py#L593`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L593)
- Remove hardcoded `45` minutes fallback
- Use `parent_program.max_session_duration` consistently

**Task 2.2: Fix fallback duration calculations** in [`session_generator.py#L2308`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L2308)
- Remove hardcoded `(len(main) * 10) + (len(accessory) * 5) + 10`
- Use `TimeEstimationService` to calculate actual duration

### Phase 3: Enforce 5% Tolerance (High Priority)

**Task 3.1: Block saving outside tolerance** in [`session_generator.py#L2965`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L2965)
- Currently: Warns but saves anyway
- Fix: Return error status or throw exception when outside 5% buffer
- Add escalation logic for user notification

**Task 3.2: Improve time filling loop** in [`session_generator.py#L2942-2962`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L2942-L2962)
- Add better logging for each iteration
- Track what's being added/removed
- Return detailed failure reason if max iterations reached

### Phase 4: Preserve Template Information (High Priority)

**Task 4.1: Store template in blocks dict** in [`session_generator.py#L2621`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L2621)
- Add `"template": template` to blocks dictionary
- Fix `_fill_to_target_duration` to use correct block order

### Phase 5: Add User Feedback (Medium Priority)

**Task 5.1: Notify on optimization failure** in [`session_generator.py#L2755-2763`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L2755-L2763)
- Add user-facing notification when fallback is used
- Return status indicating optimization vs fallback

**Task 5.2: Reduce missing movement threshold** in [`session_generator.py#L812`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L812)
- Change from 50% to 15% threshold
- Better error handling for missing movements

## Files to Modify

1. [`app/services/optimization.py`](file:///Users/shourjosmac/Documents/alloy/app/services/optimization.py) - Fix ConstraintSolver time estimation
2. [`app/services/circuit_assignment.py`](file:///Users/shourjosmac/Documents/alloy/app/services/circuit_assignment.py) - Use TimeEstimationService
3. [`app/api/routes/programs.py`](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py) - Remove fallback calculation
4. [`app/services/program.py`](file:///Users/shourjosmac/Documents/alloy/app/services/program.py) - Fix fallback duration
5. [`app/services/session_generator.py`](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py) - Enforce tolerance, fix template
6. [`app/config/heuristics.py`](file:///Users/shourjosmac/Documents/alloy/app/config/heuristics.py) - Verify 5% constant (no change needed)

## Expected Outcome

After implementation:
- Sessions consistently respect `max_session_duration` with 5% buffer
- 60-minute target → sessions in 57-63 minute range
- No hardcoded fallbacks violating user preferences
- Single source of truth for all time calculations
- Better user feedback on failures
- Proper block ordering for all session types