"""
Check the structure of exercises_json in circuit_templates.csv
"""

import csv
from pathlib import Path


def check_circuit_json():
    """Check exercises_json structure."""
    
    input_file = Path(__file__).parent.parent / "Manual-CSV Upload" / "circuit_templates.csv"
    
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader, 1):
            exercises_json = row.get('exercises_json', '')
            print(f"Row {i}: {exercises_json[:150]}...")
            if i >= 3:
                break


if __name__ == "__main__":
    check_circuit_json()
