# Implementation Plan: Circuit Block Selection with Mutual Exclusivity

## Overview
Update the session optimizer to enforce that sessions can have EITHER an accessory block OR a circuit block (never both), with circuits selected atomically and under relaxed constraints.

---

## Phase 1: Database Schema & Migration
**Files:** `app/models/program.py`, `app/models/circuit.py`, `alembic/versions/`

**Tasks:**
1. Add `has_circuits` boolean column to `Session` model
2. Add database check constraint for mutual exclusivity (accessories vs circuits)
3. Add partial unique index on `SessionExercise` for enforcement
4. Add triggers to maintain `has_circuits` flag
5. Create Alembic migration script with conflict resolution (prioritize circuits over accessories)
6. Create backup table for conflicting records before cleanup

**Agents:** database-admin, postgres-pro

---

## Phase 2: Update Session Generator Logic
**File:** `app/services/session_generator.py`

**Tasks:**
1. Add `_decide_session_type()` method to choose between circuit vs accessory block
   - Use goal weights: `fat_loss + endurance > strength + hypertrophy` → prefer circuit
   - Consider session_type: CARDIO/CONDITIONING → circuit, lifting → accessory
2. Add `_validate_mutual_exclusivity()` method to enforce no both accessories and circuits
3. Update `_normalize_session_content()` to enforce XOR logic:
   - If circuit present → remove all accessories
   - If accessories present → remove all circuits
4. Update `_prefer_finisher()` to return circuit recommendation instead of just boolean
5. Update `_generate_circuit_block()` with relaxed constraints:
   - Remove region limit constraint
   - Remove pattern diversity constraint
   - Keep max_fatigue and duration constraints
6. Add circuit block generation logic (atomic selection of all movements in circuit)

**Agents:** python-pro, backend-developer

---

## Phase 3: Update Optimization Service
**File:** `app/services/optimization.py`

**Tasks:**
1. Modify OR-Tools solver to support circuit selection as atomic unit
2. Remove circuit diversity constraints (already implemented, just document)
3. Update circuit variable selection to be all-or-nothing
4. Add circuit block as alternative to accessory block in optimization
5. Ensure circuit fatigue is properly accounted for (already normalized to 50%)

**Agents:** python-pro, backend-developer

---

## Phase 4: Create Circuit Assignment Service
**New File:** `app/services/circuit_assignment.py`

**Tasks:**
1. Create `CircuitAssignmentService` class with methods:
   - `assign_circuit_to_session()` - Atomic transaction to add all circuit exercises
   - `get_available_circuits_for_session()` - Use CircuitComparisonService for recommendations
   - `preview_circuit_assignment()` - Preview impact before committing
2. Implement transaction rollback on any failure (atomic constraint)
3. Validate session compatibility, duration limits, muscle overlap

**Agents:** backend-developer, database-admin

---

## Phase 5: API Endpoints
**File:** `app/api/routes/sessions.py`, `app/schemas/circuit.py`

**Tasks:**
1. Create new schemas in `app/schemas/circuit.py`:
   - `CircuitAssignmentCreate`
   - `CircuitAssignmentResponse`
   - `CircuitRecommendationRequest`
   - `CircuitPreviewResponse`
2. Add new endpoints:
   - `POST /sessions/{id}/circuits` - Assign circuit atomically
   - `PATCH /sessions/{id}/circuits/{role}` - Update/remove circuit
   - `GET /sessions/{id}/available-circuits` - Get recommendations
   - `POST /circuits/sessions-preview` - Preview before commit
3. Update `SessionResponse` schema to include circuit metadata

**Agents:** api-designer, backend-developer

---

## Phase 6: Update Frontend Components
**Files:** `frontend/src/components/SessionCard.tsx`, related components

**Tasks:**
1. Add session type detection (circuit vs accessory)
2. Implement conditional rendering: show circuit section OR accessory section
3. Add circuit display component for showing circuit details
4. Update session time estimation to use exact circuit durations
5. Handle circuit vs accessory UI patterns

**Agents:** frontenddeveloper, UI-designer

---

## Phase 7: Update Time Estimation Service
**File:** `app/services/time_estimation.py`

**Tasks:**
1. Add logic to calculate circuit block time (use `duration_seconds` from circuit)
2. Replace accessory time estimation with circuit time when circuit present
3. Update `estimate_session_time()` to handle circuit blocks accurately

**Agents:** backend-developer

---

## Phase 8: Update Adaptation Service
**File:** `app/services/adaptation.py`

**Tasks:**
1. Update adaptation logic to handle circuits as atomic units
2. When circuit causes soreness, remove/replace entire circuit (not individual movements)
3. Add circuit-level adaptation (swap circuit, not individual exercises)

**Agents:** backend-developer

---

## Phase 9: Update Program Service
**File:** `app/services/program.py`

**Tasks:**
1. Update microcycle generation to decide circuit vs accessory sessions upfront
2. Pass session_type hint to SessionGenerator for consistent block selection
3. Ensure goal mix influences circuit vs accessory distribution

**Agents:** backend-developer

---

## Phase 10: Testing & Validation
**Tasks:**
1. Test mutual exclusivity constraint (no both accessories and circuits)
2. Test circuit atomic selection (all movements added together)
3. Test relaxed circuit constraints (more variety available)
4. Test circuit vs accessory decision logic
5. Test time estimation accuracy with circuits
6. Test adaptation with circuits
7. Validate frontend displays correctly
8. Performance testing with relaxed constraints

**Agents:** error-detective, debugger, performance-engineer

---

## Phase 11: Documentation
**Tasks:**
1. Update API documentation with new endpoints
2. Document circuit vs accessory decision logic
3. Document mutual exclusivity constraint
4. Create migration guide for existing data

**Agents:** technical-writer

---

## Summary of Key Changes

1. **Mutual Exclusivity:** Sessions can have accessories OR circuits, never both
2. **Atomic Selection:** Circuits selected as complete units (all-or-nothing)
3. **Relaxed Constraints:** Remove region/pattern diversity limits on circuits
4. **Decision Logic:** Goal-based choice between circuit vs accessory blocks
5. **New API:** Endpoints for circuit assignment, recommendations, and preview
6. **Database Constraints:** Check constraints and triggers enforce exclusivity
7. **Frontend Updates:** Conditional rendering for circuit vs accessory sessions

**Estimated Phases:** 11
**Estimated Agents:** 10+
**Risk Level:** Medium (data migration requires care)