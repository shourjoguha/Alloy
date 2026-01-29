"""Drop the valid_unique_movements constraint from circuits_macro table."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Drop the constraint."""
    async for db in get_db():
        try:
            # Drop the constraint
            await db.execute(text("""
                ALTER TABLE circuits_macro
                DROP CONSTRAINT IF EXISTS valid_unique_movements
            """))
            await db.commit()
            print("✓ Dropped valid_unique_movements constraint")
            
        except Exception as e:
            await db.rollback()
            print(f"✗ Error dropping constraint: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
