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
    headers = None
    
    print(f"📖 Reading: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        # Read raw lines and parse manually
        reader = csv.reader(f)
        headers = next(reader)
        print(f"📋 Headers: {headers}")
        
        for row_num, row in enumerate(reader, 1):
            # Create dict from row
            row_dict = dict(zip(headers, row))
            
            # Validate JSON columns exist and are valid
            valid_row = True
            
            # Check exercises_json
            if 'exercises_json' in row_dict and row_dict['exercises_json']:
                if not row_dict['exercises_json'].strip() or row_dict['exercises_json'] == '{}':
                    # Empty JSON - set to empty array
                    row_dict['exercises_json'] = '[]'
                else:
                    try:
                        # Try to parse and validate JSON
                        json.loads(row_dict['exercises_json'])
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Row {row_num}: Invalid exercises_json - skipping row")
                        valid_row = False
                    except Exception as e:
                        print(f"⚠️  Row {row_num}: Error in exercises_json: {e} - skipping row")
                        valid_row = False
            
            # Check tags
            if 'tags' in row_dict and row_dict['tags']:
                if not row_dict['tags'].strip() or row_dict['tags'] == '{}':
                    row_dict['tags'] = '[]'
                else:
                    try:
                        json.loads(row_dict['tags'])
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Row {row_num}: Invalid tags - skipping row")
                        valid_row = False
            
            # Check muscle_volume
            if 'muscle_volume' in row_dict and row_dict['muscle_volume']:
                if not row_dict['muscle_volume'].strip() or row_dict['muscle_volume'] == '{}':
                    row_dict['muscle_volume'] = '{}'
                else:
                    try:
                        json.loads(row_dict['muscle_volume'])
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Row {row_num}: Invalid muscle_volume - skipping row")
                        valid_row = False
            
            # Check muscle_fatigue
            if 'muscle_fatigue' in row_dict and row_dict['muscle_fatigue']:
                if not row_dict['muscle_fatigue'].strip() or row_dict['muscle_fatigue'] == '{}':
                    row_dict['muscle_fatigue'] = '{}'
                else:
                    try:
                        json.loads(row_dict['muscle_fatigue'])
                    except json.JSONDecodeError as e:
                        print(f"⚠️  Row {row_num}: Invalid muscle_fatigue - skipping row")
                        valid_row = False
            
            if valid_row:
                fixed_rows.append(row_dict)
    
    # Write fixed CSV with proper JSON escaping
    print(f"✅ Valid rows: {len(fixed_rows)}")
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(fixed_rows)
    
    print(f"📁 Output: {output_file}")
    print()
    print("📌 Next Steps:")
    print("1. Import circuit_templates_fixed.csv into Supabase")
    print("2. The JSON columns will be properly formatted as JSONB")
    print()


if __name__ == "__main__":
    fix_circuit_templates_csv()
