# Supabase CSV Import Guide - Reference Data Only

## Overview

Import only reference data (movements, activities, circuits) to Supabase using your existing CSV files.

**Total CSV Files**: 12 reference data files
**Total Records**: ~3,700 reference records

---

## Tables to Import (Reference Data Only)

### ✅ Step 1: Core Reference Tables (No Dependencies)

| Order | CSV File | Table | Rows | Notes |
|-------|-----------|--------|------|--------|
| 1 | `muscles.csv` | `muscles` | 19 | Muscle catalog |
| 2 | `equipment.csv` | `equipment` | 28 | Equipment types |
| 3 | `tags.csv` | `tags` | 30 | Movement tags |
| 4 | `alembic_version.csv` | `alembic_version` | 1 | Migration tracking |

### ✅ Step 2: Movement Foundation

| Order | CSV File | Table | Rows | Depends On |
|-------|-----------|--------|------|----------|
| 5 | `movements.csv` | `movements` | 439 | None |
| 6 | `movements_legacy.csv` | `movements_legacy` | 387 | None |

### ✅ Step 3: Movement Metadata

| Order | CSV File | Table | Rows | Depends On |
|-------|-----------|--------|------|----------|
| 7 | `movement_coaching_cues.csv` | `movement_coaching_cues` | 1,082 | movements (step 5) |
| 8 | `movement_disciplines.csv` | `movement_disciplines` | 235 | movements (step 5) |
| 9 | `movement_equipment.csv` | `movement_equipment` | 432 | movements (step 5), equipment (step 2) |
| 10 | `movement_muscle_map.csv` | `movement_muscle_map` | 612 | movements (step 5), muscles (step 1) |
| 11 | `movement_tags.csv` | `movement_tags` | 466 | movements (step 5), tags (step 3) |
| 12 | `movement_relationships.csv` | `movement_relationships` | 21 | movements (step 5) |

### ✅ Step 4: Activity System

| Order | CSV File | Table | Rows | Depends On |
|-------|-----------|--------|------|----------|
| 13 | `activity_definitions.csv` | `activity_definitions` | 19 | None |
| 14 | `circuit_templates.csv` | `circuit_templates` | 27 | None |

---

## Tables to SKIP (User Data - Leave Empty)

Do NOT import these CSV files (user data should start fresh):

❌ **User Tables**:
- `users.csv` - User accounts (8 rows)
- `user_profiles.csv` - User profiles (1 row)
- `user_settings.csv` - User settings (1 row)
- `user_enjoyable_activities.csv` - User preferences (9 rows)
- `user_movement_rules.csv` - User rules (6 rows)
- `favorites.csv` - User favorites (2 rows)

❌ **User Fitness Data**:
- `soreness_logs.csv` - Soreness data (7 rows)
- `muscle_recovery_states.csv` - Recovery states (1 row)

❌ **User Program Data**:
- `programs.csv` - Programs (58 rows)
- `microcycles.csv` - Microcycles (462 rows)
- `sessions.csv` - Sessions (4,620 rows)
- `sessions_legacy_temp.csv` - Legacy sessions (4,480 rows)
- `session_exercises.csv` - Session exercises (174 rows)

❌ **System Data**:
- `heuristic_configs.csv` - Heuristic configs (10 rows) - **DELETE THIS TABLE** (configs moved to code)
- `program_disciplines.csv` - Program-discipline mapping (222 rows)

---

## Import Instructions

### Phase 1: Prepare Supabase

1. **Navigate to Supabase Dashboard**
   - URL: https://supabase.com/dashboard
   - Select your project: hazvbikfpoxwlrpsekgd

2. **Go to SQL Editor**
   - Left sidebar → SQL Editor

3. **Clear Tables** (First time only)
   ```sql
   -- Disable foreign key checks for truncation
   SET session_replication_role = 'replica';
   
   -- Clear reference data tables only
   TRUNCATE TABLE muscles CASCADE;
   TRUNCATE TABLE equipment CASCADE;
   TRUNCATE TABLE tags CASCADE;
   TRUNCATE TABLE movements CASCADE;
   TRUNCATE TABLE movements_legacy CASCADE;
   TRUNCATE TABLE movement_coaching_cues CASCADE;
   TRUNCATE TABLE movement_disciplines CASCADE;
   TRUNCATE TABLE movement_equipment CASCADE;
   TRUNCATE TABLE movement_muscle_map CASCADE;
   TRUNCATE TABLE movement_tags CASCADE;
   TRUNCATE TABLE movement_relationships CASCADE;
   TRUNCATE TABLE activity_definitions CASCADE;
   TRUNCATE TABLE circuit_templates CASCADE;
   TRUNCATE TABLE alembic_version CASCADE;
   
   -- Drop heuristic_configs table (no longer needed)
   DROP TABLE IF EXISTS heuristic_configs;
   
   -- Re-enable foreign key checks
   SET session_replication_role = 'origin';
   ```

4. **Verify Tables are Empty**
   ```sql
   SELECT 'muscles' as table_name, COUNT(*) as row_count FROM muscles
   UNION ALL
   SELECT 'equipment' as table_name, COUNT(*) as row_count FROM equipment
   UNION ALL
   SELECT 'movements' as table_name, COUNT(*) as row_count FROM movements
   UNION ALL
   SELECT 'activity_definitions' as table_name, COUNT(*) as row_count FROM activity_definitions;
   ```
   Expected: All should return `0` rows

---

### Phase 2: Import CSV Files (Follow Order)

#### Import Steps (Repeat for each file):

1. **Create New Table**
   - In SQL Editor: Click "+ New table"
   - Enter exact table name (e.g., `muscles`)
   - Click "Save"

2. **Import CSV Data**
   - Click "Import data from CSV"
   - Select CSV file from `Manual-CSV Upload/` folder
   - Upload the file
   - Review column mapping (should auto-detect correctly)
   - Click "Save"

3. **Configure Primary Key**
   - After import, select the `id` column
   - Set as primary key
   - Disable "Auto-generate ID"
   - Click "Save"

4. **Verify Import**
   - Run: `SELECT COUNT(*) FROM table_name;`
   - Verify count matches CSV row count

---

## Quick Import Reference

| Step | File | Rows | Table | Status |
|-------|-------|------|--------|--------|
| 1 | muscles.csv | 19 | muscles | ⬜ |
| 2 | equipment.csv | 28 | equipment | ⬜ |
| 3 | tags.csv | 30 | tags | ⬜ |
| 4 | alembic_version.csv | 1 | alembic_version | ⬜ |
| 5 | movements.csv | 439 | movements | ⬜ |
| 6 | movements_legacy.csv | 387 | movements_legacy | ⬜ |
| 7 | movement_coaching_cues.csv | 1,082 | movement_coaching_cues | ⬜ |
| 8 | movement_disciplines.csv | 235 | movement_disciplines | ⬜ |
| 9 | movement_equipment.csv | 432 | movement_equipment | ⬜ |
| 10 | movement_muscle_map.csv | 612 | movement_muscle_map | ⬜ |
| 11 | movement_tags.csv | 466 | movement_tags | ⬜ |
| 12 | movement_relationships.csv | 21 | movement_relationships | ⬜ |
| 13 | activity_definitions.csv | 19 | activity_definitions | ⬜ |
| 14 | circuit_templates.csv | 27 | circuit_templates | ⬜ |

---

## Total Import Time Estimate

- **Small files** (< 100 rows): ~1 minute each
- **Large files** (1,000+ rows): ~3-5 minutes each
- **Total estimated time**: 30-40 minutes for all 14 files

---

## Troubleshooting

### Issue 1: Foreign Key Violation

**Error**: `Foreign key violation: table "movement_muscle_map" violates foreign key constraint`

**Cause**: Child table imported before parent table

**Solution**: Follow the import order specified above. Import parent tables (muscles, movements) before child tables (movement_muscle_map, movement_tags).

### Issue 2: Invalid CSV Format

**Error**: `Invalid CSV format: file "muscles.csv" has invalid characters`

**Cause**: File encoding or line ending issues

**Solution**: CSV files are UTF-8 encoded with Unix line endings. Ensure your text editor doesn't modify them.

### Issue 3: Duplicate Primary Key

**Error**: `Duplicate key value violates unique constraint "movements_pkey"`

**Cause**: Attempting to import same file twice

**Solution**: 
1. Verify table was properly truncated before import
2. Check if file has duplicate `id` values (should not)

---

## Verification After Import

### Row Count Verification

```sql
SELECT 
    'muscles' as table_name, 
    (SELECT COUNT(*) FROM muscles) as count
UNION ALL
SELECT 
    'equipment' as table_name, 
    (SELECT COUNT(*) FROM equipment) as count
UNION ALL
SELECT 
    'movements' as table_name, 
    (SELECT COUNT(*) FROM movements) as count
UNION ALL
SELECT 
    'movement_coaching_cues' as table_name, 
    (SELECT COUNT(*) FROM movement_coaching_cues) as count
UNION ALL
SELECT 
    'movement_disciplines' as table_name, 
    (SELECT COUNT(*) FROM movement_disciplines) as count
UNION ALL
SELECT 
    'activity_definitions' as table_name, 
    (SELECT COUNT(*) FROM activity_definitions) as count;
```

### Foreign Key Integrity Check

```sql
-- Check for orphaned movement_cues
SELECT COUNT(*) 
FROM movement_coaching_cues mc 
LEFT JOIN movements m ON mc.movement_id = m.id 
WHERE m.id IS NULL;

-- Check for orphaned movement_tags
SELECT COUNT(*) 
FROM movement_tags mt 
LEFT JOIN movements m ON mt.movement_id = m.id 
WHERE m.id IS NULL;

-- Both should return 0
```

### User Data Tables (Should Be Empty)

```sql
SELECT 
    'users' as table_name, 
    (SELECT COUNT(*) FROM users) as count
UNION ALL
SELECT 
    'programs' as table_name, 
    (SELECT COUNT(*) FROM programs) as count
UNION ALL
SELECT 
    'sessions' as table_name, 
    (SELECT COUNT(*) FROM sessions) as count
UNION ALL
SELECT 
    'user_profiles' as table_name, 
    (SELECT COUNT(*) FROM user_profiles) as count;
```

Expected: All should return `0` rows (fresh start)

---

## After Successful Import

### 1. Update .env for Supabase

```bash
# Update DATABASE_URL to point to Supabase
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.hazvbikfpoxwlrpsekgd.supabase.co:5432/postgres
```

### 2. Test Application

```bash
# Run migrations (should be at head already)
alembic upgrade head

# Start dev environment
bash start-dev.sh
```

### 3. Verify Reference Data Loads

- Navigate to http://localhost:5173
- Open browser DevTools (F12)
- Check API calls to `/settings/movements`
- Verify movements load with equipment, tags, disciplines

### 4. Verify User Tables Are Empty

- Try to register a new user
- Verify no existing users show up
- Verify no programs exist
- Verify no workout history exists

---

## Important Notes

1. **Heuristic Configs**: `heuristic_configs.csv` should NOT be imported - these are now in `app/config/heuristics.py` (see Phase 1)
2. **Foreign Keys**: All child tables reference parent tables - import order is critical
3. **JSON Columns**: CSV files properly format JSON arrays (e.g., `["item1", "item2"]`)
4. **User Data**: User tables start empty - users will create their own accounts and data

---

## Expected Final State

After successful import:

✅ **Reference Data Populated**:
- ~50 muscles for anatomy mapping
- ~28 equipment types
- ~30 movement tags
- ~826 movements (439 + 387)
- ~1,082 coaching cues
- ~235 movement-discipline mappings
- ~432 movement-equipment mappings
- ~612 movement-muscle mappings
- ~466 movement-tag mappings
- ~21 movement relationships
- ~19 activity definitions
- ~27 circuit templates

❌ **User Data Empty**:
- 0 users
- 0 programs
- 0 sessions
- 0 workout logs
- 0 favorites

---

## Related Files

- [`MANUAL_CSV_UPLOAD_GUIDE.md`](../Manual-CSV%20Upload/MANUAL_CSV_UPLOAD_GUIDE.md) - Full upload instructions
- [`README_CONVERSION.md`](../Manual-CSV%20Upload/README_CONVERSION.md) - Technical conversion details
- [`conversion_log.txt`](../Manual-CSV%20Upload/conversion_log.txt) - Conversion process log

---

## Next Steps

After completing CSV import:

1. ✅ Reference data populated on Supabase
2. ✅ Application connects to Supabase
3. ✅ Frontend loads movements, activities, circuits
4. ✅ Users can sign up and create accounts (fresh start)
5. ✅ Users can create programs, track workouts, set goals

---

**Total Import Time**: 30-40 minutes
**Files to Import**: 12 CSV files
**Records to Import**: ~3,700 reference records
