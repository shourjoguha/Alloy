"""Phase 1: Domain Expansion - Inject missing movements directly into database.

This script adds table-stakes movements missing from the database:
- Olympic Lifting: Snatch Balance, Tall Clean
- Calisthenics: Planche progressions, Lever progressions
- Mobility: CARs, PAILs/RAILs
"""
import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.getcwd())

from app.config.settings import get_settings
from app.db.database import async_session_maker
from app.models.movement import Movement
from app.models.enums import (
    MovementPattern,
    PrimaryMuscle,
    PrimaryRegion,
    MetricType,
    SkillLevel,
    CNSLoad,
    DisciplineType,
)


def get_enum_value(enum_class, value):
    """Get enum value, handling both string and int values."""
    if isinstance(value, int):
        return enum_class(value)
    try:
        return enum_class(value)
    except ValueError:
        try:
            return enum_class(value.upper())
        except ValueError:
            pass
    raise ValueError(f"Cannot convert {value} to {enum_class.__name__}")


PHASE1_MOVEMENTS = [
    {
        "name": "Snatch Balance",
        "pattern": "olympic",
        "primary_muscle": "quadriceps",
        "primary_region": "anterior lower",
        "secondary_muscles": ["glutes", "upper_back", "core"],
        "cns_load": "very_high",
        "skill_level": "expert",
        "compound": True,
        "is_complex_lift": True,
        "is_unilateral": False,
        "metric_type": "reps",
        "discipline_tags": ["olympic", "athleticism"],
        "equipment_tags": ["barbell", "rack"],
        "substitution_group": "snatch",
    },
    {
        "name": "Tall Clean",
        "pattern": "olympic",
        "primary_muscle": "quadriceps",
        "primary_region": "anterior lower",
        "secondary_muscles": ["glutes", "upper_back", "core"],
        "cns_load": "very_high",
        "skill_level": "expert",
        "compound": True,
        "is_complex_lift": True,
        "is_unilateral": False,
        "metric_type": "reps",
        "discipline_tags": ["olympic", "athleticism"],
        "equipment_tags": ["barbell", "rack"],
        "substitution_group": "clean",
    },
    {
        "name": "Tuck Planche",
        "pattern": "isometric",
        "primary_muscle": "front_delts",
        "primary_region": "anterior upper",
        "secondary_muscles": ["triceps", "core", "biceps"],
        "cns_load": "moderate",
        "skill_level": "advanced",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["calisthenics", "skill"],
        "equipment_tags": ["bodyweight", "rings", "parallettes"],
        "substitution_group": "planche",
    },
    {
        "name": "Straddle Planche",
        "pattern": "isometric",
        "primary_muscle": "front_delts",
        "primary_region": "anterior upper",
        "secondary_muscles": ["triceps", "core", "biceps"],
        "cns_load": "high",
        "skill_level": "expert",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["calisthenics", "skill"],
        "equipment_tags": ["bodyweight", "rings", "parallettes"],
        "substitution_group": "planche",
    },
    {
        "name": "Full Planche",
        "pattern": "isometric",
        "primary_muscle": "front_delts",
        "primary_region": "anterior upper",
        "secondary_muscles": ["triceps", "core", "biceps"],
        "cns_load": "very_high",
        "skill_level": "elite",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["calisthenics", "skill"],
        "equipment_tags": ["bodyweight", "rings", "parallettes"],
        "substitution_group": "planche",
    },
    {
        "name": "Planche Push-up",
        "pattern": "horizontal_push",
        "primary_muscle": "front_delts",
        "primary_region": "anterior upper",
        "secondary_muscles": ["triceps", "chest", "core"],
        "cns_load": "very_high",
        "skill_level": "expert",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "reps",
        "discipline_tags": ["calisthenics", "skill"],
        "equipment_tags": ["bodyweight", "rings", "parallettes"],
        "substitution_group": "planche",
    },
    {
        "name": "Back Lever Hold",
        "pattern": "isometric",
        "primary_muscle": "lats",
        "primary_region": "posterior upper",
        "secondary_muscles": ["rear_delts", "biceps", "core"],
        "cns_load": "moderate",
        "skill_level": "advanced",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["calisthenics", "skill"],
        "equipment_tags": ["bodyweight", "rings", "pull_up_bar"],
        "substitution_group": "back_lever",
    },
    {
        "name": "Hip CARs",
        "pattern": "mobility",
        "primary_muscle": "core",
        "primary_region": "core",
        "secondary_muscles": ["hip_flexors", "glutes", "adductors"],
        "cns_load": "very_low",
        "skill_level": "beginner",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "reps",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight"],
        "substitution_group": "hip_cars",
    },
    {
        "name": "Shoulder CARs",
        "pattern": "mobility",
        "primary_muscle": "upper_back",
        "primary_region": "shoulder",
        "secondary_muscles": ["rear_delts", "side_delts", "traps"],
        "cns_load": "very_low",
        "skill_level": "beginner",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "reps",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight"],
        "substitution_group": "shoulder_cars",
    },
    {
        "name": "Thoracic Spine CARs",
        "pattern": "mobility",
        "primary_muscle": "upper_back",
        "primary_region": "posterior upper",
        "secondary_muscles": ["lats", "core"],
        "cns_load": "very_low",
        "skill_level": "beginner",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "reps",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight"],
        "substitution_group": "thoracic_cars",
    },
    {
        "name": "Ankle CARs",
        "pattern": "mobility",
        "primary_muscle": "calves",
        "primary_region": "anterior lower",
        "secondary_muscles": ["hip_flexors", "core"],
        "cns_load": "very_low",
        "skill_level": "beginner",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "reps",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight"],
        "substitution_group": "ankle_cars",
    },
    {
        "name": "Hip PAILs/RAILs",
        "pattern": "mobility",
        "primary_muscle": "hip_flexors",
        "primary_region": "anterior lower",
        "secondary_muscles": ["glutes", "adductors", "hamstrings"],
        "cns_load": "very_low",
        "skill_level": "intermediate",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight", "band"],
        "substitution_group": "hip_pails_rails",
    },
    {
        "name": "Shoulder PAILs/RAILs",
        "pattern": "mobility",
        "primary_muscle": "front_delts",
        "primary_region": "anterior upper",
        "secondary_muscles": ["rear_delts", "traps", "biceps"],
        "cns_load": "very_low",
        "skill_level": "intermediate",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight", "band"],
        "substitution_group": "shoulder_pails_rails",
    },
    {
        "name": "Hamstring PAILs/RAILs",
        "pattern": "mobility",
        "primary_muscle": "hamstrings",
        "primary_region": "posterior lower",
        "secondary_muscles": ["glutes", "calves", "lower_back"],
        "cns_load": "very_low",
        "skill_level": "intermediate",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight", "band"],
        "substitution_group": "hamstring_pails_rails",
    },
    {
        "name": "Thoracic PAILs/RAILs",
        "pattern": "mobility",
        "primary_muscle": "upper_back",
        "primary_region": "posterior upper",
        "secondary_muscles": ["lats", "core", "traps"],
        "cns_load": "very_low",
        "skill_level": "intermediate",
        "compound": True,
        "is_complex_lift": False,
        "is_unilateral": False,
        "metric_type": "time",
        "discipline_tags": ["mobility", "recovery"],
        "equipment_tags": ["bodyweight", "band"],
        "substitution_group": "thoracic_pails_rails",
    },
]


async def inject_movements():
    """Inject Phase 1 movements into the database."""
    settings = get_settings()
    
    async with async_session_maker() as db:
        injected = 0
        skipped = 0
        
        for movement_data in PHASE1_MOVEMENTS:
            name = movement_data["name"]
            
            existing = await db.execute(
                select(Movement).where(Movement.name == name)
            )
            if existing.scalar_one_or_none():
                print(f"⏭️  Skipping existing movement: {name}")
                skipped += 1
                continue
            
            try:
                pattern = get_enum_value(MovementPattern, movement_data["pattern"])
                primary_muscle = get_enum_value(PrimaryMuscle, movement_data["primary_muscle"])
                primary_region = get_enum_value(PrimaryRegion, movement_data["primary_region"])
                cns_load = get_enum_value(CNSLoad, movement_data["cns_load"])
                skill_level = get_enum_value(SkillLevel, movement_data["skill_level"])
                metric_type = get_enum_value(MetricType, movement_data["metric_type"])
            except (ValueError, KeyError) as e:
                print(f"❌ Skipping movement {name}: {e}")
                continue
            
            movement = Movement(
                name=name,
                pattern=pattern.value,
                primary_muscle=primary_muscle.value,
                primary_region=primary_region.value,
                cns_load=cns_load.value,
                skill_level=skill_level.value,
                compound=movement_data.get("compound", True),
                is_complex_lift=movement_data.get("is_complex_lift", False),
                is_unilateral=movement_data.get("is_unilateral", False),
                metric_type=metric_type.value,
                substitution_group=movement_data.get("substitution_group"),
            )
            
            db.add(movement)
            print(f"✅ Injected: {name}")
            injected += 1
        
        await db.commit()
        
        print(f"\n{'='*50}")
        print(f"Phase 1 Domain Expansion Complete")
        print(f"{'='*50}")
        print(f"Injected:  {injected} new movements")
        print(f"Skipped:   {skipped} existing movements")
        print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(inject_movements())
