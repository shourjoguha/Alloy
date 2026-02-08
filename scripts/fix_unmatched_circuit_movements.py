#!/usr/bin/env python3
"""
Script to fix 18 unmatched circuit movement records by mapping them to correct movement IDs.

Mappings to apply:
1. "Row" -> movement id 433 ("200/Row")
2. "Wall Ball Shots" -> movement id 408 ("Wall Ball")
3. "Medicine Ball To A Target" -> movement id 46 ("Medicine Ball Slam")
4. "Dumbbell Bench Presses" -> find closest existing dumbbell bench press movement or create new if needed
5. "Kettlebell Turkish Get Ups, Right Arm" and "Left Arm" variants -> movement id 406 ("kettlebell Turkish get ups")
6. "toes to bars" -> "toes to bar" if it exists or mark for manual review
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models.movement import Movement
from app.models.circuit_extended import CircuitMelted

import logging

logger = logging.getLogger(__name__)


# MAPPING DEFINITIONS
MAPPINGS: Dict[str, str] = {
    "Row": "Rowing Machine",
    "200/Row": "Rowing Machine",
    "Wall Ball Shots": "Wall Ball",
    "Medicine Ball To A Target": "Wall Ball",
}

# Movement IDs for known mappings
KNOWN_MAPPINGS: Dict[str, int] = {
    "Rowing Machine": 400,
    "Wall Ball": 408,
    "kettlebell Turkish get ups": 406,
}

# Variants that map to the same base movement
TURKISH_GET_UP_VARIANTS = [
    "Kettlebell Turkish Get Ups, Right Arm",
    "Kettlebell Turkish Get Ups, Left Arm",
    "Kettlebell Turkish Get Ups, Right Arm, 10 kg",
    "Kettlebell Turkish Get Ups, Left Arm, 10 kg",
    "Kettlebell Turkish Get Ups, Right Arm, 8 kg",
    "Kettlebell Turkish Get Ups, Left Arm, 8 kg",
]


async def find_movement_id_by_name(session: AsyncSession, name: str) -> Optional[int]:
    """Find movement ID by exact name match."""
    result = await session.execute(
        select(Movement.id).where(Movement.name == name)
    )
    return result.scalar_one_or_none()


async def find_closest_dumbbell_bench_press(session: AsyncSession) -> Optional[int]:
    """Find the closest matching dumbbell bench press movement."""
    # Try common variations
    variations = [
        "Dumbbell Bench Press",
        "Dumbbell Flat Bench Press",
        "Dumbbell Bench Press (flat)",
        "Dumbbell Bench Press - Flat",
        "Dumbbell Chest Press",
        "Dumbbell Chest Press (flat)",
    ]

    for variation in variations:
        movement_id = await find_movement_id_by_name(session, variation)
        if movement_id:
            logger.info(f"Found dumbbell bench press variation: {variation} (id: {movement_id})")
            return movement_id

    # Try fuzzy search for dumbbell bench press
    result = await session.execute(
        select(Movement.id, Movement.name)
        .where(Movement.name.ilike("%dumbbell%bench%press%"))
        .order_by(Movement.name)
        .limit(10)
    )
    movements = result.all()

    if movements:
        logger.info(f"Found {len(movements)} dumbbell bench press candidates:")
        for movement_id, name in movements:
            logger.info(f"  - {name} (id: {movement_id})")
        # Return the first match
        return movements[0][0]

    logger.warning("No dumbbell bench press movement found")
    return None


async def find_toes_to_bar_movement(session: AsyncSession) -> Optional[int]:
    """Find toes to bar movement (checking both singular and plural forms)."""
    # Try exact matches first
    for name in ["toes to bar", "toes to bars"]:
        movement_id = await find_movement_id_by_name(session, name)
        if movement_id:
            logger.info(f"Found toes to bar movement: {name} (id: {movement_id})")
            return movement_id

    # Try fuzzy search
    result = await session.execute(
        select(Movement.id, Movement.name)
        .where(Movement.name.ilike("%toe%bar%"))
        .order_by(Movement.name)
        .limit(10)
    )
    movements = result.all()

    if movements:
        logger.info(f"Found {len(movements)} toe-to-bar related movements:")
        for movement_id, name in movements:
            logger.info(f"  - {name} (id: {movement_id})")
        # Prefer singular form if available
        for movement_id, name in movements:
            if name.lower() == "toes to bar":
                return movement_id
        return movements[0][0]

    logger.warning("No toes to bar movement found")
    return None


async def get_unmatched_circuit_movements(session: AsyncSession) -> List[Tuple[int, str, int]]:
    """Get all circuit movements with NULL movement_id."""
    result = await session.execute(
        select(
            CircuitMelted.id,
            CircuitMelted.movement_name,
            CircuitMelted.circuit_id
        )
        .where(CircuitMelted.movement_id.is_(None))
        .order_by(CircuitMelted.circuit_id, CircuitMelted.movement_name)
    )
    return result.all()


async def build_mapping_dict(session: AsyncSession) -> Dict[str, Tuple[int, str]]:
    """
    Build a mapping dictionary from unmatched movement names to (movement_id, target_name).

    Returns a dict with format: {unmatched_name: (movement_id, target_name)}
    """
    mapping: Dict[str, Tuple[int, str]] = {}

    # Apply simple mappings from MAPPINGS dict
    for unmatched_name, target_name in MAPPINGS.items():
        if target_name in KNOWN_MAPPINGS:
            movement_id = KNOWN_MAPPINGS[target_name]
            mapping[unmatched_name] = (movement_id, target_name)
        else:
            movement_id = await find_movement_id_by_name(session, target_name)
            if movement_id:
                mapping[unmatched_name] = (movement_id, target_name)
                KNOWN_MAPPINGS[target_name] = movement_id
            else:
                logger.warning(f"Could not find movement: {target_name}")

    # Map Turkish Get Up variants
    for variant in TURKISH_GET_UP_VARIANTS:
        target_name = "kettlebell Turkish get ups"
        if target_name in KNOWN_MAPPINGS:
            movement_id = KNOWN_MAPPINGS[target_name]
            mapping[variant] = (movement_id, target_name)
        else:
            movement_id = await find_movement_id_by_name(session, target_name)
            if movement_id:
                mapping[variant] = (movement_id, target_name)
                KNOWN_MAPPINGS[target_name] = movement_id

    # Find dumbbell bench press
    dbp_movement_id = await find_closest_dumbbell_bench_press(session)
    if dbp_movement_id:
        # Map all variants of dumbbell bench press
        dbp_variants = [
            "Dumbbell Bench Presses",
            "Dumbbell Bench Press",
            "Dumbbell Flat Bench Press",
        ]
        for variant in dbp_variants:
            mapping[variant] = (dbp_movement_id, "Dumbbell Bench Press")

    # Find toes to bar
    ttb_movement_id = await find_toes_to_bar_movement(session)
    if ttb_movement_id:
        # Map both singular and plural forms
        for variant in ["toes to bar", "toes to bars"]:
            mapping[variant] = (ttb_movement_id, "toes to bar")

    return mapping


async def apply_mappings(
    session: AsyncSession,
    unmatched: List[Tuple[int, str, int]],
    mapping: Dict[str, Tuple[int, str]],
    dry_run: bool = True,
    verbose: bool = False,
) -> Dict[str, List[Dict]]:
    """
    Apply mappings to unmatched circuit movements.

    Returns a summary dict with keys: 'updated', 'skipped', 'manual_review'
    """
    summary = {
        "updated": [],
        "skipped": [],
        "manual_review": [],
    }

    for circuit_movement_id, movement_name, circuit_id in unmatched:
        if movement_name in mapping:
            movement_id, target_name = mapping[movement_name]
            summary["updated"].append({
                "circuit_movement_id": circuit_movement_id,
                "circuit_id": circuit_id,
                "original_name": movement_name,
                "target_name": target_name,
                "movement_id": movement_id,
            })

            if not dry_run:
                await session.execute(
                    text("""
                        UPDATE circuits_melted
                        SET movement_id = :movement_id
                        WHERE id = :circuit_movement_id
                    """),
                    {"movement_id": movement_id, "circuit_movement_id": circuit_movement_id}
                )
                if verbose:
                    logger.info(
                        f"Updated circuit_movement {circuit_movement_id}: "
                        f"'{movement_name}' -> {target_name} (id: {movement_id})"
                    )
            elif verbose:
                logger.info(
                    f"[DRY RUN] Would update circuit_movement {circuit_movement_id}: "
                    f"'{movement_name}' -> {target_name} (id: {movement_id})"
                )
        else:
            summary["manual_review"].append({
                "circuit_movement_id": circuit_movement_id,
                "circuit_id": circuit_id,
                "movement_name": movement_name,
            })
            if verbose:
                logger.warning(
                    f"No mapping found for '{movement_name}' in circuit {circuit_id} "
                    f"(circuit_movement_id: {circuit_movement_id})"
                )

    return summary


def print_summary(summary: Dict[str, List[Dict]], verbose: bool = False):
    """Print a formatted summary of the changes."""
    print("\n" + "=" * 80)
    print("CIRCUIT MOVEMENT FIX SUMMARY")
    print("=" * 80)

    print(f"\nRecords to be updated: {len(summary['updated'])}")
    if summary['updated']:
        print("\nUpdates:")
        for i, update in enumerate(summary['updated'], 1):
            print(
                f"  {i}. Circuit {update['circuit_id']} (cm_id: {update['circuit_movement_id']})\n"
                f"     '{update['original_name']}' -> {update['target_name']} (id: {update['movement_id']})"
            )
            if verbose:
                print(f"     Full details: {update}")

    print(f"\nRecords requiring manual review: {len(summary['manual_review'])}")
    if summary['manual_review']:
        print("\nManual Review Required:")
        for i, item in enumerate(summary['manual_review'], 1):
            print(
                f"  {i}. Circuit {item['circuit_id']} (cm_id: {item['circuit_movement_id']})\n"
                f"     '{item['movement_name']}'"
            )

    print("\n" + "=" * 80)
    print(f"Total records processed: {len(summary['updated']) + len(summary['manual_review'])}")
    print("=" * 80 + "\n")


async def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    parser = argparse.ArgumentParser(
        description="Fix unmatched circuit movement records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default)
  python scripts/fix_unmatched_circuit_movements.py

  # Dry run with verbose output
  python scripts/fix_unmatched_circuit_movements.py --dry-run --verbose

  # Apply changes
  python scripts/fix_unmatched_circuit_movements.py --apply

  # Apply changes with verbose output
  python scripts/fix_unmatched_circuit_movements.py --apply --verbose
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be changed without applying (default: True)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply to changes to database"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # If --apply is specified, disable --dry-run
    dry_run = not args.apply
    verbose = args.verbose

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.apply:
        logger.info("Running in APPLY mode - changes will be written to database")
    else:
        logger.info("Running in DRY-RUN mode - no changes will be made")

    async with async_session_maker() as session:
        # Get unmatched circuit movements
        logger.info("Fetching unmatched circuit movements...")
        unmatched = await get_unmatched_circuit_movements(session)
        logger.info(f"Found {len(unmatched)} unmatched circuit movements")

        if verbose and unmatched:
            logger.info("\nUnmatched movements:")
            for circuit_movement_id, movement_name, circuit_id in unmatched:
                logger.info(f"  - Circuit {circuit_id}: '{movement_name}' (cm_id: {circuit_movement_id})")

        # Build mapping dictionary
        logger.info("\nBuilding mapping dictionary...")
        mapping = await build_mapping_dict(session)

        if verbose and mapping:
            logger.info("\nMappings:")
            for source, (target_id, target_name) in sorted(mapping.items()):
                logger.info(f"  '{source}' -> {target_name} (id: {target_id})")

        # Apply mappings
        logger.info("\nApplying mappings...")
        summary = await apply_mappings(session, unmatched, mapping, dry_run=dry_run, verbose=verbose)

        # Print summary
        print_summary(summary, verbose=verbose)

        # Commit if not dry run
        if not dry_run and summary['updated']:
            logger.info("\nCommitting changes to database...")
            await session.commit()
            logger.info(f"Successfully updated {len(summary['updated'])} records")
        elif dry_run and summary['updated']:
            logger.info(f"\n[DRY RUN] Would update {len(summary['updated'])} records")
            logger.info("Run with --apply to commit these changes")

        if summary['manual_review']:
            logger.warning(f"\n{len(summary['manual_review'])} records require manual review")


if __name__ == "__main__":
    asyncio.run(main())
