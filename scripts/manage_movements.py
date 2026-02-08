# python3 scripts/manage_movements.py ingest-exercemus --dry-run
# python3 scripts/manage_movements.py ingest-exercemus --commit
# python3 scripts/manage_movements.py enrich
# python3 scripts/manage_movements.py fix-json
# python3 scripts/manage_movements.py verify

import asyncio
import argparse
import json
import sys
import os
import httpx
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from difflib import SequenceMatcher

# Add project root to path
sys.path.insert(0, os.getcwd())

from app.config.settings import get_settings
from app.db.database import async_session_maker
from app.models.movement import Movement
from app.models.enums import (
    MovementPattern,
    PrimaryMuscle,
    PrimaryRegion,
    MetricType,
    SkillLevel,
    CNSLoad,
)

# Constants for Exercemus Ingestion
EXERCISES_URL = "https://raw.githubusercontent.com/exercemus/exercises/minified/minified-exercises.json"
OUTPUT_DIR = Path(os.getcwd()) / "seed_data"
AMBIGUOUS_PATH = OUTPUT_DIR / "exercemus_ambiguous_candidates.json"
LOW_SCORE_PATH = OUTPUT_DIR / "exercemus_low_score_samples.json"
SUMMARY_PATH = OUTPUT_DIR / "exercemus_import_summary.json"
INVALID_PATH = OUTPUT_DIR / "exercemus_invalid_candidates.json"
MOVEMENTS_JSON_PATH = OUTPUT_DIR / "movements.json"
CLEAN_CROSSFIT_JSON_PATH = OUTPUT_DIR / "clean_crossfit_movements.json"

EQUIPMENT_TERMS = [
    "barbell", "dumbbell", "kettlebell", "machine", "smith", "smith machine",
    "cable", "band", "resistance band", "bodyweight", "trap bar", "ez bar",
    "plate", "medicine ball", "slam ball", "sandbag", "sled", "rower", "bike",
    "ski erg", "air bike", "assault bike", "box", "bench", "pull-up bar", "rings"
]

BODYWEIGHT_TERMS = ["bodyweight", "no equipment"]

NAME_TOKEN_SYNONYMS = {
    "roller": "rollout",
}

SKILL_LEVEL_MAP = {
    1: "beginner",
    2: "intermediate",
    3: "advanced",
    4: "expert",
    5: "elite"
}

@dataclass
class MovementCandidate:
    source_name: str
    source_aliases: List[str]
    canonical_base_name: str
    canonical_name_key: str
    pattern: str
    primary_muscle: str
    secondary_muscles: List[str]
    primary_region: str
    discipline_tags: List[str]
    equipment_tags: List[str]
    metric_type: str
    skill_level: str
    cns_load: str
    compound: bool
    is_complex_lift: bool
    is_unilateral: bool
    description: Optional[str]
    coaching_cues: List[str]
    substitution_group: Optional[str]
    variation_on_names: List[str]
    source_category: Optional[str]
    source_primary_muscles_raw: List[str]
    source_secondary_muscles_raw: List[str]
    source_equipment_raw: List[str]
    source_id: Optional[str]
    license_author: Optional[str]
    license_meta: Optional[Dict[str, Any]]

# --- Helper Functions ---

def clean_name_for_enrich(name):
    n = name.strip()
    if n.lower().startswith("max- "):
        n = n[5:]
    if n.lower().startswith("second "):
        n = n[7:]
    return n

def normalize_string(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower())

def clean_name_token(token: str) -> str:
    t = token.lower().strip()
    return NAME_TOKEN_SYNONYMS.get(t, t)

def is_variation_of(candidate_name: str, base_name: str) -> bool:
    c_tokens = set(clean_name_token(t) for t in candidate_name.split())
    b_tokens = set(clean_name_token(t) for t in base_name.split())
    return b_tokens.issubset(c_tokens)

def get_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def map_muscle_to_region(muscle: str) -> str:
    # Simplified mapping
    muscle = muscle.lower()
    if muscle in ["quadriceps", "hamstrings", "calves", "glutes", "adductors", "abductors"]:
        return PrimaryRegion.LEGS.value
    if muscle in ["chest", "pectorals"]:
        return PrimaryRegion.CHEST.value
    if muscle in ["lats", "traps", "rhomboids", "lower_back"]:
        return PrimaryRegion.BACK.value
    if muscle in ["shoulders", "delts", "rotator_cuff"]:
        return PrimaryRegion.SHOULDERS.value
    if muscle in ["biceps", "triceps", "forearms"]:
        return PrimaryRegion.ARMS.value
    if muscle in ["abdominals", "obliques", "core"]:
        return PrimaryRegion.CORE.value
    return PrimaryRegion.FULL_BODY.value

def map_category_to_pattern(category: str, name: str) -> str:
    cat = category.lower()
    name = name.lower()
    
    if "squat" in cat or "squat" in name:
        return MovementPattern.SQUAT.value
    if "lunge" in cat or "lunge" in name or "split squat" in name:
        return MovementPattern.LUNGE.value
    if "hinge" in cat or "deadlift" in name or "good morning" in name or "clean" in name or "snatch" in name or "swing" in name:
        return MovementPattern.HINGE.value
    if "push" in cat:
        if "press" in name or "push up" in name or "bench" in name or "dip" in name:
            if "overhead" in name or "shoulder" in name or "military" in name:
                return MovementPattern.PUSH_VERTICAL.value
            return MovementPattern.PUSH_HORIZONTAL.value
    if "pull" in cat:
        if "row" in name or "pull up" in name or "chin up" in name or "lat pulldown" in name:
            if "row" in name:
                return MovementPattern.PULL_HORIZONTAL.value
            return MovementPattern.PULL_VERTICAL.value
    if "carry" in cat or "carry" in name or "walk" in name:
        return MovementPattern.CARRY.value
    
    # Fallbacks based on name analysis
    if "press" in name:
        if "overhead" in name or "shoulder" in name:
            return MovementPattern.PUSH_VERTICAL.value
        return MovementPattern.PUSH_HORIZONTAL.value
    if "row" in name:
        return MovementPattern.PULL_HORIZONTAL.value
    if "pull up" in name or "chin up" in name:
        return MovementPattern.PULL_VERTICAL.value
    
    return MovementPattern.CORE.value # Default fallback

def extract_equipment_tags(equipment_list: List[str], name: str) -> List[str]:
    tags = set()
    
    # From source list
    if equipment_list:
        for eq in equipment_list:
            eq_lower = eq.lower()
            for term in EQUIPMENT_TERMS:
                if term in eq_lower:
                    tags.add(term)
    
    # From name
    name_lower = name.lower()
    for term in EQUIPMENT_TERMS:
        if term in name_lower:
            tags.add(term)
            
    if not tags:
        if "bodyweight" in equipment_list or not equipment_list:
             tags.add("bodyweight")
             
    return list(tags)

def build_coaching_cues(instructions: List[str], tips: Optional[List[str]]) -> List[str]:
    cues: List[str] = []
    for item in instructions:
        text = item.strip()
        if text:
            cues.append(text)
    if tips:
        for item in tips:
            text = item.strip()
            if text and text not in cues:
                cues.append(text)
    return cues

# --- Action Functions ---

async def run_ingest_exercemus(dry_run: bool = False, commit: bool = False):
    """
    Ingests movements from Exercemus.
    If dry_run is True, it only prints what would happen.
    If commit is True, it saves to DB.
    """
    print(f"Starting Exercemus Ingestion (Dry Run: {dry_run}, Commit: {commit})")
    
    if not dry_run and not commit:
        print("Neither --dry-run nor --commit specified. Doing a dry run by default.")
        dry_run = True

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Fetch Data
    print(f"Fetching exercises from {EXERCISES_URL}...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(EXERCISES_URL)
        resp.raise_for_status()
        data = resp.json()
    
    print(f"Fetched {len(data)} exercises.")

    # 2. Load Existing Movements
    async with async_session() as session:
        result = await session.execute(select(Movement))
        existing_movements = result.scalars().all()
        
        existing_map = {} # normalized_name -> Movement
        for m in existing_movements:
            existing_map[normalize_string(m.name)] = m
            
        print(f"Loaded {len(existing_movements)} existing movements from DB.")

        new_candidates = []
        ambiguous_candidates = []
        skipped_count = 0
        
        for item in data:
            name = item.get("name", "").strip()
            if not name:
                continue
                
            normalized = normalize_string(name)
            
            # Direct match check
            if normalized in existing_map:
                skipped_count += 1
                continue
                
            # Similarity check
            best_match = None
            highest_score = 0.0
            
            for exist_norm, exist_mov in existing_map.items():
                score = get_similarity(name, exist_mov.name)
                if score > highest_score:
                    highest_score = score
                    best_match = exist_mov
            
            if highest_score > 0.9:
                # Likely duplicate
                skipped_count += 1
                continue
                
            # Create Candidate
            category = item.get("category", "strength")
            muscles = item.get("primaryMuscles", [])
            equipment = item.get("equipment", [])
            
            pattern = map_category_to_pattern(category, name)
            primary_muscle = muscles[0] if muscles else "unknown"
            region = map_muscle_to_region(primary_muscle)
            
            candidate = MovementCandidate(
                source_name=name,
                source_aliases=item.get("aliases", []),
                canonical_base_name=name,
                canonical_name_key=normalized,
                pattern=pattern,
                primary_muscle=primary_muscle,
                secondary_muscles=item.get("secondaryMuscles", []),
                primary_region=region,
                discipline_tags=["strength"], # Default
                equipment_tags=extract_equipment_tags(equipment, name),
                metric_type=MetricType.REPS.value,
                skill_level=SkillLevel.INTERMEDIATE.value,
                cns_load=CNSLoad.MODERATE.value,
                compound=len(muscles) > 1,
                is_complex_lift=False,
                is_unilateral="single" in name.lower() or "one arm" in name.lower(),
                description="\n".join(item.get("instructions", [])),
                coaching_cues=build_coaching_cues(item.get("instructions", []), item.get("tips", [])),
                substitution_group=None,
                variation_on_names=[],
                source_category=category,
                source_primary_muscles_raw=muscles,
                source_secondary_muscles_raw=item.get("secondaryMuscles", []),
                source_equipment_raw=equipment,
                source_id=item.get("id"),
                license_author=item.get("author"),
                license_meta=None
            )
            
            if highest_score > 0.7:
                ambiguous_candidates.append({
                    "candidate": name,
                    "match": best_match.name,
                    "score": highest_score
                })
            else:
                new_candidates.append(candidate)

        print(f"Skipped {skipped_count} existing/similar movements.")
        print(f"Found {len(ambiguous_candidates)} ambiguous candidates.")
        print(f"Found {len(new_candidates)} likely new movements.")

        # Save Reports
        with open(AMBIGUOUS_PATH, "w") as f:
            json.dump(ambiguous_candidates, f, indent=2)
            
        if commit:
            print("Committing new movements to DB...")
            created_count = 0
            for cand in new_candidates:
                movement = Movement(
                    name=cand.source_name,
                    pattern=cand.pattern,
                    primary_muscle=cand.primary_muscle,
                    primary_region=cand.primary_region,
                    secondary_muscles=cand.secondary_muscles,
                    cns_load=cand.cns_load,
                    skill_level=cand.skill_level,
                    compound=cand.compound,
                    is_complex_lift=cand.is_complex_lift,
                    is_unilateral=cand.is_unilateral,
                    metric_type=cand.metric_type,
                    discipline_tags=cand.discipline_tags,
                    equipment_tags=cand.equipment_tags,
                    description=cand.description,
                    coaching_cues=cand.coaching_cues,
                    substitution_group=cand.substitution_group,
                )
                session.add(movement)
                created_count += 1
            
            try:
                await session.commit()
                print(f"Successfully inserted {created_count} new movements.")
            except Exception as e:
                await session.rollback()
                print(f"Error committing to database: {e}")
        else:
            print("Dry run complete. No changes made to DB.")

async def run_enrich():
    """
    Enriches existing movements with data from clean_crossfit_movements.json.
    """
    print("Starting Movement Enrichment...")
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    if not CLEAN_CROSSFIT_JSON_PATH.exists():
        print(f"Error: {CLEAN_CROSSFIT_JSON_PATH} not found.")
        return

    with open(CLEAN_CROSSFIT_JSON_PATH, 'r') as f:
        raw_cf = json.load(f)
        
    cf_names = set()
    for n in raw_cf:
        c = clean_name_for_enrich(n)
        cf_names.add(c.lower()) 

    async with async_session() as session:
        result = await session.execute(select(Movement))
        movements = result.scalars().all()
        
        updated_count = 0
        for m in movements:
            old_disc = m.primary_discipline
            new_disc = "All"
            
            m_name_clean = clean_name_for_enrich(m.name).lower()
            
            if m_name_clean in cf_names:
                new_disc = "CrossFit"
            
            # Heuristics
            if "clean" in m_name_clean or "snatch" in m_name_clean or "jerk" in m_name_clean:
                if "dumbbell" not in m_name_clean and "kettlebell" not in m_name_clean:
                     new_disc = "Weightlifting"
            
            if "squat" in m_name_clean or "deadlift" in m_name_clean or "bench" in m_name_clean:
                 if "barbell" in m_name_clean:
                     new_disc = "Powerlifting"
                     
            if new_disc != "All":
                m.primary_discipline = new_disc
                updated_count += 1
                
        await session.commit()
        print(f"Enriched {updated_count} movements with primary_discipline.")

def run_fix_json():
    """
    Fixes skill_level mapping in movements.json.
    """
    print("Running JSON Fixer...")
    if not MOVEMENTS_JSON_PATH.exists():
        print(f"Error: {MOVEMENTS_JSON_PATH} not found.")
        return

    with open(MOVEMENTS_JSON_PATH, "r") as f:
        data = json.load(f)

    movements = data.get("movements", [])
    updated_count = 0

    for m in movements:
        sl = m.get("skill_level")
        if isinstance(sl, int):
            if sl in SKILL_LEVEL_MAP:
                m["skill_level"] = SKILL_LEVEL_MAP[sl]
                updated_count += 1
            else:
                print(f"Unknown skill level {sl} for {m['name']}")

    data["movements"] = movements

    with open(MOVEMENTS_JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Updated {updated_count} movements in {MOVEMENTS_JSON_PATH}")

async def run_verify():
    """
    Verifies movement disciplines in DB.
    """
    print("Running Verification...")
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Count by discipline
        stmt = select(Movement.primary_discipline, func.count(Movement.id)).group_by(Movement.primary_discipline)
        result = await session.execute(stmt)
        for disc, count in result.all():
            print(f"{disc}: {count}")
            
        print("-" * 20)
        
        # Sample check
        samples = ["Thruster", "Bicep Curl", "Snatch", "Cat Cow", "Push-Up", "Burpee"]
        for name in samples:
            stmt = select(Movement).where(Movement.name.ilike(f"%{name}%")).limit(1)
            res = await session.execute(stmt)
            m = res.scalar_one_or_none()
            if m:
                print(f"{m.name}: {m.primary_discipline} ({m.pattern})")
            else:
                print(f"{name}: Not found")

# --- Main CLI ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage Movement Data")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Ingest Exercemus
    parser_ingest = subparsers.add_parser("ingest-exercemus", help="Ingest movements from Exercemus")
    parser_ingest.add_argument("--dry-run", action="store_true", help="Run without committing to DB")
    parser_ingest.add_argument("--commit", action="store_true", help="Commit changes to DB")

    # Enrich
    parser_enrich = subparsers.add_parser("enrich", help="Enrich existing movements")

    # Fix JSON
    parser_fix = subparsers.add_parser("fix-json", help="Fix movements.json format")

    # Verify
    parser_verify = subparsers.add_parser("verify", help="Verify movement data in DB")

    args = parser.parse_args()

    if args.command == "ingest-exercemus":
        asyncio.run(run_ingest_exercemus(dry_run=args.dry_run, commit=args.commit))
    elif args.command == "enrich":
        asyncio.run(run_enrich())
    elif args.command == "fix-json":
        run_fix_json()
    elif args.command == "verify":
        asyncio.run(run_verify())
    else:
        parser.print_help()
