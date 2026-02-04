# Investigation Report: Program Building & Time Estimation Logic
**Date:** 2026-02-04
**Scope:** Program Builder, Session Generator, Time Estimation, Circuit Assignment
**Agents Involved:** Backend Developer, Architect Reviewer, Systematic Debugging

## 1. Executive Summary
A multi-level deep dive into the backend services has confirmed **significant inconsistencies** in time estimation logic, **duplicate code** patterns, and potential **race conditions**. While the core requirement of a 5% time deviation is technically enforced by the `SessionGeneratorService` (via `_fill_to_target_duration`), the upstream components (Constraint Solver) and side-components (Circuit Assignment) use disparate, hardcoded, or inferior logic to calculate duration. This leads to inefficient optimization and potential data integrity issues.

## 2. System Trace & Data Flow
The program creation flow operates as follows:

1.  **API/ProgramService**:
    *   Receives `max_session_duration` (e.g., 60 mins).
    *   **Inconsistency**: If session generation fails, `_apply_session_fallback` hardcodes duration to `45` minutes, ignoring the user's setting.
2.  **SessionGeneratorService**:
    *   Receives `max_session_duration`.
    *   Calls `ConstraintSolver` to generate the "Main" block.
    *   **Critical Gap**: `ConstraintSolver` uses **hardcoded, conservative math** (approx. 14 mins/movement) to determine feasibility.
    *   Calls `_fill_to_target_duration` to enforce the 5% tolerance using `TimeEstimationService`.
3.  **ConstraintSolver (`optimization.py`)**:
    *   **Duplicate/Inferior Logic**: Uses internal math (`AVG_SETS_PER_MOVEMENT * 4`) to estimate duration. This typically overestimates time, causing the solver to select fewer exercises than possible.
4.  **TimeEstimationService (`time_estimation.py`)**:
    *   **Source of Truth**: Contains the detailed, correct logic (reps, rest, tempo, transitions) referenced from `heuristics.py`.
    *   Used correctly by `SessionGenerator` for final validation/filling, but ignored by `ConstraintSolver`.
5.  **CircuitAssignmentService (`circuit_assignment.py`)**:
    *   **Duplicate Logic**: Manually sums duration components (`warmup + main + ...`) instead of using `TimeEstimationService`.
    *   **Inconsistency**: Uses simple addition, potentially missing transition times or superset logic defined in the central service.

## 3. Key Findings & Blind Spots

### A. Inconsistent Time Parameters (The "Duplicate Math" Problem)
Three different services calculate "Session Duration" in three different ways:
*   **TimeEstimationService**: `(sets * (exec + rest)) + transitions`. (Correct)
*   **ConstraintSolver**: `sets * 4 minutes`. (Incorrect/Conservative)
*   **CircuitAssignmentService**: `sum(component_minutes)`. (Simplistic)

**Impact**: The Constraint Solver often "thinks" a session is full when it is not. The `SessionGenerator` then has to "fill" the remaining time using `_fill_to_target_duration`. This effectively bypasses the intelligence of the optimizer, relying on the filler logic to reach the time goal.

### B. Race Conditions
*   **CircuitAssignmentService**:
    *   Fetches session -> Checks existing exercises -> Writes new exercises.
    *   **Risk**: No database row locking (`with_for_update`) is used. Concurrent requests to assign circuits to the same session could result in a corrupted state (e.g., duplicate exercises or orphaned references) if they interleave during the `await` calls.

### C. Silent Failures
*   **Optimization Failure**: If `ConstraintSolver` fails (returns INFEASIBLE), `SessionGenerator` silently falls back to `_generate_smart_fallback_main_block`. The user is not notified that the "optimized" plan failed.
*   **Fallback Duration**: As noted, the fallback hardcodes 45 minutes, silently violating the user's time constraint if they selected 30 or 60 minutes.

### D. 2nd & 3rd Order Effects
*   **Optimizer Under-performance**: Because the solver overestimates time (14 mins vs ~8 mins real), it consistently under-fills sessions.
*   **Reliance on Filler**: The system relies heavily on `_fill_to_target_duration` to fix the solver's mistakes. This makes the "Optimization" step less relevant than intended.

## 4. Recommendations

### Immediate Fixes (High Priority)
1.  **Standardize Solver Math**: Update `ConstraintSolver._solve_session_internal` to use `TimeEstimationService` (or logic that mirrors it closely) for its duration constraints. This ensures the solver fills the session accurately.
2.  **Fix Fallback Logic**: Update `ProgramService._apply_session_fallback` to use `program.max_session_duration` instead of hardcoded `45`.
3.  **Add DB Locking**: Implement `with_for_update()` in `CircuitAssignmentService` when fetching the session to prevent race conditions.

### Architectural Refactoring (Medium Priority)
1.  **Centralize Time Logic**: Refactor `CircuitAssignmentService` to inject and use `TimeEstimationService` for all duration updates. Remove manual summation logic.
2.  **Unified Config**: Ensure `ConstraintSolver` reads parameters (like "minutes per set") from `heuristics.py` rather than internal constants.

### Testing & Validation
1.  **Trace Test**: Create a test case that traces a 60-minute program creation. Assert that `ConstraintSolver` fills it to ~55-58 minutes, leaving minimal work for `_fill_to_target_duration`.
2.  **Concurrency Test**: Simulate concurrent circuit assignments to verify locking.

## 5. File References
*   [app/services/program.py](file:///Users/shourjosmac/Documents/alloy/app/services/program.py)
*   [app/services/session_generator.py](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py)
*   [app/services/time_estimation.py](file:///Users/shourjosmac/Documents/alloy/app/services/time_estimation.py)
*   [app/services/optimization.py](file:///Users/shourjosmac/Documents/alloy/app/services/optimization.py)
*   [app/services/circuit_assignment.py](file:///Users/shourjosmac/Documents/alloy/app/services/circuit_assignment.py)
