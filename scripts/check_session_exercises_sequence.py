import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine
from sqlalchemy import text

async def check_sequence():
    async with engine.begin() as conn:
        # Check if sequence exists
        result = await conn.execute(
            text("SELECT sequence_name FROM information_schema.sequences "
                 "WHERE sequence_name LIKE '%session_exercises%'")
        )
        print("Sequences related to session_exercises:")
        for row in result:
            print(f"  Sequence: {row[0]}")

        # Check the table definition
        result = await conn.execute(
            text("SELECT column_name, column_default, is_nullable "
                 "FROM information_schema.columns "
                 "WHERE table_name = 'session_exercises' "
                 "ORDER BY ordinal_position")
        )
        print("\nsession_exercises table columns:")
        for row in result:
            print(f"  Column: {row[0]}, Default: {row[1]}, Nullable: {row[2]}")

asyncio.run(check_sequence())
