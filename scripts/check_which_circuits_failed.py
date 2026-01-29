"""Check which circuits failed to populate."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Check which circuits failed."""
    async for db in get_db():
        try:
            # Get circuits without melted data
            result = await db.execute(text("""
                SELECT id, name
                FROM circuit_templates
                WHERE id NOT IN (SELECT DISTINCT circuit_id FROM circuits_melted)
                ORDER BY id
            """))
            
            print("Circuits WITHOUT melted data:")
            print("-" * 80)
            for row in result:
                print(f"  {row.id}: {row.name}")
            print()
            
            # Get circuits without macro data
            result = await db.execute(text("""
                SELECT id, name
                FROM circuit_templates
                WHERE id NOT IN (SELECT DISTINCT circuit_id FROM circuits_macro)
                ORDER BY id
            """))
            
            print("Circuits WITHOUT macro data:")
            print("-" * 80)
            for row in result:
                print(f"  {row.id}: {row.name}")
            print()
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
