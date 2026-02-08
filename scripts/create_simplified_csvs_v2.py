"""
Create simplified CSV files for Supabase import.

Solutions:
1. circuit_templates - Remove complex JSON columns that cause parsing issues
2. movements - Remove embedding_vector column (can be repopulated later)
"""

import csv
from pathlib import Path


def simplify_circuit_templates():
    """Create circuit_templates_simplified.csv without complex JSON columns."""
    
    input_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "circuit_templates.csv"
    output_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "circuit_templates_simplified.csv"
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    simplified_rows = []
    
    print(f"📖 Reading: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, 1):
            # Keep only simple columns, remove complex JSON ones
            simplified_row = {
                'id': row.get('id') if row.get('id') else '',
                'name': row.get('name') if row.get('name') else '',
                'description': row.get('description') if row.get('description') else '',
                'circuit_type': row.get('circuit_type') if row.get('circuit_type') else '',
                'default_rounds': row.get('default_rounds') if row.get('default_rounds') else '',
                'default_duration_seconds': row.get('default_duration_seconds') if row.get('default_duration_seconds') else '',
                'difficulty_tier': row.get('difficulty_tier') if row.get('difficulty_tier') else '',
                'fatigue_factor': row.get('fatigue_factor') if row.get('fatigue_factor') else '',
                'stimulus_factor': row.get('stimulus_factor') if row.get('stimulus_factor') else '',
                'min_recovery_hours': row.get('min_recovery_hours') if row.get('min_recovery_hours') else '',
                'total_reps': row.get('total_reps') if row.get('total_reps') else '',
                'estimated_work_seconds': row.get('estimated_work_seconds') if row.get('estimated_work_seconds') else '',
                'effective_work_volume': row.get('effective_work_volume') if row.get('effective_work_volume') else '',
            }
            
            simplified_rows.append(simplified_row)
    
    # Write simplified CSV
    headers = ['id', 'name', 'description', 'circuit_type', 'default_rounds', 
                 'default_duration_seconds', 'difficulty_tier', 'fatigue_factor', 
                 'stimulus_factor', 'min_recovery_hours', 'total_reps', 
                 'estimated_work_seconds', 'effective_work_volume']
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(simplified_rows)
    
    print(f"✅ Simplified {len(simplified_rows)} rows")
    print(f"📁 Output: {output_file}")
    print()
    print("❌ Removed columns (complex JSON):")
    print("   - exercises_json (can be repopulated later)")
    print("   - tags")
    print("   - bucket_stress")
    print("   - muscle_volume")
    print("   - muscle_fatigue")
    print()


def simplify_movements():
    """Create movements_simplified.csv without embedding_vector column."""
    
    input_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "movements.csv"
    output_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "movements_simplified.csv"
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        return
    
    simplified_rows = []
    
    print(f"📖 Reading: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, 1):
            # Remove embedding_vector column
            simplified_row = {k: v for k, v in row.items() if k != 'embedding_vector'}
            
            # Set embedding_vector to NULL string for import
            # Will be repopulated later via code
            simplified_rows.append(simplified_row)
    
    # Write simplified CSV
    new_headers = [h for h in reader.fieldnames if h != 'embedding_vector']
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_headers, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(simplified_rows)
    
    print(f"✅ Simplified {len(simplified_rows)} rows")
    print(f"📁 Output: {output_file}")
    print()
    print("❌ Removed column:")
    print("   - embedding_vector (can be repopulated later via code)")
    print()


def main():
    """Run both simplifications."""
    print("🔧 Creating simplified CSV files for Supabase import")
    print("=" * 60)
    print()
    
    print("1️⃣  Circuit Templates:")
    simplify_circuit_templates()
    
    print("2️⃣  Movements:")
    simplify_movements()
    
    print("=" * 60)
    print()
    print("✅ Both files created successfully!")
    print()
    print("📋 Next Steps:")
    print("1. Import circuit_templates_simplified.csv into Supabase")
    print("2. Import movements_simplified.csv into Supabase")
    print("3. After successful import, repopulate:")
    print("   - circuit_templates.exercises_json (via seed_data/ files)")
    print("   - movements.embedding_vector (via ML/vector generation)")
    print()


if __name__ == "__main__":
    main()
