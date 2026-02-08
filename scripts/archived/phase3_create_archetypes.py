"""Phase 3: Deep Enrichment - Create biomechanical archetypes for fundamental movements."""
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import async_session_maker
from app.models.movement import Movement, MovementTag, MovementMuscleMap
from app.models.enums import (
    MovementTier, MetabolicDemand, MuscleRole, PrimaryMuscle,
    MovementPattern
)
from sqlalchemy import select

async def get_tag_id(db: async_session_maker, tag_name: str) -> int:
    """Get or create a tag ID."""
    from app.models.movement import Tag
    
    result = await db.execute(
        select(Tag.id).where(Tag.name == tag_name)
    )
    tag_id = result.scalar_one_or_none()
    
    if not tag_id:
        tag = Tag(name=tag_name)
        db.add(tag)
        await db.flush()
        tag_id = tag.id
        print(f"      Created tag: {tag_name}")
    
    return tag_id

async def update_beneficial_tags(db: async_session_maker, movement: Movement, tags: list[str]):
    """Add biomechanical tags to a movement."""
    for tag_name in tags:
        tag_id = await get_tag_id(db, tag_name)
        
        existing = await db.execute(
            select(MovementTag).where(
                MovementTag.movement_id == movement.id,
                MovementTag.tag_id == tag_id
            )
        )
        if not existing.scalar_one_or_none():
            movement_tag = MovementTag(movement_id=movement.id, tag_id=tag_id)
            db.add(movement_tag)
            print(f"      Added tag: {tag_name}")

async def get_muscle_id(db: async_session_maker, muscle: PrimaryMuscle) -> int:
    """Get muscle ID from PrimaryMuscle enum."""
    from app.models.movement import Muscle
    
    result = await db.execute(
        select(Muscle.id).where(Muscle.slug == muscle.value)
    )
    muscle_id = result.scalar_one_or_none()
    
    if not muscle_id:
        raise ValueError(f"Muscle not found: {muscle.value}")
    
    return muscle_id

async def update_muscle_maps(db: async_session_maker, movement: Movement, muscles: list[dict]):
    """Update primary and secondary muscle maps with magnitudes."""
    for muscle_data in muscles:
        muscle = muscle_data["muscle"]
        role = muscle_data["role"]
        magnitude = muscle_data.get("magnitude", 1.0)
        
        muscle_id = await get_muscle_id(db, muscle)
        
        existing = await db.execute(
            select(MovementMuscleMap).where(
                MovementMuscleMap.movement_id == movement.id,
                MovementMuscleMap.muscle_id == muscle_id
            )
        )
        existing_map = existing.scalar_one_or_none()
        
        if existing_map:
            existing_map.role = role
            existing_map.magnitude = magnitude
            print(f"      Updated {muscle.name}: {role.name} ({magnitude})")
        else:
            muscle_map = MovementMuscleMap(
                movement_id=movement.id,
                muscle_id=muscle_id,
                role=role,
                magnitude=magnitude
            )
            db.add(muscle_map)
            print(f"      Added {muscle.name}: {role.name} ({magnitude})")

async def create_archetype(movement: Movement, profile: dict):
    """Create biomechanical profile for a movement."""
    movement.tier = profile["tier"]
    movement.metabolic_demand = profile["metabolic_demand"]
    movement.biomechanics_profile = profile["biomechanics_profile"]
    return movement

async def elevate_fundamental_movements():
    """Elevate key fundamental movements to Diamond/Gold tier with biomechanical archetypes."""
    
    archetype_definitions = {
        "Conventional Deadlift": {
            "tier": MovementTier.DIAMOND,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "hinge",
                "primary_mechanism": "hip_extension",
                "lumbar_shear": "high",
                "spinal_compression": "very_high",
                "cns_load": "very_high",
                "movement_complexity": "high",
                "stability_demand": "moderate",
                "eccentric_control": "moderate",
                "concentric_power": "very_high"
            },
            "tags": ["posterior_chain", "compound", "full_body", "fundamental"],
            "muscles": [
                {"muscle": PrimaryMuscle.GLUTES, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.LOWER_BACK, "role": MuscleRole.PRIMARY, "magnitude": 0.9},
                {"muscle": PrimaryMuscle.HAMSTRINGS, "role": MuscleRole.PRIMARY, "magnitude": 0.85},
                {"muscle": PrimaryMuscle.QUADRICEPS, "role": MuscleRole.SECONDARY, "magnitude": 0.4},
                {"muscle": PrimaryMuscle.LATS, "role": MuscleRole.SECONDARY, "magnitude": 0.5}
            ]
        },
        "Back Squat": {
            "tier": MovementTier.DIAMOND,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "squat",
                "primary_mechanism": "knee_flexion_extension",
                "lumbar_shear": "low",
                "spinal_compression": "very_high",
                "cns_load": "very_high",
                "movement_complexity": "high",
                "stability_demand": "high",
                "eccentric_control": "high",
                "concentric_power": "very_high"
            },
            "tags": ["quad_dominant", "compound", "full_body", "fundamental"],
            "muscles": [
                {"muscle": PrimaryMuscle.QUADRICEPS, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.GLUTES, "role": MuscleRole.PRIMARY, "magnitude": 0.95},
                {"muscle": PrimaryMuscle.HAMSTRINGS, "role": MuscleRole.PRIMARY, "magnitude": 0.7},
                {"muscle": PrimaryMuscle.LOWER_BACK, "role": MuscleRole.SECONDARY, "magnitude": 0.8},
                {"muscle": PrimaryMuscle.ADDUCTORS, "role": MuscleRole.SECONDARY, "magnitude": 0.3}
            ]
        },
        "Front Squat": {
            "tier": MovementTier.GOLD,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "squat",
                "primary_mechanism": "knee_flexion_extension",
                "lumbar_shear": "very_low",
                "spinal_compression": "high",
                "cns_load": "high",
                "movement_complexity": "high",
                "stability_demand": "very_high",
                "eccentric_control": "high",
                "concentric_power": "high"
            },
            "tags": ["quad_dominant", "compound", "full_body", "anterior_chain"],
            "muscles": [
                {"muscle": PrimaryMuscle.QUADRICEPS, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.GLUTES, "role": MuscleRole.PRIMARY, "magnitude": 0.85},
                {"muscle": PrimaryMuscle.CORE, "role": MuscleRole.SECONDARY, "magnitude": 0.7},
                {"muscle": PrimaryMuscle.LOWER_BACK, "role": MuscleRole.SECONDARY, "magnitude": 0.5}
            ]
        },
        "Barbell Bench Press": {
            "tier": MovementTier.DIAMOND,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "horizontal_push",
                "primary_mechanism": "elbow_extension_shoulder_flexion",
                "lumbar_shear": "low",
                "spinal_compression": "moderate",
                "cns_load": "high",
                "movement_complexity": "moderate",
                "stability_demand": "moderate",
                "eccentric_control": "moderate",
                "concentric_power": "high"
            },
            "tags": ["chest_dominant", "compound", "upper_body", "fundamental"],
            "muscles": [
                {"muscle": PrimaryMuscle.CHEST, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.TRICEPS, "role": MuscleRole.PRIMARY, "magnitude": 0.7},
                {"muscle": PrimaryMuscle.FRONT_DELTS, "role": MuscleRole.SECONDARY, "magnitude": 0.6}
            ]
        },
        "Pull-Up": {
            "tier": MovementTier.GOLD,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "vertical_pull",
                "primary_mechanism": "elbow_flexion_shoulder_extension",
                "lumbar_shear": "low",
                "spinal_compression": "low",
                "cns_load": "moderate",
                "movement_complexity": "moderate",
                "stability_demand": "moderate",
                "eccentric_control": "high",
                "concentric_power": "moderate"
            },
            "tags": ["back_dominant", "compound", "upper_body", "bodyweight"],
            "muscles": [
                {"muscle": PrimaryMuscle.LATS, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.BICEPS, "role": MuscleRole.PRIMARY, "magnitude": 0.7},
                {"muscle": PrimaryMuscle.UPPER_BACK, "role": MuscleRole.SECONDARY, "magnitude": 0.5},
                {"muscle": PrimaryMuscle.REAR_DELTS, "role": MuscleRole.SECONDARY, "magnitude": 0.4}
            ]
        },
        "Chin-Up": {
            "tier": MovementTier.GOLD,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "vertical_pull",
                "primary_mechanism": "elbow_flexion_shoulder_extension",
                "lumbar_shear": "low",
                "spinal_compression": "low",
                "cns_load": "moderate",
                "movement_complexity": "moderate",
                "stability_demand": "moderate",
                "eccentric_control": "high",
                "concentric_power": "moderate"
            },
            "tags": ["back_dominant", "compound", "upper_body", "bodyweight", "supinated_grip"],
            "muscles": [
                {"muscle": PrimaryMuscle.LATS, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.BICEPS, "role": MuscleRole.PRIMARY, "magnitude": 0.9},
                {"muscle": PrimaryMuscle.FOREARMS, "role": MuscleRole.SECONDARY, "magnitude": 0.6},
                {"muscle": PrimaryMuscle.UPPER_BACK, "role": MuscleRole.SECONDARY, "magnitude": 0.4}
            ]
        },
        "Barbell Row": {
            "tier": MovementTier.GOLD,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "horizontal_pull",
                "primary_mechanism": "elbow_flexion_shoulder_extension",
                "lumbar_shear": "moderate",
                "spinal_compression": "high",
                "cns_load": "high",
                "movement_complexity": "high",
                "stability_demand": "high",
                "eccentric_control": "high",
                "concentric_power": "moderate"
            },
            "tags": ["back_dominant", "compound", "upper_body", "fundamental"],
            "muscles": [
                {"muscle": PrimaryMuscle.LATS, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.UPPER_BACK, "role": MuscleRole.PRIMARY, "magnitude": 0.9},
                {"muscle": PrimaryMuscle.BICEPS, "role": MuscleRole.PRIMARY, "magnitude": 0.6},
                {"muscle": PrimaryMuscle.REAR_DELTS, "role": MuscleRole.SECONDARY, "magnitude": 0.5},
                {"muscle": PrimaryMuscle.LOWER_BACK, "role": MuscleRole.SECONDARY, "magnitude": 0.7}
            ]
        },
        "Overhead Press": {
            "tier": MovementTier.GOLD,
            "metabolic_demand": MetabolicDemand.METABOLIC,
            "biomechanics_profile": {
                "pattern": "vertical_push",
                "primary_mechanism": "elbow_extension_shoulder_abduction",
                "lumbar_shear": "low",
                "spinal_compression": "moderate",
                "cns_load": "moderate",
                "movement_complexity": "moderate",
                "stability_demand": "moderate",
                "eccentric_control": "moderate",
                "concentric_power": "moderate"
            },
            "tags": ["shoulder_dominant", "compound", "upper_body"],
            "muscles": [
                {"muscle": PrimaryMuscle.SIDE_DELTS, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.TRICEPS, "role": MuscleRole.PRIMARY, "magnitude": 0.7},
                {"muscle": PrimaryMuscle.CHEST, "role": MuscleRole.SECONDARY, "magnitude": 0.3}
            ]
        },
        "Clean": {
            "tier": MovementTier.GOLD,
            "metabolic_demand": MetabolicDemand.NEURAL,
            "biomechanics_profile": {
                "pattern": "olympic",
                "primary_mechanism": "triple_extension",
                "lumbar_shear": "moderate",
                "spinal_compression": "high",
                "cns_load": "very_high",
                "movement_complexity": "very_high",
                "stability_demand": "very_high",
                "eccentric_control": "very_low",
                "concentric_power": "very_high"
            },
            "tags": ["olympic", "explosive", "full_body", "power"],
            "muscles": [
                {"muscle": PrimaryMuscle.QUADRICEPS, "role": MuscleRole.PRIMARY, "magnitude": 1.0},
                {"muscle": PrimaryMuscle.GLUTES, "role": MuscleRole.PRIMARY, "magnitude": 0.95},
                {"muscle": PrimaryMuscle.HAMSTRINGS, "role": MuscleRole.PRIMARY, "magnitude": 0.8},
                {"muscle": PrimaryMuscle.LATS, "role": MuscleRole.SECONDARY, "magnitude": 0.5},
                {"muscle": PrimaryMuscle.SIDE_DELTS, "role": MuscleRole.SECONDARY, "magnitude": 0.6}
            ]
        }
    }
    
    async with async_session_maker() as db:
        print("=== PHASE 3: DEEP ENRICHMENT - CREATE ARCHETYPES ===\n")
        
        for movement_name, archetype in archetype_definitions.items():
            result = await db.execute(
                select(Movement).where(Movement.name == movement_name)
            )
            movement = result.scalar_one_or_none()
            
            if not movement:
                print(f"⚠️  Movement not found: {movement_name}")
                continue
            
            print(f"Processing: {movement_name} (ID {movement.id})")
            
            movement = await create_archetype(movement, archetype)
            
            await update_beneficial_tags(db, movement, archetype["tags"])
            await update_muscle_maps(db, movement, archetype["muscles"])
            
            print(f"  ✅ Updated to {archetype['tier'].name} tier")
            print(f"  ✅ Biomechanics profile: {json.dumps(archetype['biomechanics_profile'], indent=2)}")
            print()
        
        await db.commit()
        print("=== ARCHETYPE CREATION COMPLETE ===")

async def main():
    """Main entry point."""
    await elevate_fundamental_movements()

if __name__ == "__main__":
    asyncio.run(main())
