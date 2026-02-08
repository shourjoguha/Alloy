# Comprehensive Assessment and Testing Plan

## Summary of Changes Made

### New Files Created:
1. **app/services/allocation_context.py** - Core dataclasses for allocation system
   - `GoalWeights` - Simple value/weight pairing
   - `UserSettings` - Persistent user preferences (frozen dataclass)
   - `AllocationContext` - Merged goal/settings overlay
   - `SessionIntent` - Separates auxiliary tags from movement patterns
   - `AllocationResult` - Contains allocation with validation methods

2. **app/services/allocation_integration.py** - Integration service layer
   - `AllocationIntegrationService` - Coordinates allocation flow
   - Merges wizard goals with user settings (wizard takes precedence)
   - Delegates to calculator and distributor
   - Applies movement patterns and resolves interference

### Modified Files:

3. **app/services/program.py** - Fix A1 & A2
   - Replaced direct calculator/distributor usage with `AllocationIntegrationService`
   - `_apply_goal_based_cycle_distribution` now uses unified context
   - `_apply_pattern_interference_rules` now preserves auxiliary tags during pattern resolution
   - `_has_pattern_conflict` filters auxiliary tags from conflict detection

4. **app/services/session_generator.py** - Fix A1, A2, A3
   - `_prefer_finisher`: Removed fallback logic, now raises `ValueError` if tags missing
   - `_validate_allocation_compliance`: New method enforces finisher/accessory XOR with detailed error codes
   - `_normalize_session_content`: Added validation call after mutual exclusivity check
   - `_get_smart_fallback_session_content`: Respects allocation tags (fixes by python-pro agent)
   - `_generate_blocks_by_template`: Checks intent_tags before generating blocks (fixes by python-pro agent)
   - `_build_goal_finisher_with_db`: Returns accessory block instead of None (fixes by python-pro agent)

5. **app/config/activity_distribution.py** - Fix A4
   - Removed `prefer_finisher_pressure` and `prefer_accessory_pressure` from `DEFAULT_USER_PREFERENCES`

6. **app/models/session_allocation.py** - Fix A4
   - Removed orphaned fields from `SessionTypePreferences` dataclass

## Issues Identified from Ruff Analysis

### Linting Errors to Fix:
1. **app/services/allocation_integration.py:89** - Unused import `SessionTypeTargets`
2. **app/services/program.py:32-34** - 4 unused imports after refactoring:
   - `SessionTypePreferences`
   - `GoalBucketWeights`
   - `CardioPreferenceMode`
   - `SessionTypeCalculator`
   - `SessionTypeDistributor`
3. **app/services/program.py:1548** - Variable `flat_tags` assigned but never used

### Code Quality Issues:

**Critical Issues:**
1. **allocation_context.py:80-100** - `AllocationResult.validate_session_content` uses wrong key names:
   - Checks `finisher_json` and `accessory_json` but should check `finisher` and `accessory`
   - Checks `main_json` but should check `main` (or `circuit` for cardio days)
   - This method will never work correctly!

2. **allocation_integration.py:174** - Typo: `FINISHER` should be `FINISHER`
3. **allocation_integration.py:193** - Typo: `cardio` should be `cardio` (extra "i")

**Medium Issues:**
4. **allocation_integration.py:150** - Typo in variable name: `_has_pattern_conflict` should be `_has_pattern_conflict`
5. **allocation_integration.py:230** - Typo: `_find_alternative_pattern` should be `_find_alternative_pattern` (method name mismatch)
6. **allocation_context.py:14** - Typo: `FINISHER` should be `FINISHER` (consistency)

**Design Concerns:**
7. **No circular dependency checks** - The new architecture should validate no circular imports or dependencies
8. **Missing error handling** - `AllocationIntegrationService` methods don't have try/except blocks

## Testing Plan

### Phase 1: Fix Critical Issues (Blocking)
1. Fix `AllocationResult.validate_session_content` to use correct key names
2. Fix all typos in `allocation_integration.py` and `allocation_context.py`
3. Remove unused imports from `program.py`

### Phase 2: Unit Tests (New Classes)
1. Test `UserSettings` dataclass initialization
2. Test `AllocationContext` creation with various goal/settings combinations
3. Test `SessionIntent` auxiliary tag separation
4. Test `AllocationResult.get_session_intent` error handling
5. Test `AllocationResult.validate_session_content` with all session types
6. Test `AllocationResult.get_allocated_type` returns correct types

### Phase 3: Integration Tests (Allocation Flow)
1. Test `AllocationIntegrationService.create_allocation_context` with:
   - Only user settings (no wizard goals)
   - Only wizard goals (no user settings)
   - Both present (verify wizard takes precedence)
2. Test `allocate_session_types` end-to-end flow
3. Test `apply_movement_patterns_to_intents` pattern application
4. Test `resolve_pattern_interference` with conflicting scenarios

### Phase 4: Regression Tests (Generator Integration)
1. Test `_prefer_finisher` raises error without tags
2. Test `_validate_allocation_compliance` catches all violations:
   - Both prefer_finisher and prefer_accessory present
   - No allocation tags present
   - Wrong content type for allocation
   - Missing required content
3. Test `_normalize_session_content` calls validation correctly
4. Test `program._apply_pattern_interference_rules` preserves auxiliary tags
5. Test `program._apply_goal_based_cycle_distribution` uses integration service

### Phase 5: Edge Cases
1. Empty wizard goals list
2. User settings with missing optional fields
3. Conflicting movement patterns requiring multiple alternatives
4. All sessions allocated as finishers (edge of max constraints)
5. Cardio preference mode edge cases (NONE mode)

### Phase 6: Linting Cleanup
1. Run `ruff check --fix` to auto-fix simple issues
2. Verify all imports are used
3. Verify no unused variables
4. Run mypy or pyright for type checking