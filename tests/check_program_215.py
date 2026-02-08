import asyncio
from sqlalchemy import text
from app.db.database import async_session_maker

async def check_program_215():
    async with async_session_maker() as db:
        # Get Program 215 info
        result = await db.execute(
            text('''
                SELECT id, name, goal_1, goal_weight_1, goal_2, goal_weight_2, goal_3, goal_weight_3,
                       max_session_duration, days_per_week, split_template
                FROM programs WHERE id = 215
            ''')
        )
        program = result.fetchone()

        if not program:
            print('Program 215 not found')
            return

        print(f'Program {program[0]}: {program[1]}')
        print(f'Goals: {program[2]}={program[3]}, {program[4]}={program[5]}, {program[6]}={program[7]}')
        print(f'Duration: {program[8]} min, Days/week: {program[9]}')
        print(f'Split: {program[10]}')
        print()

        # Get active microcycle
        result = await db.execute(
            text('SELECT id FROM microcycles WHERE program_id = 215 AND status = :status'),
            {'status': 'ACTIVE'}
        )
        microcycle = result.fetchone()

        if not microcycle:
            print('No active microcycle found')
            return

        print(f'Active Microcycle {microcycle[0]}')
        print()

        # Get all sessions with exercise counts
        result = await db.execute(
            text('''
                SELECT s.id, s.day_number, s.session_type, s.estimated_duration_minutes, s.coach_notes,
                       COUNT(se.id) as exercise_count
                FROM sessions s
                LEFT JOIN session_exercises se ON s.id = se.session_id
                WHERE s.microcycle_id = :microcycle_id
                GROUP BY s.id
                ORDER BY s.day_number
            '''),
            {'microcycle_id': microcycle[0]}
        )
        sessions = result.fetchall()

        print(f'Sessions in Microcycle {microcycle[0]}:')
        print('-' * 120)

        total_exercises = 0
        empty_sessions = 0
        ten_min_sessions = 0
        sessions_by_type = {}

        for session in sessions:
            exercise_count = session[5]
            total_exercises += exercise_count

            session_type = session[2]
            if session_type not in sessions_by_type:
                sessions_by_type[session_type] = []
            sessions_by_type[session_type].append({
                'id': session[0],
                'day': session[1],
                'exercises': exercise_count,
                'duration': session[3]
            })

            if exercise_count == 0:
                empty_sessions += 1
            elif session[3] == 10:
                ten_min_sessions += 1

            notes = session[4][:80] if session[4] else 'None'
            print(f'Session {session[0]} (Day {session[1]}): {session[2]:20s} | Exercises: {exercise_count:2d} | Duration: {session[3]:3d}min | Notes: {notes}')

        print()
        print(f'Total: {len(sessions)} sessions, {total_exercises} exercises')
        print(f'Empty sessions: {empty_sessions}, Default (10min) sessions: {ten_min_sessions}')
        print()
        print('Breakdown by session type:')
        for session_type, sessions_list in sessions_by_type.items():
            total_ex = sum(s['exercises'] for s in sessions_list)
            avg_dur = sum(s['duration'] for s in sessions_list) / len(sessions_list)
            print(f'  {session_type}: {len(sessions_list)} sessions, {total_ex} total exercises, avg duration: {avg_dur:.1f}min')

asyncio.run(check_program_215())
