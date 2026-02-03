# Onboarding Flow Implementation Plan

## Overview
Create a conversational, branching onboarding flow for new users that captures comprehensive fitness profile data between registration and dashboard entry.

## Research Findings

### Existing Patterns to Reuse
- **Program Wizard**: Multi-step wizard with progress tracking, validation, and conditional steps
- **Card Selection**: ActivitiesStep shows multi-select pattern with emoji icons
- **5-Point Slider**: CoachStep has dynamic labels (1-5 with contextual descriptions)
- **State Management**: 3 Zustand stores (auth, ui, program-wizard) with varying persistence strategies
- **Route Guards**: Root route checks auth status and redirects appropriately
- **Data Tables**: Existing user_profiles, user_skills, user_enjoyable_activities, user_movement_rules cover most onboarding data

### Gaps Identified
- No date picker component (uses native input)
- No toggle/switch component (uses native checkbox)
- No existing branching question system beyond simple step validation
- No onboarding completion tracking in database

---

## Architecture Design

### Data Model Changes

**user_profiles table additions:**
```python
onboarding_completed_at: DateTime | None
onboarding_version: String(50) | None
equipment_familiarity: JSON | None      # {barbell: 1-5, dumbbell: 1-5, ...}
athletic_background: JSON | None         # {sports: [], running: bool, yoga: bool, ...}
gym_comfort_level: String(50) | None   # enum: beginner, active, experienced
```

**New table: onboarding_responses**
```python
id, user_id, question_id, answer_value (JSON), answered_at, question_set_version
```

**Migration Strategy:**
- Mark all existing users as completed (`onboarding_completed_at = NOW()`)
- Set version as `'pre-onboarding-v1'` for existing users
- New users have `NULL` onboarding_completed_at

### Frontend Architecture

**New Route:** `/onboarding` (between register and dashboard)

**Route Guard Logic:**
```
Register → Token returned → verify-token → check onboarding status
  ↓
  ├─ Not completed → /onboarding
  └─ Completed → /dashboard
```

**New Store:** `onboarding-store.ts` (non-persistent)
```typescript
answers: Record<string, any>
currentQuestionIndex: number
setAnswer, navigate, submit, reset
```

**Question Configuration:** `frontend/src/config/onboarding-questions.ts`
- Declarative question definitions
- Separate flow config for branching
- Versioning support

### Backend API Design

**New Endpoints:**
1. `GET /onboarding/status` - Check completion and version
2. `POST /onboarding/submit` - Submit complete answers (transactional)
3. `PATCH /onboarding/progress` - Save partial progress (optional v1)

**New Service:** `app/services/onboarding_service.py`
- Maps answers to user_* tables
- Transactional data writing
- Pre-fills from existing data if user revisits

---

## Question Design (Conversational Style)

### Phase 1: Basics
**Q1:** "Let's get to know each other. What should I call you?" (text input)
**Q2:** "When's your birthday? Don't worry, I won't sing. 🎂" (date picker)
**Q3:** "What's your sex preference?" (card toggle: MALE/FEMALE/OTHER/PREFER_NOT_TO_SAY)

### Phase 2: Workout Philosophy (Branching)
**Q4:** "How would you describe your fitness journey?"
- Cards: "Just getting started" / "Active but new to gym" / "Been training a while"
- *Branching: "Just starting" skips equipment questions*

**Q5:** "What do you love doing outside the gym?"
- Multi-select cards: Sports, Running, Yoga, Pilates, Swimming, Nothing

**Q6:** "How familiar are you with gym toys?" (5-point sliders per equipment)
- Barbells, Dumbbells, Kettlebells, Machines, Cables
- Labels: 1="Never touched it", 5="My best friend"

**Q7:** "Which movements have you tried?" (Yes/No cards)
- Squats, Deadlifts, Bench, Pull-ups, Olympic lifts

### Phase 3: Goals
**Q8:** "What's your big goal for the next 1-3 years?"
- Cards: Build muscle, Lose fat, Get stronger, Performance, Health
**Q9:** "Tell me more about that..." (text area)

---

## Implementation Steps

### Phase 1: Database & Backend (Core)
1. Create Alembic migration for schema changes
2. Create `onboarding_responses` table
3. Add onboarding router and schemas
4. Implement onboarding_service with data mapping
5. Add onboarding status to `/auth/verify-token` response

### Phase 2: Frontend Configuration
1. Create `onboarding-questions.ts` with question definitions
2. Create `onboarding-flow.ts` with branching logic
3. Create `onboarding-store.ts` (Zustand)

### Phase 3: UI Components
1. Create reusable input components (DateToggle, SexToggle, YesNoCard)
2. Create OnboardingContainer (similar to WizardContainer)
3. Implement question renderer with branching support

### Phase 4: Integration
1. Add route to `/onboarding` in router
2. Update auth-store to track `hasCompletedOnboarding`
3. Modify `__root.tsx` route guard for onboarding check
4. Update registration flow to redirect to onboarding

### Phase 5: Testing & Polish
1. Test branching logic
2. Test data persistence
3. Test edge cases (abandon, refresh, API failures)
4. Polish conversational copy

---

## Second & Third Order Effects

### Positive Effects
- Better user personalization from day 1
- Higher engagement (onboarding completion correlates with retention)
- Cleaner user data for program generation

### Risks to Mitigate
- **Drop-off rate**: Keep flow under 10 questions, save progress, allow resume
- **Data corruption**: Transactional writes, validate before submit
- **Version conflicts**: Track onboarding_version, handle migrations
- **Performance**: Cache onboarding status in auth store

### Future Considerations
- Onboarding completion analytics (drop-off points, time-to-complete)
- A/B testing question variants
- Re-onboarding for users wanting to reset profile
- Admin view of onboarding responses
- Integration with Jerome's persona (LLM-generated questions)

---

## Files to Create/Modify

### Database
- `alembic/versions/*_add_onboarding.py` (new migration)
- `app/models/user.py` (add onboarding fields to user_profiles)
- `app/models/onboarding.py` (new OnboardingResponse model)

### Backend
- `app/api/routes/onboarding.py` (new router)
- `app/schemas/onboarding.py` (new schemas)
- `app/services/onboarding_service.py` (new service)

### Frontend
- `frontend/src/config/onboarding-questions.ts` (new)
- `frontend/src/config/onboarding-flow.ts` (new)
- `frontend/src/stores/onboarding-store.ts` (new)
- `frontend/src/routes/onboarding.tsx` (new route)
- `frontend/src/components/onboarding/*.tsx` (new components)
- `frontend/src/stores/auth-store.ts` (add hasCompletedOnboarding)
- `frontend/src/routes/__root.tsx` (modify route guard)
- `frontend/src/api/onboarding.ts` (new API client)
- `frontend/src/api/auth.ts` (update verify-token response type)

### Components to Create
- `OnboardingContainer.tsx` (main flow wrapper)
- `QuestionRenderer.tsx` (dispatches to input types)
- `BasicInput.tsx`, `DateToggle.tsx`, `SexToggle.tsx`
- `CardSelection.tsx`, `Slider5Point.tsx`, `YesNoCard.tsx`
- `OnboardingProgress.tsx` (step indicator)