"""Check circuit tables for consistency and orphaned records."""

import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.db.database import get_db


async def check_circuit_consistency():
    async for db in get_db():
        try:
            print("=" * 80)
            print("CIRCUIT TABLE CONSISTENCY CHECK")
            print("=" * 80)
            print()

            # 1. Basic counts
            result = await db.execute(text("""
                SELECT 
                    (SELECT COUNT(*) FROM circuit_templates) as total_circuits,
                    (SELECT COUNT(*) FROM circuits_melted) as melted_records,
                    (SELECT COUNT(*) FROM circuits_macro) as macro_records,
                    (SELECT COUNT(DISTINCT circuit_id) FROM circuits_melted) as circuits_with_melted,
                    (SELECT COUNT(DISTINCT circuit_id) FROM circuits_macro) as circuits_with_macro
            """))
            basic_counts = result.one()
            print("1. BASIC COUNTS")
            print("-" * 80)
            print(f"   Total circuits (circuit_templates): {basic_counts.total_circuits}")
            print(f"   Total melted records: {basic_counts.melted_records}")
            print(f"   Total macro records: {basic_counts.macro_records}")
            print(f"   Circuits with melted data: {basic_counts.circuits_with_melted}")
            print(f"   Circuits with macro data: {basic_counts.circuits_with_macro}")
            print()

            # 2. Check circuits without macro data
            result = await db.execute(text("""
                SELECT ct.id, ct.name, ct.circuit_type
                FROM circuit_templates ct
                LEFT JOIN circuits_macro cm ON ct.id = cm.circuit_id
                WHERE cm.circuit_id IS NULL
                ORDER BY ct.id
            """))
            circuits_without_macro = result.fetchall()
            print("2. CIRCUITS WITHOUT MACRO DATA")
            print("-" * 80)
            print(f"   Count: {len(circuits_without_macro)}")
            if circuits_without_macro:
                for row in circuits_without_macro:
                    print(f"   - ID {row[0]}: {row[1]} (type: {row[2]})")
            else:
                print("   All circuits have macro data")
            print()

            # 3. Check circuits without melted data
            result = await db.execute(text("""
                SELECT ct.id, ct.name, ct.circuit_type
                FROM circuit_templates ct
                LEFT JOIN circuits_melted cml ON ct.id = cml.circuit_id
                WHERE cml.circuit_id IS NULL
                ORDER BY ct.id
            """))
            circuits_without_melted = result.fetchall()
            print("3. CIRCUITS WITHOUT MELTED DATA")
            print("-" * 80)
            print(f"   Count: {len(circuits_without_melted)}")
            if circuits_without_melted:
                for row in circuits_without_melted:
                    print(f"   - ID {row[0]}: {row[1]} (type: {row[2]})")
            else:
                print("   All circuits have melted data")
            print()

            # 4. Check for orphaned macro records (no matching circuit_template)
            result = await db.execute(text("""
                SELECT DISTINCT cm.circuit_id
                FROM circuits_macro cm
                LEFT JOIN circuit_templates ct ON cm.circuit_id = ct.id
                WHERE ct.id IS NULL
            """))
            orphaned_macro = result.fetchall()
            print("4. ORPHANED MACRO RECORDS")
            print("-" * 80)
            print(f"   Count: {len(orphaned_macro)}")
            if orphaned_macro:
                for row in orphaned_macro:
                    print(f"   - circuit_id {row[0]}")
            else:
                print("   No orphaned macro records")
            print()

            # 5. Check for orphaned melted records (no matching circuit_template)
            result = await db.execute(text("""
                SELECT DISTINCT cml.circuit_id
                FROM circuits_melted cml
                LEFT JOIN circuit_templates ct ON cml.circuit_id = ct.id
                WHERE ct.id IS NULL
            """))
            orphaned_melted = result.fetchall()
            print("5. ORPHANED MELTED RECORDS")
            print("-" * 80)
            print(f"   Count: {len(orphaned_melted)}")
            if orphaned_melted:
                for row in orphaned_melted:
                    print(f"   - circuit_id {row[0]}")
            else:
                print("   No orphaned melted records")
            print()

            # 6. Check melted record distribution per circuit
            result = await db.execute(text("""
                SELECT
                    cml.circuit_id,
                    ct.name,
                    COUNT(*) as exercise_count,
                    COUNT(DISTINCT cml.metric_type) as unique_metric_types
                FROM circuits_melted cml
                JOIN circuit_templates ct ON cml.circuit_id = ct.id
                GROUP BY cml.circuit_id, ct.name
                ORDER BY cml.circuit_id
            """))
            melted_distribution = result.fetchall()
            print("6. MELTED RECORDS PER CIRCUIT")
            print("-" * 80)
            for row in melted_distribution:
                print(f"   - ID {row[0]} ({row[1]}): {row[2]} exercises, {row[3]} unique metric types")
            print()

            # 7. Check for data completeness in macro
            result = await db.execute(text("""
                SELECT
                    cm.circuit_id,
                    ct.name,
                    cm.total_exercises,
                    cm.unique_movements,
                    cm.data_completeness_score
                FROM circuits_macro cm
                JOIN circuit_templates ct ON cm.circuit_id = ct.id
                ORDER BY cm.data_completeness_score ASC
            """))
            macro_completeness = result.fetchall()
            print("7. MACRO DATA COMPLETENESS")
            print("-" * 80)
            for row in macro_completeness:
                print(f"   - ID {row[0]} ({row[1]}): {row[2]} exercises, {row[3]} unique movements, completeness: {row[4]:.2f}")
            print()

            # 8. Check for data integrity issues
            print("8. DATA INTEGRITY CHECKS")
            print("-" * 80)
            
            # Check for circuits with macro but no melted data
            result = await db.execute(text("""
                SELECT ct.id, ct.name
                FROM circuit_templates ct
                JOIN circuits_macro cm ON ct.id = cm.circuit_id
                LEFT JOIN circuits_melted cml ON ct.id = cml.circuit_id
                WHERE cml.circuit_id IS NULL
            """))
            macro_no_melted = result.fetchall()
            print(f"   Circuits with macro but NO melted data: {len(macro_no_melted)}")
            if macro_no_melted:
                for row in macro_no_melted:
                    print(f"   - ID {row[0]}: {row[1]}")
            
            # Check for circuits with melted but no macro data
            result = await db.execute(text("""
                SELECT DISTINCT ct.id, ct.name
                FROM circuit_templates ct
                JOIN circuits_melted cml ON ct.id = cml.circuit_id
                LEFT JOIN circuits_macro cm ON ct.id = cm.circuit_id
                WHERE cm.circuit_id IS NULL
            """))
            melted_no_macro = result.fetchall()
            print(f"   Circuits with melted but NO macro data: {len(melted_no_macro)}")
            if melted_no_macro:
                for row in melted_no_macro:
                    print(f"   - ID {row[0]}: {row[1]}")
            print()

            # 9. Summary
            print("=" * 80)
            print("SUMMARY")
            print("=" * 80)
            print(f"Total circuit_templates: {basic_counts.total_circuits}")
            print(f"Total circuits_macro: {basic_counts.macro_records}")
            print(f"Total circuits_melted: {basic_counts.melted_records}")
            print(f"Circuits missing macro: {len(circuits_without_macro)}")
            print(f"Circuits missing melted: {len(circuits_without_melted)}")
            print(f"Orphaned macro records: {len(orphaned_macro)}")
            print(f"Orphaned melted records: {len(orphaned_melted)}")
            print(f"Circuits with macro but no melted: {len(macro_no_melted)}")
            print(f"Circuits with melted but no macro: {len(melted_no_macro)}")
            print()

            # Issues found
            issues = []
            if circuits_without_macro:
                issues.append(f"{len(circuits_without_macro)} circuits missing macro data")
            if circuits_without_melted:
                issues.append(f"{len(circuits_without_melted)} circuits missing melted data")
            if orphaned_macro:
                issues.append(f"{len(orphaned_macro)} orphaned macro records")
            if orphaned_melted:
                issues.append(f"{len(orphaned_melted)} orphaned melted records")
            if macro_no_melted:
                issues.append(f"{len(macro_no_melted)} circuits with macro but no melted data")
            if melted_no_macro:
                issues.append(f"{len(melted_no_macro)} circuits with melted but no macro data")

            if issues:
                print("ISSUES FOUND:")
                print("-" * 80)
                for issue in issues:
                    print(f"   - {issue}")
            else:
                print("NO ISSUES FOUND - Database is consistent!")
            print()

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    asyncio.run(check_circuit_consistency())
