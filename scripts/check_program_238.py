import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine
from sqlalchemy import text

async def check_program_238():
    async with engine.begin() as conn:
        # Get all sessions for Program 238
        result = await conn.execute(
            text("""
                SELECT 
                    s.id,
                    s.date,
                    s.session_type,
                    s.total_stimulus,
                    s.total_fatigue,
                    s.estimated_duration_minutes,
                    s.coach_notes,
                    COUNT(se.id) as exercise_count
                FROM sessions s
                JOIN microcycles m ON s.microcycle_id = m.id
                LEFT JOIN session_exercises se ON s.id = se.session_id
                WHERE m.program_id = 238
                GROUP BY s.id, s.date, s.session_type, s.total_stimulus, s.total_fatigue, s.estimated_duration_minutes, s.coach_notes
                ORDER BY s.date
            """)
        )
        
        sessions = result.fetchall()
        print(f'\n=== Program 238 Sessions ({len(sessions)} total) ===\n')
        
        for session in sessions:
            session_id, date, session_type, total_stimulus, total_fatigue, est_duration, coach_notes, exercise_count = session
            
            # Check for optimization warnings in coach_notes
            has_warning = coach_notes and 'optimization' in coach_notes.lower()
            warning_msg = coach_notes[:100] if coach_notes else ''
            
            # Determine if content is "light"
            is_light = (total_stimulus is not None and total_stimulus < 50) or (total_fatigue is not None and total_fatigue < 3)
            
            print(f'Session ID: {session_id}')
            print(f'  Date: {date}')
            print(f'  Type: {session_type}')
            print(f'  Exercises: {exercise_count}')
            print(f'  Stimulus: {total_stimulus}')
            print(f'  Fatigue: {total_fatigue}')
            print(f'  Est Duration: {est_duration}')
            print(f'  Optimization Warning: {"YES" if has_warning else "NO"}')
            if warning_msg:
                print(f'  Warning: {warning_msg}')
            print(f'  Light Content: {"YES" if is_light else "NO"}')
            print()

asyncio.run(check_program_238())
