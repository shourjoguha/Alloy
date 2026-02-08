#!/usr/bin/env python3
"""
Merge duplicate movements in PostgreSQL database.

This script identifies duplicate movements (by name), selects the canonical movement
based on data quality, migrates all relationships from duplicates to canonical,
creates backups, and deletes duplicates.

Usage:
    python merge_duplicate_movements.py [--dry-run] [--verbose]

Flags:
    --dry-run: Run without making any changes to the database
    --verbose: Print detailed information about each step
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Set, Any

import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MovementMerger:
    """Handles merging of duplicate movements in PostgreSQL database."""

    # Relationship tables that reference movements
    RELATIONSHIP_TABLES = {
        'movement_equipment': {'movement_id': 'movement_id', 'other_columns': ['equipment_id']},
        'movement_muscle_map': {'movement_id': 'movement_id', 'other_columns': ['muscle_id', 'role', 'magnitude']},
        'movement_disciplines': {'movement_id': 'movement_id', 'other_columns': ['discipline']},
        'movement_tags': {'movement_id': 'movement_id', 'other_columns': ['tag_id']},
        'movement_coaching_cues': {'movement_id': 'movement_id', 'other_columns': ['cue_text', 'order']},
        'movement_relationships': {
            'source_column': 'source_movement_id',
            'target_column': 'target_movement_id',
            'other_columns': ['relationship_type', 'notes']
        },
        'session_exercises': {'movement_id': 'movement_id', 'other_columns': ['user_id', 'session_id', 'exercise_role', 'circuit_id', 'order_in_session', 'superset_group', 'target_sets', 'target_rep_range_min', 'target_rep_range_max', 'target_rpe', 'target_rir', 'target_duration_seconds', 'default_rest_seconds', 'is_complex_lift', 'substitution_allowed', 'notes', 'stimulus', 'fatigue']},
        'circuits_melted': {'movement_id': 'movement_id', 'other_columns': ['circuit_id', 'exercise_sequence', 'movement_name', 'metric_type', 'reps', 'distance_meters', 'duration_seconds', 'calories', 'rest_seconds', 'notes', 'rx_weight_male', 'rx_weight_female', 'created_at', 'updated_at']},
        'user_movement_rules': {'movement_id': 'movement_id', 'other_columns': ['user_id', 'rule_type', 'rule_operator', 'cadence', 'notes', 'created_at', 'updated_at']},
        'favorites': {'movement_id': 'movement_id', 'other_columns': ['user_id', 'program_id', 'created_at']},
        'top_set_logs': {'movement_id': 'movement_id', 'other_columns': ['workout_log_id', 'weight', 'reps', 'rpe', 'rir', 'avg_rest_seconds', 'e1rm_value', 'e1rm_formula', 'pattern', 'created_at']},
    }

    def __init__(self, db_config: Dict[str, str], dry_run: bool = False, verbose: bool = False):
        """
        Initialize the movement merger.

        Args:
            db_config: Database connection parameters
            dry_run: If True, don't make any changes to the database
            verbose: If True, print detailed information
        """
        self.db_config = db_config
        self.dry_run = dry_run
        self.verbose = verbose
        self.conn = None
        self.cursor = None

    def connect(self) -> None:
        """Establish database connection."""
        if self.verbose:
            logger.info("Connecting to database...")

        self.conn = psycopg2.connect(**self.db_config, cursor_factory=DictCursor)
        self.conn.autocommit = False
        self.cursor = self.conn.cursor()

        if self.verbose:
            logger.info(f"Connected to database: {self.db_config['dbname']}")

    def disconnect(self) -> None:
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

        if self.verbose:
            logger.info("Database connection closed.")

    def execute_query(self, query: str, params: Tuple = None, fetch: bool = True) -> List[Dict]:
        """
        Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Query parameters
            fetch: If True, fetch and return results

        Returns:
            Query results as list of dicts
        """
        if self.verbose:
            logger.debug(f"Executing query: {query[:200]}...")
            if params:
                logger.debug(f"Parameters: {params}")

        self.cursor.execute(query, params)

        if fetch:
            return [dict(row) for row in self.cursor.fetchall()]
        return []

    def backup_movements_table(self) -> str:
        """
        Create a backup of the movements table.

        Returns:
            Name of the backup table
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_table = f"movements_backup_{timestamp}"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create backup table: {backup_table}")
            return backup_table

        query = f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM movements;
        """

        self.execute_query(query, fetch=False)
        self.conn.commit()

        logger.info(f"Created backup table: {backup_table}")
        return backup_table

    def drop_unique_constraint(self) -> None:
        """Drop the unique constraint on movements.name."""
        # First, check if constraint exists
        query = """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'movements'::regclass
        AND contype = 'u'
        AND conname LIKE '%name%';
        """

        result = self.execute_query(query)

        if not result:
            logger.info("No unique constraint on movements.name found.")
            return

        constraint_name = result[0]['conname']

        if self.dry_run:
            logger.info(f"[DRY RUN] Would drop constraint: {constraint_name}")
            return

        query = f"""
        ALTER TABLE movements
        DROP CONSTRAINT {constraint_name};
        """

        self.execute_query(query, fetch=False)
        self.conn.commit()

        logger.info(f"Dropped constraint: {constraint_name}")

    def readd_unique_constraint(self) -> None:
        """Re-add the unique constraint on movements.name."""
        constraint_name = "uq_movements_name"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would re-add constraint: {constraint_name}")
            return

        query = f"""
        ALTER TABLE movements
        ADD CONSTRAINT {constraint_name} UNIQUE (name);
        """

        self.execute_query(query, fetch=False)
        self.conn.commit()

        logger.info(f"Re-added constraint: {constraint_name}")

    def calculate_data_quality_score(self, movement: Dict) -> int:
        """
        Calculate a data quality score for a movement based on non-NULL fields.

        Args:
            movement: Movement record

        Returns:
            Quality score (higher is better)
        """
        score = 0

        # Core fields (high value)
        core_fields = ['pattern', 'primary_muscle', 'primary_region', 'cns_load', 'skill_level']
        for field in core_fields:
            if movement.get(field) is not None:
                score += 10

        # Movement characteristics (medium value)
        char_fields = ['compound', 'is_complex_lift', 'is_unilateral']
        for field in char_fields:
            if movement.get(field) is not None:
                score += 5

        # Fitness function metrics (high value)
        metric_fields = ['fatigue_factor', 'stimulus_factor', 'injury_risk_factor', 'min_recovery_hours']
        for field in metric_fields:
            if movement.get(field) is not None:
                score += 8

        # Categorization (medium value)
        cat_fields = ['tier', 'metabolic_demand', 'metric_type', 'spinal_compression']
        for field in cat_fields:
            if movement.get(field) is not None:
                score += 5

        # Biomechanics and embedding (high value)
        advanced_fields = ['biomechanics_profile', 'embedding_description', 'embedding_vector']
        for field in advanced_fields:
            if movement.get(field) is not None:
                score += 7

        # Description and notes (low value)
        if movement.get('description'):
            score += 3

        # Substitution group (medium value)
        if movement.get('substitution_group'):
            score += 5

        # User-owned movements get slight preference (more likely to be current)
        if movement.get('user_id') is not None:
            score += 2

        return score

    def find_duplicate_movements(self) -> Dict[str, List[Dict]]:
        """
        Find all duplicate movements grouped by name.

        Returns:
            Dictionary mapping movement names to lists of duplicate records
        """
        query = """
        SELECT id, name, user_id, pattern, primary_muscle, primary_region,
               cns_load, skill_level, compound, is_complex_lift, is_unilateral,
               fatigue_factor, stimulus_factor, injury_risk_factor, min_recovery_hours,
               spinal_compression, metric_type, tier, metabolic_demand,
               biomechanics_profile, embedding_description, substitution_group,
               description
        FROM movements
        WHERE name IN (
            SELECT name
            FROM movements
            GROUP BY name
            HAVING COUNT(*) > 1
        )
        ORDER BY name, id;
        """

        results = self.execute_query(query)

        # Group by name
        duplicates: Dict[str, List[Dict]] = {}
        for movement in results:
            name = movement['name']
            if name not in duplicates:
                duplicates[name] = []
            duplicates[name].append(movement)

        return duplicates

    def select_canonical_movement(self, movements: List[Dict]) -> Tuple[Dict, List[Dict]]:
        """
        Select the canonical movement from a list of duplicates.

        Args:
            movements: List of duplicate movement records

        Returns:
            Tuple of (canonical_movement, duplicate_movements)
        """
        # Calculate quality scores
        for movement in movements:
            movement['_quality_score'] = self.calculate_data_quality_score(movement)

        # Sort by quality score (descending), then by id (ascending)
        movements.sort(key=lambda m: (-m['_quality_score'], m['id']))

        canonical = movements[0]
        duplicates = movements[1:]

        # Remove the temporary score field
        canonical = {k: v for k, v in canonical.items() if k != '_quality_score'}
        for dup in duplicates:
            dup.pop('_quality_score', None)

        return canonical, duplicates

    def migrate_relationships(self, canonical_id: int, duplicate_ids: List[int]) -> Dict[str, int]:
        """
        Migrate relationships from duplicate movements to canonical movement.

        Args:
            canonical_id: ID of the canonical movement
            duplicate_ids: List of duplicate movement IDs to migrate from

        Returns:
            Dictionary mapping table names to number of records migrated
        """
        migration_counts = {}

        for table_name, config in self.RELATIONSHIP_TABLES.items():
            count = 0

            if 'source_column' in config:
                # Handle tables with source and target movement columns
                source_col = config['source_column']
                target_col = config['target_column']

                # Migrate source column
                query = f"""
                UPDATE {table_name}
                SET {source_col} = %s
                WHERE {source_col} IN %s
                AND NOT EXISTS (
                    SELECT 1 FROM {table_name} t2
                    WHERE t2.{source_col} = %s
                    AND t2.{target_col} = {table_name}.{target_col}
                );
                """

                if self.dry_run:
                    self.execute_query(
                        f"SELECT COUNT(*) FROM {table_name} WHERE {source_col} IN %s",
                        (tuple(duplicate_ids),)
                    )
                    count = self.cursor.fetchone()[0]
                    logger.debug(f"[DRY RUN] Would migrate {count} records from {table_name}.{source_col}")
                else:
                    self.execute_query(query, (canonical_id, tuple(duplicate_ids), canonical_id))
                    count = self.cursor.rowcount

                # Migrate target column
                query = f"""
                UPDATE {table_name}
                SET {target_col} = %s
                WHERE {target_col} IN %s
                AND NOT EXISTS (
                    SELECT 1 FROM {table_name} t2
                    WHERE t2.{target_col} = %s
                    AND t2.{source_column} = {table_name}.{source_column}
                );
                """

                if self.dry_run:
                    self.execute_query(
                        f"SELECT COUNT(*) FROM {table_name} WHERE {target_col} IN %s",
                        (tuple(duplicate_ids),)
                    )
                    count += self.cursor.fetchone()[0]
                    logger.debug(f"[DRY RUN] Would migrate {count} records from {table_name}.{target_col}")
                else:
                    self.execute_query(query, (canonical_id, tuple(duplicate_ids), canonical_id))
                    count += self.cursor.rowcount

            else:
                # Handle tables with single movement_id column
                movement_col = config['movement_id']

                # Count records to migrate (avoiding duplicates)
                query = f"""
                SELECT COUNT(*)
                FROM {table_name}
                WHERE {movement_col} IN %s
                AND NOT EXISTS (
                    SELECT 1 FROM {table_name} t2
                    WHERE t2.{movement_col} = %s
                );
                """

                if self.dry_run:
                    self.execute_query(query, (tuple(duplicate_ids), canonical_id))
                    count = self.cursor.fetchone()[0]
                    logger.debug(f"[DRY RUN] Would migrate {count} records from {table_name}")
                else:
                    # Migrate records
                    query = f"""
                    UPDATE {table_name}
                    SET {movement_col} = %s
                    WHERE {movement_col} IN %s
                    AND NOT EXISTS (
                        SELECT 1 FROM {table_name} t2
                        WHERE t2.{movement_col} = %s
                    );
                    """

                    self.execute_query(query, (canonical_id, tuple(duplicate_ids), canonical_id))
                    count = self.cursor.rowcount

            if count > 0:
                migration_counts[table_name] = count
                logger.info(f"Migrated {count} records from {table_name}")

        return migration_counts

    def delete_duplicate_movements(self, duplicate_ids: List[int]) -> int:
        """
        Delete duplicate movements after migration.

        Args:
            duplicate_ids: List of duplicate movement IDs to delete

        Returns:
            Number of movements deleted
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete {len(duplicate_ids)} duplicate movements")
            return len(duplicate_ids)

        query = """
        DELETE FROM movements
        WHERE id IN %s;
        """

        self.execute_query(query, (tuple(duplicate_ids),))
        count = self.cursor.rowcount

        logger.info(f"Deleted {count} duplicate movements")
        return count

    def merge_all_duplicates(self) -> Dict[str, Any]:
        """
        Perform the complete merge process for all duplicate movements.

        Returns:
            Dictionary with merge statistics
        """
        stats = {
            'duplicate_groups': 0,
            'total_duplicates': 0,
            'movements_merged': 0,
            'relationships_migrated': {},
            'backup_table': None
        }

        try:
            # Step 1: Create backup
            logger.info("Step 1: Creating backup of movements table...")
            stats['backup_table'] = self.backup_movements_table()

            # Step 2: Drop unique constraint
            logger.info("Step 2: Dropping unique constraint on movements.name...")
            self.drop_unique_constraint()

            # Step 3: Find duplicates
            logger.info("Step 3: Finding duplicate movements...")
            duplicates = self.find_duplicate_movements()

            if not duplicates:
                logger.info("No duplicate movements found.")
                return stats

            stats['duplicate_groups'] = len(duplicates)
            stats['total_duplicates'] = sum(len(movements) for movements in duplicates.values())

            logger.info(f"Found {stats['duplicate_groups']} duplicate groups with {stats['total_duplicates']} total movements")

            # Step 4: Process each duplicate group
            logger.info("Step 4: Processing duplicate groups...")

            for i, (name, movements) in enumerate(duplicates.items(), 1):
                logger.info(f"\nProcessing group {i}/{stats['duplicate_groups']}: '{name}' ({len(movements)} duplicates)")

                if self.verbose:
                    for movement in movements:
                        logger.debug(f"  Movement {movement['id']}: user_id={movement['user_id']}, pattern={movement.get('pattern')}")

                # Select canonical movement
                canonical, duplicate_movements = self.select_canonical_movement(movements)
                duplicate_ids = [d['id'] for d in duplicate_movements]

                logger.info(f"  Canonical: Movement {canonical['id']} (user_id={canonical['user_id']})")
                logger.info(f"  Duplicates to merge: {duplicate_ids}")

                # Migrate relationships
                migration_counts = self.migrate_relationships(canonical['id'], duplicate_ids)

                for table, count in migration_counts.items():
                    if table not in stats['relationships_migrated']:
                        stats['relationships_migrated'][table] = 0
                    stats['relationships_migrated'][table] += count

                # Delete duplicates
                deleted = self.delete_duplicate_movements(duplicate_ids)
                stats['movements_merged'] += deleted

            # Step 5: Re-add unique constraint
            logger.info("\nStep 5: Re-adding unique constraint on movements.name...")
            self.readd_unique_constraint()

            # Commit transaction
            if not self.dry_run:
                self.conn.commit()
                logger.info("Transaction committed successfully.")

            return stats

        except Exception as e:
            # Rollback on error
            if self.conn:
                self.conn.rollback()
                logger.error(f"Transaction rolled back due to error: {e}")

            raise

    def print_summary(self, stats: Dict[str, Any]) -> None:
        """Print a summary of the merge operation."""
        logger.info("\n" + "="*70)
        logger.info("MERGE SUMMARY")
        logger.info("="*70)

        if self.dry_run:
            logger.info("DRY RUN MODE - No changes were made to the database")
            logger.info("")

        logger.info(f"Duplicate groups found: {stats['duplicate_groups']}")
        logger.info(f"Total duplicates: {stats['total_duplicates']}")
        logger.info(f"Movements merged: {stats['movements_merged']}")

        if stats['backup_table']:
            logger.info(f"Backup table: {stats['backup_table']}")

        if stats['relationships_migrated']:
            logger.info("\nRelationships migrated:")
            for table, count in sorted(stats['relationships_migrated'].items()):
                logger.info(f"  {table}: {count}")

        logger.info("="*70)


def get_db_config_from_env() -> Dict[str, str]:
    """
    Get database configuration from environment or .env file.

    Returns:
        Dictionary with database connection parameters
    """
    import os
    import re
    from pathlib import Path

    # Try to load from .env or .env.supabase file
    env_file = Path(__file__).parent.parent / '.env.supabase'
    if not env_file.exists():
        env_file = Path(__file__).parent.parent / '.env'

    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

    # Try to get DATABASE_URL and parse it
    database_url = os.getenv('DATABASE_URL')

    if database_url:
        # Parse PostgreSQL connection string
        # Format: postgresql://user:password@host:port/database
        # Or: postgresql+asyncpg://user:password@host:port/database

        # Remove asyncpg prefix if present
        database_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')

        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', database_url)
        if match:
            return {
                'dbname': match.group(5),
                'user': match.group(1),
                'password': match.group(2),
                'host': match.group(3),
                'port': int(match.group(4)),
            }

    # Fall back to individual environment variables
    return {
        'dbname': os.getenv('DB_NAME', 'postgres'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
    }


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Merge duplicate movements in PostgreSQL database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in dry-run mode to see what would happen
  python merge_duplicate_movements.py --dry-run

  # Run with verbose output
  python merge_duplicate_movements.py --verbose

  # Run both dry-run and verbose
  python merge_duplicate_movements.py --dry-run --verbose
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without making any changes to the database'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed information about each step'
    )

    args = parser.parse_args()

    # Configure logging based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Get database configuration
    db_config = get_db_config_from_env()

    logger.info("Starting duplicate movement merge process...")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made to the database")

    try:
        # Create merger instance
        merger = MovementMerger(
            db_config=db_config,
            dry_run=args.dry_run,
            verbose=args.verbose
        )

        # Connect to database
        merger.connect()

        # Perform merge
        stats = merger.merge_all_duplicates()

        # Print summary
        merger.print_summary(stats)

        # Disconnect
        merger.disconnect()

        logger.info("Merge process completed successfully.")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error during merge process: {e}", exc_info=args.verbose)
        sys.exit(1)


if __name__ == '__main__':
    main()
