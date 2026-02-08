import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine
from sqlalchemy import text

async def fix_sequence():
    async with engine.begin() as conn:
        # Create a sequence for session_exercises.id
        await conn.execute(text("""
            CREATE SEQUENCE IF NOT EXISTS session_exercises_id_seq;
        """))
        
        # Set the sequence as the default value for the id column
        await conn.execute(text("""
            ALTER TABLE session_exercises 
            ALTER COLUMN id SET DEFAULT nextval('session_exercises_id_seq');
        """))
        
        # Set the sequence ownership
        await conn.execute(text("""
            ALTER SEQUENCE session_exercises_id_seq OWNED BY session_exercises.id;
        """))
        
        print("Fixed session_exercises.id sequence")
        
        # Verify the fix
        result = await conn.execute(
            text("SELECT column_name, column_default, is_nullable "
                 "FROM information_schema.columns "
                 "WHERE table_name = 'session_exercises' "
                 "AND column_name = 'id'")
        )
        for row in result:
            print(f"Column: {row[0]}, Default: {row[1]}, Nullable: {row[2]}")

asyncio.run(fix_sequence())
