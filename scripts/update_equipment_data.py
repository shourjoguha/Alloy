"""Update equipment data for existing macro records."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import select

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db
from app.models.circuit_extended import CircuitMacro, CircuitMelted
from app.models.movement import MovementEquipment


async def main():
    """Update equipment data for all macro records."""
    async for db in get_db():
        try:
            # Get all macro records
            stmt = select(CircuitMacro)
            result = await db.execute(stmt)
            macros = result.scalars().all()
            
            print(f"Found {len(macros)} macro records")
            
            for macro in macros:
                # Get melted exercises for this circuit
                stmt = select(CircuitMelted).where(CircuitMelted.circuit_id == macro.circuit_id)
                result = await db.execute(stmt)
                melted = result.scalars().all()
                
                # Extract equipment IDs
                equipment_ids = set()
                for ex in melted:
                    if ex.movement_id:
                        stmt = (
                            select(MovementEquipment.equipment_id)
                            .where(MovementEquipment.movement_id == ex.movement_id)
                        )
                        result = await db.execute(stmt)
                        equipment_ids.update(row[0] for row in result if row[0] is not None)
                
                # Update macro
                macro.required_equipment = sorted(equipment_ids)
                macro.equipment_complexity = len(equipment_ids)
                macro.updated_at = datetime.utcnow().timestamp()
                
                print(f"Circuit {macro.circuit_id}: {len(equipment_ids)} equipment items")
            
            await db.commit()
            print(f"\nUpdated {len(macros)} macro records with equipment data")
            
        except Exception as e:
            await db.rollback()
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
