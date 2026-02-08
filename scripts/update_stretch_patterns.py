#!/usr/bin/env python3
"""
Update movements with "Stretch"/"Stretching"/"stretch" in name to have pattern "Stretch".

This script updates all 52 movements found with stretch in their name.
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


def update_stretch_patterns(db_config, verbose=False):
    """Update all movements with stretch in name to have pattern 'stretch'."""
    conn = psycopg2.connect(**db_config, cursor_factory=DictCursor)
    cursor = conn.cursor()
    
    print(f"Connected to database: {db_config['database']}\n")
    
    # Find movements with stretch variations in name
    cursor.execute("""
        SELECT id, name, pattern, primary_muscle, primary_region
        FROM movements
        WHERE name ILIKE '%stretch%' 
           OR name ILIKE '%Stretch%'
           OR name ILIKE '%Stretching%'
        ORDER BY id
    """)
    
    results = cursor.fetchall()
    
    print(f"Found {len(results)} movements with stretch in name:\n")
    
    # Update each movement
    updated_count = 0
    for i, row in enumerate(results, 1):
        old_pattern = row['pattern']
        
        if old_pattern == 'stretch':
            if verbose:
                print(f"{i}. ID {row['id']}: {row['name']} - Already has pattern 'stretch'")
            continue
        
        # Update pattern to 'stretch'
        cursor.execute("""
            UPDATE movements
            SET pattern = 'stretch'
            WHERE id = %s
        """, (row['id'],))
        
        updated_count += 1
        
        print(f"{i}. ID {row['id']}: {row['name']}")
        print(f"   Old pattern: {old_pattern}")
        print(f"   New pattern: stretch")
        print(f"   Primary muscle: {row['primary_muscle']}, Region: {row['primary_region']}")
        print()
    
    # Commit changes
    conn.commit()
    
    # Verify update
    cursor.execute("""
        SELECT COUNT(*) 
        FROM movements 
        WHERE pattern = 'stretch'
    """)
    stretch_count = cursor.fetchone()[0]
    
    print("="*80)
    print("UPDATE SUMMARY")
    print("="*80)
    print(f"\nTotal movements found: {len(results)}")
    print(f"Total movements updated: {updated_count}")
    print(f"Total movements with 'stretch' pattern: {stretch_count}")
    
    cursor.close()
    conn.close()
    print("\nDatabase connection closed.")
    
    return updated_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Update stretch movements to have pattern "stretch"',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--verbose', action='store_true', help='Print detailed information')
    
    args = parser.parse_args()
    
    db_config = get_db_config_from_env()
    
    try:
        updated = update_stretch_patterns(db_config, verbose=args.verbose)
        print(f"\n✅ Successfully updated {updated} movements")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
