"""Phase 3: Deep Enrichment - Map complex relationships (progressions, variations, regressions)."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import async_session_maker
from app.models.movement import Movement, MovementRelationship
from app.models.enums import RelationshipType
from sqlalchemy import select

async def get_movement_by_name(db: async_session_maker, name: str) -> Movement | None:
    """Get a movement by name."""
    result = await db.execute(
        select(Movement).where(Movement.name == name)
    )
    return result.scalar_one_or_none()

async def create_relationship(
    db: async_session_maker,
    source_name: str,
    target_name: str,
    relationship_type: RelationshipType,
    notes: str = None
) -> bool:
    """Create a relationship between two movements."""
    source = await get_movement_by_name(db, source_name)
    target = await get_movement_by_name(db, target_name)
    
    if not source or not target:
        print(f"  ⚠️  Missing movement: {source_name if not source else target_name}")
        return False
    
    rel_type_value = relationship_type.value
    
    from sqlalchemy import text
    
    existing = await db.execute(
        text("""
        SELECT id FROM movement_relationships
        WHERE source_movement_id = :source_id
          AND target_movement_id = :target_id
          AND relationship_type = :rel_type
        """),
        {"source_id": source.id, "target_id": target.id, "rel_type": rel_type_value}
    )
    if existing.scalar_one_or_none():
        print(f"  ℹ️  Relationship exists: {source_name} -> {target_name}")
        return False
    
    rel = MovementRelationship(
        source_movement_id=source.id,
        target_movement_id=target.id,
        relationship_type=rel_type_value,
        notes=notes
    )
    db.add(rel)
    print(f"  ✅ {rel_type_value}: {source_name} -> {target_name}")
    return True

async def map_progression_relationships():
    """Map calisthenics progression relationships."""
    
    progressions = [
        # Pull-up Progression
        ("Dead Hang", "Scapular Pull-Up", RelationshipType.PROGRESSION, "Foundational scapular strength"),
        ("Scapular Pull-Up", "Negative Pull-Up", RelationshipType.PROGRESSION, "Eccentric strength building"),
        ("Negative Pull-Up", "Assisted Pull-Up", RelationshipType.PROGRESSION, "Full ROM with assistance"),
        ("Assisted Pull-Up", "Pull-Up", RelationshipType.PROGRESSION, "Unassisted full pull-up"),
        ("Pull-Up", "Weighted Pull-Up", RelationshipType.PROGRESSION, "Progressive overload"),
        
        # Chin-up Progression
        ("Scapular Pull-Up", "Negative Chin-Up", RelationshipType.PROGRESSION, "Supinated grip variation"),
        ("Negative Chin-Up", "Chin-Up", RelationshipType.PROGRESSION, "Bicep-focused progression"),
        
        # Push-up Progression
        ("Plank", "Wall Push-Up", RelationshipType.PROGRESSION, "Foundational stability"),
        ("Wall Push-Up", "Incline Push-Up", RelationshipType.PROGRESSION, "Angle progression"),
        ("Incline Push-Up", "Knee Push-Up", RelationshipType.PROGRESSION, "Reduced lever length"),
        ("Knee Push-Up", "Push-Up", RelationshipType.PROGRESSION, "Full bodyweight push-up"),
        ("Push-Up", "Diamond Push-Up", RelationshipType.PROGRESSION, "Tricep emphasis"),
        ("Diamond Push-Up", "Handstand Push-Up", RelationshipType.PROGRESSION, "Vertical pushing"),
        
        # Squat Progression
        ("Bodyweight Squat", "Goblet Squat", RelationshipType.PROGRESSION, "Loaded squat pattern"),
        ("Goblet Squat", "Front Squat", RelationshipType.PROGRESSION, "Barbell front loaded"),
        
        # Pistol Squat Progression
        ("Bodyweight Squat", "Single-Leg Box Squat", RelationshipType.PROGRESSION, "Unilateral foundation"),
        ("Single-Leg Box Squat", "Pistol Squat to Box", RelationshipType.PROGRESSION, "Full pistol squat"),
        
        # L-Sit Progression
        ("Tuck Sit", "Tuck L-Sit", RelationshipType.PROGRESSION, "Compression hold"),
        ("Tuck L-Sit", "L-Sit", RelationshipType.PROGRESSION, "Full extension hold"),
        
        # Planche Progression
        ("Plank", "Frog Stand", RelationshipType.PROGRESSION, "Lean progression"),
        ("Frog Stand", "Tuck Planche", RelationshipType.PROGRESSION, "Static hold progression"),
        
        # Handstand Progression
        ("Pike Push-Up", "Handstand Push-Up", RelationshipType.PROGRESSION, "Vertical pressing"),
    ]
    
    return progressions

async def map_injury_regression_relationships():
    """Map injury regression relationships."""
    
    regressions = [
        # Lower Back Regressions
        ("Conventional Deadlift", "Trap Bar Deadlift", RelationshipType.REGRESSION, "Reduced lumbar shear stress"),
        ("Conventional Deadlift", "Rack Pull", RelationshipType.REGRESSION, "Reduced ROM for lumbar protection"),
        ("Back Squat", "Box Squat", RelationshipType.REGRESSION, "Reduced depth, controlled eccentric"),
        ("Back Squat", "Goblet Squat", RelationshipType.REGRESSION, "Forward-loaded, less spinal compression"),
        
        # Shoulder Regressions
        ("Overhead Press", "Landmine Press", RelationshipType.REGRESSION, "Neutral shoulder position"),
        ("Overhead Press", "Dumbbell Shoulder Press", RelationshipType.REGRESSION, "Unilateral, scapular mobility"),
        ("Bench Press", "Floor Press", RelationshipType.REGRESSION, "Reduced ROM, shoulder-friendly"),
        ("Dip", "Close-Grip Bench Press", RelationshipType.REGRESSION, "Reduced shoulder extension"),
        
        # Knee Regressions
        ("Back Squat", "Leg Press", RelationshipType.REGRESSION, "Reduced spinal loading"),
        ("Lunge", "Reverse Lunge", RelationshipType.REGRESSION, "Reduced knee shear forces"),
        ("Jump Squat", "Box Jump", RelationshipType.REGRESSION, "Controlled landing, reduced impact"),
        
        # Grip/Forearm Regressions
        ("Deadlift", "Trap Bar Deadlift", RelationshipType.REGRESSION, "Neutral grip, less grip demand"),
        ("Pull-Up", "Chin-Up", RelationshipType.REGRESSION, "Supinated grip, stronger bicep contribution"),
        
        # Hip/Ankle Mobility Regressions
        ("Deep Squat", "Heel-Elevated Squat", RelationshipType.REGRESSION, "Improved ankle mobility"),
        ("Lunge", "Split Squat", RelationshipType.REGRESSION, "Stable base, less balance demand"),
    ]
    
    return regressions

async def map_skill_regression_relationships():
    """Map skill-based regression relationships (easier variations for skill development)."""
    
    skill_regressions = [
        # Pull-up Skill Regressions
        ("Pull-Up", "Chin-Up", RelationshipType.REGRESSION, "Easier grip for beginners"),
        ("Chin-Up", "Neutral Grip Pull-Up", RelationshipType.REGRESSION, "Easier than chin-up"),
        ("Pull-Up", "Band-Assisted Pull-Up", RelationshipType.REGRESSION, "Progressive load reduction"),
        ("Pull-Up", "Jump Pull-Up", RelationshipType.REGRESSION, "Explosive concentric focus"),
        
        # Push-up Skill Regressions
        ("Push-Up", "Knee Push-Up", RelationshipType.REGRESSION, "Reduced lever length"),
        ("Push-Up", "Incline Push-Up", RelationshipType.REGRESSION, "Reduced load"),
        ("Push-Up", "Wall Push-Up", RelationshipType.REGRESSION, "Foundational pattern"),
        ("Diamond Push-Up", "Regular Push-Up", RelationshipType.REGRESSION, "Tricep to general chest"),
        
        # Handstand Skill Regressions
        ("Handstand Push-Up", "Pike Push-Up", RelationshipType.REGRESSION, "Vertical pressing without balance"),
        ("Pike Push-Up", "Decline Push-Up", RelationshipType.REGRESSION, "Less vertical angle"),
        ("Handstand Hold", "Wall Handstand", RelationshipType.REGRESSION, "Supported balance"),
        ("Wall Handstand", "Frog Stand", RelationshipType.REGRESSION, "Static hold foundation"),
        
        # Pistol Squat Skill Regressions
        ("Pistol Squat", "Bench Pistol Squat", RelationshipType.REGRESSION, "Lower target"),
        ("Pistol Squat", "Assisted Pistol Squat", RelationshipType.REGRESSION, "Support for balance"),
        ("Bench Pistol Squat", "Pistol Squat to Box", RelationshipType.REGRESSION, "Progression to full pistol"),
        
        # L-Sit Skill Regressions
        ("L-Sit", "Tuck L-Sit", RelationshipType.REGRESSION, "Knees tucked, easier compression"),
        ("Tuck L-Sit", "Tuck Sit", RelationshipType.REGRESSION, "Feet on ground"),
        
        # Planche Skill Regressions
        ("Planche", "Tuck Planche", RelationshipType.REGRESSION, "Knees tucked, body compact"),
        ("Tuck Planche", "Frog Stand", RelationshipType.REGRESSION, "More forward lean allowed"),
        
        # Core Skill Regressions
        ("Ab Wheel Rollout", "Plank", RelationshipType.REGRESSION, "Static anti-extension"),
        ("Ab Wheel Rollout", "Kneeling Rollout", RelationshipType.REGRESSION, "Shorter ROM"),
        ("Side Plank", "Modified Side Plank", RelationshipType.REGRESSION, "Knees down"),
        
        # Muscle-up Skill Regressions
        ("Muscle-Up", "Jump Muscle-Up", RelationshipType.REGRESSION, "Explosive concentric, easier transition"),
        ("Muscle-Up", "Assisted Muscle-Up", RelationshipType.REGRESSION, "Band or machine assistance"),
        
        # L-sit to V-sit Progression
        ("V-Sit", "L-Sit", RelationshipType.REGRESSION, "Straddle to full extension"),
        
        # Front Lever Skill Regressions
        ("Front Lever", "Tuck Front Lever", RelationshipType.REGRESSION, "Knees tucked"),
        ("Tuck Front Lever", "Adv Tuck Front Lever", RelationshipType.REGRESSION, "One leg extended"),
        
        # Back Lever Skill Regressions
        ("Back Lever", "Tuck Back Lever", RelationshipType.REGRESSION, "Knees tucked"),
        ("Tuck Back Lever", "Adv Tuck Back Lever", RelationshipType.REGRESSION, "One leg extended"),
    ]
    
    return skill_regressions

async def map_variation_relationships():
    """Map variation relationships between movements."""
    
    variations = [
        # Deadlift Variations
        ("Conventional Deadlift", "Sumo Deadlift", RelationshipType.VARIATION, "Wider stance, hip-dominant"),
        ("Conventional Deadlift", "Romanian Deadlift", RelationshipType.VARIATION, "Knees soft, hip hinge focus"),
        ("Conventional Deadlift", "Stiff-Leg Deadlift", RelationshipType.VARIATION, "Minimal knee flexion"),
        
        # Squat Variations
        ("Back Squat", "Front Squat", RelationshipType.VARIATION, "Anterior load, more upright"),
        ("Back Squat", "Overhead Squat", RelationshipType.VARIATION, "Overhead stability demand"),
        ("Back Squat", "Bulgarian Split Squat", RelationshipType.VARIATION, "Unilateral lunge pattern"),
        
        # Bench Press Variations
        ("Barbell Bench Press", "Close-Grip Bench Press", RelationshipType.VARIATION, "Tricep emphasis"),
        ("Barbell Bench Press", "Incline Bench Press", RelationshipType.VARIATION, "Upper chest emphasis"),
        ("Barbell Bench Press", "Dumbbell Chest Press", RelationshipType.VARIATION, "Unilateral, greater ROM"),
        
        # Row Variations
        ("Barbell Row", "Dumbbell Row", RelationshipType.VARIATION, "Unilateral, reduced spinal load"),
        ("Barbell Row", "T-Bar Row", RelationshipType.VARIATION, "Neutral grip, more stability"),
        ("Barbell Row", "Cable Row", RelationshipType.VARIATION, "Constant tension, isolation"),
        
        # Overhead Press Variations
        ("Overhead Press", "Arnold Press", RelationshipType.VARIATION, "Rotational component"),
        ("Overhead Press", "Push Press", RelationshipType.VARIATION, "Leg drive for momentum"),
        ("Overhead Press", "Landmine Press", RelationshipType.VARIATION, "Arc path, shoulder-friendly"),
        
        # Pull-up Variations
        ("Pull-Up", "Chin-Up", RelationshipType.VARIATION, "Supinated grip, bicep emphasis"),
        ("Pull-Up", "Neutral Grip Pull-Up", RelationshipType.VARIATION, "Neutral grip, wrist-friendly"),
        
        # Lunge Variations
        ("Forward Lunge", "Reverse Lunge", RelationshipType.VARIATION, "Reduced knee shear"),
        ("Forward Lunge", "Lateral Lunge", RelationshipType.VARIATION, "Frontal plane movement"),
        ("Forward Lunge", "Curtsy Lunge", RelationshipType.VARIATION, "Glute emphasis"),
        
        # Core Variations
        ("Plank", "Side Plank", RelationshipType.VARIATION, "Lateral stability"),
        ("Plank", "Ab Wheel Rollout", RelationshipType.VARIATION, "Anti-extension progression"),
        
        # Carry Variations
        ("Farmer's Carry", "Suitcase Carry", RelationshipType.VARIATION, "Unilateral, core stability"),
        ("Farmer's Carry", "Overhead Carry", RelationshipType.VARIATION, "Overhead stability"),
    ]
    
    return variations

async def map_complex_relationships():
    """Map all complex relationships between movements."""
    
    async with async_session_maker() as db:
        print("=== PHASE 3: DEEP ENRICHMENT - MAP COMPLEX RELATIONSHIPS ===\n")
        
        print("--- PROGRESSIONS (Calisthenics) ---")
        progressions = await map_progression_relationships()
        for source, target, rel_type, notes in progressions:
            await create_relationship(db, source, target, rel_type, notes)
        
        print("\n--- INJURY REGRESSIONS ---")
        regressions = await map_injury_regression_relationships()
        for source, target, rel_type, notes in regressions:
            await create_relationship(db, source, target, rel_type, notes)
        
        print("\n--- SKILL REGRESSIONS ---")
        skill_regressions = await map_skill_regression_relationships()
        for source, target, rel_type, notes in skill_regressions:
            await create_relationship(db, source, target, rel_type, notes)
        
        print("\n--- VARIATIONS ---")
        variations = await map_variation_relationships()
        for source, target, rel_type, notes in variations:
            await create_relationship(db, source, target, rel_type, notes)
        
        await db.commit()
        print("\n=== COMPLEX RELATIONSHIPS MAPPED ===")

async def main():
    """Main entry point."""
    await map_complex_relationships()

if __name__ == "__main__":
    asyncio.run(main())
