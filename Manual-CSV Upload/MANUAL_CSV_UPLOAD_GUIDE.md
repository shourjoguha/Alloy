# Manual CSV Upload Guide for Supabase

## Overview

After multiple attempts to automate the data import, we're switching to a manual CSV upload approach via the Supabase Dashboard. This approach provides:

- **Reliability**: No connection timeout issues
- **Control**: Upload tables one at a time with verification
- **Flexibility**: Import tables in correct order to respect foreign keys
- **Visibility**: See immediate feedback and verify data integrity

**Source Data**: Local database (PostgreSQL 16, 50 tables, ~13,000 rows)
**Target**: Supabase project (hazvbikfpoxwlrpsekgd)
**Method**: Supabase Dashboard CSV import (recommended for datasets <100MB)

---

## CSV Files Created

All CSV files are located in this folder: `Manual-CSV Upload/`

### Total Statistics
- **Files**: 29 CSV files
- **Total Rows**: 13,861
- **Format**: Comma-delimited, UTF-8 encoding
- **Special Handling**: JSON columns, NULL values, quoted fields

### File List with Row Counts

| File Name | Rows | Notes |
|-----------|------|--------|
| **Core Tables** |
| activity_definitions.csv | 19 | Small reference table |
| users.csv | 8 | Primary users table |
| programs.csv | 58 | Programs data |
| microcycles.csv | 462 | Microcycles data |
| equipment.csv | 28 | Equipment types |
| muscles.csv | 19 | Muscle groups |
| tags.csv | 30 | Tag system |
| heuristic_configs.csv | 10 | Configuration data |
| **Session & Exercise Data** |
| sessions.csv | 4,620 | **LARGEST TABLE** |
| sessions_legacy_temp.csv | 4,480 | Legacy session data |
| session_exercises.csv | 174 | Exercise data |
| **Movement Data** |
| movements.csv | 439 | Movement definitions |
| movements_legacy.csv | 387 | Legacy movements |
| movement_coaching_cues.csv | 1,082 | Large reference table |
| movement_tags.csv | 466 | Many-to-many relationship |
| movement_equipment.csv | 432 | Many-to-many relationship |
| movement_muscle_map.csv | 612 | Many-to-many relationship |
| movement_disciplines.csv | 235 | Many-to-many relationship |
| movement_relationships.csv | 21 | Movement relationships |
| **User Data** |
| user_profiles.csv | 1 | User profile |
| user_settings.csv | 1 | User settings |
| user_enjoyable_activities.csv | 9 | User preferences |
| user_movement_rules.csv | 6 | User rules |
| muscle_recovery_states.csv | 1 | Recovery tracking |
| soreness_logs.csv | 7 | Soreness data |
| favorites.csv | 2 | User favorites |
| **System Tables** |
| alembic_version.csv | 1 | Migration version |
| circuit_templates.csv | 27 | Circuit templates |

---

## CSV Format Specifications

### Standard Format
- **Delimiter**: Comma (`,`)
- **Encoding**: UTF-8 (no BOM)
- **Headers**: First row contains column names
- **Quoting**: Standard double quotes (`"`) for fields containing commas/newlines
- **Line Ending**: Unix-style (`\n`)

### Special Data Types Handled

**JSON Columns**:
- Tables with JSON data (e.g., `embedding_vector`, `coaching_cues`) are properly formatted as JSON strings
- Arrays use double quotes: `["item1", "item2", "item3"]`
- No double-escaping required

**NULL Values**:
- SQL NULL values converted to empty strings
- Maintains data integrity for optional fields

**Timestamps**:
- ISO 8601 format: `2026-01-25T15:13:14.049759`
- PostgreSQL timestamp precision preserved

**Enums**:
- Database enum values (e.g., `INTERMEDIATE`, `ADVANCED`) preserved as strings
- Semantic meaning maintained

---

## Step-by-Step Import Instructions

### Phase 1: Prepare Supabase Tables

**Important**: Supabase Dashboard CSV import only works for **NEW tables**. Existing tables must be cleared first.

**Clear Tables via SQL Editor:**
1. Navigate to Supabase Dashboard → SQL Editor
2. Run this SQL to clear all tables:
   ```sql
   -- Disable foreign key checks
   SET session_replication_role = 'replica';

   -- Clear all tables
   TRUNCATE TABLE activity_definitions CASCADE;
   TRUNCATE TABLE users CASCADE;
   TRUNCATE TABLE programs CASCADE;
   TRUNCATE TABLE microcycles CASCADE;
   TRUNCATE TABLE equipment CASCADE;
   TRUNCATE TABLE muscles CASCADE;
   TRUNCATE TABLE tags CASCADE;
   TRUNCATE TABLE heuristic_configs CASCADE;
   TRUNCATE TABLE movements CASCADE;
   TRUNCATE TABLE movements_legacy CASCADE;
   TRUNCATE TABLE movement_coaching_cues CASCADE;
   TRUNCATE TABLE movement_tags CASCADE;
   TRUNCATE TABLE movement_equipment CASCADE;
   TRUNCATE TABLE movement_muscle_map CASCADE;
   TRUNCATE TABLE movement_disciplines CASCADE;
   TRUNCATE TABLE movement_relationships CASCADE;
   TRUNCATE TABLE sessions CASCADE;
   TRUNCATE TABLE sessions_legacy_temp CASCADE;
   TRUNCATE TABLE session_exercises CASCADE;
   TRUNCATE TABLE user_profiles CASCADE;
   TRUNCATE TABLE user_settings CASCADE;
   TRUNCATE TABLE user_enjoyable_activities CASCADE;
   TRUNCATE TABLE user_movement_rules CASCADE;
   TRUNCATE TABLE muscle_recovery_states CASCADE;
   TRUNCATE TABLE soreness_logs CASCADE;
   TRUNCATE TABLE favorites CASCADE;
   TRUNCATE TABLE alembic_version CASCADE;
   TRUNCATE TABLE circuit_templates CASCADE;

   -- Re-enable foreign key checks
   SET session_replication_role = 'origin';
   ```

3. Execute the SQL
4. Verify all tables are empty: Run `SELECT COUNT(*) FROM table_name;` for a few tables

### Phase 2: Import Tables in Dependency Order

**Critical**: Import parent tables BEFORE child tables to respect foreign key constraints.

#### Import Order:

**Step 1: Core Reference Tables (No Dependencies)**
1. users.csv
   - Table: `users`
   - Rows: 8
   - Foreign keys: None
   - Upload via: Supabase Dashboard → Table Editor → + New table → Import CSV

2. equipment.csv
   - Table: `equipment`
   - Rows: 28
   - Foreign keys: None
   - Method: + New table → Import CSV

3. muscles.csv
   - Table: `muscles`
   - Rows: 19
   - Foreign keys: None
   - Method: + New table → Import CSV

4. tags.csv
   - Table: `tags`
   - Rows: 30
   - Foreign keys: None
   - Method: + New table → Import CSV

5. heuristic_configs.csv
   - Table: `heuristic_configs`
   - Rows: 10
   - Foreign keys: None
   - Method: + New table → Import CSV

**Step 2: Programs & Activity Data**
6. programs.csv
   - Table: `programs`
   - Rows: 58
   - Foreign key: `user_id` → users (already imported)
   - Method: + New table → Import CSV
   - Verification: Ensure all `user_id` values exist in users table

7. activity_definitions.csv
   - Table: `activity_definitions`
   - Rows: 19
   - Foreign keys: None
   - Method: + New table → Import CSV

8. microcycles.csv
   - Table: `microcycles`
   - Rows: 462
   - Foreign key: `program_id` → programs (already imported)
   - Method: + New table → Import CSV
   - Verification: Ensure all `program_id` values exist in programs table

9. circuit_templates.csv
   - Table: `circuit_templates`
   - Rows: 27
   - Foreign keys: None
   - Method: + New table → Import CSV

**Step 3: Movement Foundation**
10. movements.csv
    - Table: `movements`
    - Rows: 439
    - Foreign keys: None
    - Method: + New table → Import CSV
    - Note: Contains JSON columns (embedding_vector, coaching_cues)

11. movements_legacy.csv
    - Table: `movements_legacy`
    - Rows: 387
    - Foreign keys: None
    - Method: + New table → Import CSV

12. movement_coaching_cues.csv
    - Table: `movement_coaching_cues`
    - Rows: 1,082
    - Foreign keys: `movement_id` → movements (already imported)
    - Method: + New table → Import CSV
    - Verification: Ensure all `movement_id` values exist in movements table

**Step 4: Movement Relationships (Many-to-Many)**
13. movement_disciplines.csv
    - Table: `movement_disciplines`
    - Rows: 235
    - Foreign keys: `movement_id` → movements (already imported)
    - Composite PK: (movement_id, discipline)
    - Method: + New table → Import CSV
    - Verification: All pairs should be unique

14. movement_equipment.csv
    - Table: `movement_equipment`
    - Rows: 432
    - Foreign keys: `movement_id` → movements, `equipment_id` → equipment (both imported)
    - Composite PK: (movement_id, equipment_id)
    - Method: + New table → Import CSV

15. movement_tags.csv
    - Table: `movement_tags`
    - Rows: 466
    - Foreign keys: `movement_id` → movements, `tag_id` → tags (both imported)
    - Composite PK: (movement_id, tag_id)
    - Method: + New table → Import CSV

16. movement_muscle_map.csv
    - Table: `movement_muscle_map`
    - Rows: 612
    - Foreign keys: `movement_id` → movements, `muscle_id` → muscles (both imported)
    - Composite PK: (movement_id, muscle_id)
    - Method: + New table → Import CSV

17. movement_relationships.csv
    - Table: `movement_relationships`
    - Rows: 21
    - Foreign keys: `movement_id`, `related_movement_id` → movements (both imported)
    - Method: + New table → Import CSV
    - Verification: Ensure all movement IDs exist

**Step 5: Session Data**
18. sessions.csv
    - Table: `sessions`
    - Rows: 4,620 (LARGEST TABLE)
    - Foreign keys: `user_id` → users, `program_id` → programs, `microcycle_id` → microcycles (all imported)
    - Method: + New table → Import CSV
    - Verification: Ensure all foreign key IDs exist
    - Note: May take longer due to size

19. sessions_legacy_temp.csv
    - Table: `sessions_legacy_temp`
    - Rows: 4,480
    - Foreign keys: `user_id` → users, `program_id` → programs (both imported)
    - Method: + New table → Import CSV
    - Verification: Ensure all foreign key IDs exist

20. session_exercises.csv
    - Table: `session_exercises`
    - Rows: 174
    - Foreign keys: `session_id` → sessions (already imported)
    - Method: + New table → Import CSV
    - Verification: Ensure all `session_id` values exist in sessions table

**Step 6: User Data**
21. user_profiles.csv
    - Table: `user_profiles`
    - Rows: 1
    - Foreign key: `user_id` → users (already imported)
    - Method: + New table → Import CSV

22. user_settings.csv
    - Table: `user_settings`
    - Rows: 1
    - Foreign key: `user_id` → users (already imported)
    - Method: + New table → Import CSV

23. user_enjoyable_activities.csv
    - Table: `user_enjoyable_activities`
    - Rows: 9
    - Foreign key: `user_id` → users (already imported)
    - Method: + New table → Import CSV

24. user_movement_rules.csv
    - Table: `user_movement_rules`
    - Rows: 6
    - Foreign key: `user_id` → users (already imported)
    - Method: + New table → Import CSV

25. muscle_recovery_states.csv
    - Table: `muscle_recovery_states`
    - Rows: 1
    - Foreign key: `user_id` → users (already imported)
    - Method: + New table → Import CSV

26. soreness_logs.csv
    - Table: `soreness_logs`
    - Rows: 7
    - Foreign key: `user_id` → users (already imported)
    - Method: + New table → Import CSV

27. favorites.csv
    - Table: `favorites`
    - Rows: 2
    - Foreign key: `user_id` → users, `movement_id` → movements (both imported)
    - Method: + New table → Import CSV

**Step 7: System Tables**
28. alembic_version.csv
    - Table: `alembic_version`
    - Rows: 1
    - Foreign keys: None
    - Method: + New table → Import CSV

---

## Upload Instructions (Per Table)

For each table:

1. **Open Supabase Dashboard**: https://supabase.com/dashboard
2. **Select your project**: hazvbikfpoxwlrpsekgd
3. **Navigate to Table Editor**: Left sidebar → Table Editor
4. **Click "+ New table"**
5. **Enter table name**: Use exact name from the list above (e.g., `users`)
6. **Click "Import data from CSV"**
7. **Upload the CSV file**: Select the corresponding CSV file from `Manual-CSV Upload/` folder
8. **Preview the import**: Verify column headers are detected correctly
9. **Click "Save"** to create the table with data
10. **Configure primary key**:
    - Select the `id` column as primary key
    - Ensure "Auto-generate ID" is OFF (we're providing IDs)
11. **Click "Save" again** to finalize the table

**Repeat for all 29 tables** in the order specified above.

---

## Troubleshooting Common Issues

### Issue 1: Import fails with "Invalid CSV format"
**Cause**: Curly quotation marks instead of straight quotes
**Solution**: CSV files already use straight quotes. If issue persists, open CSV in text editor and replace curly quotes with straight quotes.

### Issue 2: Foreign key constraint violation
**Cause**: Child table imported before parent table
**Solution**: Follow the import order specified in Phase 2. Import parent tables first.

### Issue 3: Special characters display incorrectly
**Cause**: File encoding issue
**Solution**: CSV files use UTF-8 encoding. Ensure your text editor/editor doesn't convert them.

### Issue 4: JSON columns fail to import
**Cause**: JSON format issues
**Solution**: CSV files have properly formatted JSON arrays. Example: `["item1", "item2"]` with double quotes.

### Issue 5: Timeout on large files
**Cause**: File size or connection issue
**Solution**: 
- For `sessions.csv` (4,620 rows), consider uploading during off-peak hours
- If timeout persists, split the file into smaller chunks (e.g., 1,000 rows per file)

### Issue 6: Duplicate key error
**Cause**: CSV file has duplicate primary key values
**Solution**: This should not happen - the conversion process ensured no duplicates. If it does, verify the CSV file content.

---

## Verification Steps

After importing all 29 tables:

### Step 1: Verify Row Counts

Run these queries in Supabase SQL Editor:
```sql
-- Core tables
SELECT 'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'equipment' as table_name, COUNT(*) as row_count FROM equipment
UNION ALL
SELECT 'muscles' as table_name, COUNT(*) as row_count FROM muscles
UNION ALL
SELECT 'tags' as table_name, COUNT(*) as row_count FROM tags
UNION ALL
SELECT 'programs' as table_name, COUNT(*) as row_count FROM programs
UNION ALL
SELECT 'microcycles' as table_name, COUNT(*) as row_count FROM microcycles
UNION ALL
SELECT 'movements' as table_name, COUNT(*) as row_count FROM movements
UNION ALL
SELECT 'sessions' as table_name, COUNT(*) as row_count FROM sessions
UNION ALL
SELECT 'session_exercises' as table_name, COUNT(*) as row_count FROM session_exercises;
```

**Expected Results**: Compare counts with the CSV file list above. All should match.

### Step 2: Verify Foreign Key Integrity

```sql
-- Check for orphaned records
SELECT 'sessions_orphaned_users' as issue, COUNT(*) as count 
FROM sessions s LEFT JOIN users u ON s.user_id = u.id WHERE u.id IS NULL
UNION ALL
SELECT 'sessions_orphaned_programs' as issue, COUNT(*) as count 
FROM sessions s LEFT JOIN programs p ON s.program_id = p.id WHERE p.id IS NULL
UNION ALL
SELECT 'microcycles_orphaned_programs' as issue, COUNT(*) as count 
FROM microcycles m LEFT JOIN programs p ON m.program_id = p.id WHERE p.id IS NULL;
```

**Expected Results**: All counts should be 0 (no orphaned records).

### Step 3: Verify Data Integrity

```sql
-- Check for NULL values in required fields
SELECT 'users_missing_email' as issue, COUNT(*) as count 
FROM users WHERE email IS NULL OR email = ''
UNION ALL
SELECT 'movements_missing_name' as issue, COUNT(*) as count 
FROM movements WHERE name IS NULL OR name = '';
```

**Expected Results**: All counts should be 0 (no missing required data).

---

## Important Notes

### Supabase Dashboard Limitations

1. **CSV import only for NEW tables**: You cannot import into existing tables
   - **Workaround**: Clear tables via SQL Editor first, then create new tables via CSV import
   - This is why Phase 1 (Clear Tables) is critical

2. **100MB file size limit**: Dashboard CSV import has a 100MB limit
   - **Your files**: Largest is `sessions.csv` (~500KB) - well within limit
   - **All 29 files**: Total size ~10MB - well within limit

3. **Foreign key enforcement**: Foreign keys are validated during import
   - **Solution**: Import tables in the correct dependency order specified in Phase 2

### Time Estimate

- **Phase 1 (Clear Tables)**: 2-3 minutes (SQL Editor)
- **Phase 2 (Import 29 tables)**: 15-20 minutes (manual upload per table)
- **Phase 3 (Verification)**: 5-10 minutes (SQL queries)

**Total Estimated Time**: 25-35 minutes

---

## Next Steps After Migration

Once all tables are imported and verified:

1. **Update application configuration**: 
   - Verify `.env` points to Supabase connection
   - Test application connectivity

2. **Run application tests**:
   - Verify data retrieval works
   - Test CRUD operations
   - Check foreign key relationships

3. **Monitor performance**:
   - Observe query response times
   - Check connection pool usage
   - Monitor for any timeout issues

4. **Backup Supabase database**:
   - Export a fresh dump after successful import
   - Store securely for disaster recovery

---

## Files Created During Conversion Process

- **conversion_log.txt**: Complete record of CSV files created
- **README_CONVERSION.md**: Technical details about the conversion process
- **MANUAL_CSV_UPLOAD_GUIDE.md**: This file (comprehensive upload instructions)

**Total**: 3 documentation files + 29 CSV data files = 32 files created

---

## Summary

This manual CSV upload approach provides:
- ✅ Reliability: No connection timeout issues
- ✅ Control: Import tables one at a time with verification
- ✅ Flexibility: Upload in correct order to respect foreign keys
- ✅ Visibility: See immediate feedback and verify data integrity
- ✅ Documentation: Complete guides for troubleshooting and verification

**All 29 CSV files are ready for upload in the specified order.**
