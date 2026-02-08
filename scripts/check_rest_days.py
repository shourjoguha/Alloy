import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session_maker
from app.models.program import Session, SessionExercise
from sqlalchemy import select, func

async def check_rest_days():
    async with async_session_maker() as db:
        result = await db.execute(
            select(Session.id, Session.session_type, func.count(SessionExercise.id).label('exercise_count'))
            .outerjoin(SessionExercise)
            .where(Session.microcycle_id == 816)
            .group_by(Session.id)
            .order_by(Session.id)
        )
        print("Sessions in microcycle 816:")
        for row in result:
            has_exercises = "✓" if row.exercise_count > 0 else "✗"
            print(f"  Session {row.id} ({row.session_type}): {row.exercise_count} exercises {has_exercises}")

asyncio.run(check_rest_days())
