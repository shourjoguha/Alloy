"""Regenerate session exercises for all programs."""
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.database import async_session_maker
from app.models import Program, SessionExercise, Microcycle
from app.services.session_generator import SessionGeneratorService


async def regenerate_all_programs():
    """Regenerate session exercises for all programs."""
    async with async_session_maker() as db:
        # Get all programs with their sessions and microcycles
        result = await db.execute(
            select(Program)
            .options(
                selectinload(Program.microcycles).selectinload(Microcycle.sessions)
            )
        )
        programs = result.scalars().all()
        
        print(f"Found {len(programs)} programs")
        
        session_gen = SessionGeneratorService()
        regenerated_count = 0
        error_count = 0
        
        for program in programs:
            print(f"\nProcessing program {program.id}: {program.name or 'Unnamed'}")
            
            try:
                sessions_to_regenerate = []
                
                # Collect all sessions
                for microcycle in program.microcycles:
                    for session in microcycle.sessions:
                        sessions_to_regenerate.append((session, microcycle))
                
                if not sessions_to_regenerate:
                    print(f"  No sessions found for program {program.id}")
                    continue
                
                print(f"  Found {len(sessions_to_regenerate)} sessions")
                
                # Delete existing session exercises
                session_ids = [s[0].id for s in sessions_to_regenerate]
                await db.execute(
                    SessionExercise.__table__.delete()
                    .where(SessionExercise.session_id.in_(session_ids))
                )
                await db.commit()
                print("  Deleted existing session exercises")
                
                # Regenerate session exercises
                for session, microcycle in sessions_to_regenerate:
                    print(f"    Generating exercises for session {session.id} ({session.session_type})")
                    try:
                        # Generate and save session exercises
                        await session_gen.populate_session_by_id(
                            session_id=session.id,
                            program_id=program.id,
                            microcycle_id=microcycle.id
                        )
                        
                        print("      ✓ Success")
                    except Exception as e:
                        print(f"      ✗ Error: {e}")
                        await db.rollback()
                        error_count += 1
                
                regenerated_count += 1
                
            except Exception as e:
                print(f"  ✗ Error processing program {program.id}: {e}")
                await db.rollback()
                error_count += 1
        
        print(f"\n{'='*60}")
        print(f"Regenerated {regenerated_count}/{len(programs)} programs")
        print(f"Errors: {error_count}")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(regenerate_all_programs())
