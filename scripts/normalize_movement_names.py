#!/usr/bin/env python3
"""Normalize movement names with safety features and logging.

This script performs the following operations:
1. Normalizes movement names (case, spacing, punctuation)
2. Updates pattern to "plyometric" for movements with "jumping"/"Jumping" in name
3. Creates variation relationships in movement_relationships for equipment variants
4. Applies typo corrections mapping
5. Handles conflicts by skipping when pattern/muscle/region would conflict

Usage:
    python scripts/normalize_movement_names.py --dry-run --verbose
    python scripts/normalize_movement_names.py --apply
"""

import argparse
import asyncio
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import get_settings
from app.db.database import async_session_maker
from app.models.enums import MovementPattern, RelationshipType


# Typo correction mappings
TYPO_CORRECTIONS: Dict[str, str] = {
    # Common typos and variations
    "toes to bars": "toes to bar",
    "pull ups": "pull-up",
    "pull-ups": "pull-up",
    "sit ups": "sit-up",
    "sit-ups": "sit-up",
    "push ups": "push-up",
    "push-ups": "push-up",
    "dumbbell bench presses": "dumbbell bench press",
    "barbell bench presses": "barbell bench press",
    "goblet squats": "goblet squat",
    "air squats": "air squat",
    "jumping lunges": "jumping lunge",
    "lunges": "lunge",
    "burpees": "burpee",
    "kettlebell swings": "kettlebell swing",
    "deadlifts": "deadlift",
    "squats": "squat",
    "box jumps": "box jump",
    "wall balls": "wall ball",
    "double unders": "double under",
    "thrusters": "thruster",
    "snatches": "snatch",
    "cleans": "clean",
    "jerks": "jerk",
    "rows": "row",
    "planks": "plank",
    "farmers walks": "farmers walk",
    "farmers carry": "farmers walk",
    "lunging": "lunge",
}


# Equipment variants that should be linked as variations
EQUIPMENT_VARIANT_PATTERNS: Dict[str, List[str]] = {
    # Pattern: movement base names that typically have equipment variants
    "squat": ["back squat", "front squat", "goblet squat", "overhead squat"],
    "deadlift": ["conventional deadlift", "romanian deadlift", "sumo deadlift", "single leg rdl"],
    "bench press": ["barbell bench press", "dumbbell bench press", "incline bench press", "decline bench press"],
    "press": ["shoulder press", "overhead press", "push press", "strict press"],
    "row": ["barbell row", "dumbbell row", "cable row", "t-bar row", "inverted row"],
    "lunge": ["lunge", "walking lunge", "reverse lunge", "jumping lunge"],
    "pull-up": ["pull-up", "chin-up", "neutral grip pull-up"],
}


@dataclass
class NormalizationChange:
    """Record of a normalization change made."""

    movement_id: int
    old_name: str
    new_name: str
    change_type: str  # "name_normalize", "pattern_update", "typo_fix", "relationship_created"
    details: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConflictInfo:
    """Information about a normalization conflict."""

    movement_id: int
    movement_name: str
    proposed_name: str
    conflict_type: str  # "name_exists", "pattern_muscle_region_conflict"
    conflicting_with: Optional[int] = None
    conflicting_name: Optional[str] = ""


class MovementNameNormalizer:
    """Handles movement name normalization with transaction safety."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        """Initialize the normalizer.

        Args:
            dry_run: If True, don't actually apply changes
            verbose: If True, log detailed information
        """
        self.dry_run = dry_run
        self.verbose = verbose
        self.changes: List[NormalizationChange] = []
        self.conflicts: List[ConflictInfo] = []
        self.skipped: List[Tuple[int, str, str]] = []

        # Setup logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging based on verbosity."""
        log_level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

    def _normalize_name_case(self, name: str) -> str:
        """Normalize case of movement name.

        Args:
            name: Original movement name

        Returns:
            Title-cased name with proper noun handling
        """
        # Special proper nouns that should maintain specific capitalization
        proper_nouns = ["Romanian", "Sumo", "Turkish", "Bulgarian", "Nordic"]

        # Title case the name
        normalized = name.title()

        # Preserve proper noun capitalization
        for proper in proper_nouns:
            normalized = re.sub(
                f"\\b{proper.lower()}\\b",
                proper,
                normalized,
                flags=re.IGNORECASE,
            )

        return normalized

    def _normalize_spacing_punctuation(self, name: str) -> str:
        """Normalize spacing and punctuation in movement name.

        Args:
            name: Movement name

        Returns:
            Name with normalized spacing and punctuation
        """
        # Remove extra spaces
        name = re.sub(r"\s+", " ", name)

        # Remove leading/trailing spaces
        name = name.strip()

        # Standardize hyphens: use hyphen for compound words
        name = re.sub(r"\s*-\s*", "-", name)

        # Standardize apostrophes
        name = name.replace("'", "'").replace("'", "'")

        return name

    def _normalize_name(self, name: str) -> str:
        """Apply full normalization to movement name.

        Args:
            name: Original movement name

        Returns:
            Fully normalized name
        """
        # First apply typo corrections
        lower_name = name.lower().strip()
        if lower_name in TYPO_CORRECTIONS:
            name = TYPO_CORRECTIONS[lower_name]
            if self.verbose:
                self.logger.debug(f"Applied typo correction: '{name}' -> '{TYPO_CORRECTIONS[lower_name]}'")

        # Normalize case
        name = self._normalize_name_case(name)

        # Normalize spacing and punctuation
        name = self._normalize_spacing_punctuation(name)

        return name

    def _detect_plyometric_movement(self, name: str) -> bool:
        """Detect if movement is plyometric based on name.

        Args:
            name: Movement name

        Returns:
            True if movement appears to be plyometric
        """
        return bool(re.search(r"\bjumping\b", name, re.IGNORECASE))

    async def _check_name_exists(
        self, session, name: str, exclude_id: Optional[int] = None
    ) -> Optional[Tuple[int, str]]:
        """Check if a movement name already exists.

        Args:
            session: Database session
            name: Name to check
            exclude_id: Movement ID to exclude from check

        Returns:
            Tuple of (existing_id, existing_name) if found, None otherwise
        """
        if exclude_id:
            query = text("""
                SELECT id, name
                FROM movements
                WHERE LOWER(name) = :name
                AND id != :exclude_id
            """)
            result = await session.execute(
                query, {"name": name.lower(), "exclude_id": exclude_id}
            )
        else:
            query = text("""
                SELECT id, name
                FROM movements
                WHERE LOWER(name) = :name
            """)
            result = await session.execute(
                query, {"name": name.lower()}
            )

        row = result.fetchone()
        if row:
            return (row[0], row[1])
        return None

    async def _check_pattern_muscle_region_conflict(
        self,
        session,
        movement_id: int,
        new_name: str,
        pattern: str,
        primary_muscle: str,
        primary_region: str,
    ) -> bool:
        """Check if normalized name would create pattern/muscle/region conflict.

        Args:
            session: Database session
            movement_id: Current movement ID
            new_name: Proposed new name
            pattern: Current pattern
            primary_muscle: Current primary muscle
            primary_region: Current primary region

        Returns:
            True if conflict exists
        """
        # Find movements with same name
        existing = await self._check_name_exists(session, new_name, exclude_id=movement_id)

        if not existing:
            return False

        existing_id, _ = existing

        # Get the existing movement's pattern, muscle, region
        result = await session.execute(
            text("""
                SELECT pattern, primary_muscle, primary_region
                FROM movements
                WHERE id = :id
            """), {"id": existing_id}
        )

        row = result.fetchone()
        if not row:
            return False

        existing_pattern, existing_muscle, existing_region = row

        # Check if any of the key attributes differ
        if (
            existing_pattern != pattern
            or existing_muscle != primary_muscle
            or existing_region != primary_region
        ):
            self.conflicts.append(
                ConflictInfo(
                    movement_id=movement_id,
                    movement_name=new_name,
                    proposed_name=new_name,
                    conflict_type="pattern_muscle_region_conflict",
                    conflicting_with=existing_id,
                )
            )
            return True

        return False

    async def _create_variation_relationship(
        self,
        session,
        source_id: int,
        target_id: int,
        notes: str = "",
    ) -> bool:
        """Create a variation relationship between two movements.

        Args:
            session: Database session
            source_id: Source movement ID
            target_id: Target movement ID
            notes: Optional notes for the relationship

        Returns:
            True if relationship was created, False if it already exists
        """
        # Check if relationship already exists
        result = await session.execute(
            text("""
                SELECT id
                FROM movement_relationships
                WHERE source_movement_id = :source_id
                AND target_movement_id = :target_id
                AND relationship_type = :rel_type
            """),
            {
                "source_id": source_id,
                "target_id": target_id,
                "rel_type": RelationshipType.VARIATION.value
            }
        )

        if result.fetchone():
            if self.verbose:
                self.logger.debug(f"Relationship already exists: {source_id} -> {target_id}")
            return False

        # Create the relationship
        await session.execute(
            text("""
                INSERT INTO movement_relationships
                (source_movement_id, target_movement_id, relationship_type, notes)
                VALUES (:source_id, :target_id, :rel_type, :notes)
            """),
            {
                "source_id": source_id,
                "target_id": target_id,
                "rel_type": RelationshipType.VARIATION.value,
                "notes": notes,
            }
        )

        return True

    async def _find_equipment_variants(
        self, session, movement_id: int, name: str
    ) -> List[Tuple[int, str]]:
        """Find potential equipment variant movements for a given movement.

        Args:
            session: Database session
            movement_id: Current movement ID
            name: Current movement name

        Returns:
            List of (variant_id, variant_name) tuples
        """
        variants = []
        lower_name = name.lower()

        # Check each equipment variant pattern
        for base_name, variants_list in EQUIPMENT_VARIANT_PATTERNS.items():
            if base_name in lower_name:
                # Get pattern, muscle, region for current movement
                result = await session.execute(
                    text("""
                        SELECT pattern, primary_muscle, primary_region
                        FROM movements
                        WHERE id = :id
                    """), {"id": movement_id}
                )

                row = result.fetchone()
                if not row:
                    continue

                pattern, primary_muscle, primary_region = row

                # Find movements with same pattern/muscle/region but different names
                result = await session.execute(
                    text("""
                        SELECT id, name
                        FROM movements
                        WHERE pattern = :pattern
                        AND primary_muscle = :muscle
                        AND primary_region = :region
                        AND id != :id
                    """),
                    {
                        "pattern": pattern,
                        "muscle": primary_muscle,
                        "region": primary_region,
                        "id": movement_id
                    }
                )

                for variant_row in result.fetchall():
                    variant_id, variant_name = variant_row
                    # Check if it's a different equipment variant
                    if variant_name.lower() != lower_name:
                        # Check if names are semantically related (share base name)
                        variant_lower = variant_name.lower()
                        if base_name in variant_lower:
                            variants.append((variant_id, variant_name))

        return variants

    async def normalize_movement_names(self) -> Dict[str, int]:
        """Normalize all movement names in the database.

        Returns:
            Dictionary with counts of various operations
        """
        stats = {
            "name_normalized": 0,
            "pattern_updated": 0,
            "typo_fixed": 0,
            "relationships_created": 0,
            "conflicts": 0,
            "skipped": 0,
        }

        self.logger.info("=" * 60)
        self.logger.info("MOVEMENT NAME NORMALIZATION")
        self.logger.info("=" * 60)
        if self.dry_run:
            self.logger.info("DRY RUN MODE - No changes will be applied")
        self.logger.info("=" * 60)

        async with async_session_maker() as session:
            try:
                # Get all movements
                result = await session.execute(
                    select(
                        text("id"),
                        text("name"),
                        text("pattern"),
                        text("primary_muscle"),
                        text("primary_region")
                    ).select_from(text("movements")).order_by(text("id"))
                )

                movements = result.fetchall()

                self.logger.info(f"Found {len(movements)} movements to process")

                for movement_id, name, pattern, primary_muscle, primary_region in movements:
                    original_name = name

                    # Step 1: Check for plyometric pattern update
                    if self._detect_plyometric_movement(name):
                        new_pattern = MovementPattern.PLYOMETRIC.value
                        if pattern != new_pattern:
                            self.logger.info(
                                f"Movement {movement_id}: '{name}' - Pattern '{pattern}' -> '{new_pattern}'"
                            )

                            if not self.dry_run:
                                await session.execute(
                                    text("""
                                        UPDATE movements
                                        SET pattern = :pattern
                                        WHERE id = :id
                                    """),
                                    {"pattern": new_pattern, "id": movement_id}
                                )

                            self.changes.append(
                                NormalizationChange(
                                    movement_id=movement_id,
                                    old_name=name,
                                    new_name=name,
                                    change_type="pattern_update",
                                    details=f"Pattern '{pattern}' -> '{new_pattern}'",
                                )
                            )
                            stats["pattern_updated"] += 1
                            pattern = new_pattern  # Update for subsequent checks

                    # Step 2: Normalize the name
                    new_name = self._normalize_name(name)

                    # Check if name changed
                    if new_name != original_name:
                        # Check for conflicts
                        name_exists = await self._check_name_exists(
                            session, new_name, exclude_id=movement_id
                        )

                        if name_exists:
                            existing_id, existing_name = name_exists
                            self.logger.warning(
                                f"Movement {movement_id}: Cannot rename '{original_name}' -> '{new_name}' - "
                                f"already exists as movement {existing_id}"
                            )
                            self.conflicts.append(
                                ConflictInfo(
                                    movement_id=movement_id,
                                    movement_name=original_name,
                                    proposed_name=new_name,
                                    conflict_type="name_exists",
                                    conflicting_with=existing_id,
                                    conflicting_name=existing_name,
                                )
                            )
                            stats["conflicts"] += 1
                            continue

                        # Check pattern/muscle/region conflict
                        if await self._check_pattern_muscle_region_conflict(
                            session, movement_id, new_name, pattern, primary_muscle, primary_region
                        ):
                            self.logger.warning(
                                f"Movement {movement_id}: Skipping '{original_name}' -> '{new_name}' - "
                                f"would create pattern/muscle/region conflict"
                            )
                            stats["conflicts"] += 1
                            continue

                        # Apply the name change
                        self.logger.info(
                            f"Movement {movement_id}: '{original_name}' -> '{new_name}'"
                        )

                        if not self.dry_run:
                            await session.execute(
                                text("""
                                    UPDATE movements
                                    SET name = :name
                                    WHERE id = :id
                                """),
                                {"name": new_name, "id": movement_id}
                            )

                        # Determine change type
                        change_type = "name_normalize"
                        if original_name.lower() in TYPO_CORRECTIONS:
                            change_type = "typo_fix"

                        self.changes.append(
                            NormalizationChange(
                                movement_id=movement_id,
                                old_name=original_name,
                                new_name=new_name,
                                change_type=change_type,
                                details=f"Name normalized from '{original_name}'",
                            )
                        )

                        if change_type == "typo_fix":
                            stats["typo_fixed"] += 1
                        else:
                            stats["name_normalized"] += 1

                        name = new_name  # Update for subsequent checks

                    # Step 3: Create variation relationships for equipment variants
                    variants = await self._find_equipment_variants(session, movement_id, name)

                    for variant_id, variant_name in variants:
                        # Create bidirectional variation relationships
                        created = await self._create_variation_relationship(
                            session,
                            source_id=movement_id,
                            target_id=variant_id,
                            notes=f"Equipment variant: '{name}' and '{variant_name}'",
                        )

                        if created:
                            self.logger.info(
                                f"Created variation relationship: {movement_id} ('{name}') "
                                f"<-> {variant_id} ('{variant_name}')"
                            )

                            self.changes.append(
                                NormalizationChange(
                                    movement_id=movement_id,
                                    old_name=name,
                                    new_name=name,
                                    change_type="relationship_created",
                                    details=f"Variation relationship with {variant_id} ('{variant_name}')",
                                )
                            )
                            stats["relationships_created"] += 1

                        # Create reverse relationship
                        await self._create_variation_relationship(
                            session,
                            source_id=variant_id,
                            target_id=movement_id,
                            notes=f"Equipment variant: '{variant_name}' and '{name}'",
                        )

                # Commit changes if not in dry-run mode
                if not self.dry_run:
                    await session.commit()
                    self.logger.info("All changes committed successfully")
                else:
                    await session.rollback()
                    self.logger.info("Dry run complete - changes rolled back")

            except SQLAlchemyError as e:
                await session.rollback()
                self.logger.error(f"Database error: {e}")
                raise

        return stats

    def print_summary(self, stats: Dict[str, int]) -> None:
        """Print a summary of normalization operations.

        Args:
            stats: Statistics dictionary from normalization
        """
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("NORMALIZATION SUMMARY")
        self.logger.info("=" * 60)
        self.logger.info(f"Names normalized:     {stats['name_normalized']}")
        self.logger.info(f"Patterns updated:     {stats['pattern_updated']}")
        self.logger.info(f"Typos fixed:          {stats['typo_fixed']}")
        self.logger.info(f"Relationships created: {stats['relationships_created']}")
        self.logger.info(f"Conflicts detected:   {stats['conflicts']}")
        self.logger.info(f"Total changes:        {len(self.changes)}")
        self.logger.info("=" * 60)

        if self.verbose and self.changes:
            self.logger.info("\nDetailed changes:")
            for change in self.changes:
                self.logger.debug(
                    f"  [{change.change_type}] ID {change.movement_id}: "
                    f"'{change.old_name}' -> '{change.new_name}' - {change.details}"
                )

        if self.conflicts:
            self.logger.info("\nConflicts detected:")
            for conflict in self.conflicts:
                if conflict.conflict_type == "name_exists":
                    self.logger.warning(
                        f"  [{conflict.conflict_type}] Movement {conflict.movement_id}: "
                        f"'{conflict.movement_name}' -> '{conflict.proposed_name}' "
                        f"(conflicts with {conflict.conflicting_with}: '{conflict.conflicting_name}')"
                    )
                else:
                    self.logger.warning(
                        f"  [{conflict.conflict_type}] Movement {conflict.movement_id}: "
                        f"'{conflict.movement_name}' -> '{conflict.proposed_name}'"
                    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Normalize movement names with safety features",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with verbose output
  python scripts/normalize_movement_names.py --dry-run --verbose

  # Apply changes
  python scripts/normalize_movement_names.py --apply
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to database (cannot be used with --dry-run)",
    )

    return parser.parse_args()


async def main() -> None:
    """Main entry point for the script."""
    args = parse_arguments()

    # Validate arguments
    if args.dry_run and args.apply:
        print("Error: Cannot use --dry-run and --apply together")
        sys.exit(1)

    if not args.dry_run and not args.apply:
        print("Error: Must specify either --dry-run or --apply")
        sys.exit(1)

    # Verify database connection
    settings = get_settings()
    if not settings.database_url:
        print("Error: DATABASE_URL not configured")
        sys.exit(1)

    # Create normalizer and run
    normalizer = MovementNameNormalizer(
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    try:
        stats = await normalizer.normalize_movement_names()
        normalizer.print_summary(stats)

        # Note: conflicts are expected when duplicates exist
        # The merge script will handle resolving these conflicts

    except Exception as e:
        print(f"Error during normalization: {e}")
        if normalizer.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
