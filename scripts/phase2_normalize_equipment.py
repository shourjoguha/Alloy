import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())

from app.db.database import async_session_maker
from app.models.movement import Equipment, MovementEquipment
from sqlalchemy import select, text, delete


EQUIPMENT_NORMALIZATION_MAP = {
    "bands": "band",
    "dumbbells": "dumbbell",
    "medicine ball": "medicine_ball",
    "pullup_bar": "pull_up_bar",
    "bodyweight": "none",
}


async def normalize_equipment():
    """Normalize equipment naming by merging duplicates."""
    settings = {
        "database_url": os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/workout_coach")
    }
    
    async with async_session_maker() as db:
        print("=" * 60)
        print("PHASE 2: EQUIPMENT NORMALIZATION")
        print("=" * 60)
        
        merged_count = 0
        skipped_count = 0
        
        for old_name, new_name in EQUIPMENT_NORMALIZATION_MAP.items():
            print(f"\n🔄 Processing: '{old_name}' -> '{new_name}'")
            
            result = await db.execute(
                select(Equipment).where(Equipment.name == old_name)
            )
            old_equipment = result.scalar_one_or_none()
            
            if not old_equipment:
                print(f"   ⏭️  Skipping: '{old_name}' not found")
                skipped_count += 1
                continue
            
            result = await db.execute(
                select(Equipment).where(Equipment.name == new_name)
            )
            new_equipment = result.scalar_one_or_none()
            
            if not new_equipment:
                print(f"   ⚠️  Warning: Target equipment '{new_name}' not found, renaming instead")
                old_equipment.name = new_name
                await db.commit()
                merged_count += 1
                continue
            
            old_id = old_equipment.id
            new_id = new_equipment.id
            
            print(f"   📝 Old ID: {old_id}, New ID: {new_id}")
            
            result = await db.execute(
                select(MovementEquipment).where(
                    MovementEquipment.equipment_id == old_id
                )
            )
            old_mappings = result.scalars().all()
            
            print(f"   📊 Found {len(old_mappings)} movement mappings")
            
            for mapping in old_mappings:
                print(f"      Movement {mapping.movement_id}: {old_id} -> {new_id}")
                mapping.equipment_id = new_id
            
            await db.commit()
            
            await db.execute(
                delete(Equipment).where(Equipment.id == old_id)
            )
            await db.commit()
            
            print(f"   ✅ Merged '{old_name}' into '{new_name}'")
            merged_count += 1
        
        print("\n" + "=" * 60)
        print("EQUIPMENT NORMALIZATION COMPLETE")
        print("=" * 60)
        print(f"Merged:   {merged_count} equipment items")
        print(f"Skipped:  {skipped_count} items")
        print("=" * 60)


async def verify_equipment():
    """Verify equipment normalization results."""
    async with async_session_maker() as db:
        print("\n" + "=" * 60)
        print("VERIFICATION: CURRENT EQUIPMENT")
        print("=" * 60)
        
        result = await db.execute(
            select(Equipment).order_by(Equipment.name)
        )
        equipment = result.scalars().all()
        
        for eq in equipment:
            print(f"ID: {eq.id:3d}, Name: {eq.name}")
        
        print(f"\nTotal equipment: {len(equipment)}")
        print("=" * 60)


async def main():
    """Main entry point."""
    await normalize_equipment()
    await verify_equipment()

if __name__ == "__main__":
    asyncio.run(main())
