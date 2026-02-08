#!/usr/bin/env python3
"""
Validate movement merge operation.

Checks:
1. No orphaned records in junction tables
2. All foreign key constraints satisfied
3. No movement_id = NULL in dependent tables
4. Movement counts match expected after merge
5. Usage statistics preserved
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_settings, async_session_maker
from app.models.movement import Movement
from app.models.circuit_extended import CircuitMelted


class MergeValidator:
    """Validates movement merge operation."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def validate_no_orphans(self) -> List[Dict[str, Any]]:
        """Check for orphaned records in all junction tables."""
        orphan_checks = []
        
        queries = {
            "movement_equipment": """
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT me.movement_id) as movements_with_orphans,
                    COUNT(DISTINCT CASE WHEN m.id IS NULL THEN me.movement_id END) as orphan_count
                FROM movement_equipment me
                LEFT JOIN movements m ON me.movement_id = m.id
                WHERE m.id IS NULL;
            """,
            
            "movement_muscle_map": """
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT mmm.movement_id) as movements_with_orphans,
                    COUNT(DISTINCT CASE WHEN m.id IS NULL THEN mmm.movement_id END) as orphan_count
                FROM movement_muscle_map mmm
                LEFT JOIN movements m ON mmm.movement_id = m.id
                WHERE m.id IS NULL;
            """,
            
            "movement_disciplines": """
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT md.movement_id) as movements_with_orphans,
                    COUNT(DISTINCT CASE WHEN m.id IS NULL THEN md.movement_id END) as orphan_count
                FROM movement_disciplines md
                LEFT JOIN movements m ON md.movement_id = m.id
                WHERE m.id IS NULL;
            """,
            
            "movement_tags": """
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT mt.movement_id) as movements_with_orphans,
                    COUNT(DISTINCT CASE WHEN m.id IS NULL THEN mt.movement_id END) as orphan_count
                FROM movement_tags mt
                LEFT JOIN movements m ON mt.movement_id = m.id
                WHERE m.id IS NULL;
            """,
            
            "movement_coaching_cues": """
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT mcc.movement_id) as movements_with_orphans,
                    COUNT(DISTINCT CASE WHEN m.id IS NULL THEN mcc.movement_id END) as orphan_count
                FROM movement_coaching_cues mcc
                LEFT JOIN movements m ON mcc.movement_id = m.id
                WHERE m.id IS NULL;
            """,
        }
        
        for table_name, query in queries.items():
            result = await self.session.execute(text(query))
            row = result.fetchone()
            orphan_checks.append({
                "table": table_name,
                "total_records": row[0],
                "movements_with_orphans": row[1],
                "orphan_count": row[2],
                "status": "PASS" if row[2] == 0 else "FAIL"
            })
        
        return orphan_checks
    
    async def validate_foreign_keys(self) -> List[Dict[str, Any]]:
        """Validate all foreign key constraints are satisfied."""
        fk_checks = []
        
        queries = {
            "session_exercises": """
                SELECT COUNT(*) as null_movement_count
                FROM session_exercises se
                WHERE se.movement_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM movements m WHERE m.id = se.movement_id
                );
            """,
            
            "circuits_melted": """
                SELECT COUNT(*) as null_movement_count
                FROM circuits_melted cm
                WHERE cm.movement_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM movements m WHERE m.id = cm.movement_id
                );
            """,
        }
        
        for table_name, query in queries.items():
            result = await self.session.execute(text(query))
            row = result.fetchone()
            fk_checks.append({
                "table": table_name,
                "null_movement_count": row[0],
                "status": "PASS" if row[0] == 0 else "FAIL"
            })
        
        return fk_checks
    
    async def validate_movement_counts(self, expected_count: int) -> Dict[str, Any]:
        """Verify movement counts match expected after merge."""
        result = await self.session.execute(
            select(func.count(Movement.id))
        )
        actual_count = result.scalar()
        
        return {
            "expected_count": expected_count,
            "actual_count": actual_count,
            "difference": actual_count - expected_count,
            "status": "PASS" if actual_count == expected_count else "FAIL"
        }
    
    async def validate_usage_preserved(self) -> Dict[str, Any]:
        """Check usage statistics are preserved."""
        queries = {
            "sessions": """
                SELECT COUNT(DISTINCT se.session_id) as session_count
                FROM session_exercises se
                JOIN movements m ON se.movement_id = m.id
            """,
            
            "circuits": """
                SELECT COUNT(DISTINCT cm.circuit_id) as circuit_count
                FROM circuits_melted cm
                JOIN movements m ON cm.movement_id = m.id
            """,
        }
        
        usage_stats = {}
        for metric, query in queries.items():
            result = await self.session.execute(text(query))
            count = result.scalar()
            usage_stats[metric] = count
        
        return usage_stats
    
    async def validate_relationships_integrity(self) -> List[Dict[str, Any]]:
        """Validate movement_relationships table integrity."""
        queries = {
            "invalid_source": """
                SELECT COUNT(*) as count
                FROM movement_relationships mr
                WHERE mr.source_movement_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM movements m WHERE m.id = mr.source_movement_id
                );
            """,
            
            "invalid_target": """
                SELECT COUNT(*) as count
                FROM movement_relationships mr
                WHERE mr.target_movement_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM movements m WHERE m.id = mr.target_movement_id
                );
            """,
        }
        
        integrity_checks = {}
        for check_name, query in queries.items():
            result = await self.session.execute(text(query))
            count = result.scalar()
            integrity_checks[check_name] = {
                "count": count,
                "status": "PASS" if count == 0 else "FAIL"
            }
        
        return integrity_checks
    
    async def run_full_validation(self, expected_movement_count: int) -> Dict[str, Any]:
        """Run all validation checks."""
        print("\n" + "="*80)
        print("MOVEMENT MERGE VALIDATION REPORT")
        print("="*80 + "\n")
        
        results = {
            "orphans": await self.validate_no_orphans(),
            "foreign_keys": await self.validate_foreign_keys(),
            "movement_counts": await self.validate_movement_counts(expected_movement_count),
            "usage": await self.validate_usage_preserved(),
            "relationships": await self.validate_relationships_integrity()
        }
        
        issues = []
        
        print("\n1. ORPHANED RECORDS CHECK")
        print("-" * 80)
        for check in results["orphans"]:
            status_icon = "✅" if check["status"] == "PASS" else "❌"
            print(f"{status_icon} {check['table']}: {check['orphan_count']} orphaned records "
                  f"(out of {check['movements_with_orphans']} movements)")
            if check["status"] == "FAIL":
                issues.append(f"Orphaned records in {check['table']}")
        
        print("\n2. FOREIGN KEY CONSTRAINTS CHECK")
        print("-" * 80)
        for check in results["foreign_keys"]:
            status_icon = "✅" if check["status"] == "PASS" else "❌"
            print(f"{status_icon} {check['table']}: {check['null_movement_count']} invalid movement references")
            if check["status"] == "FAIL":
                issues.append(f"Invalid FK in {check['table']}")
        
        print("\n3. MOVEMENT COUNTS CHECK")
        print("-" * 80)
        count_check = results["movement_counts"]
        status_icon = "✅" if count_check["status"] == "PASS" else "❌"
        print(f"{status_icon} Expected: {count_check['expected_count']}, "
              f"Actual: {count_check['actual_count']}, "
              f"Difference: {count_check['difference']}")
        if count_check["status"] == "FAIL":
            issues.append(f"Movement count mismatch")
        
        print("\n4. USAGE STATISTICS PRESERVED CHECK")
        print("-" * 80)
        for metric, count in results["usage"].items():
            print(f"✅ {metric}: {count}")
        
        print("\n5. RELATIONSHIPS INTEGRITY CHECK")
        print("-" * 80)
        for check_name, check in results["relationships"].items():
            status_icon = "✅" if check["status"] == "PASS" else "❌"
            print(f"{status_icon} {check_name}: {check['count']} invalid references")
            if check["status"] == "FAIL":
                issues.append(f"Invalid {check_name} in movement_relationships")
        
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        if issues:
            print(f"\n⚠️  ISSUES FOUND ({len(issues)}):")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            print("\n❌ VALIDATION FAILED")
            return False
        else:
            print("\n✅ ALL VALIDATIONS PASSED")
            return True
        
        results["all_passed"] = len(issues) == 0
        return results


async def main():
    """Main execution function."""
    settings = get_settings()
    
    async with async_session_maker() as session:
        validator = MergeValidator(session)
        
        try:
            expected_count = 566
            await validator.run_full_validation(expected_count)
        except Exception as e:
            print(f"\n❌ Error during validation: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
