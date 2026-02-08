"""Debug why circuits don't have macro data."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Debug circuits without macro data."""
    async for db in get_db():
        try:
            # Get circuits without macro data
            result = await db.execute(text("""
                SELECT ct.id, ct.name, ct.exercises_json,
                    (SELECT COUNT(*) FROM circuits_melted WHERE circuit_id = ct.id) as melted_count
                FROM circuit_templates ct
                WHERE ct.id NOT IN (SELECT DISTINCT circuit_id FROM circuits_macro)
                ORDER BY ct.id
            """))
            
            print("Circuits WITHOUT macro data:")
            print("-" * 80)
            for row in result:
                print(f"\n{row.id}: {row.name}")
                print(f"  Melted exercises: {row.melted_count}")
                print(f"  Exercises in JSON: {len(row.exercises_json) if row.exercises_json else 0}")
                if row.exercises_json:
                    for i, ex in enumerate(row.exercises_json[:3], 1):
                        print(f"    Exercise {i}: {ex.get('movement_name', 'unknown')}, reps={ex.get('reps')}, distance={ex.get('distance_meters')}, duration={ex.get('duration_seconds')}, calories={ex.get('calories')}")
                    if len(row.exercises_json) > 3:
                        print(f"    ... and {len(row.exercises_json) - 3} more exercises")
            print("-" * 80)
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
