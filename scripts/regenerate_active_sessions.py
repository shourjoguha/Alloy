
import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, and_
from app.db.database import async_session_maker
from app.models import Program, Microcycle, MicrocycleStatus
from app.services.program import program_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def regenerate_active_sessions():
    """
    Regenerate sessions for the active program of the default user.
    This will trigger the new session_generator logic which populates the session_exercises table.
    """
    user_id = 1  # Default user ID
    
    async with async_session_maker() as db:
        # Find active program for user
        stmt = select(Program).where(
            and_(
                Program.user_id == user_id,
                Program.is_active == True
            )
        )
        result = await db.execute(stmt)
        program = result.scalar_one_or_none()
        
        if not program:
            logger.error(f"No active program found for user {user_id}")
            return

        logger.info(f"Found active program: {program.name} (ID: {program.id})")
        
        # Find active microcycle
        stmt = select(Microcycle).where(
            and_(
                Microcycle.program_id == program.id,
                Microcycle.status == MicrocycleStatus.ACTIVE
            )
        )
        result = await db.execute(stmt)
        microcycle = result.scalar_one_or_none()
        
        if not microcycle:
            logger.error(f"No active microcycle found for program {program.id}")
            return
            
        logger.info(f"Found active microcycle: ID {microcycle.id}, Sequence {microcycle.sequence_number}")

    # Regenerate sessions
    logger.info("Starting session regeneration...")
    try:
        await program_service.generate_active_microcycle_sessions(program.id)
        logger.info("Session regeneration completed successfully.")
    except Exception as e:
        logger.error(f"Session regeneration failed: {e}")
        logger.exception(e)

if __name__ == "__main__":
    asyncio.run(regenerate_active_sessions())
