"""
Generate vector embeddings for movements using Ollama.

This script:
1. Generates rich embedding descriptions for movements
2. Creates vector embeddings using Ollama's embedding API
3. Updates the database with the embedding vectors

Usage:
    # Generate embeddings for all movements
    python scripts/generate_movement_embeddings.py
    
    # Generate embeddings for a specific movement
    python scripts/generate_movement_embeddings.py "Barbell Squat"
    
    # Force regenerate all embeddings (overwrite existing)
    python scripts/generate_movement_embeddings.py --force
"""
import asyncio
import sys
from typing import List, Optional

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
from app.llm.embedding_provider import EmbeddingProvider


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


async def generate_and_save_embedding(session: AsyncSession, movement: Movement, embedding_provider: EmbeddingProvider, force: bool = False):
    """
    Generate and save embedding vector for a single movement.
    
    Args:
        session: Database session
        movement: Movement object
        embedding_provider: EmbeddingProvider instance
        force: If True, regenerate even if embedding already exists
    
    Returns:
        True if embedding was generated/saved, False if skipped
    """
    # Skip if already has embedding vector (unless force is True)
    if movement.embedding_vector and not force:
        return False
    
    # Get related data
    equipment_list, tags_list, disciplines_list, cues_list = await get_movement_details(session, movement)
    
    # Generate embedding description
    embedding_description = generate_embedding_description(
        movement, equipment_list, tags_list, disciplines_list, cues_list
    )
    
    # Generate vector embedding
    print(f"  Generating embedding for: {movement.name}")
    embedding_vector = await embedding_provider.embed(embedding_description)
    
    # Update movement
    movement.embedding_description = embedding_description
    movement.embedding_vector = embedding_vector
    
    return True


async def generate_embeddings_for_all(force: bool = False):
    """Generate embedding vectors for all movements."""
    
    print("Initializing embedding provider...")
    embedding_provider = EmbeddingProvider()
    
    # Check if Ollama is available
    print("Checking Ollama connection...")
    is_healthy = await embedding_provider.health_check()
    if not is_healthy:
        print("ERROR: Cannot connect to Ollama. Please ensure Ollama is running:")
        print("  ollama serve")
        sys.exit(1)
    
    # Get embedding dimension
    print("Getting embedding dimension...")
    embedding_dim = await embedding_provider.get_embedding_dim()
    print(f"  Embedding dimension: {embedding_dim}")
    
    async with async_session_maker() as session:
        # Get all movements
        result = await session.execute(select(Movement))
        movements = result.scalars().all()
        
        print(f"\nFound {len(movements)} movements")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for i, movement in enumerate(movements, 1):
            try:
                was_updated = await generate_and_save_embedding(
                    session, movement, embedding_provider, force
                )
                
                if was_updated:
                    updated_count += 1
                    print(f"  [{i}/{len(movements)}] Generated embedding for: {movement.name}")
                else:
                    skipped_count += 1
                    print(f"  [{i}/{len(movements)}] Skipped (already exists): {movement.name}")
                
                # Commit every 10 movements
                if updated_count % 10 == 0:
                    await session.commit()
                    print(f"  Committed {updated_count} embeddings...")
                
            except Exception as e:
                error_count += 1
                print(f"  ERROR generating embedding for {movement.name}: {e}")
        
        # Final commit
        await session.commit()
        
        print(f"\nCompleted!")
        print(f"Generated embeddings: {updated_count}")
        print(f"Skipped (already exists): {skipped_count}")
        print(f"Errors: {error_count}")
    
    # Close the embedding provider
    await embedding_provider.close()


async def generate_embedding_for_movement_name(movement_name: str, force: bool = False):
    """Generate embedding vector for a specific movement."""
    
    print("Initializing embedding provider...")
    embedding_provider = EmbeddingProvider()
    
    # Check if Ollama is available
    print("Checking Ollama connection...")
    is_healthy = await embedding_provider.health_check()
    if not is_healthy:
        print("ERROR: Cannot connect to Ollama. Please ensure Ollama is running:")
        print("  ollama serve")
        sys.exit(1)
    
    async with async_session_maker() as session:
        result = await session.execute(
            select(Movement).where(Movement.name == movement_name)
        )
        movement = result.scalar_one_or_none()
        
        if not movement:
            print(f"Movement not found: {movement_name}")
            return
        
        was_updated = await generate_and_save_embedding(
            session, movement, embedding_provider, force
        )
        
        if was_updated:
            await session.commit()
            print(f"Generated embedding for: {movement.name}")
            print(f"\nEmbedding description:")
            print(movement.embedding_description)
            print(f"\nEmbedding vector (first 10 dimensions):")
            print(movement.embedding_vector[:10])
            print(f"Total dimensions: {len(movement.embedding_vector)}")
        else:
            print(f"Movement already has embedding (use --force to regenerate): {movement.name}")
    
    # Close the embedding provider
    await embedding_provider.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    
    if len(sys.argv) > 1 and sys.argv[1] not in ["--force", "-f"]:
        movement_name = sys.argv[1]
        print(f"Generating embedding for: {movement_name}")
        asyncio.run(generate_embedding_for_movement_name(movement_name, force))
    else:
        mode = " (force regenerate)" if force else ""
        print(f"Generating embeddings for all movements{mode}...")
        asyncio.run(generate_embeddings_for_all(force))
