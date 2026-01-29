"""Check why circuit 138 doesn't have data."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Check circuit 138."""
    async for db in get_db():
        try:
            # Get circuit 138 details
            result = await db.execute(text("""
                SELECT id, name, exercises_json
                FROM circuit_templates
                WHERE id = 138
            """))
            row = result.one()
            
            print(f"Circuit {row.id}: {row.name}")
            print(f"Exercises in JSON: {len(row.exercises_json) if row.exercises_json else 0}")
            
            if row.exercises_json:
                for i, ex in enumerate(row.exercises_json, 1):
                    print(f"  Exercise {i}:")
                    print(f"    movement_name: {ex.get('movement_name')}")
                    print(f"    movement_id: {ex.get('movement_id')}")
                    print(f"    reps: {ex.get('reps')}")
                    print(f"    distance_meters: {ex.get('distance_meters')}")
                    print(f"    duration_seconds: {ex.get('duration_seconds')}")
                    print(f"    calories: {ex.get('calories')}")
            
            print("\n" + "=" * 80)
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
