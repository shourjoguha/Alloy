#!/usr/bin/env python3
"""
Merge duplicate movement groups with conflict resolution.

This script merges the duplicate groups provided by the user:
570<>27, 33<>484, 131<>133, 579<>336, 670<>157, 672<>163, 21<>584,
588<>530, 598<>344, 216<>217, 684<>229, 37<>495, 26<>604,
16<>609<>532, 261<>434, 617<>414, 32<>516, 623<>366

Conflict resolution logic:
- Patterns: "Push-up"/"push up" -> "horizontal_push"
- Choose canonical based on data quality (most non-NULL fields)
- Resolve pattern conflicts using logical reasoning
- Merge all related tables and dependencies
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
    
    url = settings.database_url
    url = url.replace('postgresql+asyncpg://', 'postgresql://')
    
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


class DuplicateGroupMerger:
    """Merges duplicate movement groups with conflict resolution."""
    
    def __init__(self, db_config, verbose=False):
        self.db_config = db_config
        self.verbose = verbose
        self.conn = None
        self.cursor = None
        
        # Define duplicate groups
        # Format: list of movement IDs to merge
        self.duplicate_groups = [
            [570, 27],
            [33, 484],
            [131, 133],
            [579, 336],
            [670, 157],
            [672, 163],
            [21, 584],
            [588, 530],
            [598, 344],
            [216, 217],
            [684, 229],
            [37, 495],
            [26, 604],
            [16, 609, 532],  # Triple
            [261, 434],
            [617, 414],
            [32, 516],
            [623, 366],
            [624, 311],
            [320, 321],
            [186, 318],
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
    
    def get_movement_details(self, movement_ids):
        """Get detailed info about multiple movements."""
        id_list = ','.join(map(str, movement_ids))
        self.cursor.execute(f"""
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
            WHERE m.id IN ({id_list})
            GROUP BY m.id
            ORDER BY m.id
        """)
        
        results = {}
        for row in self.cursor.fetchall():
            results[row['id']] = dict(row)
        return results
    
    def count_non_null_fields(self, movement_data):
        """Count non-NULL fields for data quality scoring."""
        count = 0
        for key, value in movement_data.items():
            if key not in ['id', 'equipment_count', 'muscle_count', 'tag_count', 'session_count', 'circuit_count']:
                if value is not None and value != '':
                    count += 1
        return count
    
    def resolve_pattern_conflict(self, movement_data_list):
        """Resolve pattern conflicts using logical reasoning."""
        patterns = set()
        for data in movement_data_list:
            if data.get('pattern'):
                patterns.add(data['pattern'])
        
        # Check for push-up pattern
        for pattern in patterns:
            if pattern and ('push-up' in pattern.lower() or 'push up' in pattern.lower()):
                return 'horizontal_push'
        
        # If all same, return that
        if len(patterns) == 1:
            return list(patterns)[0]
        
        # Prefer non-NULL patterns
        non_null = [p for p in patterns if p]
        if non_null:
            # Prefer more specific patterns over generic ones
            if 'compound' in non_null:
                return 'compound'
            if 'isolation' in non_null:
                return 'isolation'
            return non_null[0]
        
        return None
    
    def resolve_region_conflict(self, movement_data_list):
        """Resolve region conflicts."""
        regions = set()
        for data in movement_data_list:
            if data.get('primary_region'):
                regions.add(data['primary_region'])
        
        if len(regions) == 1:
            return list(regions)[0]
        
        # Prefer full_body over specific regions
        if 'full_body' in regions:
            return 'full_body'
        
        # Prefer non-NULL
        non_null = [r for r in regions if r]
        return non_null[0] if non_null else None
    
    def resolve_muscle_conflict(self, movement_data_list):
        """Resolve primary_muscle conflicts."""
        muscles = set()
        for data in movement_data_list:
            if data.get('primary_muscle'):
                muscles.add(data['primary_muscle'])
        
        if len(muscles) == 1:
            return list(muscles)[0]
        
        # Prefer full_body over specific muscles
        if 'full_body' in muscles:
            return 'full_body'
        
        # Prefer non-NULL
        non_null = [m for m in muscles if m]
        return non_null[0] if non_null else None
    
    def choose_canonical(self, movement_data_list):
        """Choose canonical movement based on data quality."""
        # Create mapping from ID to data
        data_map = {d['id']: d for d in movement_data_list}
        
        # Score each movement
        scores = []
        for data in movement_data_list:
            score = self.count_non_null_fields(data)
            scores.append((data['id'], score))
        
        # Sort by score (descending), then by equipment_count, then by muscle_count
        scores.sort(key=lambda x: (-x[1], -data_map[x[0]]['equipment_count'], -data_map[x[0]]['muscle_count']))
        
        canonical_id = scores[0][0]
        duplicate_ids = [d['id'] for d in movement_data_list if d['id'] != canonical_id]
        
        return canonical_id, duplicate_ids
    
    def update_canonical_movement(self, canonical_id, movement_data_list):
        """Update canonical movement with resolved conflicts."""
        # Resolve conflicts
        resolved_pattern = self.resolve_pattern_conflict(movement_data_list)
        resolved_region = self.resolve_region_conflict(movement_data_list)
        resolved_muscle = self.resolve_muscle_conflict(movement_data_list)
        
        updates = []
        params = []
        
        if resolved_pattern:
            updates.append("pattern = %s")
            params.append(resolved_pattern)
        if resolved_region:
            updates.append("primary_region = %s")
            params.append(resolved_region)
        if resolved_muscle:
            updates.append("primary_muscle = %s")
            params.append(resolved_muscle)
        
        if updates:
            params.append(canonical_id)
            query = f"UPDATE movements SET {', '.join(updates)} WHERE id = %s"
            self.cursor.execute(query, params)
            
            if self.verbose:
                print(f"  Updated canonical movement {canonical_id}:")
                if resolved_pattern:
                    print(f"    pattern -> {resolved_pattern}")
                if resolved_region:
                    print(f"    primary_region -> {resolved_region}")
                if resolved_muscle:
                    print(f"    primary_muscle -> {resolved_muscle}")
    
    def migrate_relationships(self, canonical_id, duplicate_ids):
        """Migrate all relationships from duplicates to canonical."""
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
        
        for duplicate_id in duplicate_ids:
            for table, movement_id_col in tables_to_migrate:
                # Check if table has movement_id column
                self.cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s 
                    AND column_name = %s
                """, (table, movement_id_col))
                
                if not self.cursor.fetchone():
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
                
                # Update all references from duplicate to canonical
                self.cursor.execute(f"""
                    UPDATE {table}
                    SET {movement_id_col} = %s
                    WHERE {movement_id_col} = %s
                """, (canonical_id, duplicate_id))
                
                updated = self.cursor.rowcount
                key = f"{table}_{duplicate_id}"
                migrated_counts[key] = migrated_counts.get(key, 0) + updated
            
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
                key = f"movement_relationships_{direction}_{duplicate_id}"
                migrated_counts[key] = migrated_counts.get(key, 0) + count
        
        return migrated_counts
    
    def delete_duplicates(self, duplicate_ids):
        """Delete duplicate movements."""
        id_list = ','.join(map(str, duplicate_ids))
        self.cursor.execute(f"DELETE FROM movements WHERE id IN ({id_list})")
        return self.cursor.rowcount
    
    def merge_group(self, movement_ids):
        """Merge a single duplicate group."""
        print(f"\n{'='*60}")
        print(f"Merging group: {'<>'.join(map(str, movement_ids))}")
        print(f"{'='*60}")
        
        # Get movement details
        movement_data = self.get_movement_details(movement_ids)
        movement_data_list = [movement_data[mid] for mid in movement_ids if mid in movement_data]
        
        if len(movement_data_list) < 2:
            print(f"  ⚠️  Only {len(movement_data_list)} movement(s) found, skipping")
            return None
        
        # Display details
        if self.verbose:
            print(f"\nMovement details:")
            for data in movement_data_list:
                print(f"\n  ID {data['id']}: {data['name']}")
                print(f"    Pattern: {data['pattern']}")
                print(f"    Primary Muscle: {data['primary_muscle']}")
                print(f"    Primary Region: {data['primary_region']}")
                print(f"    Equipment: {data['equipment_count']}")
                print(f"    Muscles: {data['muscle_count']}")
                print(f"    Sessions: {data['session_count']}")
                print(f"    Circuits: {data['circuit_count']}")
        
        # Choose canonical
        canonical_id, duplicate_ids = self.choose_canonical(movement_data_list)
        print(f"\n  Canonical: {canonical_id}")
        print(f"  Duplicates: {duplicate_ids}")
        
        # Update canonical with resolved conflicts
        self.update_canonical_movement(canonical_id, movement_data_list)
        
        # Migrate relationships
        print(f"\n  Migrating relationships...")
        migrated = self.migrate_relationships(canonical_id, duplicate_ids)
        
        total_migrated = sum(migrated.values())
        print(f"  Total records migrated: {total_migrated}")
        
        # Delete duplicates
        print(f"\n  Deleting duplicate movements {duplicate_ids}...")
        deleted = self.delete_duplicates(duplicate_ids)
        print(f"  Deleted {deleted} movement(s)")
        
        return {
            'canonical_id': canonical_id,
            'duplicate_ids': duplicate_ids,
            'migrated_counts': migrated,
            'total_migrated': total_migrated,
            'deleted': deleted,
        }
    
    def run_merges(self):
        """Run all merges."""
        print("\n" + "="*80)
        print("MERGING DUPLICATE GROUPS")
        print("="*80)
        
        results = []
        
        for i, group in enumerate(self.duplicate_groups, 1):
            print(f"\n--- Merge {i}/{len(self.duplicate_groups)} ---")
            result = self.merge_group(group)
            if result:
                results.append(result)
                
                # Commit after each merge
                self.conn.commit()
                print(f"  ✅ Merge {i} committed successfully")
        
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
            dup_str = ','.join(map(str, result['duplicate_ids']))
            print(f"\n{i}. {dup_str} -> {result['canonical_id']}")
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
        description='Merge duplicate movement groups',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--verbose', action='store_true', help='Print detailed information')
    
    args = parser.parse_args()
    
    db_config = get_db_config_from_env()
    
    try:
        merger = DuplicateGroupMerger(db_config, verbose=args.verbose)
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
