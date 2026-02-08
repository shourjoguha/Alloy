#!/usr/bin/env python3
"""Detect duplicate movements in the PostgreSQL database.

This script identifies duplicate movements based on multiple criteria:
1. Same pattern + primary_muscle + primary_region + equipment
2. Plyometric movements (name contains "jumping" or "Jumping")
3. Exact name duplicates (case-insensitive)
4. Fuzzy matches using difflib SequenceMatcher with threshold > 0.85

Results are output in structured JSON format with similarity scores.
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from typing import Dict, List, Set, Tuple, Any, Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import async_session_maker
from app.models.movement import Movement, MovementEquipment, Equipment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('detect_movement_duplicates.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class DuplicateGroup:
    """Represents a group of duplicate movements."""
    duplicate_type: str
    criteria: Dict[str, Any]
    movements: List[Dict[str, Any]]
    similarity_scores: Optional[List[float]] = None
    match_count: int = 0


@dataclass
class DuplicateSummary:
    """Summary statistics for duplicate detection."""
    total_movements: int
    total_duplicates: int
    duplicate_groups: Dict[str, int]
    affected_movement_ids: Set[int]


class MovementDuplicateDetector:
    """Detects duplicate movements using various criteria."""

    FUZZY_THRESHOLD = 0.85
    PLYOMETRIC_KEYWORDS = ["jumping", "Jumping"]

    def __init__(self, session: AsyncSession):
        """Initialize the duplicate detector."""
        self.session = session
        self.duplicate_groups: List[DuplicateGroup] = []
        self.summary = DuplicateSummary(
            total_movements=0,
            total_duplicates=0,
            duplicate_groups=defaultdict(int),
            affected_movement_ids=set()
        )

    async def fetch_all_movements(self) -> List[Movement]:
        """Fetch all movements with their equipment."""
        logger.info("Fetching all movements from database...")
        
        query = select(Movement).order_by(Movement.id)
        result = await self.session.execute(query)
        movements = result.scalars().all()
        
        logger.info(f"Fetched {len(movements)} movements")
        self.summary.total_movements = len(movements)
        
        return movements

    async def fetch_movement_equipment(self) -> Dict[int, Set[str]]:
        """Fetch equipment for each movement."""
        logger.info("Fetching movement equipment...")
        
        query = (
            select(MovementEquipment.movement_id, Equipment.name)
            .join(Equipment, MovementEquipment.equipment_id == Equipment.id)
        )
        result = await self.session.execute(query)
        
        movement_equipment: Dict[int, Set[str]] = defaultdict(set)
        for movement_id, equipment_name in result:
            movement_equipment[movement_id].add(equipment_name)
        
        logger.info(f"Equipment loaded for {len(movement_equipment)} movements")
        return movement_equipment

    def _get_equipment_key(self, equipment_set: Set[str]) -> str:
        """Convert equipment set to a sorted string key for comparison."""
        return ','.join(sorted(equipment_set)) if equipment_set else 'none'

    async def detect_attribute_duplicates(
        self,
        movements: List[Movement],
        movement_equipment: Dict[int, Set[str]]
    ) -> None:
        """Detect duplicates based on pattern + primary_muscle + primary_region + equipment."""
        logger.info("Detecting attribute-based duplicates...")
        
        # Group movements by attributes
        attribute_groups: Dict[Tuple, List[Movement]] = defaultdict(list)
        
        for movement in movements:
            equipment_key = self._get_equipment_key(movement_equipment.get(movement.id, set()))
            key = (
                movement.pattern,
                movement.primary_muscle,
                movement.primary_region,
                equipment_key
            )
            attribute_groups[key].append(movement)
        
        # Find groups with more than one movement
        for key, group_movements in attribute_groups.items():
            if len(group_movements) > 1:
                criteria = {
                    'pattern': key[0],
                    'primary_muscle': key[1],
                    'primary_region': key[2],
                    'equipment': key[3]
                }
                
                movements_data = [
                    {
                        'id': m.id,
                        'name': m.name,
                        'pattern': m.pattern,
                        'primary_muscle': m.primary_muscle,
                        'primary_region': m.primary_region
                    }
                    for m in group_movements
                ]
                
                duplicate_group = DuplicateGroup(
                    duplicate_type='attribute_match',
                    criteria=criteria,
                    movements=movements_data,
                    match_count=len(group_movements)
                )
                
                self.duplicate_groups.append(duplicate_group)
                self.summary.duplicate_groups['attribute_match'] += 1
                self.summary.affected_movement_ids.update(m.id for m in group_movements)
                
                logger.info(
                    f"Found attribute duplicate group: {criteria['pattern']} + "
                    f"{criteria['primary_muscle']} + {criteria['primary_region']} + "
                    f"{criteria['equipment']} ({len(group_movements)} movements)"
                )

    async def detect_plyometric_duplicates(
        self,
        movements: List[Movement],
        movement_equipment: Dict[int, Set[str]]
    ) -> None:
        """Detect plyometric movements (name contains 'jumping' or 'Jumping')."""
        logger.info("Detecting plyometric movements...")
        
        plyometric_movements = []
        
        for movement in movements:
            for keyword in self.PLYOMETRIC_KEYWORDS:
                if keyword in movement.name:
                    equipment = list(movement_equipment.get(movement.id, set()))
                    plyometric_movements.append({
                        'id': movement.id,
                        'name': movement.name,
                        'pattern': movement.pattern,
                        'primary_muscle': movement.primary_muscle,
                        'primary_region': movement.primary_region,
                        'equipment': equipment
                    })
                    break
        
        if plyometric_movements:
            duplicate_group = DuplicateGroup(
                duplicate_type='plyometric',
                criteria={'keywords': self.PLYOMETRIC_KEYWORDS},
                movements=plyometric_movements,
                match_count=len(plyometric_movements)
            )
            
            self.duplicate_groups.append(duplicate_group)
            self.summary.duplicate_groups['plyometric'] += 1
            self.summary.affected_movement_ids.update(m['id'] for m in plyometric_movements)
            
            logger.info(f"Found {len(plyometric_movements)} plyometric movements")

    async def detect_exact_name_duplicates(
        self,
        movements: List[Movement],
        movement_equipment: Dict[int, Set[str]]
    ) -> None:
        """Detect exact name duplicates (case-insensitive)."""
        logger.info("Detecting exact name duplicates (case-insensitive)...")
        
        name_groups: Dict[str, List[Movement]] = defaultdict(list)
        
        for movement in movements:
            normalized_name = movement.name.lower().strip()
            name_groups[normalized_name].append(movement)
        
        # Find groups with more than one movement
        for normalized_name, group_movements in name_groups.items():
            if len(group_movements) > 1:
                criteria = {'normalized_name': normalized_name}
                
                movements_data = [
                    {
                        'id': m.id,
                        'name': m.name,
                        'pattern': m.pattern,
                        'primary_muscle': m.primary_muscle,
                        'primary_region': m.primary_region,
                        'equipment': list(movement_equipment.get(m.id, set()))
                    }
                    for m in group_movements
                ]
                
                duplicate_group = DuplicateGroup(
                    duplicate_type='exact_name_match',
                    criteria=criteria,
                    movements=movements_data,
                    match_count=len(group_movements)
                )
                
                self.duplicate_groups.append(duplicate_group)
                self.summary.duplicate_groups['exact_name_match'] += 1
                self.summary.affected_movement_ids.update(m.id for m in group_movements)
                
                logger.info(
                    f"Found exact name duplicate group: '{normalized_name}' "
                    f"({len(group_movements)} movements)"
                )

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using SequenceMatcher."""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    async def detect_fuzzy_matches(
        self,
        movements: List[Movement],
        movement_equipment: Dict[int, Set[str]]
    ) -> None:
        """Detect fuzzy name matches using SequenceMatcher with threshold > 0.85."""
        logger.info("Detecting fuzzy name matches...")
        
        processed_pairs: Set[Tuple[int, int]] = set()
        fuzzy_groups: List[Tuple[float, List[Movement]]] = []
        
        # Compare each movement with every other movement
        for i, movement1 in enumerate(movements):
            for j in range(i + 1, len(movements)):
                movement2 = movements[j]
                
                # Skip if this pair has already been processed
                pair_key = tuple(sorted([movement1.id, movement2.id]))
                if pair_key in processed_pairs:
                    continue
                
                # Calculate similarity
                similarity = self._calculate_similarity(movement1.name, movement2.name)
                
                if similarity > self.FUZZY_THRESHOLD:
                    # Check if this forms a group with existing matches
                    found_group = False
                    for idx, (group_similarity, group_movements) in enumerate(fuzzy_groups):
                        if movement1 in group_movements or movement2 in group_movements:
                            # Add to existing group
                            if movement1 not in group_movements:
                                group_movements.append(movement1)
                            if movement2 not in group_movements:
                                group_movements.append(movement2)
                            # Update similarity to minimum in group
                            fuzzy_groups[idx] = (min(group_similarity, similarity), group_movements)
                            found_group = True
                            break
                    
                    if not found_group:
                        # Create new group
                        fuzzy_groups.append((similarity, [movement1, movement2]))
                    
                    processed_pairs.add(pair_key)
                    logger.info(
                        f"Fuzzy match: '{movement1.name}' ~ '{movement2.name}' "
                        f"(similarity: {similarity:.3f})"
                    )
        
        # Create duplicate groups from fuzzy matches
        for similarity, group_movements in fuzzy_groups:
            criteria = {
                'similarity_threshold': self.FUZZY_THRESHOLD,
                'average_similarity': round(similarity, 3)
            }
            
            movements_data = [
                {
                    'id': m.id,
                    'name': m.name,
                    'pattern': m.pattern,
                    'primary_muscle': m.primary_muscle,
                    'primary_region': m.primary_region,
                    'equipment': list(movement_equipment.get(m.id, set()))
                }
                for m in group_movements
            ]
            
            duplicate_group = DuplicateGroup(
                duplicate_type='fuzzy_name_match',
                criteria=criteria,
                movements=movements_data,
                similarity_scores=[similarity],
                match_count=len(group_movements)
            )
            
            self.duplicate_groups.append(duplicate_group)
            self.summary.duplicate_groups['fuzzy_name_match'] += 1
            self.summary.affected_movement_ids.update(m.id for m in group_movements)
        
        logger.info(f"Found {len(fuzzy_groups)} fuzzy match groups")

    async def detect_all_duplicates(self) -> Dict[str, Any]:
        """Run all duplicate detection methods and return results."""
        logger.info("=" * 80)
        logger.info("Starting movement duplicate detection")
        logger.info("=" * 80)
        
        # Fetch data
        movements = await self.fetch_all_movements()
        movement_equipment = await self.fetch_movement_equipment()
        
        # Run all detection methods
        await self.detect_attribute_duplicates(movements, movement_equipment)
        await self.detect_plyometric_duplicates(movements, movement_equipment)
        await self.detect_exact_name_duplicates(movements, movement_equipment)
        await self.detect_fuzzy_matches(movements, movement_equipment)
        
        # Calculate total duplicates
        self.summary.total_duplicates = len(self.summary.affected_movement_ids)
        
        # Log summary
        logger.info("=" * 80)
        logger.info("Duplicate Detection Summary")
        logger.info("=" * 80)
        logger.info(f"Total movements scanned: {self.summary.total_movements}")
        logger.info(f"Total duplicates found: {self.summary.total_duplicates}")
        logger.info(f"Unique affected movements: {len(self.summary.affected_movement_ids)}")
        logger.info("Duplicate groups by type:")
        for dup_type, count in self.summary.duplicate_groups.items():
            logger.info(f"  - {dup_type}: {count} groups")
        logger.info("=" * 80)
        
        return self._format_output()

    def _format_output(self) -> Dict[str, Any]:
        """Format output as structured JSON."""
        return {
            'summary': {
                'total_movements': self.summary.total_movements,
                'total_duplicates': self.summary.total_duplicates,
                'unique_affected_movements': len(self.summary.affected_movement_ids),
                'duplicate_groups_by_type': dict(self.summary.duplicate_groups)
            },
            'duplicate_groups': [
                {
                    'duplicate_type': group.duplicate_type,
                    'criteria': group.criteria,
                    'movements': group.movements,
                    'similarity_scores': group.similarity_scores,
                    'match_count': group.match_count
                }
                for group in self.duplicate_groups
            ],
            'affected_movement_ids': sorted(list(self.summary.affected_movement_ids))
        }


async def main():
    """Main function to run duplicate detection."""
    async with async_session_maker() as session:
        detector = MovementDuplicateDetector(session)
        results = await detector.detect_all_duplicates()
        
        # Write results to JSON file
        output_file = 'movement_duplicates_report.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results written to {output_file}")
        logger.info(f"Total duplicate groups found: {len(results['duplicate_groups'])}")
        
        # Print summary to console
        print("\n" + "=" * 80)
        print("DUPLICATE DETECTION COMPLETE")
        print("=" * 80)
        print(f"Total movements scanned: {results['summary']['total_movements']}")
        print(f"Total duplicates found: {results['summary']['total_duplicates']}")
        print(f"Unique affected movements: {results['summary']['unique_affected_movements']}")
        print("\nDuplicate groups by type:")
        for dup_type, count in results['summary']['duplicate_groups_by_type'].items():
            print(f"  - {dup_type}: {count} groups")
        print(f"\nResults saved to: {output_file}")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
