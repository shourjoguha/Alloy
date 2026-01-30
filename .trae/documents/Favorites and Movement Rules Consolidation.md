# Favorites & Movement Rules Consolidation - Implementation Plan

## Overview
Consolidate two separate favorites/movement rules systems into a single unified system with persistent user-level preferences that flow between settings and program wizard.

---

## Phase 1: Database Migration (Week 1)

### 1.1 Create Alembic Migration
**File:** `alembic/versions/unify_movement_preferences.py`

**Upgrade steps:**
- Add `created_at`, `updated_at`, `program_id`, `substitute_movement_id` columns
- Backfill `created_at` with `NOW()` for existing records
- Add foreign key constraints
- Add composite indexes for performance
- Add unique constraints (partial indexes for user-level vs program-level rules)
- Run deduplication logic to resolve conflicts

**Deduplication Strategy:**
- For same user+movement: prioritize HARD_YES over PREFERRED over HARD_NO
- Keep the most recent based on existing ID order
- Delete duplicates, notify affected users

### 1.2 Update SQLAlchemy Model
**File:** `app/models/user.py`

Update `UserMovementRule` class with:
- New columns: `created_at`, `updated_at`, `program_id`, `substitute_movement_id`
- New relationships: `scope_program`, `substitute_movement`
- New methods: `@property is_favorite`, `@property scope`
- New `__table_args__` with unique constraints

---

## Phase 2: Backend API Implementation (Week 1-2)

### 2.1 Create Unified API Router
**File:** `app/api/routes/movement_preferences.py`

Implement:
- `GET /api/movement-preferences` - List with filters
- `POST /api/movement-preferences` - Create single or batch
- `GET /api/movement-preferences/{id}` - Get by ID
- `PATCH /api/movement-preferences/{id}` - Partial update
- `PUT /api/movement-preferences/{id}` - Full replace
- `DELETE /api/movement-preferences/{id}` - Delete single
- `DELETE /api/movement-preferences` - Batch delete

### 2.2 Update Existing Routers as Delegates
**Files:** `app/api/routes/favorites.py`, `app/api/routes/settings.py`

Refactor to delegate to unified API:
- `/api/favorites` → calls unified API with `rule_type=HARD_YES`
- `/api/settings/movement-rules` → calls unified API

Maintain backward compatibility by:
- Keeping existing response formats
- Supporting existing request schemas
- Deprecation warnings (optional)

### 2.3 Update Schemas
**File:** `app/schemas/movement_preferences.py`

Create:
- `MovementPreferenceCreate`
- `MovementPreferenceBatchCreate`
- `MovementPreferenceUpdate`
- `MovementPreferenceReplace`
- `MovementPreferenceResponse`
- `MovementPreferenceListResponse`
- `MovementPreferenceBatchResponse`

---

## Phase 3: Frontend API Layer (Week 2)

### 3.1 Create Unified API Client
**File:** `frontend/src/api/movement-preferences.ts`

Implement:
- Query key hierarchy
- `useUserMovementRules()` - Fetch persistent rules
- `useUserActivities()` - Fetch enjoyable activities
- `useUserPreferences()` - Combined hook
- `useUpsertMovementRule()` - Create/update with optimistic updates
- `useDeleteMovementRule()` - Delete with optimistic updates
- `useBatchUpsertMovementRules()` - Batch operations
- `usePersistWizardPreferences()` - Sync wizard to user prefs

### 3.2 Update Existing API Files
**Files:** `frontend/src/api/favorites.ts`, `frontend/src/api/settings.ts`

Mark as deprecated or update to use new unified client.

---

## Phase 4: Frontend State Management (Week 2-3)

### 4.1 Enhance Zustand Store
**File:** `frontend/src/stores/program-wizard-store.ts`

Add:
- `initializeFromUserPreferences()` - Load user prefs on wizard start
- `persistToUserPreferences()` - Save wizard prefs on completion
- `hasUnsavedChanges()` - Check for unsaved modifications

### 4.2 Update Components
**Files:** 
- `frontend/src/components/settings/FavoritesTab.tsx`
- `frontend/src/components/wizard/MovementsStep.tsx`
- `frontend/src/components/wizard/ActivitiesAndMovementsStep.tsx`

Changes:
- Replace ephemeral-only state with `useUserPreferences()` hook
- Initialize wizard from user preferences on mount
- Add "Save as Defaults" button to wizard
- Implement optimistic updates

---

## Phase 5: Testing & Validation (Week 3)

### 5.1 Database Tests
- Test migration on staging with sample data
- Verify deduplication logic
- Check indexes performance
- Test rollback procedure

### 5.2 API Tests
- Unit tests for all CRUD operations
- Test batch operations
- Test duplicate prevention
- Test backward compatibility

### 5.3 Frontend Tests
- Component integration tests
- State sync tests (settings ↔ wizard)
- Optimistic update tests
- Error handling tests

### 5.4 E2E Tests
- Create program in wizard with prefs
- Modify prefs in settings
- Verify wizard reflects changes
- Verify wizard changes persist to settings

---

## Phase 6: Deployment (Week 4)

### 6.1 Pre-Deployment Checklist
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Migration tested on staging
- [ ] Rollback procedure documented
- [ ] Monitoring/alerting configured

### 6.2 Deployment Steps
1. Deploy backend with new migration
2. Monitor migration execution
3. Verify deduplication completed
4. Deploy frontend with new components
5. Monitor error rates
6. Validate user preferences working

### 6.3 Post-Deployment
- Monitor database performance
- Check for duplicate preference reports
- Validate program generation with new preferences
- Collect user feedback

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Migration failure | Test on staging, have rollback ready |
| Performance degradation | Add indexes before migration, batch operations |
| Data loss | Backup database before migration |
| User confusion | Communicate changes, show "preferences merged" notification |
| API breaking changes | Maintain backward compatibility layer |

---

## Success Metrics

- Zero data loss during migration
- User preferences persist between settings and wizard
- Page load time < 2 seconds with new API
- Error rate < 0.1% post-launch
- 95% of users report positive experience with new flow