# Diversity-Based Movement Scoring System Implementation Plan

## Overview

Replace the current stimulus/fatigue constraint-based session generation with a **diversity-focused, configurable decision tree scoring system** using externalized YAML configuration.

## Phase 1: Configuration Infrastructure (1-2 days)

### 1.1 Create YAML Configuration Schema
**File: `app/config/movement_scoring.yaml`**

```yaml
# 6-Level Scoring Hierarchy
scoring_dimensions:
  - id: "pattern_alignment"
    name: "Pattern Alignment"
    weight: 1.0
    priority_level: 1
    enabled: true
    feature_source: "pattern"
    scoring_rules:
      - condition: "pattern in target_patterns"
        score: 100
      - condition: "pattern in compatible_patterns"
        score: 80

  - id: "muscle_coverage"
    name: "Muscle Coverage"
    weight: 0.9
    priority_level: 2
    enabled: true
    feature_source: "primary_muscle"
    scoring_rules:
      - condition: "primary_muscle in target_muscles"
        score: 100
      - condition: "primary_muscle in synergist_muscles"
        score: 80

  - id: "discipline_preference"
    name: "Discipline Preference"
    weight: 0.8
    priority_level: 3
    enabled: true
    feature_source: "discipline"
    scoring_rules:
      - condition: "discipline_preference > 0.6"
        score: 100

# Goal-specific modifiers
goal_discipline_modifiers:
  explosiveness:
    olympic_weightlifting: 1.5
    plyometric: 1.2
  speed:
    plyometric: 1.5
    olympic_weightlifting: 1.1
  calisthenics:
    calisthenics: 1.5

# Block-specific rep/set ranges
rep_set_ranges:
  warmup:
    sets: [1, 2]
    reps: [10, 15]
    rest_seconds: [60, 90]
  main:
    strength:
      sets: [4, 6]
      reps: [2, 5]
      rest_seconds: [180, 300]
    hypertrophy:
      sets: [3, 4]
      reps: [6, 12]
      rest_seconds: [60, 120]
  accessory:
    sets: [2, 4]
    reps: [8, 15]
    rest_seconds: [60, 90]
```

### 1.2 Create Scoring Engine
**File: `app/ml/scoring/movement_scorer.py`**

- `GlobalMovementScorer` class with config loading/reloading
- `ScoringResult` dataclass with dimension breakdown
- Decision tree evaluation through all dimensions in priority order
- Discipline normalization (sum to 1.0)

### 1.3 Create Metrics Tracker
**File: `app/ml/scoring/scoring_metrics.py`**

- `ScoringMetrics` dataclass
- `ScoringMetricsTracker` for collection/analysis
- Success rate calculation (6 criteria: structural completeness, movement count, pattern diversity, muscle coverage, hard constraints)
- Variance contribution logging per dimension

## Phase 2: Integration with Existing System (2-3 days)

### 2.1 Create New Optimization Service
**File: `app/services/optimization_v2.py`**

- `DiversityOptimizationService` class
- OR-Tools integration with diversity scoring
- 6-step progressive relaxation:
  1. Expand pattern compatibility
  2. Include synergist muscles
  3. Reduce discipline weight
  4. Accept isolation movements
  5. Accept generic movements
  6. Emergency selection

### 2.2 Update Session Generator
**File: `app/services/session_generator.py`**

- Add feature flag: `use_diversity_scoring = False`
- Integrate `DiversityOptimizationService` when flag enabled
- Keep existing `ConstraintSolver` as fallback

### 2.3 Integrate Discipline Preferences
**File: `app/services/optimization_v2.py`**

- Load `disciplines_json` from context
- Normalize to sum=1.0 (user 1-5 → 0.2-1.0 → normalize)
- Apply goal-specific boosts (explosiveness→olympic, speed→plyometric, calisthenics→calisthenics)
- Use normalized weights in scoring

### 2.4 Update Pattern Exposure Tracking
**File: `app/services/program.py`**

- Keep existing `PatternExposure` model
- Add pattern rotation by session type (CARDIO/CONDITIONING/REGULAR)
- Track % unique movements in microcycle

## Phase 3: Testing & Validation (2-3 days)

### 3.1 Unit Tests
**File: `tests/test_diversity_scoring.py`**

- Test YAML config loading
- Test dimension scoring logic
- Test discipline normalization
- Test goal-specific modifiers

### 3.2 Integration Tests
**File: `tests/test_optimization_v2.py`**

- Test complete session generation with new scorer
- Test progressive relaxation
- Test goal conflict scenarios
- Test mixed goals (strength+hypertrophy)

### 3.3 Performance Tests
- Compare speed vs current optimizer
- Verify <100 sessions per minute target

## Phase 4: Migration & Rollout (1-2 days)

### 4.1 Pre-Implementation Backup
```bash
# Database backup
pg_dump -h localhost -p 5433 -U gainsly -d gainslydb > backup_before_diversity_scoring_TIMESTAMP.sql

# Git backup
git checkout main
git pull origin main
git checkout -b backup/pre-diversity-scoring-stable
git add .
git commit -m "Backup: Stable state before diversity scoring implementation"
git push origin backup/pre-diversity-scoring-stable

# Create feature branch
git checkout main
git checkout -b feature/diversity-scoring-system
```

### 4.2 Feature Flag Rollout
- Add `FEATURE_FLAGS = {"use_diversity_scoring": False}` to `app/config/features.py`
- Roll out to 10% of users (admin only initially)
- Monitor success rate metrics for 7 days
- Gradually increase to 100% if metrics healthy

### 4.3 Rollback Procedure
If new system fails:
1. Set `FEATURE_FLAGS["use_diversity_scoring"] = False`
2. Monitor for 24 hours
3. If issues persist: `git checkout backup/pre-diversity-scoring-stable`

## Key Design Decisions

### Goal Conflict Resolution
**Current Issue**: No blocking goal conflicts defined in `INTERFERENCE_RULES`

**Solution**: Add goal-to-goal conflict rules to YAML:
```yaml
goal_conflict_resolution:
  conflicts:
    - pair: ["strength", "endurance"]
      severity: "high"
      resolution: "warn_user"
      recommended_split: "separate_days"
    
    - pair: ["strength", "hypertrophy"]
      severity: "low"
      resolution: "mix_rep_ranges"
      recommended_split: "same_day"
```

### Mixed Goals (Strength + Hypertrophy)
**Approach**: Proportional rep/set allocation across microcycle
- Week 1-2: Focus on strength ranges (4-6 sets, 2-5 reps)
- Week 3-4: Focus on hypertrophy ranges (3-4 sets, 6-12 reps)
- Microcycle-level goal weights determine phase ratios

### Equipment Constraints
**Question**: Where are equipment constraints collected?

**Current Investigation Needed**: 
- `UserProfile.equipment_available` field exists?
- `UserMovementRule` table for equipment exclusions?
- Program wizard for equipment selection?

**Pending Clarification**: Please confirm collection method

### Cloud Hosting
**Recommended**: Render + Netlify + Supabase
- Cost: $0-25/month for <100 users
- Simplest setup (GitHub push → deploy)
- Migrate to AWS S3 later if needed
- Future task, not blocking current implementation

## Success Criteria

### KPIs
1. **Session Quality**:
   - Movement count: Warmup=2-5, Cooldown=2-5, Main=2-10, Accessory=2-4, Finisher=1
   - Time utilization: 95-105% of target duration
   - Pattern diversity: Session-type dependent

2. **Movement Variety**:
   - % unique movements in microcycle: >70%
   - Pattern rotation: No repeats within 2 sessions of SAME TYPE

3. **Success Rate**: 
   - Sessions meeting all 6 criteria / total sessions
   - Target: >85%

### Variance Tracking
- Log contribution % for each dimension
- Example: Pattern alignment contributed 35%, Muscle coverage 28%, Discipline preference 22%
- Available via API for coaches

## Open Questions

1. **Equipment Constraints**: How are they collected? (UserProfile, UserMovementRule, Program wizard?)
2. **Cloud Hosting**: Is Render + Netlify + Supabase acceptable?
3. **Goal Conflicts**: Does conflict resolution approach (block/warn/mix) work for you?
4. **Implementation Priority**: Should I start with Phase 1 or need more design refinements?

## Implementation Order

1. Create `app/config/movement_scoring.yaml` (YAML schema)
2. Create `app/ml/scoring/movement_scorer.py` (scoring engine)
3. Create `app/ml/scoring/scoring_metrics.py` (metrics tracker)
4. Create `app/services/optimization_v2.py` (new optimizer)
5. Update `app/services/session_generator.py` (integration)
6. Add tests and validate
7. Execute backup plan
8. Deploy with feature flags