#!/usr/bin/env python3
"""
Fix movement pattern and primary_muscle issues based on user requirements.

Category 1: Pattern changes (excluding ID 25)
Category 2: No changes to deadlifts
Category 3: Core pattern + primary_muscle fixes
Category 4: Merge 433, 400, 514 into "Rowing Machine"
Category 5: No changes to Olympic lifts
Additional: Update primary_muscle to "core" for IDs 37, 617
"""
import sys
import argparse
from pathlib import Path

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


def fix_pattern_issues(db_config, verbose=False):
    """Fix movement pattern and primary_muscle issues."""
    conn = psycopg2.connect(**db_config, cursor_factory=DictCursor)
    cursor = conn.cursor()
    
    print(f"Connected to database: {db_config['database']}\n")
    
    print("="*80)
    print("APPLYING USER-SPECIFIED FIXES")
    print("="*80)
    print()
    
    # Category 1: Pattern changes (excluding ID 25 as user requested)
    print("CATEGORY 1: Pattern Changes (excluding ID 25)")
    print("-"*80)
    
    pattern_changes = [
        (667, 'horizontal_pull', 'Crossover Reverse Lunge'),
        (357, 'core', 'Seated Flat Bench Leg Pull-In'),
        (579, 'core', 'Flat Bench Leg Pull In'),
        (367, 'horizontal_pull', 'Straight Bar Bench Mid Rows'),
        (300, 'horizontal_push', 'Supine Chest Throw'),
    ]
    
    for movement_id, new_pattern, name in pattern_changes:
        cursor.execute("SELECT pattern FROM movements WHERE id = %s", (movement_id,))
        old_pattern = cursor.fetchone()[0]
        
        if verbose:
            print(f"ID {movement_id}: {name}")
            print(f"  Old pattern: {old_pattern}")
            print(f"  New pattern: {new_pattern}")
            print()
        
        cursor.execute("UPDATE movements SET pattern = %s WHERE id = %s", (new_pattern, movement_id))
    
    print(f"✅ Updated {len(pattern_changes)} patterns (Category 1)\n")
    
    # Category 2: No changes to deadlifts
    print("CATEGORY 2: Deadlifts - No changes (as requested)")
    print("-"*80)
    print("✅ No changes made\n")
    
    # Category 3: Core pattern + primary_muscle fixes
    print("CATEGORY 3: Core Pattern + Primary Muscle Fixes")
    print("-"*80)
    
    # First, ensure all have pattern = "core"
    core_pattern_ids = [37, 41, 156, 213, 407, 583, 617, 610]
    for movement_id in core_pattern_ids:
        cursor.execute("SELECT pattern FROM movements WHERE id = %s", (movement_id,))
        old_pattern = cursor.fetchone()[0]
        
        if old_pattern != 'core':
            cursor.execute("UPDATE movements SET pattern = 'core' WHERE id = %s", (movement_id,))
            if verbose:
                print(f"ID {movement_id}: pattern {old_pattern} → core")
    
    # Update specific primary_muscle values
    # ID 37 "Plank": update Primary Muscle to "core"
    cursor.execute("UPDATE movements SET primary_muscle = 'core' WHERE id = 37")
    if verbose:
        print("ID 37: Plank - primary_muscle → core")
    
    # ID 610 "Rear Leg Raises": update Primary Muscle to "hip_flexors"
    cursor.execute("UPDATE movements SET primary_muscle = 'hip_flexors' WHERE id = 610")
    if verbose:
        print("ID 610: Rear Leg Raises - primary_muscle → hip_flexors")
    
    print(f"✅ Updated core patterns and primary muscles (Category 3)\n")
    
    # Category 4: Merge 433, 400, 514 into "Rowing Machine"
    print("CATEGORY 4: Merge Rowing Movements")
    print("-"*80)
    
    # Keep ID 400 as canonical "Rowing Machine", merge 433 and 514 into it
    # Also update 433's display name to "Row" for circuits
    
    # First, get current info
    cursor.execute("SELECT name FROM movements WHERE id = 400")
    canonical_name = cursor.fetchone()[0]
    
    if verbose:
        print(f"Canonical movement: ID 400 - {canonical_name}")
        print(f"Duplicates to merge: ID 433 (200/Row), ID 514 (Rowing, Stationary)")
        print()
    
    # Get movement details for duplicates
    cursor.execute("SELECT id, name, pattern, primary_muscle, primary_region FROM movements WHERE id IN (433, 514)")
    duplicates = cursor.fetchall()
    
    for dup in duplicates:
        if verbose:
            print(f"Merging ID {dup['id']}: {dup['name']}")
            print(f"  Pattern: {dup['pattern']}, Muscle: {dup['primary_muscle']}, Region: {dup['primary_region']}")
        
        # Migrate all relationships from duplicate to canonical (ID 400)
        tables_to_migrate = [
            ("movement_equipment", "movement_id"),
            ("movement_muscle_map", "movement_id"),
            ("movement_disciplines", "movement_id"),
            ("movement_tags", "movement_id"),
            ("movement_coaching_cues", "movement_id"),
            ("session_exercises", "movement_id"),
            ("circuits_melted", "movement_id"),
        ]
        
        for table, movement_id_col in tables_to_migrate:
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s 
                AND column_name = %s
            """, (table, movement_id_col))
            
            if not cursor.fetchone():
                continue
            
            # Get all other PK columns (non-movement_id)
            cursor.execute("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass
                AND i.indisprimary = true
                AND a.attname != %s
            """, (table, movement_id_col))
            
            other_pk_cols = [row[0] for row in cursor.fetchall()]
            
            if other_pk_cols:
                # Delete records from canonical that have same other PK values as duplicate
                for pk_col in other_pk_cols:
                    cursor.execute(f"""
                        DELETE FROM {table}
                        WHERE {movement_id_col} = %s
                        AND {pk_col} IN (
                            SELECT {pk_col}
                            FROM {table}
                            WHERE {movement_id_col} = %s
                        )
                    """, (400, dup['id']))
            
            # Update all references from duplicate to canonical
            cursor.execute(f"""
                UPDATE {table}
                SET {movement_id_col} = %s
                WHERE {movement_id_col} = %s
            """, (400, dup['id']))
        
        if verbose:
            print(f"  ✅ Migrated relationships to ID 400")
            print()
    
    # Delete duplicates
    cursor.execute("DELETE FROM movements WHERE id IN (433, 514)")
    deleted_count = cursor.rowcount
    
    if verbose:
        print(f"✅ Deleted {deleted_count} duplicate movements")
    
    print(f"✅ Merged rowing movements (Category 4)\n")
    
    # Category 5: Olympic lifts - No changes
    print("CATEGORY 5: Olympic Lifts - No changes (as requested)")
    print("-"*80)
    print("✅ No changes made\n")
    
    # Additional: Update primary_muscle to "core" for IDs 37, 617
    # Note: 37 already updated in Category 3, just need to update 617 if not already done
    print("ADDITIONAL: Update primary_muscle to 'core' for IDs 37, 617")
    print("-"*80)
    
    cursor.execute("UPDATE movements SET primary_muscle = 'core' WHERE id IN (37, 617)")
    
    if verbose:
        print("✅ Updated primary_muscle to 'core' for IDs 37, 617")
    
    print()
    
    # Commit all changes
    conn.commit()
    
    # Verification
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    print()
    
    # Verify Category 1 changes
    print("Category 1 (Pattern Changes):")
    for movement_id, new_pattern, name in pattern_changes:
        cursor.execute("SELECT pattern FROM movements WHERE id = %s", (movement_id,))
        result = cursor.fetchone()
        status = "✓" if result[0] == new_pattern else "✗"
        print(f"  ID {movement_id} ({name}): {result[0]} {status}")
    
    print()
    
    # Verify Category 3 changes
    print("Category 3 (Core + Primary Muscle):")
    cursor.execute("SELECT id, name, pattern, primary_muscle FROM movements WHERE id IN (37, 610)")
    results = cursor.fetchall()
    for r in results:
        pattern_status = "✓" if r['pattern'] == 'core' else "✗"
        if r['id'] == 37:
            muscle_status = "✓" if r['primary_muscle'] == 'core' else "✗"
        elif r['id'] == 610:
            muscle_status = "✓" if r['primary_muscle'] == 'hip_flexors' else "✗"
        else:
            muscle_status = "✓" if r['pattern'] == 'core' else "✗"
        
        print(f"  ID {r['id']} ({r['name']}): pattern={r['pattern']} {pattern_status}, primary_muscle={r['primary_muscle']} {muscle_status}")
    
    print()
    
    # Verify Category 4 merge
    print("Category 4 (Rowing Merge):")
    cursor.execute("SELECT COUNT(*) FROM movements WHERE id IN (433, 514)")
    remaining = cursor.fetchone()[0]
    
    cursor.execute("SELECT id, name FROM movements WHERE id = 400")
    canonical = cursor.fetchone()
    
    print(f"  Duplicates deleted: {2 - remaining}")
    print(f"  Canonical ID 400: {canonical['name']}")
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\n✅ All changes applied successfully")
    
    cursor.close()
    conn.close()
    print("\nDatabase connection closed.")
    
    return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fix movement pattern and primary_muscle issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--verbose', action='store_true', help='Print detailed information')
    
    args = parser.parse_args()
    
    db_config = get_db_config_from_env()
    
    try:
        fix_pattern_issues(db_config, verbose=args.verbose)
        print(f"\n✅ Successfully completed all fixes")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
