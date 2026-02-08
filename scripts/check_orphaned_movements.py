"""
SQL queries to identify orphaned movement references.

This script provides SQL queries to find all tables that reference
non-existent movements in the movements table.

Usage:
    Run these queries directly in your database (PostgreSQL/SQLite)
    or use the Python functions below if connected to the database.
"""

# ============================================================================
# SQL QUERIES FOR DATABASE INSPECTION
# ============================================================================

SQL_QUERIES = {
    # -------------------------------------------------------------------------
    # 1. Check circuits_melted for orphaned movement references
    # -------------------------------------------------------------------------
    "circuits_melted_orphans": """
        SELECT
            cm.id as melted_id,
            cm.circuit_id,
            cm.movement_id,
            cm.movement_name,
            cm.exercise_sequence
        FROM circuits_melted cm
        LEFT JOIN movements m ON cm.movement_id = m.id
        WHERE cm.movement_id IS NOT NULL
          AND m.id IS NULL
        ORDER BY cm.circuit_id, cm.exercise_sequence;
    """,

    # -------------------------------------------------------------------------
    # 2. Count orphaned references in circuits_melted
    # -------------------------------------------------------------------------
    "circuits_melted_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM circuits_melted cm
        LEFT JOIN movements m ON cm.movement_id = m.id
        WHERE cm.movement_id IS NOT NULL
          AND m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 3. Check user_movement_rules for orphaned movement references
    # -------------------------------------------------------------------------
    "user_movement_rules_orphans": """
        SELECT
            umr.id as rule_id,
            umr.user_id,
            umr.movement_id,
            umr.rule_type,
            umr.created_at
        FROM user_movement_rules umr
        LEFT JOIN movements m ON umr.movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY umr.user_id, umr.movement_id;
    """,

    # -------------------------------------------------------------------------
    # 4. Count orphaned references in user_movement_rules
    # -------------------------------------------------------------------------
    "user_movement_rules_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM user_movement_rules umr
        LEFT JOIN movements m ON umr.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 5. Check session_exercises for orphaned movement references
    # -------------------------------------------------------------------------
    "session_exercises_orphans": """
        SELECT
            se.id as exercise_id,
            se.session_id,
            se.movement_id,
            se.exercise_role,
            se.order_in_session
        FROM session_exercises se
        LEFT JOIN movements m ON se.movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY se.session_id, se.order_in_session;
    """,

    # -------------------------------------------------------------------------
    # 6. Count orphaned references in session_exercises
    # -------------------------------------------------------------------------
    "session_exercises_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM session_exercises se
        LEFT JOIN movements m ON se.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 7. Check top_set_logs for orphaned movement references
    # -------------------------------------------------------------------------
    "top_set_logs_orphans": """
        SELECT
            tsl.id as log_id,
            tsl.workout_log_id,
            tsl.movement_id,
            tsl.weight,
            tsl.reps,
            tsl.created_at
        FROM top_set_logs tsl
        LEFT JOIN movements m ON tsl.movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY tsl.created_at DESC;
    """,

    # -------------------------------------------------------------------------
    # 8. Count orphaned references in top_set_logs
    # -------------------------------------------------------------------------
    "top_set_logs_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM top_set_logs tsl
        LEFT JOIN movements m ON tsl.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 9. Check favorites for orphaned movement references
    # -------------------------------------------------------------------------
    "favorites_orphans": """
        SELECT
            f.id as favorite_id,
            f.user_id,
            f.movement_id,
            f.program_id,
            f.created_at
        FROM favorites f
        LEFT JOIN movements m ON f.movement_id = m.id
        WHERE f.movement_id IS NOT NULL
          AND m.id IS NULL
        ORDER BY f.user_id, f.created_at;
    """,

    # -------------------------------------------------------------------------
    # 10. Count orphaned references in favorites
    # -------------------------------------------------------------------------
    "favorites_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM favorites f
        LEFT JOIN movements m ON f.movement_id = m.id
        WHERE f.movement_id IS NOT NULL
          AND m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 11. Check movement_disciplines for orphaned movement references
    # -------------------------------------------------------------------------
    "movement_disciplines_orphans": """
        SELECT
            md.movement_id,
            md.discipline
        FROM movement_disciplines md
        LEFT JOIN movements m ON md.movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY md.movement_id, md.discipline;
    """,

    # -------------------------------------------------------------------------
    # 12. Count orphaned references in movement_disciplines
    # -------------------------------------------------------------------------
    "movement_disciplines_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM movement_disciplines md
        LEFT JOIN movements m ON md.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 13. Check movement_equipment for orphaned movement references
    # -------------------------------------------------------------------------
    "movement_equipment_orphans": """
        SELECT
            me.movement_id,
            me.equipment_id,
            e.name as equipment_name
        FROM movement_equipment me
        LEFT JOIN movements m ON me.movement_id = m.id
        LEFT JOIN equipment e ON me.equipment_id = e.id
        WHERE m.id IS NULL
        ORDER BY me.movement_id, me.equipment_id;
    """,

    # -------------------------------------------------------------------------
    # 14. Count orphaned references in movement_equipment
    # -------------------------------------------------------------------------
    "movement_equipment_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM movement_equipment me
        LEFT JOIN movements m ON me.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 15. Check movement_tags for orphaned movement references
    # -------------------------------------------------------------------------
    "movement_tags_orphans": """
        SELECT
            mt.movement_id,
            mt.tag_id,
            t.name as tag_name
        FROM movement_tags mt
        LEFT JOIN movements m ON mt.movement_id = m.id
        LEFT JOIN tags t ON mt.tag_id = t.id
        WHERE m.id IS NULL
        ORDER BY mt.movement_id, mt.tag_id;
    """,

    # -------------------------------------------------------------------------
    # 16. Count orphaned references in movement_tags
    # -------------------------------------------------------------------------
    "movement_tags_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM movement_tags mt
        LEFT JOIN movements m ON mt.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 17. Check movement_coaching_cues for orphaned movement references
    # -------------------------------------------------------------------------
    "movement_coaching_cues_orphans": """
        SELECT
            mcc.id as cue_id,
            mcc.movement_id,
            mcc.cue_text,
            mcc.order
        FROM movement_coaching_cues mcc
        LEFT JOIN movements m ON mcc.movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY mcc.movement_id, mcc.order;
    """,

    # -------------------------------------------------------------------------
    # 18. Count orphaned references in movement_coaching_cues
    # -------------------------------------------------------------------------
    "movement_coaching_cues_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM movement_coaching_cues mcc
        LEFT JOIN movements m ON mcc.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 19. Check movement_muscle_map for orphaned movement references
    # -------------------------------------------------------------------------
    "movement_muscle_map_orphans": """
        SELECT
            mmm.id as map_id,
            mmm.movement_id,
            mmm.muscle_id,
            mmm.role,
            mmm.magnitude
        FROM movement_muscle_map mmm
        LEFT JOIN movements m ON mmm.movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY mmm.movement_id, mmm.muscle_id;
    """,

    # -------------------------------------------------------------------------
    # 20. Count orphaned references in movement_muscle_map
    # -------------------------------------------------------------------------
    "movement_muscle_map_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM movement_muscle_map mmm
        LEFT JOIN movements m ON mmm.movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 21. Check movement_relationships for orphaned source_movement_id
    # -------------------------------------------------------------------------
    "movement_relationships_source_orphans": """
        SELECT
            mr.id as relationship_id,
            mr.source_movement_id,
            mr.target_movement_id,
            mr.relationship_type
        FROM movement_relationships mr
        LEFT JOIN movements m ON mr.source_movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY mr.source_movement_id;
    """,

    # -------------------------------------------------------------------------
    # 22. Check movement_relationships for orphaned target_movement_id
    # -------------------------------------------------------------------------
    "movement_relationships_target_orphans": """
        SELECT
            mr.id as relationship_id,
            mr.source_movement_id,
            mr.target_movement_id,
            mr.relationship_type
        FROM movement_relationships mr
        LEFT JOIN movements m ON mr.target_movement_id = m.id
        WHERE m.id IS NULL
        ORDER BY mr.target_movement_id;
    """,

    # -------------------------------------------------------------------------
    # 23. Count orphaned references in movement_relationships (source)
    # -------------------------------------------------------------------------
    "movement_relationships_source_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM movement_relationships mr
        LEFT JOIN movements m ON mr.source_movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 24. Count orphaned references in movement_relationships (target)
    # -------------------------------------------------------------------------
    "movement_relationships_target_orphans_count": """
        SELECT COUNT(*) as orphaned_count
        FROM movement_relationships mr
        LEFT JOIN movements m ON mr.target_movement_id = m.id
        WHERE m.id IS NULL;
    """,

    # -------------------------------------------------------------------------
    # 25. Summary: Count all orphaned movement references across all tables
    # -------------------------------------------------------------------------
    "all_orphans_summary": """
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
    # 26. Get all unique orphaned movement IDs across all tables
    # -------------------------------------------------------------------------
    "unique_orphaned_movement_ids": """
        WITH orphaned_ids AS (
            SELECT movement_id FROM circuits_melted cm
            LEFT JOIN movements m ON cm.movement_id = m.id
            WHERE cm.movement_id IS NOT NULL AND m.id IS NULL
            UNION
            SELECT movement_id FROM user_movement_rules umr
            LEFT JOIN movements m ON umr.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT movement_id FROM session_exercises se
            LEFT JOIN movements m ON se.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT movement_id FROM top_set_logs tsl
            LEFT JOIN movements m ON tsl.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT movement_id FROM favorites f
            LEFT JOIN movements m ON f.movement_id = m.id
            WHERE f.movement_id IS NOT NULL AND m.id IS NULL
            UNION
            SELECT movement_id FROM movement_disciplines md
            LEFT JOIN movements m ON md.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT movement_id FROM movement_equipment me
            LEFT JOIN movements m ON me.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT movement_id FROM movement_tags mt
            LEFT JOIN movements m ON mt.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT movement_id FROM movement_coaching_cues mcc
            LEFT JOIN movements m ON mcc.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT movement_id FROM movement_muscle_map mmm
            LEFT JOIN movements m ON mmm.movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT source_movement_id FROM movement_relationships mr
            LEFT JOIN movements m ON mr.source_movement_id = m.id
            WHERE m.id IS NULL
            UNION
            SELECT target_movement_id FROM movement_relationships mr
            LEFT JOIN movements m ON mr.target_movement_id = m.id
            WHERE m.id IS NULL
        )
        SELECT DISTINCT movement_id
        FROM orphaned_ids
        ORDER BY movement_id;
    """,

    # -------------------------------------------------------------------------
    # 27. Get detailed orphan count per movement ID
    # -------------------------------------------------------------------------
    "orphaned_movement_details": """
        WITH orphaned_in_circuits AS (
            SELECT cm.movement_id, 'circuits_melted' as table_name, COUNT(*) as count
            FROM circuits_melted cm
            LEFT JOIN movements m ON cm.movement_id = m.id
            WHERE cm.movement_id IS NOT NULL AND m.id IS NULL
            GROUP BY cm.movement_id
        ),
        orphaned_in_rules AS (
            SELECT umr.movement_id, 'user_movement_rules' as table_name, COUNT(*) as count
            FROM user_movement_rules umr
            LEFT JOIN movements m ON umr.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY umr.movement_id
        ),
        orphaned_in_sessions AS (
            SELECT se.movement_id, 'session_exercises' as table_name, COUNT(*) as count
            FROM session_exercises se
            LEFT JOIN movements m ON se.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY se.movement_id
        ),
        orphaned_in_top_sets AS (
            SELECT tsl.movement_id, 'top_set_logs' as table_name, COUNT(*) as count
            FROM top_set_logs tsl
            LEFT JOIN movements m ON tsl.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY tsl.movement_id
        ),
        orphaned_in_favorites AS (
            SELECT f.movement_id, 'favorites' as table_name, COUNT(*) as count
            FROM favorites f
            LEFT JOIN movements m ON f.movement_id = m.id
            WHERE f.movement_id IS NOT NULL AND m.id IS NULL
            GROUP BY f.movement_id
        ),
        orphaned_in_disciplines AS (
            SELECT md.movement_id, 'movement_disciplines' as table_name, COUNT(*) as count
            FROM movement_disciplines md
            LEFT JOIN movements m ON md.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY md.movement_id
        ),
        orphaned_in_equipment AS (
            SELECT me.movement_id, 'movement_equipment' as table_name, COUNT(*) as count
            FROM movement_equipment me
            LEFT JOIN movements m ON me.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY me.movement_id
        ),
        orphaned_in_tags AS (
            SELECT mt.movement_id, 'movement_tags' as table_name, COUNT(*) as count
            FROM movement_tags mt
            LEFT JOIN movements m ON mt.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY mt.movement_id
        ),
        orphaned_in_cues AS (
            SELECT mcc.movement_id, 'movement_coaching_cues' as table_name, COUNT(*) as count
            FROM movement_coaching_cues mcc
            LEFT JOIN movements m ON mcc.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY mcc.movement_id
        ),
        orphaned_in_muscle_map AS (
            SELECT mmm.movement_id, 'movement_muscle_map' as table_name, COUNT(*) as count
            FROM movement_muscle_map mmm
            LEFT JOIN movements m ON mmm.movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY mmm.movement_id
        ),
        orphaned_in_relationships_source AS (
            SELECT mr.source_movement_id as movement_id, 'movement_relationships (source)' as table_name, COUNT(*) as count
            FROM movement_relationships mr
            LEFT JOIN movements m ON mr.source_movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY mr.source_movement_id
        ),
        orphaned_in_relationships_target AS (
            SELECT mr.target_movement_id as movement_id, 'movement_relationships (target)' as table_name, COUNT(*) as count
            FROM movement_relationships mr
            LEFT JOIN movements m ON mr.target_movement_id = m.id
            WHERE m.id IS NULL
            GROUP BY mr.target_movement_id
        )
        SELECT * FROM orphaned_in_circuits
        UNION ALL
        SELECT * FROM orphaned_in_rules
        UNION ALL
        SELECT * FROM orphaned_in_sessions
        UNION ALL
        SELECT * FROM orphaned_in_top_sets
        UNION ALL
        SELECT * FROM orphaned_in_favorites
        UNION ALL
        SELECT * FROM orphaned_in_disciplines
        UNION ALL
        SELECT * FROM orphaned_in_equipment
        UNION ALL
        SELECT * FROM orphaned_in_tags
        UNION ALL
        SELECT * FROM orphaned_in_cues
        UNION ALL
        SELECT * FROM orphaned_in_muscle_map
        UNION ALL
        SELECT * FROM orphaned_in_relationships_source
        UNION ALL
        SELECT * FROM orphaned_in_relationships_target
        ORDER BY movement_id, table_name;
    """,

    # -------------------------------------------------------------------------
    # 28. Check total movements in database
    # -------------------------------------------------------------------------
    "total_movements": """
        SELECT COUNT(*) as total_movements FROM movements;
    """,

    # -------------------------------------------------------------------------
    # 29. Get basic movement stats
    # -------------------------------------------------------------------------
    "movement_stats": """
        SELECT
            COUNT(*) as total_movements,
            COUNT(CASE WHEN user_id IS NULL THEN 1 END) as system_movements,
            COUNT(CASE WHEN user_id IS NOT NULL THEN 1 END) as user_movements,
            COUNT(DISTINCT pattern) as unique_patterns,
            COUNT(DISTINCT primary_region) as unique_regions
        FROM movements;
    """,
}


# ============================================================================
# PYTHON FUNCTIONS FOR DATABASE INSPECTION
# ============================================================================

async def check_orphaned_movements(db_session):
    """
    Run all orphaned movement checks and return a comprehensive report.

    Args:
        db_session: SQLAlchemy async session

    Returns:
        dict: Summary of orphaned references across all tables
    """
    from sqlalchemy import text

    results = {}

    # Run the summary query first
    summary_query = text(SQL_QUERIES["all_orphans_summary"])
    result = await db_session.execute(summary_query)
    summary_rows = result.fetchall()

    results["summary"] = [
        {"table_name": row[0], "orphaned_count": row[1]}
        for row in summary_rows
    ]

    # Get unique orphaned movement IDs
    unique_ids_query = text(SQL_QUERIES["unique_orphaned_movement_ids"])
    result = await db_session.execute(unique_ids_query)
    unique_ids = [row[0] for row in result.fetchall()]
    results["unique_orphaned_movement_ids"] = unique_ids
    results["total_unique_orphaned_movements"] = len(unique_ids)

    # Get detailed orphaned movement details
    details_query = text(SQL_QUERIES["orphaned_movement_details"])
    result = await db_session.execute(details_query)
    details_rows = result.fetchall()

    results["orphaned_movement_details"] = [
        {"movement_id": row[0], "table_name": row[1], "count": row[2]}
        for row in details_rows
    ]

    # Get movement stats
    stats_query = text(SQL_QUERIES["movement_stats"])
    result = await db_session.execute(stats_query)
    stats_row = result.fetchone()

    results["movement_stats"] = {
        "total_movements": stats_row[0],
        "system_movements": stats_row[1],
        "user_movements": stats_row[2],
        "unique_patterns": stats_row[3],
        "unique_regions": stats_row[4],
    }

    return results


async def get_table_specific_orphans(db_session, table_name):
    """
    Get orphaned movement references for a specific table.

    Args:
        db_session: SQLAlchemy async session
        table_name: Name of the table to check

    Returns:
        list: Orphaned records for the specified table
    """
    from sqlalchemy import text

    query_key = f"{table_name}_orphans"
    if query_key not in SQL_QUERIES:
        raise ValueError(f"No query defined for table: {table_name}")

    query = text(SQL_QUERIES[query_key])
    result = await db_session.execute(query)
    rows = result.fetchall()

    # Get column names from the query
    columns = result.keys()

    return [
        {col: row[i] for i, col in enumerate(columns)}
        for row in rows
    ]


def print_orphan_report(results):
    """
    Print a formatted report of orphaned movement references.

    Args:
        results: Dictionary returned by check_orphaned_movements()
    """
    print("=" * 80)
    print("ORPHANED MOVEMENT REFERENCES REPORT")
    print("=" * 80)

    print("\n1. MOVEMENT STATISTICS")
    print("-" * 80)
    stats = results["movement_stats"]
    print(f"Total movements in database: {stats['total_movements']}")
    print(f"  - System movements: {stats['system_movements']}")
    print(f"  - User movements: {stats['user_movements']}")
    print(f"  - Unique patterns: {stats['unique_patterns']}")
    print(f"  - Unique regions: {stats['unique_regions']}")

    print("\n2. SUMMARY OF ORPHANED REFERENCES BY TABLE")
    print("-" * 80)
    total_orphans = 0
    for item in results["summary"]:
        count = item["orphaned_count"]
        table = item["table_name"]
        total_orphans += count
        if count > 0:
            print(f"  {table}: {count} orphaned reference(s)")
        else:
            print(f"  {table}: No orphans ✓")

    print(f"\n  TOTAL ORPHANED REFERENCES: {total_orphans}")
    print(f"  UNIQUE ORPHANED MOVEMENT IDs: {results['total_unique_orphaned_movements']}")

    if results["unique_orphaned_movement_ids"]:
        print("\n3. UNIQUE ORPHANED MOVEMENT IDs")
        print("-" * 80)
        print(f"  {', '.join(map(str, results['unique_orphaned_movement_ids']))}")

        print("\n4. DETAILED BREAKDOWN BY MOVEMENT ID")
        print("-" * 80)
        for item in results["orphaned_movement_details"]:
            movement_id = item["movement_id"]
            table_name = item["table_name"]
            count = item["count"]
            print(f"  Movement ID {movement_id}: {count} reference(s) in {table_name}")
    else:
        print("\n3. ORPHANED MOVEMENT DETAILS")
        print("-" * 80)
        print("  No orphaned movement references found. ✓")

    print("\n" + "=" * 80)
    print("RECOMMENDATION:")
    print("=" * 80)
    if total_orphans > 0:
        print("Orphaned movement references were found. Based on your requirement:")
        print("  'if a movement is missing, we should just take it as not present")
        print("   rather than causing an error'")
        print("")
        print("Options:")
        print("  1. Clean up orphaned references by deleting them")
        print("  2. Set movement_id to NULL where allowed (circuits_melted, favorites)")
        print("  3. Keep orphaned references but handle them gracefully in code")
        print("")
        print("Recommended approach:")
        print("  - Use LEFT JOINs in queries to handle missing movements")
        print("  - Add NULL checks in code that references movement relationships")
        print("  - Consider cleanup scripts to remove stale references")
    else:
        print("No orphaned movement references found. Database integrity is good. ✓")

    print("=" * 80 + "\n")


# ============================================================================
# MAIN ENTRY POINT FOR STANDALONE EXECUTION
# ============================================================================

if __name__ == "__main__":
    import asyncio
    import sys
    from pathlib import Path
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    async def main():
        from app.config.settings import get_settings
        settings = get_settings()

        # Create engine
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
        )

        # Create session maker
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        print("Connecting to database...")
        async with async_session_maker() as session:
            print("Running orphaned movement checks...\n")
            results = await check_orphaned_movements(session)
            print_orphan_report(results)

        await engine.dispose()

    # Run async main
    asyncio.run(main())
