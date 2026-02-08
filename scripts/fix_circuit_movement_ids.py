#!/usr/bin/env python3
"""
Fix Circuit Movement IDs with Fuzzy Matching

This script reads all circuits_melted records where movement_id IS NULL,
attempts to find matching movements in the movements table using exact
and fuzzy string matching, and updates the movement_id for matched records.

Usage:
    python scripts/fix_circuit_movement_ids.py [--dry-run] [--verbose] [--fuzzy-threshold N]

Options:
    --dry-run              Preview changes without committing to database
    --verbose              Show detailed matching information
    --fuzzy-threshold N    Minimum similarity ratio for fuzzy match (0.0-1.0, default: 0.85)

Examples:
    # Preview what would be changed
    python scripts/fix_circuit_movement_ids.py --dry-run --verbose

    # Run with default fuzzy threshold (0.85)
    python scripts/fix_circuit_movement_ids.py

    # Run with more aggressive fuzzy matching (0.75)
    python scripts/fix_circuit_movement_ids.py --fuzzy-threshold 0.75

The script reports:
- Total records needing fixes
- Exact matches found
- Fuzzy matches found
- Unmatched movement names
- Update statistics
"""

import argparse
import asyncio
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models.circuit_extended import CircuitMelted
from app.models.movement import Movement


class CircuitMovementFixer:
    """Fixes movement_id in circuits_melted table using fuzzy matching."""

    def __init__(
        self,
        dry_run: bool = False,
        verbose: bool = False,
        fuzzy_threshold: float = 0.85
    ):
        """
        Initialize the fixer.

        Args:
            dry_run: If True, preview changes without committing
            verbose: If True, show detailed matching information
            fuzzy_threshold: Minimum similarity ratio for fuzzy match (0.0-1.0)
        """
        self.dry_run = dry_run
        self.verbose = verbose
        self.fuzzy_threshold = fuzzy_threshold

        # Statistics tracking
        self.stats = {
            "total_records": 0,
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "unmatched": 0,
            "records_updated": 0,
            "records_skipped": 0,
        }

        # Track unmatched movement names
        self.unmatched_names: List[Tuple[int, str]] = []

    async def fetch_unmatched_records(
        self,
        session: AsyncSession
    ) -> List[Dict]:
        """
        Fetch all circuits_melted records where movement_id IS NULL.

        Args:
            session: Async SQLAlchemy session

        Returns:
            List of dictionaries with unmatched record data
        """
        query = (
            select(
                CircuitMelted.id,
                CircuitMelted.circuit_id,
                CircuitMelted.movement_name,
                CircuitMelted.exercise_sequence,
            )
            .where(CircuitMelted.movement_id.is_(None))
            .order_by(CircuitMelted.circuit_id, CircuitMelted.exercise_sequence)
        )

        result = await session.execute(query)
        records = result.all()

        self.stats["total_records"] = len(records)

        if self.verbose:
            print(f"\nFound {len(records)} records with NULL movement_id")

        return [
            {
                "id": record.id,
                "circuit_id": record.circuit_id,
                "movement_name": record.movement_name,
                "exercise_sequence": record.exercise_sequence,
            }
            for record in records
        ]

    async def fetch_movement_names(
        self,
        session: AsyncSession
    ) -> Dict[str, int]:
        """
        Fetch all movement names and their IDs for matching.

        Args:
            session: Async SQLAlchemy session

        Returns:
            Dictionary mapping movement names to IDs
        """
        query = select(Movement.id, Movement.name)
        result = await session.execute(query)

        movements = {name: id for id, name in result.all()}

        if self.verbose:
            print(f"Loaded {len(movements)} movements for matching")

        return movements

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        Normalize movement name for comparison.

        Args:
            name: Original movement name

        Returns:
            Normalized name (lowercase, stripped, standardized spacing)
        """
        return " ".join(name.strip().lower().split())

    def find_exact_match(
        self,
        movement_name: str,
        movements: Dict[str, int]
    ) -> Optional[int]:
        """
        Find exact match for movement name.

        Args:
            movement_name: Name to match
            movements: Dictionary of movement names to IDs

        Returns:
            Movement ID if exact match found, None otherwise
        """
        normalized_name = self.normalize_name(movement_name)

        # Try exact match first (case-insensitive)
        for name, movement_id in movements.items():
            if self.normalize_name(name) == normalized_name:
                return movement_id

        return None

    def find_fuzzy_match(
        self,
        movement_name: str,
        movements: Dict[str, int]
    ) -> Optional[Tuple[int, float]]:
        """
        Find fuzzy match for movement name using SequenceMatcher.

        Args:
            movement_name: Name to match
            movements: Dictionary of movement names to IDs

        Returns:
            Tuple of (movement_id, similarity_ratio) if match found, None otherwise
        """
        normalized_name = self.normalize_name(movement_name)
        best_match_id = None
        best_ratio = 0.0

        for name, movement_id in movements.items():
            normalized_db_name = self.normalize_name(name)
            ratio = SequenceMatcher(None, normalized_name, normalized_db_name).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_match_id = movement_id

        if best_ratio >= self.fuzzy_threshold:
            return best_match_id, best_ratio

        return None

    async def update_movement_id(
        self,
        session: AsyncSession,
        record_id: int,
        movement_id: int
    ) -> None:
        """
        Update movement_id for a record.

        Args:
            session: Async SQLAlchemy session
            record_id: ID of circuits_melted record to update
            movement_id: Movement ID to set
        """
        stmt = (
            update(CircuitMelted)
            .where(CircuitMelted.id == record_id)
            .values(movement_id=movement_id)
        )

        await session.execute(stmt)
        self.stats["records_updated"] += 1

    def log_match(
        self,
        record: Dict,
        match_type: str,
        movement_id: Optional[int] = None,
        similarity: Optional[float] = None
    ) -> None:
        """
        Log match information if verbose mode is enabled.

        Args:
            record: Record dictionary
            match_type: Type of match ('exact', 'fuzzy', 'unmatched')
            movement_id: Matched movement ID (if any)
            similarity: Similarity ratio for fuzzy matches (if any)
        """
        if not self.verbose:
            return

        if match_type == "exact":
            print(
                f"  [EXACT] Record {record['id']} (circuit {record['circuit_id']}, "
                f"seq {record['exercise_sequence']}): '{record['movement_name']}' "
                f"-> Movement ID {movement_id}"
            )
        elif match_type == "fuzzy":
            print(
                f"  [FUZZY] Record {record['id']} (circuit {record['circuit_id']}, "
                f"seq {record['exercise_sequence']}): '{record['movement_name']}' "
                f"-> Movement ID {movement_id} (similarity: {similarity:.2%})"
            )
        elif match_type == "unmatched":
            print(
                f"  [NO MATCH] Record {record['id']} (circuit {record['circuit_id']}, "
                f"seq {record['exercise_sequence']}): '{record['movement_name']}'"
            )

    async def run(self) -> None:
        """Run the movement ID fixing process."""
        async with async_session_maker() as session:
            # Fetch unmatched records
            unmatched_records = await self.fetch_unmatched_records(session)

            if not unmatched_records:
                print("\nNo records with NULL movement_id found. Database is up to date!")
                return

            # Fetch all movements for matching
            movements = await self.fetch_movement_names(session)

            if not movements:
                print("\nError: No movements found in database!")
                return

            # Process each record
            print("\nProcessing unmatched records...")

            for record in unmatched_records:
                movement_name = record["movement_name"]

                # Try exact match first
                movement_id = self.find_exact_match(movement_name, movements)

                if movement_id:
                    self.stats["exact_matches"] += 1
                    self.log_match(record, "exact", movement_id)

                    if not self.dry_run:
                        await self.update_movement_id(session, record["id"], movement_id)
                    else:
                        self.stats["records_skipped"] += 1

                    continue

                # Try fuzzy match
                fuzzy_result = self.find_fuzzy_match(movement_name, movements)

                if fuzzy_result:
                    movement_id, similarity = fuzzy_result
                    self.stats["fuzzy_matches"] += 1
                    self.log_match(record, "fuzzy", movement_id, similarity)

                    if not self.dry_run:
                        await self.update_movement_id(session, record["id"], movement_id)
                    else:
                        self.stats["records_skipped"] += 1

                else:
                    self.stats["unmatched"] += 1
                    self.log_match(record, "unmatched")
                    self.unmatched_names.append(
                        (record["id"], record["movement_name"])
                    )

            # Commit changes if not in dry-run mode
            if not self.dry_run and self.stats["records_updated"] > 0:
                await session.commit()
                print("\nChanges committed to database.")
            elif self.dry_run:
                print("\nDry-run mode: No changes committed to database.")

            # Print statistics
            self.print_statistics()

    def print_statistics(self) -> None:
        """Print matching and update statistics."""
        print("\n" + "=" * 60)
        print("STATISTICS")
        print("=" * 60)
        print(f"Total records with NULL movement_id:  {self.stats['total_records']}")
        print(f"Exact matches found:                  {self.stats['exact_matches']}")
        print(f"Fuzzy matches found:                  {self.stats['fuzzy_matches']}")
        print(f"Unmatched records:                    {self.stats['unmatched']}")

        if self.dry_run:
            print(f"\nRecords that would be updated:        {self.stats['exact_matches'] + self.stats['fuzzy_matches']}")
        else:
            print(f"\nRecords updated:                     {self.stats['records_updated']}")

        print("=" * 60)

        # Show unmatched names if any
        if self.unmatched_names:
            print("\nUNMATCHED MOVEMENT NAMES")
            print("-" * 60)
            for record_id, name in self.unmatched_names[:20]:  # Show first 20
                print(f"  Record {record_id}: {name}")

            if len(self.unmatched_names) > 20:
                print(f"  ... and {len(self.unmatched_names) - 20} more")

            print("-" * 60)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fix circuit movement IDs using fuzzy matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes without committing
  python scripts/fix_circuit_movement_ids.py --dry-run --verbose

  # Run with default fuzzy threshold (0.85)
  python scripts/fix_circuit_movement_ids.py

  # Run with more aggressive fuzzy matching (0.75)
  python scripts/fix_circuit_movement_ids.py --fuzzy-threshold 0.75
        """
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing to database"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed matching information"
    )

    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.85,
        metavar="N",
        help="Minimum similarity ratio for fuzzy match (0.0-1.0, default: 0.85)"
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Validate fuzzy threshold
    if not 0.0 <= args.fuzzy_threshold <= 1.0:
        print("Error: fuzzy-threshold must be between 0.0 and 1.0")
        sys.exit(1)

    print("=" * 60)
    print("CIRCUIT MOVEMENT ID FIXER")
    print("=" * 60)
    print(f"Dry-run mode:         {args.dry_run}")
    print(f"Verbose mode:          {args.verbose}")
    print(f"Fuzzy threshold:       {args.fuzzy_threshold:.2%}")
    print("=" * 60)

    # Create and run fixer
    fixer = CircuitMovementFixer(
        dry_run=args.dry_run,
        verbose=args.verbose,
        fuzzy_threshold=args.fuzzy_threshold
    )

    try:
        asyncio.run(fixer.run())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
