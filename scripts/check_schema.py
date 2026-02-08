import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from app.db.database import engine
from sqlalchemy import text

async def check_schema():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default 
            FROM information_schema.columns 
            WHERE table_name = 'movements' 
            ORDER BY ordinal_position
        """))
        print("Current movements table schema:")
        print("="*80)
        for row in result:
            print(f"{row[0]:30} {row[1]:15} nullable={row[2]:5} default={row[3]}")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(check_schema())
