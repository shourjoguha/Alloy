"""
Seed Supabase with reference data only (no user data).

This script populates:
- Movement system (movements, muscles, equipment, disciplines)
- Activity system (activities, disciplines)
- Circuit templates

User data tables remain empty for fresh start.
"""

import asyncio
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import async_session_maker
from app.models import (
    Movement, Muscle, Equipment, MovementDiscipline, Tag, MovementCoachingCue,
    MovementRelationship, MovementMuscleMap, MovementEquipment, MovementTag,
    Discipline, ActivityDefinition, ActivityMuscleMap, CircuitTemplate
)
from app.models.enums import (
    MovementPattern, PrimaryMuscle, PrimaryRegion, MetricType,
    Tier, MetabolicDemand, DisciplineCategory, ActivityCategory
)


async def seed_muscles(session: AsyncSession) -> int:
    """Seed muscles from movements.json."""
    seed_file = Path(__file__).parent.parent / "seed_data" / "movements.json"
    
    if not seed_file.exists():
        print(f"⚠️  Seed file not found: {seed_file}")
        return 0
    
    with open(seed_file) as f:
        data = json.load(f)
    
    # Extract unique muscles
    muscles_set = set()
    for movement in data.get("movements", []):
        for muscle_map in movement.get("muscle_map", []):
            muscle_name = muscle_map.get("muscle")
            if muscle_name:
                muscles_set.add(muscle_name)
    
    # Create muscle records
    count = 0
    for muscle_name in muscles_set:
        # Try to parse muscle name to enum values
        primary_muscle = PrimaryMuscle.UNKNOWN
        primary_region = PrimaryRegion.UNKNOWN
        
        for pm in PrimaryMuscle:
            if muscle_name.upper().replace("_", "").replace(" ", "") == pm.name.upper():
                primary_muscle = pm
                break
        
        for pr in PrimaryRegion:
            if muscle_name.upper() in pr.name.upper():
                primary_region = pr
                break
        
        muscle = Muscle(
            name=muscle_name,
            primary_muscle=primary_muscle,
            primary_region=primary_region
        )
        session.add(muscle)
        count += 1
    
    await session.commit()
    print(f"✅ Seeded {count} muscles")
    return count


async def seed_equipment(session: AsyncSession) -> int:
    """Seed equipment from movements.json."""
    seed_file = Path(__file__).parent.parent / "seed_data" / "movements.json"
    
    with open(seed_file) as f:
        data = json.load(f)
    
    equipment_set = set()
    for movement in data.get("movements", []):
        for eq in movement.get("equipment", []):
            equipment_set.add(eq)
    
    count = 0
    for eq_name in equipment_set:
        equipment = Equipment(name=eq_name)
        session.add(equipment)
        count += 1
    
    await session.commit()
    print(f"✅ Seeded {count} equipment types")
    return count


async def seed_disciplines(session: AsyncSession) -> int:
    """Seed disciplines from movements.json and activities.json."""
    disciplines = {
        "powerlifting": DisciplineCategory.POWERLIFTING,
        "hypertrophy": DisciplineCategory.HYPERTROPHY,
        "strength": DisciplineCategory.STRENGTH,
        "endurance": DisciplineCategory.ENDURANCE,
        "calisthenics": DisciplineCategory.CALISTHENICS,
        "athleticism": DisciplineCategory.ATHLETICISM,
        "crossfit": DisciplineCategory.CROSSFIT,
        "mobility": DisciplineCategory.MOBILITY,
        "yoga": DisciplineCategory.YOGA,
        "running": DisciplineCategory.RUNNING,
        "cycling": DisciplineCategory.CYCLING,
        "swimming": DisciplineCategory.SWIMMING,
        "hiking": DisciplineCategory.HIKING,
        "basketball": DisciplineCategory.BASKETBALL,
        "football": DisciplineCategory.FOOTBALL,
    }
    
    count = 0
    for disc_name, category in disciplines.items():
        discipline = Discipline(
            name=disc_name,
            category=category,
            description=f"{disc_name} discipline"
        )
        session.add(discipline)
        count += 1
    
    await session.commit()
    print(f"✅ Seeded {count} disciplines")
    return count


async def seed_tags(session: AsyncSession) -> int:
    """Seed common movement tags."""
    tags = [
        "compound", "isolation", "push", "pull", "squat", "hinge", "lunge",
        "horizontal", "vertical", "unilateral", "bilateral", "upper", "lower",
        "core", "stabilizer", "primary", "accessory"
    ]
    
    count = 0
    for tag_name in tags:
        tag = Tag(name=tag_name)
        session.add(tag)
        count += 1
    
    await session.commit()
    print(f"✅ Seeded {count} tags")
    return count


async def seed_movements(session: AsyncSession) -> int:
    """Seed movements from movements.json."""
    seed_file = Path(__file__).parent.parent / "seed_data" / "movements.json"
    
    with open(seed_file) as f:
        data = json.load(f)
    
    # Get existing references
    muscles_result = await session.execute(select(Muscle))
    muscles_map = {m.name: m for m in muscles_result.scalars().all()}
    
    equipment_result = await session.execute(select(Equipment))
    equipment_map = {e.name: e for e in equipment_result.scalars().all()}
    
    disciplines_result = await session.execute(select(Discipline))
    disciplines_map = {d.name: d for d in disciplines_result.scalars().all()}
    
    count = 0
    for movement_data in data.get("movements", []):
        # Map pattern string to enum
        pattern_str = movement_data.get("pattern", "compound")
        try:
            pattern = MovementPattern[pattern_str.lower()]
        except (KeyError, AttributeError):
            pattern = MovementPattern.COMPOUND
        
        movement = Movement(
            name=movement_data.get("name"),
            pattern=pattern,
            tier=mier_str_to_enum(movement_data.get("tier", "tier_3")),
            metabolic_demand=metabolic_str_to_enum(movement_data.get("metabolic_demand", "moderate")),
            metric_type=metric_str_to_enum(movement_data.get("metric_type", "reps")),
            description=movement_data.get("description", "")
        )
        session.add(movement)
        
        # Add relationships
        await session.flush()  # Get movement ID
        
        # Add muscle mappings
        for muscle_map in movement_data.get("muscle_map", []):
            muscle_name = muscle_map.get("muscle")
            if muscle_name in muscles_map:
                mm = MovementMuscleMap(
                    movement_id=movement.id,
                    muscle_id=muscles_map[muscle_name].id,
                    role=muscle_map.get("role", "primary")
                )
                session.add(mm)
        
        # Add equipment
        for eq_name in movement_data.get("equipment", []):
            if eq_name in equipment_map:
                me = MovementEquipment(
                    movement_id=movement.id,
                    equipment_id=equipment_map[eq_name].id
                )
                session.add(me)
        
        # Add disciplines
        for disc_name in movement_data.get("disciplines", []):
            if disc_name in disciplines_map:
                md = MovementDiscipline(
                    movement_id=movement.id,
                    discipline_id=disciplines_map[disc_name].id
                )
                session.add(md)
        
        count += 1
    
    await session.commit()
    print(f"✅ Seeded {count} movements")
    return count


def mier_str_to_enum(mier_str: str) -> Tier:
    """Convert string to Tier enum."""
    mapping = {
        "tier_1": Tier.TIER_1,
        "tier_2": Tier.TIER_2,
        "tier_3": Tier.TIER_3,
    }
    return mapping.get(mier_str.lower(), Tier.TIER_3)


def metabolic_str_to_enum(metabolic_str: str) -> MetabolicDemand:
    """Convert string to MetabolicDemand enum."""
    mapping = {
        "low": MetabolicDemand.LOW,
        "moderate": MetabolicDemand.MODERATE,
        "high": MetabolicDemand.HIGH,
    }
    return mapping.get(metabolic_str.lower(), MetabolicDemand.MODERATE)


def metric_str_to_enum(metric_str: str) -> MetricType:
    """Convert string to MetricType enum."""
    mapping = {
        "reps": MetricType.REPS,
        "time": MetricType.TIME,
        "time_under_tension": MetricType.TIME_UNDER_TENSION,
        "distance": MetricType.DISTANCE,
    }
    return mapping.get(metric_str.lower(), MetricType.REPS)


async def seed_activities(session: AsyncSession) -> int:
    """Seed activity definitions from activities.json."""
    seed_file = Path(__file__).parent.parent / "seed_data" / "activities.json"
    
    if not seed_file.exists():
        print(f"⚠️  Seed file not found: {seed_file}")
        return 0
    
    with open(seed_file) as f:
        data = json.load(f)
    
    # Get existing disciplines
    disciplines_result = await session.execute(select(Discipline))
    disciplines_map = {d.name: d for d in disciplines_result.scalars().all()}
    
    # Get existing muscles
    muscles_result = await session.execute(select(Muscle))
    muscles_map = {m.name: m for m in muscles_result.scalars().all()}
    
    count = 0
    for activity_data in data.get("activities", []):
        disc_name = activity_data.get("discipline", "running")
        discipline = disciplines_map.get(disc_name)
        
        activity = ActivityDefinition(
            name=activity_data.get("name"),
            discipline_id=discipline.id if discipline else None,
            description=activity_data.get("description", ""),
            category=ActivityCategory.CARDIO,
            cns_impact=activity_data.get("cns_impact", "moderate"),
            calories_per_minute=activity_data.get("calories_per_minute", 10),
            duration_minutes=activity_data.get("duration_minutes", 30)
        )
        session.add(activity)
        
        # Add muscle mappings
        await session.flush()
        for muscle_name in activity_data.get("affected_muscles", []):
            if muscle_name in muscles_map:
                amm = ActivityMuscleMap(
                    activity_id=activity.id,
                    muscle_id=muscles_map[muscle_name].id
                )
                session.add(amm)
        
        count += 1
    
    await session.commit()
    print(f"✅ Seeded {count} activities")
    return count


async def seed_circuit_templates(session: AsyncSession) -> int:
    """Seed circuit templates from scraped_circuits.json."""
    seed_file = Path(__file__).parent.parent / "seed_data" / "scraped_circuits.json"
    
    if not seed_file.exists():
        print(f"⚠️  Seed file not found: {seed_file}")
        return 0
    
    with open(seed_file) as f:
        data = json.load(f)
    
    count = 0
    for circuit_data in data.get("circuits", []):
        circuit = CircuitTemplate(
            name=circuit_data.get("name"),
            description=circuit_data.get("description", ""),
            category=circuit_data.get("category", "hiit"),
            duration_minutes=circuit_data.get("duration", 20),
            rounds=circuit_data.get("rounds", 3),
            exercises=circuit_data.get("exercises", []),
            rest_seconds=circuit_data.get("rest_seconds", 60)
        )
        session.add(circuit)
        count += 1
    
    await session.commit()
    print(f"✅ Seeded {count} circuit templates")
    return count


async def main():
    """Main seeding function."""
    print("🌱 Seeding Supabase with reference data...")
    print()
    
    async with async_session_maker() as session:
        # Check if data already exists
        existing_movements = await session.execute(select(Movement).limit(1))
        if existing_movements.first():
            print("⚠️  Reference data already exists. Skipping seed.")
            return
        
        # Seed in order of dependencies
        await seed_muscles(session)
        await seed_equipment(session)
        await seed_disciplines(session)
        await seed_tags(session)
        await seed_movements(session)
        await seed_activities(session)
        await seed_circuit_templates(session)
        
        print()
        print("✅ Reference data seeding complete!")
        print()
        print("User data tables are empty and ready for fresh start.")


if __name__ == "__main__":
    asyncio.run(main())
