"""
Core movement management library for dynamic movement and relationship creation.

This library provides reusable functions to:
- Add new movements with full biomechanical data
- Create relationships between movements
- Import movements from JSON/CSV
- Validate movement data
"""
import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.db.database import async_session_maker
from app.models.movement import (
    Movement,
    MovementRelationship,
    MovementEquipment,
    MovementTag,
    MovementDiscipline,
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
    RelationshipType
)


class MovementManager:
    """Core movement management operations."""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = async_session_maker()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
        await self.session.close()
    
    async def get_or_create_equipment(self, name: str) -> Equipment:
        """Get existing equipment or create new."""
        result = await self.session.execute(
            select(Equipment).where(Equipment.name == name)
        )
        equipment = result.scalar_one_or_none()
        
        if not equipment:
            equipment = Equipment(name=name)
            self.session.add(equipment)
            await self.session.flush()
        
        return equipment
    
    async def get_or_create_tag(self, name: str) -> Tag:
        """Get existing tag or create new."""
        result = await self.session.execute(
            select(Tag).where(Tag.name == name)
        )
        tag = result.scalar_one_or_none()
        
        if not tag:
            tag = Tag(name=name)
            self.session.add(tag)
            await self.session.flush()
        
        return tag
    
    async def get_movement_by_name(self, name: str) -> Optional[Movement]:
        """Get movement by exact name."""
        result = await self.session.execute(
            select(Movement).where(Movement.name == name)
        )
        return result.scalar_one_or_none()
    
    async def find_similar_movements(self, name: str, limit: int = 5) -> List[str]:
        """Find movements with similar names using fuzzy matching."""
        result = await self.session.execute(
            select(Movement.name).order_by(Movement.name)
        )
        all_movements = result.scalars().all()
        
        name_lower = name.lower()
        
        def similarity(s1: str, s2: str) -> int:
            """Calculate similarity between two strings using common substring."""
            s1_lower, s2_lower = s1.lower(), s2.lower()
            
            if s1_lower == s2_lower:
                return 100
            if s1_lower in s2_lower or s2_lower in s1_lower:
                return 80
            
            common_chars = set(s1_lower) & set(s2_lower)
            total_chars = set(s1_lower) | set(s2_lower)
            return int((len(common_chars) / len(total_chars)) * 100)
        
        similar = [
            (m, similarity(name, m))
            for m in all_movements
            if similarity(name, m) > 30
        ]
        
        similar.sort(key=lambda x: (-x[1], x[0]))
        
        return [m[0] for m in similar[:limit]]
    
    async def add_movement(self, movement_data: Dict[str, Any]) -> Optional[Movement]:
        """
        Add a new movement with full biomechanical data.
        
        Args:
            movement_data: Dictionary containing movement fields
            
        Returns:
            Created Movement object or None if movement exists
        
        Example:
            movement_data = {
                "name": "Barbell Squat",
                "pattern": "squat",
                "primary_muscle": "quadriceps",
                "primary_region": "anterior lower",
                "skill_level": "beginner",
                "compound": True,
                "equipment": ["barbell", "squat_rack"],
                "tags": ["compound", "lower_body"],
                "disciplines": ["powerlifting", "bodybuilding"],
                "tier": "gold",
                "biomechanics_profile": {...}
            }
        """
        existing = await self.get_movement_by_name(movement_data["name"])
        if existing:
            print(f"Movement already exists: {movement_data['name']}")
            return existing
        
        try:
            movement = Movement(
                name=movement_data["name"],
                pattern=MovementPattern(movement_data.get("pattern", "isolation")),
                primary_muscle=PrimaryMuscle(movement_data.get("primary_muscle", "full_body")),
                primary_region=PrimaryRegion(movement_data.get("primary_region", "full_body")),
                cns_load=CNSLoad(movement_data.get("cns_load", "moderate")),
                skill_level=SkillLevel(movement_data.get("skill_level", "intermediate")),
                compound=movement_data.get("compound", False),
                is_complex_lift=movement_data.get("is_complex_lift", False),
                is_unilateral=movement_data.get("is_unilateral", False),
                fatigue_factor=movement_data.get("fatigue_factor", 1.0),
                stimulus_factor=movement_data.get("stimulus_factor", 1.0),
                injury_risk_factor=movement_data.get("injury_risk_factor", 1.0),
                min_recovery_hours=movement_data.get("min_recovery_hours", 48),
                spinal_compression=SpinalCompression(movement_data.get("spinal_compression", "moderate")),
                metric_type=MetricType(movement_data.get("metric_type", "reps")),
                tier=MovementTier(movement_data.get("tier", "bronze")),
                metabolic_demand=MetabolicDemand(movement_data.get("metabolic_demand", "neural")),
                biomechanics_profile=movement_data.get("biomechanics_profile"),
                description=movement_data.get("description"),
                substitution_group=movement_data.get("substitution_group")
            )
            
            self.session.add(movement)
            await self.session.flush()
            
            if "equipment" in movement_data:
                await self._add_equipment(movement, movement_data["equipment"])
            
            if "tags" in movement_data:
                await self._add_tags(movement, movement_data["tags"])
            
            if "disciplines" in movement_data:
                await self._add_disciplines(movement, movement_data["disciplines"])
            
            print(f"Created movement: {movement.name} (ID: {movement.id})")
            return movement
            
        except Exception as e:
            print(f"Error creating movement '{movement_data['name']}': {e}")
            await self.session.rollback()
            return None
    
    async def _add_equipment(self, movement: Movement, equipment_names: List[str]):
        """Add equipment relationships to movement."""
        for name in equipment_names:
            equipment = await self.get_or_create_equipment(name)
            
            existing = await self.session.execute(
                select(MovementEquipment).where(
                    MovementEquipment.movement_id == movement.id,
                    MovementEquipment.equipment_id == equipment.id
                )
            )
            
            if not existing.scalar_one_or_none():
                self.session.add(MovementEquipment(
                    movement_id=movement.id,
                    equipment_id=equipment.id
                ))
    
    async def _add_tags(self, movement: Movement, tag_names: List[str]):
        """Add tag relationships to movement."""
        for name in tag_names:
            tag = await self.get_or_create_tag(name)
            
            existing = await self.session.execute(
                select(MovementTag).where(
                    MovementTag.movement_id == movement.id,
                    MovementTag.tag_id == tag.id
                )
            )
            
            if not existing.scalar_one_or_none():
                self.session.add(MovementTag(
                    movement_id=movement.id,
                    tag_id=tag.id
                ))
    
    async def _add_disciplines(self, movement: Movement, discipline_names: List[str]):
        """Add discipline relationships to movement."""
        for name in discipline_names:
            try:
                discipline = DisciplineType(name)
                
                existing = await self.session.execute(
                    select(MovementDiscipline).where(
                        MovementDiscipline.movement_id == movement.id,
                        MovementDiscipline.discipline == discipline
                    )
                )
                
                if not existing.scalar_one_or_none():
                    self.session.add(MovementDiscipline(
                        movement_id=movement.id,
                        discipline=discipline
                    ))
            except ValueError:
                print(f"Warning: Invalid discipline '{name}' for movement {movement.name}")
    
    async def add_relationship(
        self,
        source_name: str,
        target_name: str,
        relationship_type: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Create a relationship between two movements.
        
        Args:
            source_name: Name of source movement
            target_name: Name of target movement
            relationship_type: Type of relationship (progression, regression, variation, antagonist)
            notes: Optional notes about the relationship
            
        Returns:
            True if relationship was created, False if it already exists or failed
        """
        source = await self.get_movement_by_name(source_name)
        target = await self.get_movement_by_name(target_name)
        
        if not source:
            print(f"Source movement not found: {source_name}")
            similar = await self.find_similar_movements(source_name)
            if similar:
                print(f"Did you mean: {', '.join(similar)}")
            return False
        if not target:
            print(f"Target movement not found: {target_name}")
            similar = await self.find_similar_movements(target_name)
            if similar:
                print(f"Did you mean: {', '.join(similar)}")
            return False
        
        try:
            rel_type = RelationshipType(relationship_type)
        except ValueError:
            print(f"Invalid relationship type: {relationship_type}")
            print(f"Valid types: {[rt.value for rt in RelationshipType]}")
            return False
        
        existing = await self.session.execute(
            select(MovementRelationship).where(
                MovementRelationship.source_movement_id == source.id,
                MovementRelationship.target_movement_id == target.id,
                MovementRelationship.relationship_type == rel_type
            )
        )
        
        if existing.scalar_one_or_none():
            print(f"Relationship already exists: {source_name} -> {target_name} ({relationship_type})")
            return False
        
        try:
            rel = MovementRelationship(
                source_movement_id=source.id,
                target_movement_id=target.id,
                relationship_type=rel_type,
                notes=notes
            )
            self.session.add(rel)
            print(f"Created relationship: {source_name} -> {target_name} ({relationship_type})")
            return True
            
        except Exception as e:
            print(f"Error creating relationship: {e}")
            return False
    
    async def import_from_json(self, json_file: str) -> Dict[str, int]:
        """
        Import movements and relationships from JSON file.
        
        Expected JSON structure:
        {
            "movements": [...],
            "relationships": [...]
        }
        """
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        results = {
            "movements_created": 0,
            "movements_failed": 0,
            "relationships_created": 0,
            "relationships_failed": 0
        }
        
        if "movements" in data:
            for movement_data in data["movements"]:
                movement = await self.add_movement(movement_data)
                if movement:
                    results["movements_created"] += 1
                else:
                    results["movements_failed"] += 1
        
        if "relationships" in data:
            for rel_data in data["relationships"]:
                success = await self.add_relationship(
                    rel_data["source"],
                    rel_data["target"],
                    rel_data["type"],
                    rel_data.get("notes")
                )
                if success:
                    results["relationships_created"] += 1
                else:
                    results["relationships_failed"] += 1
        
        return results
    
    async def get_movement_summary(self, movement_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed summary of a movement including relationships."""
        movement = await self.get_movement_by_name(movement_name)
        if not movement:
            return None
        
        outgoing = await self.session.execute(
            select(MovementRelationship).where(
                MovementRelationship.source_movement_id == movement.id
            )
        )
        outgoing_rels = outgoing.scalars().all()
        
        incoming = await self.session.execute(
            select(MovementRelationship).where(
                MovementRelationship.target_movement_id == movement.id
            )
        )
        incoming_rels = incoming.scalars().all()
        
        return {
            "id": movement.id,
            "name": movement.name,
            "pattern": movement.pattern.value,
            "primary_muscle": movement.primary_muscle.value,
            "tier": movement.tier.value,
            "skill_level": movement.skill_level.value,
            "outgoing_relationships": len(outgoing_rels),
            "incoming_relationships": len(incoming_rels)
        }


async def add_single_movement(movement_data: Dict[str, Any]) -> Optional[Movement]:
    """Convenience function to add a single movement."""
    async with MovementManager() as manager:
        return await manager.add_movement(movement_data)


async def add_single_relationship(
    source: str,
    target: str,
    rel_type: str,
    notes: Optional[str] = None
) -> bool:
    """Convenience function to add a single relationship."""
    async with MovementManager() as manager:
        return await manager.add_relationship(source, target, rel_type, notes)


async def import_movements_from_json(json_file: str) -> Dict[str, int]:
    """Convenience function to import from JSON file."""
    async with MovementManager() as manager:
        return await manager.import_from_json(json_file)
