# Movement Table Deduplication Plan (Final)

## Overview
Deduplicate movements table by identifying duplicate groups, normalizing names, and creating variation relationships instead of merging equipment variants.

---

## Phase 1: Dependency Mapping & Analysis

### 1.1 Create Analysis Script
**File**: `scripts/analyze_movement_dependencies.py`
- Query all movement-related tables
- Count movements in each relationship
- Identify active vs unused movements
- Output comprehensive statistics

**Tables to Analyze**:
- `movements` (main table)
- `movement_equipment` (junction)
- `movement_muscle_map` (junction)
- `movement_disciplines` (junction)
- `movement_tags` (junction)
- `movement_coaching_cues` (junction)
- `movement_relationships` (relationships)
- `session_exercises` (usage)
- `circuits_melted` (usage)
- `user_movement_rules` (preferences)
- `favorites` (favorites)
- `top_set_logs` (performance tracking)

---

## Phase 2: Duplicate Detection

### 2.1 Identify Duplicate Groups
**File**: `scripts/detect_movement_duplicates.py`

**Duplicate Criteria (ALL must match to be duplicate)**:
- Same `pattern`
- Same `primary_muscle`
- Same `primary_region`
- Same `equipment` (all equipment in movement_equipment junction must match)

**Plyometric Pattern Detection**:
- If movement name contains "jumping" or "Jumping" → update `pattern` to "plyometric"
- This prevents false positives like "lunge" vs "jumping lunges"

**Duplicate Categories to Detect**:

**A. Exact Name Duplicates (Case-Insensitive)**
- "Air Squats" vs "air squats"
- "Pull-Ups" vs "pull ups"
- "Sit-Up" vs "sit ups"
- "Toes to bar" vs "toes to bars"

**B. Equipment Variants (Same Pattern + Different Equipment)**
- Squat group: Back Squat, Front Squat, Goblet Squat
- Deadlift group: Conventional Deadlift, Romanian Deadlift, Single Leg RDL
- Press group: Dumbbell Chest Press, Incline Bench Press, Dumbbell Bench Press
- **Note**: These will NOT be merged (see Phase 3C)

**C. Fuzzy Similarity (Levenshtein Distance)**
- Typo variants: "Alternating" vs "Alternating", "lunge" vs "jumping lunges"
- Phonetic similarity using Soundex/Double Metaphone
- Similarity threshold: > 0.85

**D. Wildcard/Partial Matches**
- "Row*" → "200/Row", "Rowing Machine"
- Using existing pattern from phase2_merge_duplicate_movements.py

### 2.2 Output Format
```python
{
    "duplicate_groups": [
        {
            "canonical_id": 123,
            "canonical_name": "Dumbbell Bench Press",
            "duplicates": [
                {"id": 456, "name": "Dumbbell Bench Presses"},
                {"id": 789, "name": "Dumbbell Chest Press"}
            ],
            "similarity_score": 0.95,
            "duplicate_type": "equipment_variant",
            "match_criteria": {
                "pattern": "horizontal_push",
                "primary_muscle": "chest",
                "primary_region": "anterior_upper",
                "equipment": ["dumbbell", "bench"]
            }
        }
    ],
    "plyometric_updates": [
        {"id": 456, "name": "jumping lunges", "old_pattern": "lunge", "new_pattern": "plyometric"}
    ]
}
```

---

## Phase 3: Name Normalization & Relationship Management

### 3.1 Create Normalization Script
**File**: `scripts/normalize_movement_names.py`

**Normalization Strategies**:

**A. Case Normalization**
- Apply title case: "air squats" → "Air Squats"
- Preserve proper nouns: "Romanian Deadlift" (not "Romanian")

**B. Spacing & Punctuation**
- Remove extra spaces: "toes  to  bar" → "Toes to Bar"
- Standardize hyphens: "Single Leg" vs "Single-Leg"
- Standardize apostrophes: "womens" vs "women's"

**C. Equipment Suffix Handling (NEW APPROACH)**
- Do NOT merge equipment variants as same movement
- Instead, create `movement_relationships` entries:
  - `relationship_type`: "variation"
  - `source_movement_id`: canonical movement
  - `target_movement_id`: equipment variant
  - Example: "Dumbbell Bench Press" ↔ "Barbell Bench Press"
- **No bilateral exception** - all equipment variants now linked via relationships

**D. Plural/Singular Normalization**
- Standardize to singular form: "Pull-Ups" → "Pull-Up"

**E. Typo Correction**
- Apply common typo mappings:
  - "toes to bars" → "toes to bar"
  - "Alternating" vs "Alternating"
  - "Dumbbell Bench Presses" → "Dumbbell Bench Press"

### 3.2 Plyometric Pattern Update
- Detect movements with "jumping"/"Jumping" in name
- Update `pattern` to "plyometric"
- Log all updates for review

### 3.3 Validation Rules
- Check against existing unique constraint
- Verify movement pattern is valid enum
- Verify primary_muscle is valid enum
- Verify primary_region is valid enum
- Skip normalization if conflicts found

---

## Phase 4: Safe Merge Process

### 4.1 Create Merge Script
**File**: `scripts/merge_duplicate_movements.py`

**Canonical Movement Selection Criteria**:
1. **Best Data Quality** (most non-NULL fields populated)
2. **Most Equipment** (more equipment associations)
3. **Most Muscles** (more muscle associations)
4. **Tiebreaker**: None specified (using data quality only)

**A. Drop Constraints Before Merge**
```python
# Temporarily drop unique constraint
await session.execute(
    text("ALTER TABLE movements DROP CONSTRAINT movements_name_key")
)

# After migration:
await session.execute(
    text("ALTER TABLE movements ADD CONSTRAINT movements_name_key UNIQUE (name)")
```

**B. Migrate Relationships**
For each duplicate movement, migrate to canonical:
1. `movement_equipment` → Add equipment to canonical (merge)
2. `movement_muscle_map` → Add muscles to canonical (merge roles)
3. `movement_disciplines` → Add disciplines to canonical (merge)
4. `movement_tags` → Add tags to canonical (merge)
5. `movement_coaching_cues` → Append cues to canonical
6. `movement_relationships` → Update relationships (source/target)
7. `session_exercises` → Update movement_id to canonical
8. `circuits_melted` → Update movement_id to canonical
9. `user_movement_rules` → Update movement_id to canonical
10. `favorites` → Update movement_id to canonical
11. `top_set_logs` → Update movement_id to canonical

**C. Handle Conflicts**
- If both canonical and duplicate have same equipment → skip (already handled via relationships)
- If both have same muscle role → skip (avoid duplicates)
- Preserve most complete metadata (non-NULL fields)

**D. Delete Duplicate Movements**
- Only after all relationships migrated
- Use transaction with rollback on error
- Log all deletions

### 4.2 Rollback Capability
- Create backup table: `movements_backup`
- Store deleted movement IDs in `deleted_movements` table
- Enable undo via `scripts/undo_movement_merge.py`

---

## Phase 5: Validation & Cleanup

### 5.1 Validation Script
**File**: `scripts/validate_movement_merge.py`

**Checks**:
- No orphaned records in junction tables
- All foreign key constraints satisfied
- No movement_id = NULL in dependent tables
- Movement counts match expected after merge
- Usage statistics preserved

### 5.2 Data Quality Report
- Movements merged (count)
- Relationships migrated (count by table)
- Variation relationships created (count)
- Plyometric patterns updated (count)
- Duplicate names resolved (list)
- Remaining duplicates (if any)
- Orphaned records (should be 0)

---

## Execution Order

```bash
# Step 1: Analyze dependencies
python scripts/analyze_movement_dependencies.py

# Step 2: Detect duplicates
python scripts/detect_movement_duplicates.py

# Step 3: Normalize names and create variation relationships (dry-run first)
python scripts/normalize_movement_names.py --dry-run --verbose

# Step 4: Normalize names and create variation relationships (apply)
python scripts/normalize_movement_names.py --apply

# Step 5: Merge duplicates (dry-run first)
python scripts/merge_duplicate_movements.py --dry-run --verbose

# Step 6: Merge duplicates (apply)
python scripts/merge_duplicate_movements.py --apply

# Step 7: Validate merge
python scripts/validate_movement_merge.py
```

---

## Agent Collaboration Strategy

**Phase 1 (Analysis)**:
- `postgres-pro` agent: Run SQL queries for dependency statistics
- `data-engineer` agent: Analyze data flow and pipeline requirements
- `search` agent: Document existing deduplication scripts

**Phase 2 (Detection)**:
- `search` agent: Analyze duplicate detection patterns
- `python-pro` agent: Create detection script with fuzzy matching

**Phase 3 (Normalization)**:
- `python-pro` agent: Create normalization script
- `data-engineer` agent: Design relationship migration strategy

**Phase 4 (Merge)**:
- `database-admin` agent: Handle constraint dropping/adding
- `backend-developer` agent: Create merge service functions
- `error-coordinator` agent: Design transaction rollback logic
- `debugger` agent: Add comprehensive logging

**Phase 5 (Validation)**:
- `postgres-pro` agent: Run validation queries
- `database-optimiser` agent: Verify constraint recreation

---

## Safety Features

1. **Dry-Run Mode**: All scripts support `--dry-run` flag
2. **Transaction Safety**: Database operations in transactions with rollback
3. **Backup Creation**: Automatic backup before any deletion
4. **Detailed Logging**: Every operation logged for audit
5. **Undo Capability**: Can restore from backup if needed
6. **Constraint Management**: Drop/re-add constraints during merge
7. **Conflict Handling**: Skips ambiguous cases for manual review

---

## Expected Outcomes

- **Reduced Movement Count**: 20-30% reduction expected (excluding equipment variants)
- **Cleaner Names**: Consistent naming conventions
- **Variation Relationships**: Equipment variants linked instead of merged
- **Plyometric Pattern Corrections**: All jumping movements properly classified
- **Preserved Relationships**: All sessions/circuits still work
- **Better Search**: Reduced confusion in movement selection