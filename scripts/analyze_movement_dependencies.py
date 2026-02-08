"""
Movement Dependencies Analysis Script

This script analyzes all movement-related tables in the database to provide
comprehensive statistics on movement dependencies, usage, and relationships.

Usage:
    python scripts/analyze_movement_dependencies.py

Output:
    - Console output with detailed statistics
    - JSON file saved to scripts/movement_dependencies_analysis.json
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config.settings import get_settings
from app.db.database import async_session_maker, engine

# ============================================================================
# SQL QUERIES FOR MOVEMENT DEPENDENCY ANALYSIS
# ============================================================================

SQL_QUERIES: Dict[str, str] = {
    # -------------------------------------------------------------------------
    # 1. Main movements table statistics
    # -------------------------------------------------------------------------
    "movements_basic_stats": """
        SELECT
            COUNT(*) as total_movements,
            COUNT(CASE WHEN user_id IS NULL THEN 1 END) as system_movements,
            COUNT(CASE WHEN user_id IS NOT NULL THEN 1 END) as user_movements,
            COUNT(CASE WHEN is_complex_lift = TRUE THEN 1 END) as complex_lifts,
            COUNT(CASE WHEN is_unilateral = TRUE THEN 1 END) as unilateral_movements,
            COUNT(CASE WHEN compound = TRUE THEN 1 END) as compound_movements,
            AVG(fatigue_factor) as avg_fatigue_factor,
            AVG(stimulus_factor) as avg_stimulus_factor,
            AVG(injury_risk_factor) as avg_injury_risk_factor,
            AVG(min_recovery_hours) as avg_recovery_hours
        FROM movements;
    """,

    "movements_by_pattern": """
        SELECT
            pattern,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY pattern
        ORDER BY count DESC;
    """,

    "movements_by_primary_region": """
        SELECT
            primary_region,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY primary_region
        ORDER BY count DESC;
    """,

    "movements_by_primary_muscle": """
        SELECT
            primary_muscle,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY primary_muscle
        ORDER BY count DESC;
    """,

    "movements_by_tier": """
        SELECT
            tier,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY tier
        ORDER BY tier;
    """,

    "movements_by_cns_load": """
        SELECT
            cns_load,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY cns_load
        ORDER BY cns_load;
    """,

    "movements_by_skill_level": """
        SELECT
            skill_level,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY skill_level
        ORDER BY skill_level;
    """,

    "movements_by_metric_type": """
        SELECT
            metric_type,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY metric_type
        ORDER BY count DESC;
    """,

    "movements_by_spinal_compression": """
        SELECT
            spinal_compression,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        GROUP BY spinal_compression
        ORDER BY spinal_compression;
    """,

    "movements_with_embeddings": """
        SELECT
            COUNT(*) as movements_with_embeddings,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements
        WHERE embedding_vector IS NOT NULL;
    """,

    "movements_with_substitution_group": """
        SELECT
            COUNT(DISTINCT substitution_group) as unique_substitution_groups,
            COUNT(*) as movements_in_substitution_groups
        FROM movements
        WHERE substitution_group IS NOT NULL;
    """,

    # -------------------------------------------------------------------------
    # 2. Equipment table statistics
    # -------------------------------------------------------------------------
    "equipment_stats": """
        SELECT
            COUNT(*) as total_equipment,
            COUNT(DISTINCT name) as unique_equipment_names
        FROM equipment;
    """,

    "equipment_usage": """
        SELECT
            e.name as equipment_name,
            COUNT(DISTINCT me.movement_id) as movement_count,
            COUNT(me.movement_id) as total_associations
        FROM equipment e
        LEFT JOIN movement_equipment me ON e.id = me.equipment_id
        GROUP BY e.id, e.name
        ORDER BY movement_count DESC;
    """,

    "movements_without_equipment": """
        SELECT
            COUNT(*) as movements_without_equipment,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movements), 2) as percentage
        FROM movements m
        LEFT JOIN movement_equipment me ON m.id = me.movement_id
        WHERE me.movement_id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 3. Tags table statistics
    # -------------------------------------------------------------------------
    "tags_stats": """
        SELECT
            COUNT(*) as total_tags,
            COUNT(DISTINCT name) as unique_tag_names
        FROM tags;
    """,

    "tags_usage": """
        SELECT
            t.name as tag_name,
            COUNT(DISTINCT mt.movement_id) as movement_count,
            COUNT(mt.movement_id) as total_associations
        FROM tags t
        LEFT JOIN movement_tags mt ON t.id = mt.tag_id
        GROUP BY t.id, t.name
        ORDER BY movement_count DESC
        LIMIT 50;
    """,

    # -------------------------------------------------------------------------
    # 4. Muscles table statistics
    # -------------------------------------------------------------------------
    "muscles_stats": """
        SELECT
            COUNT(*) as total_muscles,
            COUNT(DISTINCT region) as unique_regions,
            AVG(stimulus_coefficient) as avg_stimulus_coefficient,
            AVG(fatigue_coefficient) as avg_fatigue_coefficient
        FROM muscles;
    """,

    "muscles_by_region": """
        SELECT
            region,
            COUNT(*) as count
        FROM muscles
        GROUP BY region
        ORDER BY region;
    """,

    # -------------------------------------------------------------------------
    # 5. Movement-Equipment junction statistics
    # -------------------------------------------------------------------------
    "movement_equipment_stats": """
        SELECT
            COUNT(*) as total_associations,
            COUNT(DISTINCT movement_id) as movements_with_equipment,
            COUNT(DISTINCT equipment_id) as equipment_used,
            AVG(equipment_count) as avg_equipment_per_movement
        FROM (
            SELECT
                movement_id,
                equipment_id,
                COUNT(*) OVER (PARTITION BY movement_id) as equipment_count
            FROM movement_equipment
        ) subquery;
    """,

    "movement_equipment_distribution": """
        SELECT
            equipment_count,
            COUNT(*) as movement_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(DISTINCT movement_id) FROM movement_equipment), 2) as percentage
        FROM (
            SELECT movement_id, COUNT(*) as equipment_count
            FROM movement_equipment
            GROUP BY movement_id
        ) subquery
        GROUP BY equipment_count
        ORDER BY equipment_count;
    """,

    # -------------------------------------------------------------------------
    # 6. Movement-Muscle-Map junction statistics
    # -------------------------------------------------------------------------
    "movement_muscle_map_stats": """
        SELECT
            COUNT(*) as total_associations,
            COUNT(DISTINCT movement_id) as movements_with_muscles,
            COUNT(DISTINCT muscle_id) as muscles_used,
            AVG(muscle_count) as avg_muscles_per_movement
        FROM (
            SELECT
                movement_id,
                muscle_id,
                COUNT(*) OVER (PARTITION BY movement_id) as muscle_count
            FROM movement_muscle_map
        ) subquery;
    """,

    "muscle_role_distribution": """
        SELECT
            role,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movement_muscle_map), 2) as percentage
        FROM movement_muscle_map
        GROUP BY role
        ORDER BY count DESC;
    """,

    "movement_muscle_distribution": """
        SELECT
            muscle_count,
            COUNT(*) as movement_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(DISTINCT movement_id) FROM movement_muscle_map), 2) as percentage
        FROM (
            SELECT movement_id, COUNT(*) as muscle_count
            FROM movement_muscle_map
            GROUP BY movement_id
        ) subquery
        GROUP BY muscle_count
        ORDER BY muscle_count;
    """,

    # -------------------------------------------------------------------------
    # 7. Movement-Disciplines junction statistics
    # -------------------------------------------------------------------------
    "movement_disciplines_stats": """
        SELECT
            COUNT(*) as total_associations,
            COUNT(DISTINCT movement_id) as movements_with_disciplines,
            COUNT(DISTINCT discipline) as unique_disciplines,
            AVG(discipline_count) as avg_disciplines_per_movement
        FROM (
            SELECT
                movement_id,
                discipline,
                COUNT(*) OVER (PARTITION BY movement_id) as discipline_count
            FROM movement_disciplines
        ) subquery;
    """,

    "discipline_distribution": """
        SELECT
            discipline,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movement_disciplines), 2) as percentage
        FROM movement_disciplines
        GROUP BY discipline
        ORDER BY count DESC;
    """,

    # -------------------------------------------------------------------------
    # 8. Movement-Tags junction statistics
    # -------------------------------------------------------------------------
    "movement_tags_stats": """
        SELECT
            COUNT(*) as total_associations,
            COUNT(DISTINCT movement_id) as movements_with_tags,
            COUNT(DISTINCT tag_id) as tags_used,
            AVG(tag_count) as avg_tags_per_movement
        FROM (
            SELECT
                movement_id,
                tag_id,
                COUNT(*) OVER (PARTITION BY movement_id) as tag_count
            FROM movement_tags
        ) subquery;
    """,

    # -------------------------------------------------------------------------
    # 9. Movement-Coaching-Cues statistics
    # -------------------------------------------------------------------------
    "movement_coaching_cues_stats": """
        SELECT
            COUNT(*) as total_cues,
            COUNT(DISTINCT movement_id) as movements_with_cues,
            AVG(cue_count) as avg_cues_per_movement
        FROM (
            SELECT
                movement_id,
                COUNT(*) OVER (PARTITION BY movement_id) as cue_count
            FROM movement_coaching_cues
        ) subquery;
    """,

    # -------------------------------------------------------------------------
    # 10. Movement-Relationships statistics
    # -------------------------------------------------------------------------
    "movement_relationships_stats": """
        SELECT
            COUNT(*) as total_relationships,
            COUNT(DISTINCT source_movement_id) as movements_with_outgoing,
            COUNT(DISTINCT target_movement_id) as movements_with_incoming,
            COUNT(DISTINCT source_movement_id || '-' || target_movement_id) as unique_pairs
        FROM movement_relationships;
    """,

    "relationship_type_distribution": """
        SELECT
            relationship_type,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM movement_relationships), 2) as percentage
        FROM movement_relationships
        GROUP BY relationship_type
        ORDER BY count DESC;
    """,

    # -------------------------------------------------------------------------
    # 11. Session-Exercises usage statistics
    # -------------------------------------------------------------------------
    "session_exercises_stats": """
        SELECT
            COUNT(*) as total_exercises,
            COUNT(DISTINCT session_id) as unique_sessions,
            COUNT(DISTINCT movement_id) as unique_movements_used,
            COUNT(DISTINCT movement_id) * 100.0 / (SELECT COUNT(*) FROM movements) as movement_coverage_percentage
        FROM session_exercises;
    """,

    "session_exercise_role_distribution": """
        SELECT
            exercise_role,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM session_exercises), 2) as percentage
        FROM session_exercises
        GROUP BY exercise_role
        ORDER BY count DESC;
    """,

    "movement_usage_in_sessions": """
        SELECT
            COUNT(*) as movement_count,
            COUNT(DISTINCT se.movement_id) as unique_movements,
            AVG(exercise_count) as avg_sessions_per_movement
        FROM (
            SELECT movement_id, COUNT(*) as exercise_count
            FROM session_exercises
            GROUP BY movement_id
        ) se;
    """,

    # -------------------------------------------------------------------------
    # 12. Circuits-Melted usage statistics
    # -------------------------------------------------------------------------
    "circuits_melted_stats": """
        SELECT
            COUNT(*) as total_circuit_movements,
            COUNT(DISTINCT circuit_id) as unique_circuits,
            COUNT(DISTINCT movement_id) as unique_movements_used,
            COUNT(CASE WHEN movement_id IS NOT NULL THEN 1 END) as with_movement_id,
            COUNT(CASE WHEN movement_id IS NULL THEN 1 END) as without_movement_id
        FROM circuits_melted;
    """,

    "circuits_melted_orphaned_movements": """
        SELECT
            COUNT(*) as orphaned_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM circuits_melted), 2) as percentage
        FROM circuits_melted cm
        LEFT JOIN movements m ON cm.movement_id = m.id
        WHERE cm.movement_id IS NOT NULL AND m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 13. User-Movement-Rules statistics
    # -------------------------------------------------------------------------
    "user_movement_rules_stats": """
        SELECT
            COUNT(*) as total_rules,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT movement_id) as unique_movements_with_rules
        FROM user_movement_rules;
    """,

    "user_movement_rules_orphaned_movements": """
        SELECT
            COUNT(*) as orphaned_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM user_movement_rules), 2) as percentage
        FROM user_movement_rules umr
        LEFT JOIN movements m ON umr.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    "user_movement_rules_by_type": """
        SELECT
            rule_type,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM user_movement_rules), 2) as percentage
        FROM user_movement_rules
        GROUP BY rule_type
        ORDER BY count DESC;
    """,

    # -------------------------------------------------------------------------
    # 14. Favorites statistics
    # -------------------------------------------------------------------------
    "favorites_stats": """
        SELECT
            COUNT(*) as total_favorites,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT movement_id) as unique_movements_favorited,
            COUNT(CASE WHEN movement_id IS NOT NULL THEN 1 END) as movement_favorites,
            COUNT(CASE WHEN program_id IS NOT NULL THEN 1 END) as program_favorites
        FROM favorites;
    """,

    "favorites_orphaned_movements": """
        SELECT
            COUNT(*) as orphaned_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM favorites), 2) as percentage
        FROM favorites f
        LEFT JOIN movements m ON f.movement_id = m.id
        WHERE f.movement_id IS NOT NULL AND m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 15. Top-Set-Logs statistics
    # -------------------------------------------------------------------------
    "top_set_logs_stats": """
        SELECT
            COUNT(*) as total_logs,
            COUNT(DISTINCT workout_log_id) as unique_workout_logs,
            COUNT(DISTINCT movement_id) as unique_movements_logged,
            AVG(weight) as avg_weight,
            AVG(reps) as avg_reps,
            MAX(weight) as max_weight,
            MAX(reps) as max_reps
        FROM top_set_logs;
    """,

    "top_set_logs_orphaned_movements": """
        SELECT
            COUNT(*) as orphaned_count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM top_set_logs), 2) as percentage
        FROM top_set_logs tsl
        LEFT JOIN movements m ON tsl.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 16. Orphaned references summary
    # -------------------------------------------------------------------------
    "all_orphaned_summary": """
        WITH circuits_melted_orphans AS (
            SELECT COUNT(*) as count FROM circuits_melted cm
            LEFT JOIN movements m ON cm.movement_id = m.id
            WHERE cm.movement_id IS NOT NULL AND m.id IS NULL
        ),
        user_movement_rules_orphans AS (
            SELECT COUNT(*) as count FROM user_movement_rules umr
            LEFT JOIN movements m ON umr.movement_id = m.id
            WHERE m.id IS NULL
        ),
        session_exercises_orphans AS (
            SELECT COUNT(*) as count FROM session_exercises se
            LEFT JOIN movements m ON se.movement_id = m.id
            WHERE m.id IS NULL
        ),
        top_set_logs_orphans AS (
            SELECT COUNT(*) as count FROM top_set_logs tsl
            LEFT JOIN movements m ON tsl.movement_id = m.id
            WHERE m.id IS NULL
        ),
        favorites_orphans AS (
            SELECT COUNT(*) as count FROM favorites f
            LEFT JOIN movements m ON f.movement_id = m.id
            WHERE f.movement_id IS NOT NULL AND m.id IS NULL
        ),
        movement_disciplines_orphans AS (
            SELECT COUNT(*) as count FROM movement_disciplines md
            LEFT JOIN movements m ON md.movement_id = m.id
            WHERE m.id IS NULL
        ),
        movement_equipment_orphans AS (
            SELECT COUNT(*) as count FROM movement_equipment me
            LEFT JOIN movements m ON me.movement_id = m.id
            WHERE m.id IS NULL
        ),
        movement_tags_orphans AS (
            SELECT COUNT(*) as count FROM movement_tags mt
            LEFT JOIN movements m ON mt.movement_id = m.id
            WHERE m.id IS NULL
        ),
        movement_coaching_cues_orphans AS (
            SELECT COUNT(*) as count FROM movement_coaching_cues mcc
            LEFT JOIN movements m ON mcc.movement_id = m.id
            WHERE m.id IS NULL
        ),
        movement_muscle_map_orphans AS (
            SELECT COUNT(*) as count FROM movement_muscle_map mmm
            LEFT JOIN movements m ON mmm.movement_id = m.id
            WHERE m.id IS NULL
        ),
        movement_relationships_source_orphans AS (
            SELECT COUNT(*) as count FROM movement_relationships mr
            LEFT JOIN movements m ON mr.source_movement_id = m.id
            WHERE m.id IS NULL
        ),
        movement_relationships_target_orphans AS (
            SELECT COUNT(*) as count FROM movement_relationships mr
            LEFT JOIN movements m ON mr.target_movement_id = m.id
            WHERE m.id IS NULL
        )
        SELECT
            'circuits_melted' as table_name,
            (SELECT count FROM circuits_melted_orphans) as orphaned_count
        UNION ALL
        SELECT 'user_movement_rules', (SELECT count FROM user_movement_rules_orphans)
        UNION ALL
        SELECT 'session_exercises', (SELECT count FROM session_exercises_orphans)
        UNION ALL
        SELECT 'top_set_logs', (SELECT count FROM top_set_logs_orphans)
        UNION ALL
        SELECT 'favorites', (SELECT count FROM favorites_orphans)
        UNION ALL
        SELECT 'movement_disciplines', (SELECT count FROM movement_disciplines_orphans)
        UNION ALL
        SELECT 'movement_equipment', (SELECT count FROM movement_equipment_orphans)
        UNION ALL
        SELECT 'movement_tags', (SELECT count FROM movement_tags_orphans)
        UNION ALL
        SELECT 'movement_coaching_cues', (SELECT count FROM movement_coaching_cues_orphans)
        UNION ALL
        SELECT 'movement_muscle_map', (SELECT count FROM movement_muscle_map_orphans)
        UNION ALL
        SELECT 'movement_relationships (source)', (SELECT count FROM movement_relationships_source_orphans)
        UNION ALL
        SELECT 'movement_relationships (target)', (SELECT count FROM movement_relationships_target_orphans)
        ORDER BY orphaned_count DESC;
    """,

    # -------------------------------------------------------------------------
    # 17. Movement name analysis
    # -------------------------------------------------------------------------
    "movement_name_length_stats": """
        SELECT
            AVG(LENGTH(name)) as avg_name_length,
            MIN(LENGTH(name)) as min_name_length,
            MAX(LENGTH(name)) as max_name_length,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY LENGTH(name)) as median_name_length
        FROM movements;
    """,

    "duplicate_movement_names": """
        SELECT
            LOWER(name) as name_lower,
            COUNT(*) as count,
            STRING_AGG(DISTINCT name, ', ') as variations
        FROM movements
        GROUP BY LOWER(name)
        HAVING COUNT(*) > 1
        ORDER BY count DESC;
    """,

    # -------------------------------------------------------------------------
    # 18. Movement completeness analysis
    # -------------------------------------------------------------------------
    "movement_completeness": """
        SELECT
            COUNT(*) as total_movements,
            COUNT(CASE WHEN description IS NOT NULL THEN 1 END) as with_description,
            COUNT(CASE WHEN biomechanics_profile IS NOT NULL THEN 1 END) as with_biomechanics,
            COUNT(CASE WHEN embedding_description IS NOT NULL THEN 1 END) as with_embedding_description,
            COUNT(CASE WHEN embedding_vector IS NOT NULL THEN 1 END) as with_embedding_vector
        FROM movements;
    """,
}


# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

async def execute_query(
    session: AsyncSession,
    query_name: str,
    query: str,
) -> List[Dict[str, Any]]:
    """
    Execute a SQL query and return results as a list of dictionaries.

    Args:
        session: SQLAlchemy async session
        query_name: Name of the query for logging
        query: SQL query to execute

    Returns:
        List of dictionaries representing query results

    Raises:
        Exception: If query execution fails
    """
    try:
        result = await session.execute(text(query))
        rows = result.fetchall()
        columns = result.keys()

        return [
            {col: row[i] for i, col in enumerate(columns)}
            for row in rows
        ]
    except Exception as e:
        print(f"  Error executing query '{query_name}': {e}")
        raise


async def analyze_movement_dependencies(
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    Analyze all movement-related tables and return comprehensive statistics.

    Args:
        session: SQLAlchemy async session

    Returns:
        Dictionary containing all analysis results organized by category

    Raises:
        Exception: If analysis fails
    """
    print("Starting movement dependency analysis...")
    print("-" * 80)

    results: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
        "analysis_summary": {},
        "movements": {},
        "equipment": {},
        "tags": {},
        "muscles": {},
        "junction_tables": {},
        "usage_tables": {},
        "orphaned_references": {},
        "name_analysis": {},
        "completeness": {},
    }

    # Execute all queries
    for query_name, query in SQL_QUERIES.items():
        print(f"Executing query: {query_name}")
        try:
            data = await execute_query(session, query_name, query)

            # Categorize results based on query name
            if query_name.startswith("movements"):
                if query_name == "movements_basic_stats":
                    results["movements"]["basic_stats"] = data[0] if data else {}
                elif query_name == "movements_with_embeddings":
                    results["movements"]["with_embeddings"] = data[0] if data else {}
                elif query_name == "movements_with_substitution_group":
                    results["movements"]["with_substitution_group"] = data[0] if data else {}
                else:
                    category = query_name.replace("movements_by_", "")
                    results["movements"][f"by_{category}"] = data

            elif query_name.startswith("equipment"):
                if query_name == "equipment_stats":
                    results["equipment"]["stats"] = data[0] if data else {}
                else:
                    results["equipment"][query_name] = data

            elif query_name.startswith("tags"):
                if query_name == "tags_stats":
                    results["tags"]["stats"] = data[0] if data else {}
                else:
                    results["tags"][query_name] = data

            elif query_name.startswith("muscles"):
                if query_name == "muscles_stats":
                    results["muscles"]["stats"] = data[0] if data else {}
                else:
                    results["muscles"][query_name] = data

            elif query_name.startswith("movement_equipment"):
                results["junction_tables"]["movement_equipment"] = results["junction_tables"].get("movement_equipment", {})
                results["junction_tables"]["movement_equipment"][query_name] = data

            elif query_name.startswith("movement_muscle"):
                results["junction_tables"]["movement_muscle_map"] = results["junction_tables"].get("movement_muscle_map", {})
                results["junction_tables"]["movement_muscle_map"][query_name] = data

            elif query_name.startswith("movement_disciplines"):
                results["junction_tables"]["movement_disciplines"] = results["junction_tables"].get("movement_disciplines", {})
                results["junction_tables"]["movement_disciplines"][query_name] = data

            elif query_name.startswith("movement_tags"):
                results["junction_tables"]["movement_tags"] = results["junction_tables"].get("movement_tags", {})
                results["junction_tables"]["movement_tags"][query_name] = data

            elif query_name.startswith("movement_coaching_cues"):
                results["junction_tables"]["movement_coaching_cues"] = results["junction_tables"].get("movement_coaching_cues", {})
                results["junction_tables"]["movement_coaching_cues"][query_name] = data

            elif query_name.startswith("movement_relationships"):
                results["junction_tables"]["movement_relationships"] = results["junction_tables"].get("movement_relationships", {})
                results["junction_tables"]["movement_relationships"][query_name] = data

            elif query_name.startswith("session_exercises"):
                results["usage_tables"]["session_exercises"] = results["usage_tables"].get("session_exercises", {})
                results["usage_tables"]["session_exercises"][query_name] = data

            elif query_name.startswith("circuits_melted"):
                results["usage_tables"]["circuits_melted"] = results["usage_tables"].get("circuits_melted", {})
                results["usage_tables"]["circuits_melted"][query_name] = data

            elif query_name.startswith("user_movement_rules"):
                results["usage_tables"]["user_movement_rules"] = results["usage_tables"].get("user_movement_rules", {})
                results["usage_tables"]["user_movement_rules"][query_name] = data

            elif query_name.startswith("favorites"):
                results["usage_tables"]["favorites"] = results["usage_tables"].get("favorites", {})
                results["usage_tables"]["favorites"][query_name] = data

            elif query_name.startswith("top_set_logs"):
                results["usage_tables"]["top_set_logs"] = results["usage_tables"].get("top_set_logs", {})
                results["usage_tables"]["top_set_logs"][query_name] = data

            elif query_name == "all_orphaned_summary":
                results["orphaned_references"]["summary"] = data

            elif query_name.startswith("movement_name"):
                results["name_analysis"][query_name] = data

            elif query_name.startswith("movement_completeness"):
                results["completeness"][query_name] = data

            print(f"  Completed: {len(data)} rows returned")

        except Exception as e:
            print(f"  Failed: {e}")
            results[f"{query_name}_error"] = str(e)

    print("-" * 80)
    print("Analysis complete.")

    return results


def print_analysis_report(results: Dict[str, Any]) -> None:
    """
    Print a formatted report of the movement dependency analysis.

    Args:
        results: Dictionary containing all analysis results
    """
    print("\n" + "=" * 80)
    print("MOVEMENT DEPENDENCY ANALYSIS REPORT")
    print("=" * 80)
    print(f"Analysis Timestamp: {results['timestamp']}")
    print("=" * 80)

    # 1. Movements Overview
    print("\n1. MOVEMENTS OVERVIEW")
    print("-" * 80)
    if "basic_stats" in results.get("movements", {}):
        stats = results["movements"]["basic_stats"]
        print(f"Total movements: {stats.get('total_movements', 0)}")
        print(f"  - System movements: {stats.get('system_movements', 0)}")
        print(f"  - User movements: {stats.get('user_movements', 0)}")
        print(f"  - Complex lifts: {stats.get('complex_lifts', 0)}")
        print(f"  - Unilateral movements: {stats.get('unilateral_movements', 0)}")
        print(f"  - Compound movements: {stats.get('compound_movements', 0)}")
        print(f"\nAverage metrics:")
        print(f"  - Fatigue factor: {stats.get('avg_fatigue_factor', 0):.2f}")
        print(f"  - Stimulus factor: {stats.get('avg_stimulus_factor', 0):.2f}")
        print(f"  - Injury risk factor: {stats.get('avg_injury_risk_factor', 0):.2f}")
        print(f"  - Recovery hours: {stats.get('avg_recovery_hours', 0):.1f}")

    # Movements by pattern
    if "by_pattern" in results.get("movements", {}):
        print(f"\nMovements by pattern:")
        for item in results["movements"]["by_pattern"][:5]:
            print(f"  - {item['pattern']}: {item['count']} ({item['percentage']}%)")

    # Movements by tier
    if "by_tier" in results.get("movements", {}):
        print(f"\nMovements by tier:")
        for item in results["movements"]["by_tier"]:
            print(f"  - {item['tier']}: {item['count']} ({item['percentage']}%)")

    # 2. Reference Tables
    print("\n2. REFERENCE TABLES")
    print("-" * 80)

    # Equipment
    if "stats" in results.get("equipment", {}):
        stats = results["equipment"]["stats"]
        print(f"Equipment: {stats.get('total_equipment', 0)} items")

    # Tags
    if "stats" in results.get("tags", {}):
        stats = results["tags"]["stats"]
        print(f"Tags: {stats.get('total_tags', 0)} items")

    # Muscles
    if "stats" in results.get("muscles", {}):
        stats = results["muscles"]["stats"]
        print(f"Muscles: {stats.get('total_muscles', 0)} items")

    # 3. Junction Tables
    print("\n3. JUNCTION TABLES")
    print("-" * 80)

    for table_name, table_data in results.get("junction_tables", {}).items():
        if "stats" in table_data:
            stats = table_data["stats"]
            print(f"\n{table_name}:")
            print(f"  - Total associations: {stats.get('total_associations', 0)}")
            print(f"  - Movements linked: {stats.get('movements_with_equipment', stats.get('movements_with_muscles', stats.get('movements_with_disciplines', stats.get('movements_with_tags', stats.get('movements_with_cues', 0)))))}")

    # 4. Usage Tables
    print("\n4. USAGE TABLES")
    print("-" * 80)

    for table_name, table_data in results.get("usage_tables", {}).items():
        if "stats" in table_data:
            stats = table_data["stats"]
            print(f"\n{table_name}:")
            if table_name == "session_exercises":
                print(f"  - Total exercises: {stats.get('total_exercises', 0)}")
                print(f"  - Unique sessions: {stats.get('unique_sessions', 0)}")
                print(f"  - Unique movements used: {stats.get('unique_movements_used', 0)}")
                print(f"  - Movement coverage: {stats.get('movement_coverage_percentage', 0):.1f}%")
            elif table_name == "circuits_melted":
                print(f"  - Total circuit movements: {stats.get('total_circuit_movements', 0)}")
                print(f"  - Unique circuits: {stats.get('unique_circuits', 0)}")
                print(f"  - Unique movements used: {stats.get('unique_movements_used', 0)}")
            elif table_name == "favorites":
                print(f"  - Total favorites: {stats.get('total_favorites', 0)}")
                print(f"  - Unique users: {stats.get('unique_users', 0)}")
                print(f"  - Unique movements favorited: {stats.get('unique_movements_favorited', 0)}")
            elif table_name == "top_set_logs":
                print(f"  - Total logs: {stats.get('total_logs', 0)}")
                print(f"  - Unique movements logged: {stats.get('unique_movements_logged', 0)}")

    # 5. Orphaned References
    print("\n5. ORPHANED REFERENCES")
    print("-" * 80)

    if "summary" in results.get("orphaned_references", {}):
        total_orphans = 0
        for item in results["orphaned_references"]["summary"]:
            count = item.get("orphaned_count", 0)
            total_orphans += count
            if count > 0:
                print(f"  {item['table_name']}: {count} orphaned reference(s)")

        if total_orphans == 0:
            print("  No orphaned references found. Database integrity is good.")

    # 6. Name Analysis
    print("\n6. NAME ANALYSIS")
    print("-" * 80)

    if "movement_name_length_stats" in results.get("name_analysis", {}):
        stats = results["name_analysis"]["movement_name_length_stats"][0]
        print(f"Movement name length:")
        print(f"  - Average: {stats.get('avg_name_length', 0):.1f} characters")
        print(f"  - Minimum: {stats.get('min_name_length', 0)} characters")
        print(f"  - Maximum: {stats.get('max_name_length', 0)} characters")
        print(f"  - Median: {stats.get('median_name_length', 0):.1f} characters")

    if "duplicate_movement_names" in results.get("name_analysis", {}):
        duplicates = results["name_analysis"]["duplicate_movement_names"]
        if duplicates:
            print(f"\nPotential duplicate names (case-insensitive): {len(duplicates)}")
            for item in duplicates[:5]:
                print(f"  - '{item['name_lower']}': {item['count']} variations ({item['variations']})")

    # 7. Completeness
    print("\n7. MOVEMENT COMPLETENESS")
    print("-" * 80)

    if "movement_completeness" in results.get("completeness", {}):
        stats = results["completeness"]["movement_completeness"][0]
        total = stats.get("total_movements", 0)
        print(f"Out of {total} movements:")
        print(f"  - With description: {stats.get('with_description', 0)} ({stats.get('with_description', 0) * 100 / total if total > 0 else 0:.1f}%)")
        print(f"  - With biomechanics profile: {stats.get('with_biomechanics', 0)} ({stats.get('with_biomechanics', 0) * 100 / total if total > 0 else 0:.1f}%)")
        print(f"  - With embedding description: {stats.get('with_embedding_description', 0)} ({stats.get('with_embedding_description', 0) * 100 / total if total > 0 else 0:.1f}%)")
        print(f"  - With embedding vector: {stats.get('with_embedding_vector', 0)} ({stats.get('with_embedding_vector', 0) * 100 / total if total > 0 else 0:.1f}%)")

    print("\n" + "=" * 80)
    print("Analysis complete. Full results saved to movement_dependencies_analysis.json")
    print("=" * 80 + "\n")


async def save_results_to_json(
    results: Dict[str, Any],
    output_path: str,
) -> None:
    """
    Save analysis results to a JSON file.

    Args:
        results: Dictionary containing all analysis results
        output_path: Path where JSON file will be saved

    Raises:
        IOError: If file writing fails
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to: {output_path}")
    except IOError as e:
        print(f"Error saving results to {output_path}: {e}")
        raise


async def main() -> None:
    """
    Main entry point for the movement dependencies analysis script.
    """
    print("=" * 80)
    print("MOVEMENT DEPENDENCY ANALYSIS SCRIPT")
    print("=" * 80)
    print()

    settings = get_settings()
    print(f"Database URL: {settings.database_url}")
    print()

    try:
        # Connect to database and run analysis
        async with async_session_maker() as session:
            results = await analyze_movement_dependencies(session)

        # Print formatted report
        print_analysis_report(results)

        # Save results to JSON
        output_path = Path(__file__).parent / "movement_dependencies_analysis.json"
        await save_results_to_json(results, str(output_path))

        print("\nScript completed successfully.")

    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Ensure engine is disposed
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
