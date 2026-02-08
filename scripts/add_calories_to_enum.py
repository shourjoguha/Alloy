"""Add 'calories' to the metrictype enum if it doesn't exist."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Add calories enum value to PostgreSQL metrictype type."""
    async for db in get_db():
        try:
            # Check if calories already exists
            result = await db.execute(text(
                "SELECT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'calories' AND enumtypid = 'metrictype'::regtype)"
            ))
            exists = result.scalar()
            
            if exists:
                print("✓ 'calories' already exists in metrictype enum")
                return
            
            # Add calories to the enum
            await db.execute(text("ALTER TYPE metrictype ADD VALUE 'calories';"))
            await db.commit()
            print("✓ Successfully added 'calories' to metrictype enum")
            
        except Exception as e:
            await db.rollback()
            print(f"✗ Error adding 'calories' to enum: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
