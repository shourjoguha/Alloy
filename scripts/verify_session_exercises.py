import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session_maker
from app.models.program import Session, SessionExercise
from sqlalchemy import select, func

async def verify_exercises():
    async with async_session_maker() as db:
        # Count session exercises for program 109
        result = await db.execute(
            select(func.count(SessionExercise.id))
            .join(Session)
            .where(Session.microcycle_id == 816)
        )
        count = result.scalar()
        print(f"Session exercises count for microcycle 816: {count}")

        # Get sessions with exercise counts
        result = await db.execute(
            select(Session.id, func.count(SessionExercise.id).label('exercise_count'))
            .outerjoin(SessionExercise)
            .where(Session.microcycle_id == 816)
            .group_by(Session.id)
            .order_by(Session.id)
        )
        print("\nSessions with exercise counts:")
        for row in result:
            print(f"  Session {row.id}: {row.exercise_count} exercises")

        # Sample exercises from one session
        result = await db.execute(
            select(SessionExercise)
            .join(Session)
            .where(Session.microcycle_id == 816)
            .order_by(Session.id, SessionExercise.order_in_session)
            .limit(5)
        )
        print("\nSample exercises:")
        for ex in result.scalars():
            print(f"  SessionExercise id={ex.id}, session_id={ex.session_id}, movement_id={ex.movement_id}, exercise_role={ex.exercise_role}")

asyncio.run(verify_exercises())
