#!/usr/bin/env python3
"""
Update circuits_melted table for movements with metric_type="calories".

For records where metric_type is "calories":
1. Set "reps" field to NULL
2. Update "calories" field value to the current "reps" value (typically 20)

Also updates related circuit_macro tables and other dependencies.
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


def update_circuit_calories(db_config, verbose=False):
    """Update circuits_melted table for calorie-based movements."""
    conn = psycopg2.connect(**db_config, cursor_factory=DictCursor)
    cursor = conn.cursor()
    
    print(f"Connected to database: {db_config['database']}\n")
    
    # Find all records with metric_type="calories"
    cursor.execute("""
        SELECT id, circuit_id, movement_id, exercise_sequence, metric_type, reps, calories
        FROM circuits_melted
        WHERE metric_type = 'calories'
        ORDER BY circuit_id, exercise_sequence
    """)
    
    results = cursor.fetchall()
    
    print(f"Found {len(results)} records with metric_type='calories':\n")
    
    # Update each record
    updated_count = 0
    for i, row in enumerate(results, 1):
        old_reps = row['reps']
        old_calories = row['calories']
        
        if verbose:
            print(f"{i}. ID {row['id']}: Circuit {row['circuit_id']}, Movement {row['movement_id']}, Seq {row['exercise_sequence']}")
            print(f"   Current: reps={old_reps}, calories={old_calories}")
        
        # Update: set reps to NULL, calories to the old reps value
        cursor.execute("""
            UPDATE circuits_melted
            SET reps = NULL,
                calories = %s
            WHERE id = %s
        """, (old_reps, row['id']))
        
        updated_count += 1
        
        if verbose:
            print(f"   Updated: reps=NULL, calories={old_reps}")
            print()
    
    # Commit changes
    conn.commit()
    
    # Verify update
    cursor.execute("""
        SELECT id, circuit_id, movement_id, metric_type, reps, calories
        FROM circuits_melted
        WHERE metric_type = 'calories'
        ORDER BY circuit_id, exercise_sequence
    """)
    
    verify_results = cursor.fetchall()
    
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    print(f"\nAfter update, {len(verify_results)} records with metric_type='calories':\n")
    
    for row in verify_results:
        print(f"ID {row['id']}: reps={row['reps']}, calories={row['calories']}")
    
    # Check for other tables that might need updates
    print("\n" + "="*80)
    print("CHECKING OTHER TABLES")
    print("="*80)
    
    # Check if there are any other circuit-related tables with calorie data
    tables_to_check = [
        'circuit_templates',
        'sessions',
        'session_exercises',
    ]
    
    for table in tables_to_check:
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = %s 
            AND column_name = 'calories'
        """, (table,))
        
        has_calories_col = cursor.fetchone()[0] > 0
        
        if has_calories_col:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"\n{table}: has 'calories' column ({count} rows)")
        else:
            print(f"\n{table}: no 'calories' column")
    
    # Check circuit_templates exercises_json for calorie data
    cursor.execute("""
        SELECT COUNT(*) 
        FROM circuit_templates
        WHERE exercises_json::text ILIKE '%calories%'
    """)
    json_count = cursor.fetchone()[0]
    
    if json_count > 0:
        print(f"\ncircuit_templates: {json_count} records with 'calories' in exercises_json")
        print("  Note: exercises_json may contain calorie data that needs manual review")
    
    cursor.close()
    conn.close()
    print("\nDatabase connection closed.")
    
    return updated_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Update circuit calories metric data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--verbose', action='store_true', help='Print detailed information')
    
    args = parser.parse_args()
    
    db_config = get_db_config_from_env()
    
    try:
        updated = update_circuit_calories(db_config, verbose=args.verbose)
        print(f"\n✅ Successfully updated {updated} records")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
