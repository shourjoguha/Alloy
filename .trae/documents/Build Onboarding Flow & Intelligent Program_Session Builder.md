# Build Plan: Onboarding Flow & Intelligent Program/Session Builder

## Phase 1: Onboarding Flow Integration

### 1.1 Database Schema Setup
- Run Alembic migrations for onboarding tables (onboarding_responses, user_enjoyable_activities)
- Verify existing tables: users, user_profiles, user_movement_rules
- Create migration if needed for missing columns

### 1.2 Backend Implementation
- Verify `app/services/onboarding.py` has `submit_onboarding()` function
- Verify `app/api/routes/onboarding.py` has `/onboarding/submit` endpoint
- Ensure data mapping from questionnaire to database tables
- Add audit trail logging in onboarding_responses table

### 1.3 Frontend Implementation
- Verify `frontend/src/components/onboarding/OnboardingContainer.tsx`
- Verify `frontend/src/components/onboarding/QuestionRenderer.tsx`
- Verify `frontend/src/config/onboarding-questions.ts` has 8 questions
- Verify `frontend/src/config/onboarding-flow.ts` has branching logic
- Verify `frontend/src/stores/onboarding-store.ts` has Zustand persistence
- Verify route guard in `frontend/src/routes/__root.tsx` checks onboarding status

---

## Phase 2: Program Builder Enhancements

### 2.1 Fix Known Issues
- **Fix #1**: Goal Interference Validation - ensure no conflicting goals
- **Fix #2**: Ten-Dollar Method - verify goal weights sum to 10 (or 100)
- **Fix #3**: Experience-Based Defaults - auto-populate based on gym_comfort_level

### 2.2 Program Creation Flow
- Verify `app/services/program.py` creates program shells synchronously
- Verify background task `generate_active_microcycle_sessions()` runs AFTER commit
- Ensure session shells are created for all days (including rest days)

### 2.3 Frontend Program Wizard
- Verify `frontend/src/stores/program-wizard-store.ts` validation
- Verify `frontend/src/routes/program.wizard.tsx` has 7-step flow
- Add auto-population from onboarding data (goals, activities, equipment)

---

## Phase 3: Session Builder Enhancements

### 3.1 Fix Known Issues (Critical)
- **Fix #4**: Circuit Selection - Use SIMILARITY for finishers, COMPLEMENTARITY for accessories
- **Fix #5**: Circuit/Accessory Mutual Exclusivity - Enforce XOR logic
- **Fix #6**: Mobility in Main Lifts - Add pattern exclusion filter
- **Fix #7**: Main Lifts Compound Structure - Require 2-3 compound movements

### 3.2 Optimization Service
- Verify `app/services/optimization.py` uses Google OR-Tools
- Add constraint for min/max compound movements
- Add constraint for pattern exclusions (mobility, cardio, stretch)
- Verify fatigue/stimulus calculations

### 3.3 Circuit Comparison
- Verify `app/services/circuit_comparison.py` has similarity and complementarity weights
- Create `calculate_finisher_similarity_score()` function
- Modify `recommend_circuits_for_session()` to accept `is_finisher: bool`

### 3.4 Time Estimation
- Verify `app/services/time_estimation.py` calculates duration correctly
- Add detailed breakdown (warmup, main, accessories, finisher, cooldown)

---

## Phase 4: Integration & Testing

### 4.1 Onboarding → Program Integration
- Auto-populate program wizard with onboarding data:
  - `gym_comfort_level` → Default split template
  - `equipment_familiarity` → Movement filter
  - `goal_category` → Default goals
  - `athletic_activities` → Default enjoyable activities

### 4.2 End-to-End Testing
- Test registration → onboarding → dashboard flow
- Test program creation with onboarding data
- Test session generation for all session types
- Verify circuit/accessory mutual exclusivity

### 4.3 Verification & Logging
- Add comprehensive logging for session generation
- Add error handling and retry mechanisms
- Verify all background tasks complete successfully

---

## Phase 5: Code Quality & Documentation

### 5.1 Type Checking & Linting
- Run `ruff check` for Python
- Run `npm run typecheck` for TypeScript
- Run `npm run lint` for React

### 5.2 Final Verification
- Verify all migrations applied
- Verify all API endpoints working
- Verify all frontend routes working
- Verify database constraints enforced

---

**Estimated Complexity**: High (5 phases, ~25 tasks)
**Dependencies**: All onboarding-flow code verified and accurate
**Risk Level**: Medium (known issues documented, fixes clear)