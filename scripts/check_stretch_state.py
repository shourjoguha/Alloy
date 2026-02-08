#!/usr/bin/env python3
"""Check current state of stretch movements."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import DictCursor
from app.config.settings import get_settings
import re

settings = get_settings()
url = settings.database_url.replace('postgresql+asyncpg://', 'postgresql://')
match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', url)

conn = psycopg2.connect(
    host=match.group(3),
    port=int(match.group(4)),
    database=match.group(5),
    user=match.group(1),
    password=match.group(2),
    cursor_factory=DictCursor
)

cursor = conn.cursor()

# Check current patterns of stretch movements
cursor.execute("""
    SELECT id, name, pattern, primary_muscle, primary_region
    FROM movements
    WHERE name ILIKE '%stretch%' 
       OR name ILIKE '%Stretch%'
       OR name ILIKE '%Stretching%'
    ORDER BY id
    LIMIT 10
""")

results = cursor.fetchall()

print(f'Current state of stretch movements (first 10):\n')
for r in results:
    print(f'ID {r["id"]}: {r["name"]}')
    print(f'  Pattern: {r["pattern"]}, Muscle: {r["primary_muscle"]}, Region: {r["primary_region"]}')
    print()

# Count patterns
cursor.execute("""
    SELECT pattern, COUNT(*) as count
    FROM movements
    WHERE name ILIKE '%stretch%' 
       OR name ILIKE '%Stretch%'
       OR name ILIKE '%Stretching%'
    GROUP BY pattern
    ORDER BY count DESC
""")

pattern_counts = cursor.fetchall()

print('Pattern distribution:')
for pc in pattern_counts:
    print(f'  {pc["pattern"]}: {pc["count"]}')

conn.close()
