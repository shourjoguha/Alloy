import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check_structure():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'program_disciplines'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()
        print("program_disciplines table structure:")
        for col in columns:
            print(f"  {col[0]}: {col[1]} (nullable: {col[2]})")
        
        result = await conn.execute(text("""
            SELECT con.conname, con.contype
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            WHERE rel.relname = 'program_disciplines'
        """))
        constraints = result.fetchall()
        print("\nConstraints:")
        for con in constraints:
            print(f"  {con[0]}: type {con[1]}")

asyncio.run(check_structure())
