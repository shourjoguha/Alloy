# Onboarding Flow Fixes - Multi-Phase Implementation Plan

## Overview
Fix critical bugs and improve encapsulation of onboarding flow based on coordinated agent analysis.

---

## Phase 1: Critical State Persistence (HIGH PRIORITY)

**Goal:** Fix data loss on page refresh and state desync

### Tasks:
1. Add `persist` middleware to `onboarding-store.ts`
   - Import `persist` from zustand/middleware
   - Wrap store creation with persist()
   - Configure localStorage key: 'alloy-onboarding-storage'
   - Persist: answers, currentQuestionId

2. Fix race condition in `OnboardingContainer.handleSubmit()`
   - Move `reset()` call after `navigate()`
   - Ensure state cleanup only happens after successful redirect

---

## Phase 2: UI Improvements (MEDIUM PRIORITY)

**Goal:** Improve user experience and prevent errors

### Tasks:
1. Add loading state to submit button
   - Pass `isSubmitting` to `QuestionRenderer`
   - Disable button during submission
   - Show loading spinner/text

2. Fix validation mismatch between UI and store
   - Use `canProceed()` from onboarding-store in QuestionRenderer
   - Ensure button disabled state matches store validation

3. Remove dead code in `OnboardingContainer`
   - Remove unused `isLast` variable (line 112)
   - Remove unused import `isLastQuestion as isLastQuestionFn`

4. Standardize "last question" calculation
   - Use `isLastQuestionFn()` consistently
   - Remove redundant index-based calculation

---

## Phase 3: Progress Tracking (HIGH PRIORITY)

**Goal:** Enable progress saving and recovery

### Tasks:
1. Call `saveOnboardingProgress()` on each answer
   - Add call in `QuestionRenderer.handleNext()`
   - Save after each question completion
   - Enable progress recovery after refresh

2. Add retry mechanism for failed submissions
   - Show error display with retry button
   - Keep answers preserved on error
   - Allow user to resubmit

---

## Phase 4: Encapsulation & Feature Toggling (LOW PRIORITY)

**Goal:** Make onboarding truly toggleable

### Tasks:
1. Create feature flags configuration
   - Add `frontend/config/features.ts` with onboarding flags
   - Support: enabled, allowSkip, requiredForNewUsers

2. Add route-level guards
   - Add `beforeLoad` to onboarding route
   - Check feature flags before allowing access

3. Handle "Skip for now" button behavior
   - Either remove button or set explicit skipped status
   - Update route guard logic accordingly

---

## Phase 5: Testing & Verification

**Goal:** Ensure all fixes work end-to-end

### Tasks:
1. Manual testing of complete flow
   - Register new user
   - Complete all onboarding questions
   - Verify persistence on refresh
   - Verify redirect to dashboard

2. Test edge cases
   - Submit with invalid data
   - Test network failure handling
   - Verify redirect loop prevention

---

## Agent Allocation:
- **Phase 1-2:** Frontend Developer (state, UI fixes)
- **Phase 3:** Frontend Developer (progress tracking)
- **Phase 4:** Architect Reviewer (feature flags)
- **Phase 5:** Fullstack Developer (testing)