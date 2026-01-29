"""Check current schema of circuits_macro table."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Check circuits_macro table schema."""
    async for db in get_db():
        try:
            # Get column information
            result = await db.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'circuits_macro'
                ORDER BY ordinal_position
            """))
            
            print("circuits_macro table schema:")
            print("-" * 80)
            for row in result:
                print(f"{row.column_name:40} {row.data_type:20} nullable: {row.is_nullable}")
            print("-" * 80)
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
