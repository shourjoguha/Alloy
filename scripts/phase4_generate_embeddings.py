"""
Generate embedding descriptions for movements.

This script creates rich text descriptions for LLM-based semantic search.
The embedding_description field provides comprehensive context for:
- Semantic movement matching
- Similarity search
- AI-driven movement recommendations
"""
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models.movement import (
    Movement,
    MovementEquipment,
    MovementTag,
    MovementDiscipline,
    MovementCoachingCue,
    Equipment,
    Tag
)
from app.models.enums import (
    MovementPattern,
    PrimaryMuscle,
    PrimaryRegion,
    SkillLevel,
    CNSLoad,
    SpinalCompression,
    MetricType,
    MovementTier,
    MetabolicDemand,
    DisciplineType,
)


def generate_embedding_description(movement: Movement, equipment_list, tags_list, disciplines_list, cues_list) -> str:
    """
    Generate a comprehensive embedding description for a movement.
    
    This description is designed for LLM-based semantic search and includes:
    - Movement classification and characteristics
    - Primary and secondary target muscles
    - Equipment requirements
    - Movement pattern and biomechanics
    - Skill level and complexity
    - Usage contexts (disciplines)
    - Coaching cues and technique notes
    """
    
    # Base description template
    parts = []
    
    # Name and pattern
    parts.append(f"Movement: {movement.name}")
    parts.append(f"Pattern: {movement.pattern}")
    
    # Muscle focus
    parts.append(f"Primary muscle: {movement.primary_muscle}")
    parts.append(f"Primary region: {movement.primary_region}")
    
    # Movement characteristics
    characteristics = []
    characteristics.append(f"compound={movement.compound}")
    characteristics.append(f"unilateral={movement.is_unilateral}")
    characteristics.append(f"complex_lift={movement.is_complex_lift}")
    parts.append(f"Characteristics: {', '.join(characteristics)}")
    
    # Load and complexity
    parts.append(f"CNS load: {movement.cns_load}")
    parts.append(f"Skill level: {movement.skill_level}")
    parts.append(f"Spinal compression: {movement.spinal_compression}")
    
    # Movement tier and metabolic demand
    parts.append(f"Tier: {movement.tier}")
    parts.append(f"Metabolic demand: {movement.metabolic_demand}")
    
    # Measurement type
    parts.append(f"Metric type: {movement.metric_type}")
    
    # Equipment
    if equipment_list:
        equipment_names = [e.name for e in equipment_list]
        parts.append(f"Equipment: {', '.join(equipment_names)}")
    
    # Tags
    if tags_list:
        tag_names = [t.name for t in tags_list]
        parts.append(f"Tags: {', '.join(tag_names)}")
    
    # Disciplines
    if disciplines_list:
        discipline_values = [d.discipline for d in disciplines_list]
        parts.append(f"Disciplines: {', '.join(discipline_values)}")
    
    # Substitution group
    if movement.substitution_group:
        parts.append(f"Substitution group: {movement.substitution_group}")
    
    # Description
    if movement.description:
        parts.append(f"Description: {movement.description}")
    
    # Coaching cues
    if cues_list:
        cue_texts = [c.cue_text for c in cues_list]
        parts.append(f"Coaching cues: {' | '.join(cue_texts)}")
    
    # Biomechanics profile
    if movement.biomechanics_profile:
        biomechanics = movement.biomechanics_profile
        biomechanics_parts = []
        for key, value in biomechanics.items():
            biomechanics_parts.append(f"{key}={value}")
        parts.append(f"Biomechanics: {', '.join(biomechanics_parts)}")
    
    return "\n".join(parts)


async def get_movement_details(session: AsyncSession, movement: Movement):
    """Fetch related equipment, tags, disciplines, and cues for a movement."""
    
    # Get equipment
    equipment_result = await session.execute(
        select(Equipment)
        .join(MovementEquipment, Equipment.id == MovementEquipment.equipment_id)
        .where(MovementEquipment.movement_id == movement.id)
    )
    equipment_list = equipment_result.scalars().all()
    
    # Get tags
    tags_result = await session.execute(
        select(Tag)
        .join(MovementTag, Tag.id == MovementTag.tag_id)
        .where(MovementTag.movement_id == movement.id)
    )
    tags_list = tags_result.scalars().all()
    
    # Get disciplines
    disciplines_list = await session.execute(
        select(MovementDiscipline)
        .where(MovementDiscipline.movement_id == movement.id)
    )
    disciplines_list = disciplines_list.scalars().all()
    
    # Get coaching cues
    cues_result = await session.execute(
        select(MovementCoachingCue)
        .where(MovementCoachingCue.movement_id == movement.id)
        .order_by(MovementCoachingCue.order)
    )
    cues_list = cues_result.scalars().all()
    
    return equipment_list, tags_list, disciplines_list, cues_list


async def generate_embeddings_for_all():
    """Generate embedding descriptions for all movements."""
    
    async with async_session_maker() as session:
        # Get all movements
        result = await session.execute(select(Movement))
        movements = result.scalars().all()
        
        print(f"Found {len(movements)} movements")
        
        updated_count = 0
        skipped_count = 0
        
        for movement in movements:
            # Skip if already has embedding description
            if movement.embedding_description:
                skipped_count += 1
                continue
            
            # Get related data
            equipment_list, tags_list, disciplines_list, cues_list = await get_movement_details(session, movement)
            
            # Generate embedding description
            embedding_description = generate_embedding_description(
                movement, equipment_list, tags_list, disciplines_list, cues_list
            )
            
            # Update movement
            movement.embedding_description = embedding_description
            updated_count += 1
            
            if updated_count % 10 == 0:
                print(f"Generated {updated_count} embeddings...")
        
        await session.commit()
        
        print(f"\nCompleted!")
        print(f"Generated embeddings: {updated_count}")
        print(f"Skipped (already exists): {skipped_count}")


async def generate_embedding_for_movement_name(movement_name: str):
    """Generate embedding description for a specific movement."""
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Movement).where(Movement.name == movement_name)
        )
        movement = result.scalar_one_or_none()
        
        if not movement:
            print(f"Movement not found: {movement_name}")
            return
        
        # Get related data
        equipment_list, tags_list, disciplines_list, cues_list = await get_movement_details(session, movement)
        
        # Generate embedding description
        embedding_description = generate_embedding_description(
            movement, equipment_list, tags_list, disciplines_list, cues_list
        )
        
        # Update movement
        movement.embedding_description = embedding_description
        await session.commit()
        
        print(f"Generated embedding for: {movement.name}")
        print(f"\n{embedding_description}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        movement_name = sys.argv[1]
        print(f"Generating embedding for: {movement_name}")
        asyncio.run(generate_embedding_for_movement_name(movement_name))
    else:
        print("Generating embeddings for all movements...")
        asyncio.run(generate_embeddings_for_all())
