# Plan: Fix Circuit Selection and Program Builder Logic

## Problem Summary
1. **Same circuit appears in every finisher** - Due to interference/complementarity logic favoring DIVERSITY when finishers should favor SIMILARITY
2. **Mobility movements appear in main lifts** - No constraints preventing mobility patterns in main lift selection
3. **Main lifts lack compound movement structure** - No enforcement of 2-3 compound movements rule
4. **Warm-ups use hardcoded names** - Not pulling from movement database

---

## Phase 1: Fix Finisher Circuit Selection (CRITICAL)

### File: `app/services/circuit_comparison.py`

**Create new similarity-based scoring for finishers:**
- Add `SIMILARITY_SCORE_WEIGHTS` constant with opposite weights:
  - Pattern similarity: 30% (same patterns = good)
  - Region similarity: 30% (same region = good)
  - Muscle similarity: 30% (same muscles = good)
  - Equipment overlap: 10% (shared equipment = good)

**Create new function `calculate_finisher_similarity_score()`:**
- Calculate Jaccard similarity (not diversity) for patterns, muscles
- Binary match for regions (1.0 if same, 0.0 if different)
- Return score 0-1 where higher = more similar to main lifts

**Modify `recommend_circuits_for_session()`:**
- Add `is_finisher: bool = False` parameter
- If `is_finisher=True`, use similarity scoring instead of complementarity
- Sort circuits by similarity score descending (most similar first)

### File: `app/services/session_generator.py`

**Modify `_generate_circuit_block()`:**
- Add `is_finisher: bool = False` parameter
- Pass `is_finisher=True` when calling circuit recommendation for finishers
- Ensure finisher circuits are selected by similarity, not complementarity

---

## Phase 2: Prevent Mobility in Main Lifts (HIGH PRIORITY)

### File: `app/services/optimization.py`

**Modify `solve_session()` constraint setup:**

**Add pattern exclusion filter before solver:**
```python
# Exclude mobility and cardio patterns from main lift selection
excluded_patterns = {"mobility", "cardio", "stretch"}
filtered_movements = [
    m for m in request.available_movements 
    if m.pattern not in excluded_patterns
]
```

**Or add constraint:**
```python
# Add constraint: No mobility/cardio patterns in main lifts
for m in request.available_movements:
    if m.pattern in {"mobility", "cardio", "stretch"}:
        if m.id in movement_vars:
            model.Add(movement_vars[m.id] == 0)
```

---

## Phase 3: Enforce Compound Movement Structure (HIGH PRIORITY)

### File: `app/services/optimization.py`

**Add compound movement constraints to `solve_session()`:**

**Constraint 1: Minimum compound movements (2-3)**
```python
# Count selected compound movements
compound_vars = [
    movement_vars[m.id] 
    for m in request.available_movements 
    if m.compound and m.pattern not in {"mobility", "cardio", "stretch"}
]
total_compound = sum(compound_vars)

# Require 2-3 compound movements
model.Add(total_compound >= 2)
model.Add(total_compound <= 3)
```

**Constraint 2: Allow compound substitution**
```python
# If using fewer compounds, require more isolation movements
isolation_vars = [
    movement_vars[m.id] 
    for m in request.available_movements 
    if not m.compound and m.pattern not in {"mobility", "cardio", "stretch"}
]
total_isolation = sum(isolation_vars)

# Either: 2-3 compounds OR 1 compound + 2 isolations
has_sufficient_compounds = total_compound >= 2
has_sufficient_isolations = total_compound == 1 and total_isolation >= 2
model.Add(has_sufficient_compounds + has_sufficient_isolations >= 1)
```

---

## Phase 4: Improve Warm-up Integration (MEDIUM PRIORITY)

### File: `app/services/session_generator.py`

**Create new function `_get_mobility_warmup_movements()`:**
```python
async def _get_mobility_warmup_movements(
    self, 
    db: AsyncSession, 
    primary_region: str,
    patterns: List[str]
) -> List[Movement]:
    """Get mobility movements from database for warm-up."""
    # Query movements with pattern="mobility"
    # Filter by primary_region if possible
    # Return 2-3 movements for warm-up
```

**Modify `_get_smart_fallback_session_content()`:**
- Replace hardcoded "Dynamic Stretching" with database lookup
- Call `_get_mobility_warmup_movements()` to get actual mobility movements
- Ensure returned movements exist in database

### File: `app/llm/optimization.py`

**Update `PromptCache.get_pattern_based_warmup()`:**
- Replace hardcoded movement names with pattern-based queries
- Use movement database for CARs and other mobility work

---

## Phase 5: Reinforce Endurance/Cardio Day Logic (LOW PRIORITY)

### File: `app/services/session_generator.py`

**Modify `_get_fast_conditioning_session_content()`:**
- Ensure full-body movements are preferred for cardio-only days
- Add pattern filter: `["carry", "sled_push", "sled_pull", "cardio", "conditioning"]`
- Verify muscle targets include full-body patterns

**Verify existing logic:**
- Check that `_normalize_session_content()` correctly handles conditioning-only days
- Ensure no main lifts + circuits for pure cardio sessions

---

## Testing & Validation

### Unit Tests to Add:
1. Test finisher similarity scoring vs complementarity
2. Test mobility exclusion from main lifts
3. Test compound movement constraint enforcement
4. Test warm-up mobility movement selection

### Integration Tests:
1. Generate program with finishers → verify circuits match main lift muscles
2. Generate program with endurance goal → verify no mobility in main lifts
3. Generate full program → verify warm-ups use database movements
4. Generate strength program → verify 2-3 compound movements per session

---

## Second-Order Effects Analysis

### Positive Effects:
1. **Finishers will be more effective** - Targeting the same muscles as main lifts
2. **Programs will be more coherent** - Mobility stays in warm-up, not main lifts
3. **Main lifts will be more effective** - Proper compound movement structure
4. **Warm-ups will be more varied** - Using actual database movements

### Potential Issues to Monitor:
1. **Fewer circuit options** - Similarity scoring may reduce pool of available finishers
   - *Mitigation*: Lower similarity threshold if pool is too small
2. **Solver complexity** - Additional constraints may increase solve time
   - *Mitigation*: Monitor solve times, add timeout if needed
3. **Warm-up movement availability** - Database may lack enough mobility movements
   - *Mitigation*: Add fallback to hardcoded names if database lookup fails

---

## Implementation Order
1. Phase 1 (Finisher similarity) - CRITICAL, fixes main user complaint
2. Phase 2 (Mobility exclusion) - HIGH, prevents incorrect placement
3. Phase 3 (Compound constraints) - HIGH, enforces proper structure
4. Phase 4 (Warm-up integration) - MEDIUM, improves quality
5. Phase 5 (Cardio reinforcement) - LOW, polish existing logic