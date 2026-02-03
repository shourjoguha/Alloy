"""Database seeding script for initial data."""
import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker, init_db
from app.models import (
    Movement,
    User,
    UserSettings,
    HeuristicConfig,
    ActivityDefinition,
    ActivityCategory,
    MovementPattern,
    PrimaryMuscle,
    PrimaryRegion,
    MetricType,
    SkillLevel,
    CNSLoad,
    E1RMFormula,
    ExperienceLevel,
    PersonaTone,
    PersonaAggression,
)


SEED_DATA_DIR = Path(__file__).parent.parent.parent / "seed_data"


def get_enum_value(enum_class, value):
    """Get enum value, handling both string and int values."""
    if isinstance(value, int):
        return enum_class(value)
    try:
        return enum_class(value)
    except ValueError:
        # Try uppercase
        return enum_class(value.upper())


async def seed_movements(db: AsyncSession) -> int:
    """Seed movement repository from JSON file."""
    movements_file = SEED_DATA_DIR / "movements.json"
    
    if not movements_file.exists():
        print(f"Movements file not found: {movements_file}")
        return 0
    
    with open(movements_file) as f:
        data = json.load(f)
    
    movements = data.get("movements", [])
    created_count = 0
    
    for m in movements:
        # Check if movement already exists
        existing = await db.execute(
            select(Movement).where(Movement.name == m["name"])
        )
        if existing.scalar_one_or_none():
            continue
        
        # Map enums
        try:
            pattern = get_enum_value(MovementPattern, m["pattern"])
            primary_muscle = get_enum_value(PrimaryMuscle, m["primary_muscle"])
            primary_region = get_enum_value(PrimaryRegion, m["primary_region"])
            cns_load = get_enum_value(CNSLoad, m["cns_load"])
            skill_level = get_enum_value(SkillLevel, m["skill_level"])
            metric_type = get_enum_value(MetricType, m["metric_type"])
        except (ValueError, KeyError) as e:
            print(f"Skipping movement {m['name']}: {e}")
            continue
        
        movement = Movement(
            name=m["name"],
            pattern=pattern.value,
            primary_muscle=primary_muscle.value,
            primary_region=primary_region.value,
            secondary_muscles=m.get("secondary_muscles", []),
            cns_load=cns_load.value,
            skill_level=skill_level.value,
            compound=m.get("compound", True),
            is_complex_lift=m.get("is_complex_lift", False),
            is_unilateral=m.get("is_unilateral", False),
            metric_type=metric_type.value,
            discipline_tags=m.get("discipline_tags", []),
            equipment_tags=m.get("equipment_tags", []),
            substitution_group=m.get("substitution_group"),
            description=m.get("description"),
            coaching_cues=m.get("coaching_cues", []),
        )
        db.add(movement)
        created_count += 1
    
    await db.commit()
    print(f"Created {created_count} movements")
    return created_count


async def seed_activity_definitions(db: AsyncSession) -> int:
    """Seed activity definitions from JSON file."""
    activities_file = SEED_DATA_DIR / "activities.json"
    
    if not activities_file.exists():
        print(f"Activities file not found: {activities_file}")
        return 0
    
    with open(activities_file) as f:
        activities = json.load(f)
    
    created_count = 0
    
    for a in activities:
        # Check if activity already exists
        existing = await db.execute(
            select(ActivityDefinition).where(ActivityDefinition.name == a["name"])
        )
        if existing.scalar_one_or_none():
            continue
        
        try:
            category = get_enum_value(ActivityCategory, a["category"])
            default_metric = get_enum_value(MetricType, a["default_metric_type"])
        except (ValueError, KeyError) as e:
            print(f"Skipping activity {a['name']}: {e}")
            continue
            
        activity = ActivityDefinition(
            name=a["name"],
            category=category.value,
            default_metric_type=default_metric.value,
            default_equipment_tags=a.get("default_equipment_tags", []),
            # Note: cns_impact will be stored in ActivityMuscleMap later, 
            # but we can't seed it directly here without the junction model fully set up for seeding.
            # For now, we seed the definition.
        )
        db.add(activity)
        created_count += 1
        
    await db.commit()
    print(f"Created {created_count} activity definitions")
    return created_count


async def seed_heuristic_configs(db: AsyncSession) -> int:
    """Seed heuristic configurations from JSON file."""
    configs_file = SEED_DATA_DIR / "heuristic_configs.json"
    
    if not configs_file.exists():
        print(f"Configs file not found: {configs_file}")
        return 0
    
    with open(configs_file) as f:
        data = json.load(f)
    
    configs = data.get("configs", [])
    created_count = 0
    
    for c in configs:
        # Check if config already exists
        existing = await db.execute(
            select(HeuristicConfig).where(
                HeuristicConfig.name == c["name"],
                HeuristicConfig.version == c["version"]
            )
        )
        if existing.scalar_one_or_none():
            continue
        
        config = HeuristicConfig(
            name=c["name"],
            version=c["version"],
            json_blob=c["json_blob"],
            description=c.get("description"),
            active=c.get("active", False),
        )
        db.add(config)
        created_count += 1
    
    await db.commit()
    print(f"Created {created_count} heuristic configs")
    return created_count


async def seed_default_user(db: AsyncSession) -> User | None:
    """Create default user for MVP (single-user mode)."""
    # Check if default user exists
    existing = await db.execute(
        select(User).where(User.id == 1)
    )
    if existing.scalar_one_or_none():
        print("Default user already exists")
        return None
    
    user = User(
        id=1,
        name="Default User",
        experience_level=ExperienceLevel.INTERMEDIATE,
        persona_tone=PersonaTone.SUPPORTIVE,
        persona_aggression=PersonaAggression.BALANCED,
    )
    db.add(user)
    await db.flush()  # Get the ID
    
    # Create user settings
    settings = UserSettings(
        user_id=user.id,
        active_e1rm_formula=E1RMFormula.EPLEY,
        use_metric=True,
    )
    db.add(settings)
    
    await db.commit()
    print(f"Created default user with ID {user.id}")
    return user


async def seed_all():
    """Run all seed functions."""
    print("Initializing database...")
    await init_db()
    
    async with async_session_maker() as db:
        print("\nSeeding database...")
        
        # Seed movements
        await seed_movements(db)
        
        # Seed activities
        await seed_activity_definitions(db)
        
        # Seed heuristic configs
        await seed_heuristic_configs(db)
        
        # Create default user
        await seed_default_user(db)
        
        print("\nSeeding complete!")


async def reset_and_seed():
    """Drop all tables, recreate, and seed."""
    from app.db.database import engine, Base
    
    print("Dropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    print("Creating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    await seed_all()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        asyncio.run(reset_and_seed())
    else:
        asyncio.run(seed_all())
