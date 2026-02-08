import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from app.db.database import engine
from sqlalchemy import text

async def check_sequence():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT pg_get_serial_sequence('movements', 'id') as sequence
        """))
        print("Serial sequence for movements.id:")
        print("="*80)
        for row in result:
            print(f"Sequence: {row[0]}")
        print("="*80)
        
        result2 = await conn.execute(text("""
            SELECT count(*) FROM movements
        """))
        print("\nCurrent count of movements:")
        print("="*80)
        for row in result2:
            print(f"Count: {row[0]}")
        print("="*80)

if __name__ == "__main__":
    asyncio.run(check_sequence())
