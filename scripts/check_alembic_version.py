import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check_version():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.fetchone()
        if version:
            print(f"Current Alembic version: {version[0]}")
        else:
            print("No Alembic version found")

asyncio.run(check_version())
