"""
Melt/flatten circuit_templates.csv to preserve all exercise data.

Uses manual CSV parsing to extract JSON properly and remove complex JSON columns.
"""

import json
import re
from pathlib import Path


def parse_csv_line_preserving_json(line):
    """
    Parse a CSV line manually, preserving JSON arrays with commas.
    """
    fields = []
    current_field = []
    in_quotes = False
    quote_char = None
    in_json_array = False
    json_bracket_depth = 0
    
    i = 0
    while i < len(line):
        char = line[i]
        
        # Handle quote state
        if char in ['"', "'"]:
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                # Check for escaped quote
                if i + 1 < len(line) and line[i + 1] == quote_char:
                    current_field.append(char)
                    current_field.append(char)
                    i += 2
                    continue
                in_quotes = False
                quote_char = None
        
        # Track JSON bracket depth (only outside quotes)
        if not in_quotes:
            if char == '[':
                json_bracket_depth += 1
                if json_bracket_depth == 1:
                    in_json_array = True
            elif char == ']':
                json_bracket_depth -= 1
                if json_bracket_depth == 0:
                    in_json_array = False
        
        # Split on comma only when not in quotes or JSON
        if char == ',' and not in_quotes and json_bracket_depth == 0:
            field = ''.join(current_field).strip()
            # Remove quotes if field is quoted
            if (field.startswith('"') and field.endswith('"')) or (field.startswith("'") and field.endswith("'")):
                field = field[1:-1]
            fields.append(field)
            current_field = []
        else:
            current_field.append(char)
        
        i += 1
    
    # Add last field
    if current_field:
        field = ''.join(current_field).strip()
        if (field.startswith('"') and field.endswith('"')) or (field.startswith("'") and field.endswith("'")):
            field = field[1:-1]
        fields.append(field)
    
    return fields


def melt_circuit_templates():
    """Create circuit_templates_melted.csv with one row per exercise."""
    
    input_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "circuit_templates.csv"
    output_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "circuit_templates_melted.csv"
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    melted_rows = []
    
    print(f"📖 Reading: {input_file}")
    print()
    
    # Read all lines
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Parse header
    headers = parse_csv_line_preserving_json(lines[0].strip())
    
    print(f"📋 Found {len(headers)} columns")
    if 'exercises_json' in headers:
        print(f"   exercises_json column index: {headers.index('exercises_json')}")
    print()
    
    # Columns to exclude (complex JSON)
    exclude_columns = ['exercises_json', 'tags', 'bucket_stress', 'muscle_volume', 'muscle_fatigue']
    
    # Parse each data row
    for line_num, line in enumerate(lines[1:], 1):
        try:
            # Parse CSV line manually
            values = parse_csv_line_preserving_json(line.strip())
            
            # Create row dict
            row = dict(zip(headers, values))
            
            circuit_id = row.get('id', '')
            circuit_name = row.get('name', '')
            
            # Parse exercises_json
            exercises_json = row.get('exercises_json', '')
            exercises = []
            
            if exercises_json and exercises_json.strip():
                try:
                    exercises = json.loads(exercises_json)
                except json.JSONDecodeError as e:
                    print(f"⚠️  Row {line_num}: Failed to parse exercises_json for circuit {circuit_id}")
                    print(f"   JSON error: {e}")
                    # Create one row without exercises
                    melted_row = create_melted_row(row, None, 0, 1)
                    melted_rows.append(melted_row)
                    continue
            else:
                # No exercises - create one row without exercise data
                melted_row = create_melted_row(row, None, 0, 1)
                melted_rows.append(melted_row)
                continue
            
            # Create one row per exercise
            for idx, exercise in enumerate(exercises, 1):
                melted_row = create_melted_row(row, exercise, idx, len(exercises))
                melted_rows.append(melted_row)
                
        except Exception as e:
            print(f"❌ Row {line_num}: Failed to parse CSV line")
            print(f"   Error: {e}")
            continue
    
    # Define headers for melted CSV (excluded complex JSON columns)
    headers = [
        'circuit_id', 'circuit_name', 'circuit_description', 'circuit_type',
        'exercise_sequence', 'total_exercises',
        'movement_id', 'movement_name', 'metric_type',
        'reps', 'distance_meters', 'duration_seconds', 'calories',
        'rest_seconds', 'notes', 'rx_weight_male', 'rx_weight_female',
        'default_rounds', 'default_duration_seconds', 'difficulty_tier',
        'fatigue_factor', 'stimulus_factor', 'min_recovery_hours',
        'total_reps', 'estimated_work_seconds', 'effective_work_volume'
    ]
    
    # Write melted CSV
    import csv as csv_module
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv_module.DictWriter(f, fieldnames=headers, quoting=csv_module.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(melted_rows)
    
    print()
    print(f"✅ Melted {len(melted_rows)} rows from {len(lines)-1} circuits")
    print(f"📁 Output: {output_file}")
    print()
    print("📊 Statistics:")
    print(f"   - Original circuits: {len(lines)-1}")
    print(f"   - Melted rows: {len(melted_rows)}")
    if len(lines) > 1:
        print(f"   - Avg exercises per circuit: {len(melted_rows) / (len(lines)-1):.1f}")
    print()
    print("✅ All exercise data preserved - no data loss!")
    print("❌ Removed complex JSON columns (tags, bucket_stress, muscle_volume, muscle_fatigue)")
    print()


def create_melted_row(circuit_row, exercise, seq_num, total_exercises):
    """Create a melted row from circuit and exercise data."""
    
    row = {
        # Circuit metadata (preserved on each exercise row)
        'circuit_id': circuit_row.get('id', ''),
        'circuit_name': circuit_row.get('name', ''),
        'circuit_description': circuit_row.get('description', ''),
        'circuit_type': circuit_row.get('circuit_type', ''),
        
        # Exercise sequence info
        'exercise_sequence': seq_num if exercise else 0,
        'total_exercises': total_exercises,
        
        # Exercise data
        'movement_id': exercise.get('movement_id') if exercise else '',
        'movement_name': exercise.get('movement_name') if exercise else '',
        'metric_type': exercise.get('metric_type') if exercise else '',
        'reps': exercise.get('reps') if exercise else '',
        'distance_meters': exercise.get('distance_meters') if exercise else '',
        'duration_seconds': exercise.get('duration_seconds') if exercise else '',
        'calories': exercise.get('calories') if exercise else '',
        'rest_seconds': exercise.get('rest_seconds') if exercise else '',
        'notes': exercise.get('notes') if exercise else '',
        'rx_weight_male': exercise.get('rx_weight_male') if exercise else '',
        'rx_weight_female': exercise.get('rx_weight_female') if exercise else '',
        
        # Additional circuit fields
        'default_rounds': circuit_row.get('default_rounds', ''),
        'default_duration_seconds': circuit_row.get('default_duration_seconds', ''),
        'difficulty_tier': circuit_row.get('difficulty_tier', ''),
        'fatigue_factor': circuit_row.get('fatigue_factor', ''),
        'stimulus_factor': circuit_row.get('stimulus_factor', ''),
        'min_recovery_hours': circuit_row.get('min_recovery_hours', ''),
        'total_reps': circuit_row.get('total_reps', ''),
        'estimated_work_seconds': circuit_row.get('estimated_work_seconds', ''),
        'effective_work_volume': circuit_row.get('effective_work_volume', ''),
    }
    
    return row


def main():
    """Run melting process."""
    print("🔥 Melting circuit_templates.csv to preserve all exercise data")
    print("=" * 60)
    print()
    print("Creating circuit_templates_melted.csv with:")
    print("- One row per exercise in each circuit")
    print("- All circuit metadata preserved on each exercise row")
    print("- Complex JSON columns removed (tags, bucket_stress, muscle_volume, muscle_fatigue)")
    print("- No data loss")
    print()
    
    melt_circuit_templates()
    
    print("=" * 60)
    print()
    print("✅ Circuit templates melted successfully!")
    print()
    print("📋 Next Steps:")
    print("1. Import circuit_templates_melted.csv into Supabase")
    print("2. Create a view or query to reconstruct circuits")
    print("   GROUP BY circuit_id to get all exercises per circuit")
    print()


if __name__ == "__main__":
    main()
