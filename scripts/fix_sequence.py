"""Fix auto-increment sequence for movements table."""
import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())
from app.db.database import engine
from sqlalchemy import text

async def fix_sequence():
    async with engine.begin() as conn:
        print("Checking current max id...")
        result = await conn.execute(text("""
            SELECT COALESCE(MAX(id), 0) FROM movements
        """))
        max_id = result.scalar_one()
        print(f"Current max id: {max_id}")
        
        print("\nCreating sequence...")
        await conn.execute(text("""
            CREATE SEQUENCE IF NOT EXISTS movements_id_seq
            START WITH {next_id}
            INCREMENT BY 1
            NO MINVALUE
            NO MAXVALUE
            CACHE 1
        """.format(next_id=max_id + 1)))
        
        print("\nSetting sequence ownership...")
        await conn.execute(text("""
            ALTER TABLE movements 
            ALTER COLUMN id SET DEFAULT nextval('movements_id_seq')
        """))
        
        print("\nSetting sequence ownership to table...")
        await conn.execute(text("""
            ALTER SEQUENCE movements_id_seq OWNED BY movements.id
        """))
        
        print("\nVerifying sequence...")
        result = await conn.execute(text("""
            SELECT pg_get_serial_sequence('movements', 'id') as sequence
        """))
        sequence = result.scalar_one()
        print(f"Sequence: {sequence}")
        
        print("\n✅ Sequence setup complete!")

if __name__ == "__main__":
    asyncio.run(fix_sequence())
