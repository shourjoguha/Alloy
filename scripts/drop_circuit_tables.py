"""
Script to drop circuit tables if they exist from previous failed migration
"""
import asyncio
from sqlalchemy import text
from app.db.database import get_db


async def main():
    async for db in get_db():
        try:
            # Drop tables in correct order (child tables first)
            await db.execute(text("DROP TABLE IF EXISTS circuits_macro CASCADE"))
            await db.execute(text("DROP TABLE IF EXISTS circuits_melted CASCADE"))
            
            await db.commit()
            print("Successfully dropped circuit tables")
            
        except Exception as e:
            await db.rollback()
            print(f"Error dropping tables: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
