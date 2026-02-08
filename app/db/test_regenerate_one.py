"""Test regenerate one program to debug."""
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.database import async_session_maker
from app.models import Program, SessionExercise
from app.services.session_generator import SessionGeneratorService


async def test_regenerate_one_program():
    """Regenerate session exercises for program 133."""
    async with async_session_maker() as db:
        # Get program 133 with microcycles and sessions
        result = await db.execute(
            select(Program)
            .options(
                selectinload(Program.microcycles).selectinload(Microcycle.sessions),
                selectinload(Program.goals),
            )
            .where(Program.id == 133)
        )
        program = result.scalar_one_or_none()
        
        if not program:
            print("Program 133 not found")
            return
        
        print(f"Program {program.id}: {program.name or 'Unnamed'}")
        print(f"User ID: {program.user_id}")
        print(f"Max duration: {program.max_session_duration}")
        
        sessions_to_regenerate = []
        
        # Collect first 3 sessions only
        for microcycle in program.microcycles:
            for session in microcycle.sessions:
                sessions_to_regenerate.append((session, microcycle))
                if len(sessions_to_regenerate) >= 3:
                    break
            if len(sessions_to_regenerate) >= 3:
                break
        
        print(f"\nTesting {len(sessions_to_regenerate)} sessions")
        
        # Delete existing session exercises
        session_ids = [s[0].id for s in sessions_to_regenerate]
        await db.execute(
            SessionExercise.__table__.delete()
            .where(SessionExercise.session_id.in_(session_ids))
        )
        await db.commit()
        print("Deleted existing session exercises")
        
        # Regenerate session exercises
        session_gen = SessionGeneratorService()
        for session, microcycle in sessions_to_regenerate:
            print(f"\n--- Session {session.id} ({session.session_type}) ---")
            print(f"  Intent tags: {session.intent_tags}")
            print(f"  Date: {session.date}")
            
            try:
                await session_gen.populate_session_by_id(
                    session_id=session.id,
                    program_id=program.id,
                    microcycle_id=microcycle.id
                )
                
                print("  ✓ Success")
                
                # Check if exercises were actually saved
                check_result = await db.execute(
                    select(SessionExercise).where(SessionExercise.session_id == session.id)
                )
                exercise_count = len(list(check_result.scalars().all()))
                print(f"  Saved exercises in DB: {exercise_count}")
                
            except Exception as e:
                print(f"  ✗ Error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                await db.rollback()


if __name__ == "__main__":
    from app.models import Microcycle
    asyncio.run(test_regenerate_one_program())
