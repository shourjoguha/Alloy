"""Check constraints on circuits_macro table."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Check circuits_macro table constraints."""
    async for db in get_db():
        try:
            # Get check constraints
            result = await db.execute(text("""
                SELECT conname, pg_get_constraintdef(oid) as definition
                FROM pg_constraint
                WHERE conrelid = 'circuits_macro'::regclass
                AND contype = 'c'
            """))
            
            print("circuits_macro table check constraints:")
            print("-" * 80)
            for row in result:
                print(f"{row.conname}:")
                print(f"  {row.definition}")
                print("-" * 80)
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
