import asyncio
import sys
import os
sys.path.insert(0, os.getcwd())

from app.db.database import async_session_maker
from app.models.movement import Movement, MovementMuscleMap, MovementEquipment, MovementTag, MovementDiscipline
from sqlalchemy import select, text, delete, func


DUPLICATE_MAPPINGS = {
    "Pull-Up": [
        "Pullups",
    ],
    "Row": [
        "Row*",
    ],
    "Single-Leg Squats": [
        "Single Leg Squats",
    ],
    "Dumbbell Chest Press": [
        "Dumbbell Bench Presses",
    ],
}


async def analyze_duplicate(movement_name: str, duplicate_names: list[str]) -> dict:
    """Analyze potential duplicate movements."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Movement).where(Movement.name == movement_name)
        )
        canonical = result.scalar_one_or_none()
        
        if not canonical:
            return {"status": "not_found", "message": f"Canonical movement '{movement_name}' not found"}
        
        duplicates_info = []
        
        for dup_name in duplicate_names:
            result = await db.execute(
                select(Movement).where(Movement.name == dup_name)
            )
            duplicate = result.scalar_one_or_none()
            
            if not duplicate:
                duplicates_info.append({"name": dup_name, "status": "not_found"})
                continue
            
            result = await db.execute(
                select(func.count(MovementMuscleMap.id)).where(
                    MovementMuscleMap.movement_id == duplicate.id
                )
            )
            muscle_count = result.scalar_one()
            
            result = await db.execute(
                select(func.count(MovementEquipment.movement_id)).where(
                    MovementEquipment.movement_id == duplicate.id
                )
            )
            equipment_count = result.scalar_one()
            
            duplicates_info.append({
                "name": dup_name,
                "id": duplicate.id,
                "status": "found",
                "muscle_mappings": muscle_count,
                "equipment_mappings": equipment_count,
                "canonical_comparison": {
                    "pattern_match": canonical.pattern == duplicate.pattern,
                    "primary_muscle_match": canonical.primary_muscle == duplicate.primary_muscle,
                    "primary_region_match": canonical.primary_region == duplicate.primary_region,
                }
            })
        
        return {
            "status": "analyzed",
            "canonical": {
                "id": canonical.id,
                "name": canonical.name,
                "pattern": canonical.pattern,
                "primary_muscle": canonical.primary_muscle,
            },
            "duplicates": duplicates_info
        }


async def merge_duplicate(canonical_name: str, duplicate_name: str) -> dict:
    """Merge duplicate movement into canonical."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Movement).where(Movement.name == canonical_name)
        )
        canonical = result.scalar_one_or_none()
        
        if not canonical:
            return {"status": "error", "message": f"Canonical movement '{canonical_name}' not found"}
        
        result = await db.execute(
            select(Movement).where(Movement.name == duplicate_name)
        )
        duplicate = result.scalar_one_or_none()
        
        if not duplicate:
            return {"status": "error", "message": f"Duplicate movement '{duplicate_name}' not found"}
        
        canonical_id = canonical.id
        duplicate_id = duplicate.id
        
        print(f"\n  Merging: '{duplicate_name}' (ID {duplicate_id}) -> '{canonical_name}' (ID {canonical_id})")
        
        result = await db.execute(
            select(MovementMuscleMap).where(
                MovementMuscleMap.movement_id == duplicate_id
            )
        )
        muscle_maps = result.scalars().all()
        print(f"    Muscle mappings: {len(muscle_maps)}")
        
        for mapping in muscle_maps:
            existing = await db.execute(
                select(MovementMuscleMap).where(
                    MovementMuscleMap.movement_id == canonical_id,
                    MovementMuscleMap.muscle_id == mapping.muscle_id
                )
            )
            if existing.scalar_one_or_none():
                print(f"      Muscle {mapping.muscle_id}: Deleting duplicate (already exists on canonical)")
                await db.execute(
                    delete(MovementMuscleMap).where(
                        MovementMuscleMap.movement_id == duplicate_id,
                        MovementMuscleMap.muscle_id == mapping.muscle_id
                    )
                )
            else:
                print(f"      Muscle {mapping.muscle_id}: {duplicate_id} -> {canonical_id}")
                mapping.movement_id = canonical_id
        
        result = await db.execute(
            select(MovementEquipment).where(
                MovementEquipment.movement_id == duplicate_id
            )
        )
        equipment_maps = result.scalars().all()
        print(f"    Equipment mappings: {len(equipment_maps)}")
        
        for mapping in equipment_maps:
            existing = await db.execute(
                select(MovementEquipment).where(
                    MovementEquipment.movement_id == canonical_id,
                    MovementEquipment.equipment_id == mapping.equipment_id
                )
            )
            if existing.scalar_one_or_none():
                print(f"      Equipment {mapping.equipment_id}: Deleting duplicate (already exists on canonical)")
                await db.execute(
                    delete(MovementEquipment).where(
                        MovementEquipment.movement_id == duplicate_id,
                        MovementEquipment.equipment_id == mapping.equipment_id
                    )
                )
            else:
                print(f"      Equipment {mapping.equipment_id}: {duplicate_id} -> {canonical_id}")
                mapping.movement_id = canonical_id
        
        result = await db.execute(
            select(MovementTag).where(
                MovementTag.movement_id == duplicate_id
            )
        )
        tag_maps = result.scalars().all()
        print(f"    Tag mappings: {len(tag_maps)}")
        
        for mapping in tag_maps:
            existing = await db.execute(
                select(MovementTag).where(
                    MovementTag.movement_id == canonical_id,
                    MovementTag.tag_id == mapping.tag_id
                )
            )
            if existing.scalar_one_or_none():
                print(f"      Tag {mapping.tag_id}: Deleting duplicate (already exists on canonical)")
                await db.execute(
                    delete(MovementTag).where(
                        MovementTag.movement_id == duplicate_id,
                        MovementTag.tag_id == mapping.tag_id
                    )
                )
            else:
                print(f"      Tag {mapping.tag_id}: {duplicate_id} -> {canonical_id}")
                mapping.movement_id = canonical_id
        
        result = await db.execute(
            select(MovementDiscipline).where(
                MovementDiscipline.movement_id == duplicate_id
            )
        )
        discipline_maps = result.scalars().all()
        print(f"    Discipline mappings: {len(discipline_maps)}")
        
        for mapping in discipline_maps:
            existing = await db.execute(
                select(MovementDiscipline).where(
                    MovementDiscipline.movement_id == canonical_id,
                    MovementDiscipline.discipline == mapping.discipline
                )
            )
            if existing.scalar_one_or_none():
                print(f"      Discipline {mapping.discipline}: Deleting duplicate (already exists on canonical)")
                await db.execute(
                    delete(MovementDiscipline).where(
                        MovementDiscipline.movement_id == duplicate_id,
                        MovementDiscipline.discipline == mapping.discipline
                    )
                )
            else:
                print(f"      Discipline {mapping.discipline}: {duplicate_id} -> {canonical_id}")
                mapping.movement_id = canonical_id
        
        await db.commit()
        
        await db.execute(
            delete(Movement).where(Movement.id == duplicate_id)
        )
        await db.commit()
        
        print(f"    ✅ Deleted duplicate movement '{duplicate_name}' (ID {duplicate_id})")
        
        return {"status": "merged", "canonical_id": canonical_id, "duplicate_id": duplicate_id}


async def main():
    """Main entry point for movement deduplication."""
    print("=" * 70)
    print("PHASE 2: MOVEMENT DEDUPLICATION")
    print("=" * 70)
    
    print("\n🔍 ANALYZING POTENTIAL DUPLICATES")
    print("=" * 70)
    
    for canonical_name, duplicate_names in DUPLICATE_MAPPINGS.items():
        print(f"\n📋 Canonical: '{canonical_name}'")
        print("-" * 70)
        
        analysis = await analyze_duplicate(canonical_name, duplicate_names)
        
        if analysis["status"] == "not_found":
            print(f"  ⚠️  {analysis['message']}")
            continue
        
        canonical = analysis["canonical"]
        print(f"  Canonical ID: {canonical['id']}")
        print(f"  Pattern: {canonical['pattern']}")
        print(f"  Primary Muscle: {canonical['primary_muscle']}")
        
        for dup in analysis["duplicates"]:
            if dup["status"] == "not_found":
                print(f"  ⏭️  Skipping '{dup['name']}': Not found")
                continue
            
            print(f"\n  📝 Duplicate: '{dup['name']}' (ID {dup['id']})")
            print(f"    Muscle mappings: {dup['muscle_mappings']}")
            print(f"    Equipment mappings: {dup['equipment_mappings']}")
            
            comparison = dup["canonical_comparison"]
            print(f"    Pattern match: {'✅' if comparison['pattern_match'] else '❌'}")
            print(f"    Primary muscle match: {'✅' if comparison['primary_muscle_match'] else '❌'}")
            print(f"    Primary region match: {'✅' if comparison['primary_region_match'] else '❌'}")
    
    print("\n" + "=" * 70)
    print("MERGING DUPLICATES")
    print("=" * 70)
    
    merged_count = 0
    skipped_count = 0
    
    for canonical_name, duplicate_names in DUPLICATE_MAPPINGS.items():
        for duplicate_name in duplicate_names:
            result = await merge_duplicate(canonical_name, duplicate_name)
            
            if result["status"] == "merged":
                merged_count += 1
            else:
                skipped_count += 1
                print(f"  ⚠️  {result['message']}")
    
    print("\n" + "=" * 70)
    print("DEDUPLICATION COMPLETE")
    print("=" * 70)
    print(f"Merged:   {merged_count} movements")
    print(f"Skipped:  {skipped_count} movements")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
