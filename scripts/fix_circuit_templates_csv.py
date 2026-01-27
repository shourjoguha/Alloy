"""
Fix circuit_templates.csv for Supabase import.

Issues:
1. JSON columns (exercises_json, tags, muscle_volume, muscle_fatigue) need proper escaping
2. Curly brackets in JSON are breaking CSV parsing

Solution: Re-export with proper JSON escaping
"""

import csv
import json
from pathlib import Path


def fix_circuit_templates_csv():
    """Fix circuit_templates.csv by properly escaping JSON columns."""
    
    input_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "circuit_templates.csv"
    output_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "circuit_templates_fixed.csv"
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    fixed_rows = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        for row_num, row in enumerate(reader, 1):
            # Fix exercises_json column
            if 'exercises_json' in row and row['exercises_json']:
                # Ensure it's valid JSON
                try:
                    json.loads(row['exercises_json'])
                except json.JSONDecodeError:
                    print(f"⚠️  Row {row_num}: Invalid JSON in exercises_json")
                    continue
            
            # Fix tags column
            if 'tags' in row and row['tags']:
                try:
                    json.loads(row['tags'])
                except json.JSONDecodeError:
                    print(f"⚠️  Row {row_num}: Invalid JSON in tags")
                    continue
            
            # Fix muscle_volume column
            if 'muscle_volume' in row and row['muscle_volume']:
                try:
                    json.loads(row['muscle_volume'])
                except json.JSONDecodeError:
                    print(f"⚠️  Row {row_num}: Invalid JSON in muscle_volume")
                    continue
            
            # Fix muscle_fatigue column
            if 'muscle_fatigue' in row and row['muscle_fatigue']:
                try:
                    json.loads(row['muscle_fatigue'])
                except json.JSONDecodeError:
                    print(f"⚠️  Row {row_num}: Invalid JSON in muscle_fatigue")
                    continue
            
            fixed_rows.append(row)
    
    # Write fixed CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(fixed_rows)
    
    print(f"✅ Fixed {len(fixed_rows)} rows")
    print(f"📁 Output: {output_file}")
    print(f"📄 Columns: {headers}")


if __name__ == "__main__":
    fix_circuit_templates_csv()
