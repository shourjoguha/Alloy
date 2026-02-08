#!/usr/bin/env python3
"""System health diagnostics for Gainsly database.

This script checks the current state of the database before and after migrations,
providing record counts and basic integrity checks.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.settings import get_settings
from app.db.database import async_session_maker


async def diagnose_system() -> dict:
    """Run diagnostics on the database."""
    settings = get_settings()
    
    async with async_session_maker() as session:
        diagnostics = {}
        
        # Table record counts
        tables_to_check = [
            'movements',
            'session_exercises',
            'muscles',
            'movement_muscle_map',
            'tags',
            'movement_tags',
            'movement_disciplines',
            'movement_equipment',
            'movement_coaching_cues',
            'sessions',
            'programs',
            'users',
            'circuit_templates'
        ]
        
        print("\n" + "=" * 70)
        print("GAINSLY DATABASE DIAGNOSTICS")
        print("=" * 70)
        print(f"\nDatabase: {settings.database_url}")
        
        print("\n" + "-" * 70)
        print("RECORD COUNTS")
        print("-" * 70)
        
        for table in tables_to_check:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            diagnostics[f'{table}_count'] = count
            print(f"  {table:<30} {count:>10}")
        
        # Check for orphaned records
        print("\n" + "-" * 70)
        print("INTEGRITY CHECKS")
        print("-" * 70)
        
        # SessionExercises with invalid movement_id
        result = await session.execute(text("""
            SELECT COUNT(*) FROM session_exercises se
            LEFT JOIN movements m ON se.movement_id = m.id
            WHERE m.id IS NULL
        """))
        orphaned = result.scalar()
        diagnostics['orphaned_session_exercises'] = orphaned
        print(f"  Orphaned session_exercises: {orphaned}")
        
        # SessionExercises with invalid session_id
        result = await session.execute(text("""
            SELECT COUNT(*) FROM session_exercises se
            LEFT JOIN sessions s ON se.session_id = s.id
            WHERE s.id IS NULL
        """))
        orphaned = result.scalar()
        diagnostics['orphaned_session_exercises_by_session'] = orphaned
        print(f"  Orphaned session_exercises (by session): {orphaned}")
        
        # MovementMuscleMap with invalid references
        result = await session.execute(text("""
            SELECT COUNT(*) FROM movement_muscle_map mm
            LEFT JOIN movements m ON mm.movement_id = m.id
            LEFT JOIN muscles ms ON mm.muscle_id = ms.id
            WHERE m.id IS NULL OR ms.id IS NULL
        """))
        orphaned = result.scalar()
        diagnostics['orphaned_muscle_maps'] = orphaned
        print(f"  Orphaned movement_muscle_map entries: {orphaned}")
        
        # MovementTags with invalid references
        result = await session.execute(text("""
            SELECT COUNT(*) FROM movement_tags mt
            LEFT JOIN movements m ON mt.movement_id = m.id
            LEFT JOIN tags t ON mt.tag_id = t.id
            WHERE m.id IS NULL OR t.id IS NULL
        """))
        orphaned = result.scalar()
        diagnostics['orphaned_movement_tags'] = orphaned
        print(f"  Orphaned movement_tags entries: {orphaned}")
        
        # Check Enum values
        print("\n" + "-" * 70)
        print("ENUM VALUE CHECKS")
        print("-" * 70)
        
        result = await session.execute(text("""
            SELECT DISTINCT primary_region FROM movements ORDER BY primary_region
        """))
        primary_regions = [row[0] for row in result.fetchall()]
        diagnostics['primary_regions_in_use'] = primary_regions
        print(f"  PrimaryRegion values in movements:")
        for region in primary_regions:
            print(f"    - {region}")
        
        result = await session.execute(text("""
            SELECT DISTINCT session_section FROM session_exercises ORDER BY session_section
        """))
        session_sections = [row[0] for row in result.fetchall()]
        diagnostics['session_sections_in_use'] = session_sections
        print(f"\n  SessionSection values in session_exercises:")
        for section in session_sections:
            print(f"    - {section}")
        
        result = await session.execute(text("""
            SELECT DISTINCT role FROM session_exercises ORDER BY role
        """))
        exercise_roles = [row[0] for row in result.fetchall()]
        diagnostics['exercise_roles_in_use'] = exercise_roles
        print(f"\n  ExerciseRole values in session_exercises:")
        for role in exercise_roles:
            print(f"    - {role}")
        
        print("\n" + "=" * 70)
        print("DIAGNOSTICS COMPLETE")
        print("=" * 70 + "\n")
        
        return diagnostics


async def main():
    """Main entry point."""
    try:
        diagnostics = await diagnose_system()
        
        # Exit with error if orphaned records found
        if diagnostics.get('orphaned_session_exercises', 0) > 0:
            sys.exit(1)
        if diagnostics.get('orphaned_session_exercises_by_session', 0) > 0:
            sys.exit(1)
        if diagnostics.get('orphaned_muscle_maps', 0) > 0:
            sys.exit(1)
        if diagnostics.get('orphaned_movement_tags', 0) > 0:
            sys.exit(1)
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
