# Session Generation Flow - Visual Diagram

## Phase 1: Program Creation (Synchronous)

```
┌─────────────────────────────────────────────────────────────────┐
│ API Request: POST /programs                                 │
│ {goals, duration_weeks, split_template, days_per_week}     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ ProgramService.create_program()                                │
│ [app/services/program.py:46]                                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Validate Input                                             │
│    - User exists                                              │
│    - Goals valid (8-12 weeks, interference check)             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Create Program Object                                      │
│    Program(                                                  │
│      user_id, split_template, days_per_week,                  │
│      goals, duration_weeks, ...                              │
│    )                                                         │
│    db.add(program)                                            │
│    await db.flush() ← Get program.id                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Create Program Disciplines                                │
│    FOR each discipline:                                       │
│      ProgramDiscipline(program_id, discipline_type, weight)    │
│      db.add(program_discipline)                               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Generate Microcycles                                     │
│    FOR each microcycle in program:                            │
│      - Calculate microcycle length (7-14 days)               │
│      - Determine if deload                                   │
│      - Build split configuration                              │
│      - Create microcycle                                     │
│      - Create sessions from split template                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Create Microcycle                                        │
│    Microcycle(                                               │
│      program_id, start_date, length_days,                    │
│      sequence_number, status, is_deload                      │
│    )                                                         │
│    db.add(microcycle)                                        │
│    await db.flush() ← Get microcycle.id                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Create Sessions (Session Shells)                           │
│    FOR each day in split template structure:                   │
│      Session(                                                 │
│        user_id, microcycle_id, date,                        │
│        day_number, session_type, intent_tags                  │
│      )                                                       │
│      db.add(session)                                         │
│                                                              │
│    Example: 4 days/week, 7-day cycle → 7 sessions created │
│      Day 1: Training (full_body)                            │
│      Day 2: Rest (recovery)                                 │
│      Day 3: Training (full_body)                            │
│      Day 4: Training (full_body)                            │
│      Day 5: Rest (recovery)                                 │
│      Day 6: Training (full_body)                            │
│      Day 7: Rest (recovery)                                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. COMMIT Transaction                                         │
│    await db.commit()                                         │
│    - All program data committed                               │
│    - All microcycles committed                              │
│    - ALL SESSIONS committed and visible                       │
│                                                              │
│    ⚠️ CRITICAL: This makes all sessions visible to other  │
│       transactions (including background tasks)                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Create Movement Rules & Enjoyable Activities                │
│    IF provided in request:                                   │
│      Create/Update UserMovementRule                          │
│      Create/Update UserEnjoyableActivity                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. COMMIT Transaction                                         │
│    await db.commit()                                         │
│    - Movement rules committed                                │
│    - Enjoyable activities committed                          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. Add Background Task                                     │
│     background_tasks.add_task(                               │
│       program_service.generate_active_microcycle_sessions,        │
│       program.id,                                            │
│     )                                                       │
│                                                              │
│     ⚠️ CRITICAL: Must be AFTER commit!                    │
│        If added before commit, background task may query DB   │
│        before sessions are visible, leading to partial data.   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. Return Program Response                                  │
│     return program                                           │
└─────────────────────────────────────────────────────────────────┘

```

## Phase 2: Session Content Generation (Asynchronous Background Task)

```
┌─────────────────────────────────────────────────────────────────┐
│ Background Task Starts (after API response sent)                │
│ program_service.generate_active_microcycle_sessions(program_id)  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. Fetch Program and Active Microcycle                        │
│    async with async_session_maker() as db:                     │
│      program = await db.get(Program, program_id)              │
│      microcycle = await db.get(Microcycle,                   │
│        where program_id AND status=ACTIVE)                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Fetch ALL Sessions for Active Microcycle                   │
│    sessions_result = await db.execute(                        │
│      select(Session)                                        │
│      .where(Session.microcycle_id == microcycle.id)          │
│      .order_by(Session.day_number)                           │
│    )                                                         │
│    sessions = list(sessions_result.scalars().all())           │
│                                                              │
│    ⚠️ CRITICAL QUERY: Should return ALL 7 sessions        │
│       If only returns 2 sessions, that's the bug!           │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Initialize Tracking                                       │
│    used_movements = set()                                   │
│    used_movement_groups = {}                                 │
│    used_main_patterns = {}                                   │
│    used_accessory_movements = {}                             │
│    previous_day_volume = {}                                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Loop Through Sessions                                     │
│    FOR idx, session in enumerate(sessions):                  │
│                                                              │
│      Session 1/7: Day 1, Training                          │
│      Session 2/7: Day 2, Rest (skip)                       │
│      Session 3/7: Day 3, Training                          │
│      Session 4/7: Day 4, Training                          │
│      Session 5/7: Day 5, Rest (skip)                       │
│      Session 6/7: Day 6, Training                          │
│      Session 7/7: Day 7, Rest (skip)                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Skip Recovery Sessions                                     │
│    IF session.session_type == RECOVERY:                       │
│      continue                                               │
│                                                              │
│    ⚠️ Only 4 training sessions will be processed         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Apply Pattern Interference Rules                           │
│    async with async_session_maker() as db:                     │
│      session = await _apply_pattern_interference_rules(       │
│        db, session, used_main_patterns, microcycle           │
│      )                                                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Populate Session with Exercises                             │
│    current_volume = await session_generator.populate_session_   │
│      by_id(                                                 │
│        session.id,                                           │
│        program_id,                                           │
│        microcycle_id,                                        │
│        used_movements,                                       │
│        used_movement_groups,                                   │
│        used_main_patterns,                                   │
│        used_accessory_movements,                              │
│        previous_day_volume,                                   │
│      )                                                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7a. Fetch Session Context (DB Transaction 1)              │
│    async with async_session_maker() as db:                     │
│      session = await db.get(Session, session_id)             │
│      program = await db.get(Program, program_id)            │
│      microcycle = await db.get(Microcycle, microcycle_id)   │
│      movements_by_pattern = await _load_movements()          │
│      movement_rules = await _load_user_movement_rules()       │
│      user_profile = await db.get(UserProfile, user_id)       │
│      all_movements = await _load_all_movements()             │
│    # Context collected, transaction closed                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7b. Generate Content (NO DB Connection)                     │
│    content = await generate_session_exercises_offline(       │
│      context_data,                                          │
│      used_movements,                                       │
│      used_movement_groups,                                   │
│      used_accessory_movements,                              │
│      fatigued_muscles,                                     │
│    )                                                         │
│                                                              │
│    This can take several seconds (LLM call)                  │
│    No DB lock held during this time                          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7c. Save Exercises (DB Transaction 2)                     │
│    async with async_session_maker() as db:                     │
│      session = await db.get(Session, session_id)             │
│      session.estimated_duration_minutes = content.duration     │
│                                                              │
│      await _save_session_exercises(                          │
│        db, session, content, movement_map, user_id         │
│      )                                                       │
│        # Creates SessionExercise records                       │
│                                                              │
│      db.add(session)                                         │
│      await db.commit() ← Save exercises to DB               │
│                                                              │
│      current_volume = await _calculate_session_volume(db,      │
│        session)                                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Update Tracking for Next Session                           │
│    used_movements.update(session_movements)                   │
│    used_main_patterns[session.day_number] = patterns          │
│    used_accessory_movements[session.day_number] = accessories │
│    previous_day_volume = current_volume                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. Continue to Next Session (Loop)                           │
│    IF session generation failed:                               │
│      continue (don't stop other sessions)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. Generate Jerome Notes (Batched)                          │
│     await _generate_microcycle_jerome_notes(                 │
│       program, microcycle, sessions                          │
│     )                                                         │
│     # Batch LLM call for all session notes                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. Log Completion                                          │
│     logger.info("COMPLETED for program X")                   │
└─────────────────────────────────────────────────────────────────┘

```

## Transaction Timeline

```
Time  │  Transaction Activity
──────┼────────────────────────────────────────────────────────────
T0    │ API Request: POST /programs
      │
T1    │ BEGIN Transaction (API Handler)
      │
T2    │ INSERT INTO programs
      │ FLUSH → program.id available
      │
T3    │ INSERT INTO program_disciplines
      │
T4    │ BEGIN Microcycle Loop
      │
T5    │ INSERT INTO microcycles
      │ FLUSH → microcycle.id available
      │
T6    │ INSERT INTO sessions (7 sessions)
      │   Day 1: INSERT session
      │   Day 2: INSERT session
      │   Day 3: INSERT session
      │   Day 4: INSERT session
      │   Day 5: INSERT session
      │   Day 6: INSERT session
      │   Day 7: INSERT session
      │
T7    │ COMMIT (All sessions now visible)
      │   ⚠️ CRITICAL POINT
      │
T8    │ INSERT INTO user_movement_rules (if provided)
      │ INSERT INTO user_enjoyable_activities (if provided)
      │
T9    │ COMMIT (Movement rules visible)
      │
T10   │ Add Background Task to Queue
      │
T11   │ API Response Sent
      │
T12   │ Background Task Starts
      │
T13   │ BEGIN Transaction (Background Task)
      │
T14   │ SELECT sessions WHERE microcycle_id = X
      │   ⚠️ Should see ALL 7 sessions
      │   If only sees 2, that's the bug!
      │
T15   │ COMMIT (End fetch transaction)
      │
T16   │ BEGIN Session 1 Population
      │
T17   │ SELECT session, program, microcycle
      │
T18   │ COMMIT (Context fetch)
      │
T19   │ LLM Call (No DB connection, several seconds)
      │
T20   │ BEGIN Save Transaction
      │
T21   │ INSERT INTO session_exercises (10-20 records)
      │
T22   │ UPDATE sessions SET estimated_duration_minutes
      │
T23   │ COMMIT (Exercises saved)
      │
T24   │ Repeat for Sessions 2, 3, 4 (skip 5, 7 as rest)
      │
T25   │ Generate Jerome Notes (Batched LLM)
      │
T26   │ UPDATE sessions SET coach_notes for each
      │
T27   │ COMMIT (Notes saved)
      │
T28   │ Log "COMPLETED for program X"
```

## Potential Failure Points

### Point A: T6 - Session Creation Loop
```
❌ IF: Loop only creates sessions for day 1 and day 10
❌ THEN: Only 2 sessions in database
❌ CAUSE: Split template configuration error
```

### Point B: T7 - Commit
```
❌ IF: Commit happens before all sessions added
❌ THEN: Only flushed sessions visible
❌ CAUSE: Flush vs Commit misunderstanding
✅ FIXED: Background task added AFTER commit
```

### Point C: T14 - Background Task Query
```
❌ IF: Query only returns 2 sessions
❌ THEN: Background task only populates 2 sessions
❌ CAUSE: Transaction isolation, timing, or query error
```

### Point D: T16-T24 - Session Population
```
❌ IF: Population fails for some sessions
❌ THEN: Sessions remain empty (no exercises)
❌ CAUSE: LLM timeout, error, or exception
✅ HANDLED: Failures caught and continue to next session
```

## Debugging Queries

### Query 1: Check Session Creation Count
```sql
-- Run immediately after program creation
SELECT
  COUNT(*) as total_sessions,
  MIN(day_number) as first_day,
  MAX(day_number) as last_day,
  COUNT(DISTINCT session_type) as types
FROM sessions
WHERE microcycle_id = <microcycle_id>;

-- Expected: total_sessions=7, first_day=1, last_day=7, types=2
-- If only 2 sessions: That's the bug!
```

### Query 2: Check Session Population Status
```sql
SELECT
  s.id,
  s.day_number,
  s.session_type,
  COUNT(se.id) as exercise_count,
  s.coach_notes IS NOT NULL as has_notes,
  s.estimated_duration_minutes IS NOT NULL as has_duration
FROM sessions s
LEFT JOIN session_exercises se ON s.id = se.session_id
WHERE s.microcycle_id = <microcycle_id>
GROUP BY s.id, s.day_number, s.session_type, s.coach_notes, s.estimated_duration_minutes
ORDER BY s.day_number;

-- Expected: 7 rows, 4 with exercises (training days)
-- If only 2 with exercises: Population issue
```

### Query 3: Check Session Creation Order
```sql
SELECT
  id,
  day_number,
  session_type,
  date,
  created_at
FROM sessions
WHERE microcycle_id = <microcycle_id>
ORDER BY id;

-- Check if sessions are created sequentially
-- Look for gaps in day_number
```

## Key Files Reference

- **API Handler**: [app/api/routes/programs.py:56](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py#L56-L220)
- **Program Service**: [app/services/program.py:46](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L46-L323)
- **Microcycle Creation**: [app/services/program.py:940](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L940-L1005)
- **Session Population**: [app/services/session_generator.py:263](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L263-L449)
- **Background Task**: [app/services/program.py:352](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L352-L379)

## Critical Code Sections

### 1. Commit Before Background Task
**File**: [app/api/routes/programs.py:195-213](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py#L195-L213)
```python
# Commit all changes (program, microcycles, sessions, movement rules, enjoyable activities)
# This ensures all sessions are visible to the background task
try:
    await db.commit()
    logger.info(f"Successfully committed all changes for program_id={program.id}")
except Exception as e:
    await db.rollback()
    logger.exception(f"Failed to commit program creation for program_id={program.id}")
    raise HTTPException(status_code=500, detail="Internal server error")

# CRITICAL: Add background task AFTER all transactions are committed
# This ensures all sessions are available when the background task queries the database
# If the background task is added before commit, it may query for sessions before they are
# committed, leading to only seeing the first and last sessions that were flushed
background_tasks.add_task(
    program_service.generate_active_microcycle_sessions,
    program.id,
)
```

### 2. Session Query in Background Task
**File**: [app/services/program.py:412-416](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L412-L416)
```python
# Get all sessions for this microcycle
sessions_result = await db.execute(
    select(Session).where(Session.microcycle_id == microcycle.id)
    .order_by(Session.day_number)
)
sessions = list(sessions_result.scalars().all())

logger.info(f"[_generate_session_content_async] Found {len(sessions)} sessions to generate")
```

### 3. Session Creation Loop
**File**: [app/services/program.py:983-1003](file:///Users/shourjosmac/Documents/alloy/app/services/program.py#L983-L1003)
```python
# Create sessions from split template structure
for day_def in structure:
    day_num = day_def.get("day", 1)
    day_type = day_def.get("type", "rest")
    focus_patterns = day_def.get("focus", [])
    
    # Calculate session date
    session_date = start_date + timedelta(days=day_num - 1)
    
    # Map day type to SessionType enum
    session_type = self._map_day_type_to_session_type(day_type)
    
    # Create session (even for rest days - they can have recovery activities)
    session = Session(
        user_id=user_id,
        microcycle_id=microcycle.id,
        date=session_date,
        day_number=day_num,
        session_type=session_type,
        intent_tags=focus_patterns,
    )
    db.add(session)

return microcycle
```
