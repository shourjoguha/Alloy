import asyncio
from sqlalchemy import text
from app.db.database import async_session_maker

async def check_session_notes():
    async with async_session_maker() as db:
        # Get all sessions in Microcycle 1447 (the one we're investigating)
        result = await db.execute(
            text('''
                SELECT s.id, s.day_number, s.session_type, s.coach_notes,
                       COUNT(se.id) as exercise_count,
                       s.estimated_duration_minutes
                FROM sessions s
                LEFT JOIN session_exercises se ON s.id = se.session_id
                WHERE s.id IN (15163, 15164, 15165, 15166, 15167, 15168, 15169, 15170, 15171, 15172, 15173, 15174, 15175, 15176)
                GROUP BY s.id
                ORDER BY s.day_number
            ''')
        )
        sessions = result.fetchall()

        print(f'Sessions in Microcycle 1447 (Program 215):')
        print('=' * 150)

        for session in sessions:
            session_id = session[0]
            day = session[1]
            session_type = session[2]
            notes = session[3]
            exercise_count = session[4]
            duration = session[5]

            notes_display = notes[:100] if notes else 'None'
            print(f'Session {session_id} (Day {day:2d}): {session_type:15s} | Exercises: {exercise_count:2d} | Duration: {duration:3d}min | Notes: {notes_display}')

        print()
        print('Sessions with 0 exercises:')
        empty_sessions = [s for s in sessions if s[4] == 0]
        for session in empty_sessions:
            print(f'  - Session {session[0]} (Day {session[1]}): {session[2]} - Notes: {session[3]}')

        print()
        print('Sessions with 10 min duration:')
        ten_min_sessions = [s for s in sessions if s[5] == 10]
        for session in ten_min_sessions:
            print(f'  - Session {session[0]} (Day {session[1]}): {session[2]} - Notes: {session[3]}')

asyncio.run(check_session_notes())
