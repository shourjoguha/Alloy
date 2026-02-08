#!/usr/bin/env python3
"""
Merge exact name duplicate movements with proper dependency handling.

This script merges 8 exact name match groups found in duplicate detection:
1. clean (30, 626)
2. snatch (32, 652)
3. clean and jerk (33, 630)
4. calorie echo bike (71, 380)
5. rack delivery (247, 650)
6. wide stance stiff legs (316, 660)
7. calorie row (372, 538)
8. snatch balance (546, 653)
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import DictCursor
from app.config.settings import get_settings


def get_db_config_from_env():
    """Get database configuration from environment."""
    import re
    settings = get_settings()
    
    # Parse database_url: postgresql+asyncpg://user:pass@host:port/database
    # We need postgresql://user:pass@host:port/database for psycopg2
    url = settings.database_url
    
    # Remove asyncpg and use postgresql
    url = url.replace('postgresql+asyncpg://', 'postgresql://')
    
    # Parse using regex
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', url)
    if not match:
        raise ValueError(f"Invalid database URL format: {url}")
    
    return {
        'host': match.group(3),
        'port': int(match.group(4)),
        'database': match.group(5),
        'user': match.group(1),
        'password': match.group(2),
    }


class ExactNameDuplicateMerger:
    """Merges exact name duplicate movements."""
    
    def __init__(self, db_config, verbose=False):
        self.db_config = db_config
        self.verbose = verbose
        self.conn = None
        self.cursor = None
        
        # Define exact name match groups to merge
        # Format: (canonical_id, duplicate_id, reason)
        self.merge_groups = [
            # Group 1: clean - keep 30 (has more data, full_body)
            (30, 626, "Canonical has full_body primary_muscle vs hamstrings"),
            
            # Group 2: snatch - keep 32 (has more data, full_body)
            (32, 652, "Canonical has full_body primary_muscle vs quadriceps"),
            
            # Group 3: clean and jerk - keep 33 (has more data, full_body)
            (33, 630, "Canonical has full_body primary_muscle vs side_delts"),
            
            # Group 4: calorie echo bike - keep 71 (lower ID, same data)
            (71, 380, "Canonical has lower ID, identical data"),
            
            # Group 5: rack delivery - keep 247 (lower ID, same data)
            (247, 650, "Canonical has lower ID, identical data"),
            
            # Group 6: wide stance stiff legs - keep 316 (lower ID, same data)
            (316, 660, "Canonical has lower ID, identical data"),
            
            # Group 7: calorie row - keep 372 (lower ID, same data)
            (372, 538, "Canonical has lower ID, identical data"),
            
            # Group 8: snatch balance - keep 546 (lower ID, same data)
            (546, 653, "Canonical has lower ID, identical data"),
        ]
    
    def connect(self):
        """Connect to database."""
        self.conn = psycopg2.connect(**self.db_config, cursor_factory=DictCursor)
        self.cursor = self.conn.cursor()
        print(f"Connected to database: {self.db_config['database']}")
    
    def close(self):
        """Close database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("Database connection closed.")
    
    def get_movement_info(self, movement_id):
        """Get detailed info about a movement."""
        self.cursor.execute("""
            SELECT m.id, m.name, m.pattern, m.primary_muscle, m.primary_region,
                   COUNT(DISTINCT eq.equipment_id) as equipment_count,
                   COUNT(DISTINCT mm.muscle_id) as muscle_count,
                   COUNT(DISTINCT mt.tag_id) as tag_count,
                   COUNT(DISTINCT se.id) as session_count,
                   COUNT(DISTINCT cm.id) as circuit_count
            FROM movements m
            LEFT JOIN movement_equipment eq ON m.id = eq.movement_id
            LEFT JOIN movement_muscle_map mm ON m.id = mm.movement_id
            LEFT JOIN movement_tags mt ON m.id = mt.movement_id
            LEFT JOIN session_exercises se ON m.id = se.movement_id
            LEFT JOIN circuits_melted cm ON m.id = cm.movement_id
            WHERE m.id = %s
            GROUP BY m.id
        """, (movement_id,))
        return self.cursor.fetchone()
    
    def migrate_relationships(self, canonical_id, duplicate_id):
        """Migrate all relationships from duplicate to canonical."""
        tables_to_migrate = [
            ("movement_equipment", "movement_id"),
            ("movement_muscle_map", "movement_id"),
            ("movement_disciplines", "movement_id"),
            ("movement_tags", "movement_id"),
            ("movement_coaching_cues", "movement_id"),
            ("session_exercises", "movement_id"),
            ("circuits_melted", "movement_id"),
        ]
        
        migrated_counts = {}
        
        for table, movement_id_col in tables_to_migrate:
            # Check if table has movement_id column
            self.cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s 
                AND column_name = %s
            """, (table, movement_id_col))
            
            if not self.cursor.fetchone():
                if self.verbose:
                    print(f"  Skipping {table} (no movement_id column)")
                continue
            
            # Get all other PK columns (non-movement_id)
            self.cursor.execute("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass
                AND i.indisprimary = true
                AND a.attname != %s
            """, (table, movement_id_col))
            
            other_pk_cols = [row[0] for row in self.cursor.fetchall()]
            
            if other_pk_cols:
                # Delete records from canonical that have same other PK values as duplicate
                # This prevents unique constraint violations
                for pk_col in other_pk_cols:
                    self.cursor.execute(f"""
                        DELETE FROM {table}
                        WHERE {movement_id_col} = %s
                        AND {pk_col} IN (
                            SELECT {pk_col}
                            FROM {table}
                            WHERE {movement_id_col} = %s
                        )
                    """, (canonical_id, duplicate_id))
                    
                    deleted = self.cursor.rowcount
                    if self.verbose and deleted > 0:
                        print(f"  Removed {deleted} conflicting {pk_col} records from {table}")
            
            # Update all references from duplicate to canonical
            self.cursor.execute(f"""
                UPDATE {table}
                SET {movement_id_col} = %s
                WHERE {movement_id_col} = %s
            """, (canonical_id, duplicate_id))
            
            updated = self.cursor.rowcount
            migrated_counts[table] = updated
            
            if self.verbose and updated > 0:
                print(f"  Updated {updated} records in {table}")
        
        # Handle movement_relationships (bidirectional)
        for direction in ["source", "target"]:
            col = f"{direction}_movement_id"
            
            # Delete self-referential relationships first
            self.cursor.execute(f"""
                DELETE FROM movement_relationships
                WHERE {col} = %s
                AND source_movement_id = %s
                AND target_movement_id = %s
            """, (canonical_id, canonical_id, canonical_id))
            
            # Update references
            self.cursor.execute(f"""
                UPDATE movement_relationships
                SET {col} = %s
                WHERE {col} = %s
            """, (canonical_id, duplicate_id))
            
            count = self.cursor.rowcount
            key = f"movement_relationships_{direction}"
            migrated_counts[key] = count
            
            if self.verbose and count > 0:
                print(f"  Updated {count} {direction} relationships")
        
        return migrated_counts
    
    def delete_duplicate(self, duplicate_id):
        """Delete duplicate movement."""
        self.cursor.execute("DELETE FROM movements WHERE id = %s", (duplicate_id,))
        return self.cursor.rowcount
    
    def merge_group(self, canonical_id, duplicate_id, reason):
        """Merge a single duplicate group."""
        print(f"\n{'='*60}")
        print(f"Merging: {duplicate_id} -> {canonical_id}")
        print(f"Reason: {reason}")
        print(f"{'='*60}")
        
        # Get movement info
        canonical_info = self.get_movement_info(canonical_id)
        duplicate_info = self.get_movement_info(duplicate_id)
        
        if self.verbose:
            print(f"\nCanonical ({canonical_id}): {canonical_info['name']}")
            print(f"  Pattern: {canonical_info['pattern']}")
            print(f"  Equipment: {canonical_info['equipment_count']}")
            print(f"  Muscles: {canonical_info['muscle_count']}")
            print(f"  Tags: {canonical_info['tag_count']}")
            print(f"  Sessions: {canonical_info['session_count']}")
            print(f"  Circuits: {canonical_info['circuit_count']}")
            
            print(f"\nDuplicate ({duplicate_id}): {duplicate_info['name']}")
            print(f"  Pattern: {duplicate_info['pattern']}")
            print(f"  Equipment: {duplicate_info['equipment_count']}")
            print(f"  Muscles: {duplicate_info['muscle_count']}")
            print(f"  Tags: {duplicate_info['tag_count']}")
            print(f"  Sessions: {duplicate_info['session_count']}")
            print(f"  Circuits: {duplicate_info['circuit_count']}")
        
        # Migrate relationships
        print(f"\nMigrating relationships...")
        migrated = self.migrate_relationships(canonical_id, duplicate_id)
        
        total_migrated = sum(migrated.values())
        print(f"Total records migrated: {total_migrated}")
        
        # Delete duplicate
        print(f"\nDeleting duplicate movement {duplicate_id}...")
        deleted = self.delete_duplicate(duplicate_id)
        print(f"Deleted {deleted} movement(s)")
        
        return {
            'canonical_id': canonical_id,
            'duplicate_id': duplicate_id,
            'migrated_counts': migrated,
            'total_migrated': total_migrated,
            'deleted': deleted,
        }
    
    def run_merges(self):
        """Run all merges."""
        print("\n" + "="*80)
        print("MERGING EXACT NAME DUPLICATES")
        print("="*80)
        
        results = []
        
        for i, (canonical_id, duplicate_id, reason) in enumerate(self.merge_groups, 1):
            print(f"\n--- Merge {i}/{len(self.merge_groups)} ---")
            result = self.merge_group(canonical_id, duplicate_id, reason)
            results.append(result)
            
            # Commit after each merge
            self.conn.commit()
            print(f"✅ Merge {i} committed successfully")
        
        # Print summary
        print("\n" + "="*80)
        print("MERGE SUMMARY")
        print("="*80)
        
        total_migrated = sum(r['total_migrated'] for r in results)
        total_deleted = sum(r['deleted'] for r in results)
        
        print(f"\nTotal groups merged: {len(results)}")
        print(f"Total movements deleted: {total_deleted}")
        print(f"Total records migrated: {total_migrated}")
        
        print("\nDetailed breakdown:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['duplicate_id']} -> {result['canonical_id']}")
            for table, count in result['migrated_counts'].items():
                if count > 0:
                    print(f"   {table}: {count}")
        
        print("\n" + "="*80)
        print("✅ All merges completed successfully")
        print("="*80)
        
        return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Merge exact name duplicate movements',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--verbose', action='store_true', help='Print detailed information')
    
    args = parser.parse_args()
    
    db_config = get_db_config_from_env()
    
    try:
        merger = ExactNameDuplicateMerger(db_config, verbose=args.verbose)
        merger.connect()
        
        results = merger.run_merges()
        
        merger.close()
        
        print(f"\n✅ Successfully merged {len(results)} duplicate groups")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
