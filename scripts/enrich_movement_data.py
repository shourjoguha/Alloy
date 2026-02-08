"""
Script to enrich movement data with fitness function metrics (fatigue, stimulus, injury risk).
Uses logic-based heuristics to populate values based on movement characteristics.
"""
import asyncio
import csv
from sqlalchemy import select
from app.db.database import async_session_maker
from app.models import Movement, CNSLoad, SkillLevel

def calculate_metrics(m: Movement):
    """
    Calculate fitness metrics based on movement attributes.
    
    Heuristics:
    - Fatigue: Driven by CNS Load + Compound/Isolation
    - Stimulus: Driven by Compound/Isolation + Pattern
    - Injury Risk: Driven by Skill Level + Complexity
    - Recovery: Driven by CNS Load
    """
    
    # 1. Base Fatigue Factor (0.0 - 1.0)
    # CNS Load is the primary driver
    cns_map = {
        CNSLoad.VERY_HIGH: 0.9,
        CNSLoad.HIGH: 0.7,
        CNSLoad.MODERATE: 0.5,
        CNSLoad.LOW: 0.3,
        CNSLoad.VERY_LOW: 0.1
    }
    fatigue = cns_map.get(CNSLoad(m.cns_load), 0.5)
    
    # Adjust for Compound vs Isolation
    if m.compound:
        fatigue += 0.1
    else:
        fatigue -= 0.1
        
    # Clamp
    fatigue = max(0.1, min(1.0, fatigue))
    
    # 2. Stimulus Factor (0.0 - 1.0)
    # Compound movements generally provide higher systemic stimulus
    if m.compound:
        stimulus = 0.8
        if m.cns_load in [CNSLoad.VERY_HIGH.value, CNSLoad.HIGH.value]:
            stimulus = 0.95
    else:
        stimulus = 0.5
        if m.cns_load == CNSLoad.MODERATE.value:
            stimulus = 0.6
            
    # Adjust for complexity (complex lifts often have better stimulus if done right, but we keep it safe)
    if m.is_complex_lift:
        stimulus += 0.05
        
    stimulus = max(0.1, min(1.0, stimulus))
    
    # 3. Injury Risk Factor (0.0 - 1.0)
    # Driven by Skill Level and Complexity
    skill_map = {
        SkillLevel.ELITE: 0.9,      # High risk if you fail
        SkillLevel.EXPERT: 0.8,
        SkillLevel.ADVANCED: 0.6,
        SkillLevel.INTERMEDIATE: 0.4,
        SkillLevel.BEGINNER: 0.2
    }
    risk = skill_map.get(SkillLevel(m.skill_level), 0.3)
    
    if m.is_complex_lift:
        risk += 0.2
    if m.is_unilateral:
        risk += 0.1  # Stability challenge
        
    risk = max(0.1, min(1.0, risk))
    
    # 4. Minimum Recovery Hours (Integer)
    # Driven by Fatigue
    if fatigue >= 0.8:
        recovery = 72
    elif fatigue >= 0.6:
        recovery = 48
    elif fatigue >= 0.4:
        recovery = 24
    else:
        recovery = 12
        
    return fatigue, stimulus, risk, recovery

async def enrich_movements():
    async with async_session_maker() as db:
        print("Fetching movements...")
        result = await db.execute(select(Movement))
        movements = result.scalars().all()
        
        print(f"Found {len(movements)} movements. Calculating metrics...")
        
        updates = []
        for m in movements:
            f, s, i, r = calculate_metrics(m)
            
            m.fatigue_factor = f
            m.stimulus_factor = s
            m.injury_risk_factor = i
            m.min_recovery_hours = r
            
            updates.append({
                "name": m.name,
                "pattern": m.pattern,
                "fatigue": f,
                "stimulus": s,
                "risk": i,
                "recovery": r
            })
            
        await db.commit()
        print("Database updated.")
        
        # Export audit CSV
        csv_file = "movement_audit.csv"
        with open(csv_file, 'w', newline='') as csvfile:
            fieldnames = ['name', 'pattern', 'fatigue', 'stimulus', 'risk', 'recovery']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for row in updates:
                writer.writerow(row)
                
        print(f"Audit log written to {csv_file}")

if __name__ == "__main__":
    asyncio.run(enrich_movements())