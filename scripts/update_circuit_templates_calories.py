#!/usr/bin/env python3
"""
Update circuit_templates exercises_json for movements with metric_type="calories".

For exercises in exercises_json where metric_type is "calories":
1. Set "reps" field to null
2. Update "calories" field to current "reps" value
"""
import sys
import argparse
from pathlib import Path
import json

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


def update_circuit_templates_calories(db_config, verbose=False):
    """Update circuit_templates exercises_json for calorie-based exercises."""
    conn = psycopg2.connect(**db_config, cursor_factory=DictCursor)
    cursor = conn.cursor()
    
    print(f"Connected to database: {db_config['database']}\n")
    
    # Find all circuit_templates with calorie exercises
    cursor.execute("""
        SELECT id, name, exercises_json
        FROM circuit_templates
        WHERE exercises_json::text ILIKE '%calories%'
        ORDER BY id
    """)
    
    results = cursor.fetchall()
    
    print(f"Found {len(results)} circuit_templates with 'calories' in exercises_json\n")
    
    updated_circuits = 0
    updated_exercises = 0
    
    for circuit in results:
        circuit_id = circuit['id']
        circuit_name = circuit['name']
        exercises_json = circuit['exercises_json']
        
        # Parse JSON if it's a string
        if isinstance(exercises_json, str):
            exercises = json.loads(exercises_json)
        else:
            exercises = exercises_json
        
        # Update exercises with calories metric_type
        updated = False
        for ex in exercises:
            if ex.get('metric_type') == 'calories':
                old_reps = ex.get('reps')
                old_calories = ex.get('calories')
                
                if verbose:
                    print(f"Circuit {circuit_id} ({circuit_name}):")
                    print(f"  Exercise: {ex.get('movement_name')}")
                    print(f"  Current: reps={old_reps}, calories={old_calories}")
                
                # Update: set reps to null, calories to old reps value
                ex['reps'] = None
                ex['calories'] = old_reps
                
                updated_exercises += 1
                updated = True
                
                if verbose:
                    print(f"  Updated: reps=None, calories={old_reps}")
                    print()
        
        # Update circuit if any exercises were modified
        if updated:
            cursor.execute("""
                UPDATE circuit_templates
                SET exercises_json = %s
                WHERE id = %s
            """, (json.dumps(exercises), circuit_id))
            
            updated_circuits += 1
    
    # Commit changes
    conn.commit()
    
    # Verify update
    cursor.execute("""
        SELECT id, name, exercises_json
        FROM circuit_templates
        WHERE exercises_json::text ILIKE '%calories%'
        ORDER BY id
    """)
    
    verify_results = cursor.fetchall()
    
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    print(f"\nAfter update, {len(verify_results)} circuit_templates still have 'calories' in exercises_json\n")
    
    for circuit in verify_results:
        exercises_json = circuit['exercises_json']
        if isinstance(exercises_json, str):
            exercises = json.loads(exercises_json)
        else:
            exercises = exercises_json
        
        print(f"Circuit {circuit['id']} ({circuit['name']}):")
        for ex in exercises:
            if ex.get('metric_type') == 'calories':
                print(f"  Exercise: {ex.get('movement_name')}")
                print(f"  reps={ex.get('reps')}, calories={ex.get('calories')}")
    
    cursor.close()
    conn.close()
    print("\nDatabase connection closed.")
    
    return updated_circuits, updated_exercises


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Update circuit templates calorie exercises',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument('--verbose', action='store_true', help='Print detailed information')
    
    args = parser.parse_args()
    
    db_config = get_db_config_from_env()
    
    try:
        circuits, exercises = update_circuit_templates_calories(db_config, verbose=args.verbose)
        print(f"\n✅ Successfully updated {circuits} circuits, {exercises} exercises")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
