import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine
from sqlalchemy import text

async def check_schema():
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT column_name, column_default, is_nullable "
                 "FROM information_schema.columns "
                 "WHERE table_name = 'session_exercises' "
                 "AND column_name = 'id'")
        )
        print("session_exercises.id column info:")
        for row in result:
            print(f"  Column: {row[0]}, Default: {row[1]}, Nullable: {row[2]}")

asyncio.run(check_schema())
