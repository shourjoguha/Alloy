import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check_tables():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%discipline%'
            ORDER BY table_name
        """))
        tables = result.fetchall()
        for table in tables:
            print(f"Table: {table[0]}")

asyncio.run(check_tables())
