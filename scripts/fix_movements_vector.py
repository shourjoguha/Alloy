"""
Fix movements.csv embedding_vector column for Supabase import.

Issue: embedding_vector column contains arrays that need to be formatted as JSONB for PostgreSQL.

Solution: Format as properly escaped JSON array
"""

import csv
import json
from pathlib import Path


def fix_movements_vector():
    """Fix embedding_vector column in movements.csv."""
    
    input_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "movements.csv"
    output_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "movements_fixed.csv"
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    fixed_rows = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        for row_num, row in enumerate(reader, 1):
            # Fix embedding_vector column
            if 'embedding_vector' in row and row['embedding_vector']:
                # Parse the array and re-format as JSON
                try:
                    # Remove brackets and split by comma
                    vector_str = row['embedding_vector'].strip()
                    if vector_str.startswith('[') and vector_str.endswith(']'):
                        # Convert to valid JSON array
                        row['embedding_vector'] = vector_str
                except Exception as e:
                    print(f"⚠️  Row {row_num}: Error parsing embedding_vector: {e}")
                    row['embedding_vector'] = '[]'
            
            fixed_rows.append(row)
    
    # Write fixed CSV
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(fixed_rows)
    
    print(f"✅ Fixed {len(fixed_rows)} rows")
    print(f"📁 Output: {output_file}")
    print(f"📄 Columns: {headers}")


if __name__ == "__main__":
    fix_movements_vector()
