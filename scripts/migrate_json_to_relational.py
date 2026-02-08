import asyncio
import logging
import json
from sqlalchemy import text, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.config.settings import get_settings
from app.models.movement import (
    Movement, Muscle, MovementMuscleMap, MovementDiscipline,
    MovementEquipment, MovementTag, MovementCoachingCue,
    Equipment, Tag
)
from app.models.program import Session, SessionExercise
from app.models.circuit import CircuitTemplate
from app.models.enums import (
    MuscleRole, DisciplineType, SessionSection, ExerciseRole, CircuitType,
    PrimaryMuscle, PrimaryRegion
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def map_muscle_to_region(muscle: PrimaryMuscle) -> str:
    m = muscle.value
    if m in [PrimaryMuscle.QUADRICEPS.value, PrimaryMuscle.HIP_FLEXORS.value, PrimaryMuscle.ADDUCTORS.value]:
        return PrimaryRegion.ANTERIOR_LOWER.value
    if m in [PrimaryMuscle.HAMSTRINGS.value, PrimaryMuscle.GLUTES.value, PrimaryMuscle.CALVES.value, PrimaryMuscle.LOWER_BACK.value]:
        return PrimaryRegion.POSTERIOR_LOWER.value
    if m in [PrimaryMuscle.CHEST.value, PrimaryMuscle.FRONT_DELTS.value, PrimaryMuscle.BICEPS.value, PrimaryMuscle.FOREARMS.value]:
        return PrimaryRegion.ANTERIOR_UPPER.value
    if m in [PrimaryMuscle.LATS.value, PrimaryMuscle.UPPER_BACK.value, PrimaryMuscle.REAR_DELTS.value, PrimaryMuscle.TRICEPS.value]:
        return PrimaryRegion.POSTERIOR_UPPER.value
    if m in [PrimaryMuscle.SIDE_DELTS.value]:
        return PrimaryRegion.SHOULDER.value
    if m in [PrimaryMuscle.CORE.value, PrimaryMuscle.OBLIQUES.value]:
        return PrimaryRegion.FULL_BODY.value # Best fit given available regions
    return PrimaryRegion.FULL_BODY.value

async def seed_muscles(session):
    print("Seeding muscles...")
    # Check if muscles exist
    result = await session.execute(select(Muscle))
    existing_muscles = {m.slug: m for m in result.scalars().all()}
    
    count_added = 0
    for pm in PrimaryMuscle:
        if pm.value not in existing_muscles:
            region = map_muscle_to_region(pm)
            new_muscle = Muscle(
                slug=pm.value,
                name=pm.value.replace("_", " ").title(),
                region=region,
                stimulus_coefficient=1.0,
                fatigue_coefficient=1.0
            )
            session.add(new_muscle)
            count_added += 1
            
    if count_added > 0:
        await session.flush()
        print(f"Seeded {count_added} muscles.")
    else:
        print("Muscles already seeded.")

async def migrate():
    print("Starting migration...")
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            await seed_muscles(session)
            
            print("Migrating movements...")
            await migrate_movements(session)
            print("Migrating sessions...")
            await migrate_sessions(session)
            await session.commit()
            print("Migration committed successfully.")
        except Exception as e:
            print(f"Migration failed: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

async def migrate_movements(session):
    # Fetch raw data using text() from movements_legacy table
    stmt = text("SELECT id, name, secondary_muscles, discipline_tags, equipment_tags, tags, coaching_cues, primary_discipline FROM movements_legacy")
    result = await session.execute(stmt)
    rows = result.fetchall()
    
    # Pre-fetch caches
    muscles_result = (await session.execute(select(Muscle))).scalars().all()
    muscles_by_slug = {m.slug: m.id for m in muscles_result}
    muscles_by_name = {m.name.lower(): m.id for m in muscles_result}
    
    equipments = {e.name.lower(): e for e in (await session.execute(select(Equipment))).scalars().all()}
    tags = {t.name.lower(): t for t in (await session.execute(select(Tag))).scalars().all()}
    
    count_muscles = 0
    count_disciplines = 0
    count_equipments = 0
    count_tags = 0
    count_cues = 0

    for row in rows:
        # Secondary Muscles
        # JSON columns might be returned as strings or dicts depending on driver/DB
        # Assuming list/dict if using postgres/sqlite json support, but handle string just in case
        def parse_json(val):
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except:
                    return []
            return val if val else []

        sec_muscles = parse_json(row.secondary_muscles)
        if sec_muscles:
            for muscle_name in sec_muscles:
                m_key = muscle_name.lower()
                m_id = muscles_by_slug.get(m_key)
                if not m_id:
                    # Try matching name (e.g. "upper_back" -> "upper back")
                    m_id = muscles_by_name.get(m_key.replace("_", " "))
                
                if m_id:
                    # Check if exists
                    exists = await session.execute(select(MovementMuscleMap).filter_by(movement_id=row.id, muscle_id=m_id, role=MuscleRole.SECONDARY))
                    if not exists.scalar_one_or_none():
                        session.add(MovementMuscleMap(movement_id=row.id, muscle_id=m_id, role=MuscleRole.SECONDARY))
                        count_muscles += 1
        
        # Disciplines
        disciplines = parse_json(row.discipline_tags)
        
        # Add primary_discipline if valid
        if row.primary_discipline and row.primary_discipline.lower() != 'all':
             # Check if already in list (case insensitive)
             if not any(d.lower() == row.primary_discipline.lower() for d in disciplines):
                 disciplines.append(row.primary_discipline)

        if disciplines:
            for disc in disciplines:
                # Handle slight variations if needed
                disc_clean = disc.lower().replace(" ", "_")
                dt = None
                try:
                    dt = DisciplineType(disc_clean)
                except ValueError:
                    try:
                        dt = DisciplineType[disc.upper()]
                    except KeyError:
                        pass
                
                if dt:
                    # Use dt.value to ensure we send the string value to the DB, matching the DB enum labels
                    print(f"DEBUG: disc={disc}, clean={disc_clean}, dt={dt}, dt.value={dt.value}")
                    # Check if exists
                    exists = await session.execute(select(MovementDiscipline).filter_by(movement_id=row.id, discipline=dt.value))
                    if not exists.scalar_one_or_none():
                        session.add(MovementDiscipline(movement_id=row.id, discipline=dt.value))
                        count_disciplines += 1
                else:
                    # Fallback: Add as a Tag if not a valid Discipline
                    print(f"Info: Mapping '{disc}' to Tag instead of Discipline.")
                    t = tags.get(disc_clean)
                    if not t:
                        t = Tag(name=disc_clean)
                        session.add(t)
                        await session.flush()
                        tags[t.name] = t
                    
                    exists_tag = await session.execute(select(MovementTag).filter_by(movement_id=row.id, tag_id=t.id))
                    if not exists_tag.scalar_one_or_none():
                        session.add(MovementTag(movement_id=row.id, tag_id=t.id))
                        count_tags += 1

        # Equipment
        eq_tags = parse_json(row.equipment_tags)
        if eq_tags:
            for eq_name in eq_tags:
                eq_clean = eq_name.lower()
                eq = equipments.get(eq_clean)
                if not eq:
                    eq = Equipment(name=eq_clean)
                    session.add(eq)
                    await session.flush() # Get ID
                    equipments[eq.name] = eq
                
                exists = await session.execute(select(MovementEquipment).filter_by(movement_id=row.id, equipment_id=eq.id))
                if not exists.scalar_one_or_none():
                    session.add(MovementEquipment(movement_id=row.id, equipment_id=eq.id))
                    count_equipments += 1

        # Tags
        tag_list = parse_json(row.tags)
        if tag_list:
            for tag_name in tag_list:
                tag_clean = tag_name.lower()
                t = tags.get(tag_clean)
                if not t:
                    t = Tag(name=tag_clean)
                    session.add(t)
                    await session.flush()
                    tags[t.name] = t
                
                exists = await session.execute(select(MovementTag).filter_by(movement_id=row.id, tag_id=t.id))
                if not exists.scalar_one_or_none():
                    session.add(MovementTag(movement_id=row.id, tag_id=t.id))
                    count_tags += 1
        
        # Coaching Cues
        cues = parse_json(row.coaching_cues)
        if cues:
            # Check if cues already exist to avoid dupes
            existing_cues = (await session.execute(select(MovementCoachingCue).filter_by(movement_id=row.id))).scalars().all()
            if not existing_cues:
                for i, cue in enumerate(cues):
                    session.add(MovementCoachingCue(movement_id=row.id, cue_text=cue, order=i))
                    count_cues += 1

    print(f"Movements processed: {len(rows)}")
    print(f"Added: {count_muscles} muscle maps, {count_disciplines} disciplines, {count_equipments} equipment refs, {count_tags} tags, {count_cues} cues")

async def migrate_sessions(session):
    # Fetch raw data from legacy temp table, joining with current sessions to ensure existence
    stmt = text("""
        SELECT t.id, t.warmup_json, t.main_json, t.accessory_json, t.finisher_json, t.cooldown_json 
        FROM sessions_legacy_temp t
        JOIN sessions s ON s.id = t.id
    """)
    result = await session.execute(stmt)
    rows = result.fetchall()

    # Cache movements (case insensitive)
    movements_result = await session.execute(select(Movement.id, Movement.name))
    movements = {name.lower(): id for id, name in movements_result.all()}
    
    count_exercises = 0
    count_sessions_processed = 0

    for row in rows:
        session_has_exercises = False
        
        # Helper to process section
        async def process_section(json_data, section_enum, role_enum):
            nonlocal count_exercises
            
            def parse_json(val):
                if isinstance(val, str):
                    try:
                        return json.loads(val)
                    except:
                        return None
                return val

            data = parse_json(json_data)
            if not data:
                # print(f"No data for section {section_enum.value} in session {row.id}")
                return False
            
            exercises = []
            if isinstance(data, dict) and 'exercises' in data:
                exercises = data['exercises']
            elif isinstance(data, list):
                exercises = data
            
            if not exercises:
                # print(f"No exercises in section {section_enum.value} for session {row.id}")
                return False

            added_any = False
            for i, ex in enumerate(exercises):
                mov_name = ex.get('movement') or ex.get('name')
                if not mov_name:
                    print(f"Skipping exercise with no name in session {row.id}")
                    continue
                
                mov_id = movements.get(mov_name.lower())
                if not mov_id:
                     print(f"Movement '{mov_name}' not found for session {row.id}")
                     continue

                # Check if already exists to avoid duplication if script re-runs
                # Logic: Same session, same movement, same role, same order?
                # For safety, we trust the script is run once or we check.
                # Checking every insert is slow. We'll assume clean run or catch unique constraint (but no unique constraint on these fields combined yet).
                # Let's check existence by session_id + order + role
                exists = await session.execute(select(SessionExercise).filter_by(
                    session_id=row.id,
                    role=role_enum,
                    order_in_session=i
                ))
                if exists.scalar_one_or_none():
                    continue

                # Helpers for type safety
                def safe_int(val):
                    try: return int(val) if val is not None else None
                    except: return None
                
                def safe_float(val):
                    try: return float(val) if val is not None else None
                    except: return None

                reps = safe_int(ex.get('reps'))
                min_reps = safe_int(ex.get('rep_range_min'))
                max_reps = safe_int(ex.get('rep_range_max'))
                
                if reps is not None:
                    min_reps = reps
                    max_reps = reps

                # Debug what we are inserting
                print(f"Inserting SessionExercise: section={section_enum.value}, role={role_enum.value}, mov_id={mov_id}")

                se = SessionExercise(
                    session_id=row.id,
                    movement_id=mov_id,
                    session_section=section_enum.value,
                    role=role_enum.value,
                    order_in_session=i,
                    target_sets=safe_int(ex.get('sets')) or 1,
                    target_rep_range_min=min_reps,
                    target_rep_range_max=max_reps,
                    target_rpe=safe_float(ex.get('target_rpe')) if ex.get('target_rpe') else safe_float(ex.get('rpe')),
                    default_rest_seconds=safe_int(ex.get('rest_seconds') or ex.get('rest')),
                )
                session.add(se)
                count_exercises += 1
                added_any = True
            
            return added_any

        h1 = await process_section(row.warmup_json, SessionSection.WARMUP, ExerciseRole.WARMUP)
        h2 = await process_section(row.main_json, SessionSection.MAIN, ExerciseRole.MAIN)
        h3 = await process_section(row.accessory_json, SessionSection.ACCESSORY, ExerciseRole.ACCESSORY)

        # Special handling for Finisher Circuit metadata
        if row.finisher_json:
            try:
                # Check if already migrated
                current_sess = await session.execute(select(Session.finisher_circuit_id).where(Session.id == row.id))
                curr_cid = current_sess.scalar()

                if not curr_cid:
                    finisher_val = row.finisher_json
                    if isinstance(finisher_val, str):
                        finisher_val = json.loads(finisher_val)
                    
                    # If it's a dict with metadata (type/rounds) or just complex structure, create template
                    if isinstance(finisher_val, dict) and ('type' in finisher_val or 'rounds' in finisher_val):
                        c_type_str = finisher_val.get('type', 'circuit').upper().replace(" ", "_")
                        try:
                            c_type = CircuitType[c_type_str]
                        except KeyError:
                            # Try to map common variations
                            if "AMRAP" in c_type_str: c_type = CircuitType.AMRAP
                            elif "EMOM" in c_type_str: c_type = CircuitType.EMOM
                            elif "HIIT" in c_type_str: c_type = CircuitType.HIIT
                            elif "TABATA" in c_type_str: c_type = CircuitType.TABATA
                            else: c_type = CircuitType.ROUNDS_FOR_TIME

                        # Safe integer conversion
                        def get_int(d, k, def_val=None):
                            try: return int(d.get(k)) if d.get(k) is not None else def_val
                            except: return def_val

                        ct = CircuitTemplate(
                            name=f"Imported Finisher Session {row.id}",
                            description="Imported from legacy session data",
                            circuit_type=c_type,
                            exercises_json=finisher_val.get('exercises', []) if 'exercises' in finisher_val else [],
                            default_rounds=get_int(finisher_val, 'rounds', 1),
                            default_duration_seconds=get_int(finisher_val, 'duration_seconds') or (get_int(finisher_val, 'duration_minutes', 0) * 60 if get_int(finisher_val, 'duration_minutes') else None),
                            tags=["imported"]
                        )
                        session.add(ct)
                        await session.flush()
                        
                        # Update session
                        await session.execute(
                            update(Session).where(Session.id == row.id).values(finisher_circuit_id=ct.id)
                        )
                        print(f"Created CircuitTemplate {ct.id} for Session {row.id}")
            except Exception as e:
                print(f"Error migrating finisher for session {row.id}: {e}")

        h4 = await process_section(row.finisher_json, SessionSection.FINISHER, ExerciseRole.FINISHER)
        h5 = await process_section(row.cooldown_json, SessionSection.COOLDOWN, ExerciseRole.COOLDOWN)
        
        if h1 or h2 or h3 or h4 or h5:
            count_sessions_processed += 1

    print(f"Sessions processed: {len(rows)} (with data: {count_sessions_processed})")
    print(f"Added {count_exercises} session exercises")

if __name__ == "__main__":
    asyncio.run(migrate())
