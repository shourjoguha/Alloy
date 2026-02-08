"""Add primary_region and region_diversity_score to circuits_macro table using raw SQL."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Add primary_region and region_diversity_score columns to circuits_macro."""
    async for db in get_db():
        try:
            # Check if columns already exist
            result = await db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'circuits_macro'
                AND column_name IN ('primary_region', 'region_diversity_score')
            """))
            existing_columns = {row.column_name for row in result}
            
            # Add primary_region column if it doesn't exist
            if 'primary_region' not in existing_columns:
                await db.execute(text("""
                    ALTER TABLE circuits_macro
                    ADD COLUMN primary_region primaryregion DEFAULT 'full body' NOT NULL
                """))
                print("✓ Added primary_region column")
            else:
                print("✓ primary_region column already exists")
            
            # Add region_diversity_score column if it doesn't exist
            if 'region_diversity_score' not in existing_columns:
                await db.execute(text("""
                    ALTER TABLE circuits_macro
                    ADD COLUMN region_diversity_score DOUBLE PRECISION DEFAULT 0.0 NOT NULL
                """))
                print("✓ Added region_diversity_score column")
            else:
                print("✓ region_diversity_score column already exists")
            
            await db.commit()
            print("\n✓ Successfully added columns to circuits_macro table")
            
        except Exception as e:
            await db.rollback()
            print(f"✗ Error adding columns: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
