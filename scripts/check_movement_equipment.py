"""Check movement_equipment table data."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import select, func, text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db


async def main():
    """Check movement equipment data."""
    async for db in get_db():
        try:
            # Check total records in movement_equipment
            result = await db.execute(select(func.count()).select_from(text("movement_equipment")))
            count = result.scalar()
            print(f"Total movement_equipment records: {count}")
            
            if count > 0:
                # Get some sample records
                result = await db.execute(text("""
                    SELECT me.movement_id, me.equipment_id, m.name as movement_name, e.name as equipment_name
                    FROM movement_equipment me
                    JOIN movements m ON me.movement_id = m.id
                    JOIN equipment e ON me.equipment_id = e.id
                    LIMIT 10
                """))
                
                print("\nSample movement_equipment records:")
                print("-" * 80)
                for row in result:
                    print(f"Movement {row.movement_id} ({row.movement_name}): Equipment {row.equipment_id} ({row.equipment_name})")
            
            # Check if movements table has equipment column
            result = await db.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'movements' 
                AND column_name LIKE '%equipment%'
            """))
            
            print("\nEquipment-related columns in movements table:")
            print("-" * 80)
            for row in result:
                print(f"  {row.column_name}: {row.data_type}")
            
        except Exception as e:
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
