# Phase 2: Supabase Setup with Reference Data Only

## Overview

Set up Supabase with all reference data needed for the app to function, but with **zero user data**. This allows a fresh start on production.

---

## Tables to Populate (Reference Data Only)

### ✅ 1. Movement System (Core Reference Data)

| Table | Purpose | Records | Source |
|--------|---------|----------|---------|
| `muscle` | All muscle names for anatomy mapping | ~50 | `seed_data/movements.json` |
| `equipment` | Equipment types (barbell, dumbbell, etc.) | ~20 | `seed_data/movements.json` |
| `movement_discipline` | Discipline categories (powerlifting, hypertrophy) | ~12 | `seed_data/movements.json` + activities |
| `tag` | Movement tags (compound, isolation, etc.) | ~20 | Common list |
| `movement_coaching_cue` | Coaching tips for movements | ~200 | `seed_data/movements.json` |
| `movement` | All exercise movements with properties | ~500 | `seed_data/movements.json`, `clean_crossfit_movements.json`, `net_new_movements.json` |
| `movement_relationship` | Movement substitutions | ~50 | `seed_data/movements.json` |
| `movement_muscle_map` | Muscle ↔ Movement mappings | ~1000 | `seed_data/movements.json` |
| `movement_equipment` | Equipment ↔ Movement mappings | ~600 | `seed_data/movements.json` |
| `movement_tag` | Tags ↔ Movement mappings | ~1500 | `seed_data/movements.json` |

### ✅ 2. Activity System (External Activities)

| Table | Purpose | Records | Source |
|--------|---------|----------|---------|
| `discipline` | Activity disciplines (running, cycling, etc.) | ~15 | `seed_data/activities.json` |
| `activity_definition` | Activity definitions with metadata | ~15 | `seed_data/activities.json` |
| `activity_muscle_map` | Muscle impact for activities | ~100 | `seed_data/activities.json` |

### ✅ 3. Circuit Templates

| Table | Purpose | Records | Source |
|--------|---------|----------|---------|
| `circuit_template` | Pre-built workout circuits | ~20 | `seed_data/scraped_circuits.json` |

---

## Tables to Leave EMPTY (User Data Only)

### ❌ User Accounts & Settings
- `user` - User accounts
- `user_profile` - User profiles
- `user_settings` - User preferences

### ❌ User Preferences
- `user_movement_rule` - Movement rules
- `user_enjoyable_activity` - Enjoyable activities

### ❌ User Fitness Data
- `user_biometric_history` - Biometrics history
- `user_skill` - User skill levels
- `user_injury` - Injury history

### ❌ User Workout Programs
- `program` - User programs
- `microcycle` - Program microcycles
- `session` - Workout sessions
- `session_exercise` - Session exercises
- `workout_log` - Workout logs
- `top_set_log` - Top set logs
- `soreness_log` - Soreness tracking
- `recovery_signal` - Recovery signals
- `muscle_recovery_state` - Muscle recovery states

### ❌ User Goals & Progress
- `user_goal` - User goals
- `goal_checkin` - Goal check-ins
- `favorite` - User favorites

### ❌ User Activity Tracking
- `user_fatigue_state` - Fatigue states
- `activity_instance` - Activity instances
- `activity_instance_link` - Activity links
- `pattern_exposure` - Pattern exposure

### ❌ AI Coaching & Integrations
- `conversation_thread` - AI conversations
- `conversation_turn` - Conversation turns
- `external_provider_account` - External accounts
- `external_ingestion_run` - Ingestion runs
- `external_activity_record` - External records
- `external_metric_stream` - Metric streams
- `macro_cycle` - Macro cycles
- `user_fatigue_state` - Fatigue tracking

### ❌ Program Planning
- `program_discipline` - Program disciplines
- `discipline` - User discipline experience
- `activity_definition` - User custom activities

### ❌ Config & State
- `heuristic_config` - Moved to code (see Phase 1) - **DELETE this table**

---

## Implementation Steps

### Step 1: Set Up Supabase Project
1. Create Supabase project at https://supabase.com
2. Get connection details:
   - Database URL
   - API keys
3. Update `.env` with Supabase credentials

### Step 2: Run Migrations
```bash
# Point to Supabase
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres

# Run migrations
alembic upgrade head
```

### Step 3: Seed Reference Data
```bash
# Run seed script
python scripts/supabase_seed_reference_data.py
```

### Step 4: Verify Seeding
```bash
# Check reference data
psql postgres://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres -c "\dt"

# Count movements
psql ... -c "SELECT COUNT(*) FROM movements;"

# Count activities
psql ... -c "SELECT COUNT(*) FROM activity_definitions;"
```

### Step 5: Clean Up Heuristic Config Table
Since heuristic configs are now in code:
```sql
-- Drop heuristic_configs table (no longer needed)
DROP TABLE IF EXISTS heuristic_configs;
```

---

## Environment Variables

### Local Development (Current)
```bash
DATABASE_URL=postgresql+asyncpg://gainsly:gainslypass@localhost:5433/gainslydb
```

### Supabase (Production)
```bash
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres
```

---

## Verification Checklist

After seeding Supabase, verify:

- [ ] **Movement system** populated (movements, muscles, equipment, disciplines)
- [ ] **Activity system** populated (activities, disciplines)
- [ ] **Circuit templates** populated
- [ ] **User tables** are empty (users, programs, workouts, etc.)
- [ ] **Heuristic config table** dropped (migrated to code)
- [ ] **Migrations** run successfully
- [ ] **API** connects to Supabase
- [ ] **Frontend** loads reference data correctly

---

## Data Source Files

Reference data files in `seed_data/`:
- `movements.json` - Main movement database
- `clean_crossfit_movements.json` - CrossFit movements
- `net_new_movements.json` - New movements
- `activities.json` - Activity definitions
- `scraped_circuits.json` - Circuit templates

---

## Estimated Record Counts

After seeding:
- **Movements**: ~500 exercises
- **Muscles**: ~50 muscle groups
- **Equipment**: ~20 types
- **Disciplines**: ~15 categories
- **Tags**: ~20 tags
- **Activities**: ~15 activities
- **Circuits**: ~20 templates
- **Total reference records**: ~3,500+

---

## Notes

1. **Heuristic configs** are now in `app/config/heuristics.py` - no need for database
2. **User tables** will populate organically as users sign up
3. **Reference data** provides core functionality without requiring user input
4. **Foreign keys** ensure data integrity (movements require muscles, etc.)
5. **Seed script** handles dependencies in correct order

---

## Related Files

- [`.env`](../../.env) - Database connection config
- [`scripts/supabase_seed_reference_data.py`](../scripts/supabase_seed_reference_data.py) - Seed script
- [`app/config/heuristics.py`](../../app/config/heuristics.py) - Heuristic configs (code)
- [`alembic/versions/`](../../alembic/versions/) - Database migrations
