# Unified CLI : You can now run all operations from one place:
#- python3 scripts/manage_crossfit_data.py scrape
#- python3 scripts/manage_crossfit_data.py clean
#- python3 scripts/manage_crossfit_data.py ingest
#- python3 scripts/manage_crossfit_data.py verify
#- python3 scripts/manage_crossfit_data.py all

import requests
from bs4 import BeautifulSoup
import re
import json
import os
import sys
import asyncio
import argparse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.getcwd())

from app.parsing.crossfit import CrossFitParser
from app.models.movement import Movement
from app.models.circuit import CircuitTemplate
from app.models.enums import (
    MovementPattern, PrimaryMuscle, PrimaryRegion, 
    MetricType, SkillLevel, CNSLoad, CircuitType
)
from app.config.settings import get_settings

# --- Constants ---
EXISTING_MOVEMENTS_FILE = os.path.join(os.getcwd(), 'seed_data', 'movements.json')
SCRAPED_CIRCUITS_FILE = os.path.join(os.getcwd(), 'seed_data', 'scraped_circuits.json')
NEW_MOVEMENTS_FILE = os.path.join(os.getcwd(), 'seed_data', 'net_new_movements.json')
CLEAN_MOVEMENTS_FILE = os.path.join(os.getcwd(), 'seed_data', 'clean_crossfit_movements.json')

NAMED_WORKOUTS = {"grace", "isabel", "hidalgo", "fran", "murph", "helen", "diane", "elizabeth"}

DENY_LIST = [
    "compare to", "crossfit.com", "for time", "rounds for", "rounds, each",
    "starting today", "the cap team", "to create a", "complete the",
    "of burpees", "of double-unders", "bodyweight barbell"
]

# --- Helper Functions ---

def load_existing_movements_set():
    if not os.path.exists(EXISTING_MOVEMENTS_FILE):
        return set()
    with open(EXISTING_MOVEMENTS_FILE, 'r') as f:
        data = json.load(f)
        if isinstance(data, dict) and 'movements' in data:
            items = data['movements']
        elif isinstance(data, list):
            items = data
        else:
            items = []
        movements = set()
        for m in items:
            if isinstance(m, dict) and 'name' in m:
                movements.add(re.sub(r'[^a-z0-9\s]', '', m['name'].lower()).strip())
    return movements

def refine_ladder_exercises(exercises, raw_text):
    """
    Detects schemes like "30-24-18-12-6 reps" and expands the exercises list.
    """
    match = re.search(r"(\d+(?:-\d+)+)\s+reps", raw_text, re.IGNORECASE)
    if not match:
        return exercises, False, None

    scheme_str = match.group(1)
    counts = [int(x) for x in scheme_str.split("-")]
    
    # Filter out the "header" movements (like "for time of:")
    real_movements = []
    for ex in exercises:
        name = ex.get('movement', '').lower()
        if not name:
            continue
        # Skip if the movement name is suspiciously like a header
        if "for time" in name or "reps" in name:
            continue
        if ex.get('metric_type') == 'unknown' and ex.get('reps') is None:
             # Likely a movement that needs reps assigned
             real_movements.append(ex)
        elif ex.get('metric_type') != 'unknown':
             # Keep valid movements too
             real_movements.append(ex)
    
    if not real_movements:
        return exercises, False, None

    # Expand
    expanded = []
    for count in counts:
        for mov in real_movements:
            new_ex = mov.copy()
            new_ex['reps'] = count
            new_ex['metric_type'] = 'reps'
            # Update original text for clarity in the expanded list
            new_ex['original'] = f"{count} reps {mov.get('movement', 'movement')}" 
            expanded.append(new_ex)
            
    return expanded, True, len(counts)

def fetch_url(url):
    print(f"Fetching {url}...")
    try:
        response = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        })
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching page: {e}")
        return None

# --- Scraping Logic ---

def parse_workouts(html, existing_movements):
    soup = BeautifulSoup(html, 'html.parser')
    parser = CrossFitParser(existing_movements)
    date_regex = re.compile(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{6}$", re.IGNORECASE)
    headers = soup.find_all(string=date_regex)
    
    circuits = []
    new_movement_candidates = set()
    
    print(f"Found {len(headers)} potential workout segments.")

    for header in headers:
        header_text = header.strip()
        container = header.parent
        while container and container.name not in ['article', 'section', 'div']:
             container = container.parent
        if not container: continue
            
        full_text = container.get_text(separator="\n")
        if "Rest Day" in full_text[:100]: continue
            
        # Extract workout text (simplified logic from original script)
        parts = full_text.split(header_text)
        workout_text = ""
        stimulus_text = ""
        
        if len(parts) > 1:
            content_after = parts[1].strip()
            # Clean up known footers
            content_after = re.sub(r'Post (time|rounds|score|load).*', '', content_after, flags=re.IGNORECASE).strip()
            
            # Extract Stimulus
            if "Stimulus and Strategy" in content_after:
                subparts = content_after.split("Stimulus and Strategy")
                workout_text = subparts[0].strip()
                stimulus_text = subparts[1].strip()
            else:
                workout_text = content_after
        
        if not workout_text: continue

        # Identify Circuit Type
        ctype = "rounds_for_time"
        lower_w = workout_text.lower()
        if "rounds for time" in lower_w: ctype = "rounds_for_time"
        elif "amrap" in lower_w: ctype = "amrap"
        elif "emom" in lower_w: ctype = "emom"
        elif "ladder" in lower_w or re.search(r'\d+(?:-\d+)+\s+reps', lower_w): ctype = "ladder"
        elif "tabata" in lower_w: ctype = "tabata"
        elif "chipper" in lower_w: ctype = "chipper"

        # Parse Exercises
        parsed_data = parser.parse_workout(workout_text)
        exercises = parsed_data['exercises']
        
        if parsed_data['circuit_type'] != "unknown":
            ctype = parsed_data['circuit_type']

        # Ladder Expansion
        rounds_count = parsed_data.get('rounds')
        if ctype == "ladder" or re.search(r'\d+(?:-\d+)+\s+reps', workout_text):
            expanded_exercises, was_expanded, ladder_rounds = refine_ladder_exercises(exercises, workout_text)
            if was_expanded:
                exercises = expanded_exercises
                ctype = "ladder"
                rounds_count = ladder_rounds

        # Collect new movements
        for ex in exercises:
            if ex['is_new']:
                new_movement_candidates.add(ex['movement'])
        
        if exercises:
            circuits.append({
                "name": f"CrossFit {header_text}",
                "date_header": header_text,
                "circuit_type": ctype,
                "description": stimulus_text,
                "raw_workout": workout_text,
                "exercises": exercises,
                "metadata": {
                    "time_cap": parsed_data.get('time_cap'),
                    "rounds": rounds_count,
                    "interval_notes": parsed_data.get('interval_notes')
                }
            })

    return circuits, list(new_movement_candidates)

def run_scrape():
    print("Starting Scrape...")
    existing = load_existing_movements_set()
    html = fetch_url("https://www.crossfit.com/workout")
    if html:
        circuits, new_movements = parse_workouts(html, existing)
        
        # Save Circuits
        with open(SCRAPED_CIRCUITS_FILE, 'w') as f:
            json.dump(circuits, f, indent=2)
        print(f"Saved {len(circuits)} circuits to {SCRAPED_CIRCUITS_FILE}")
        
        # Save New Movements
        with open(NEW_MOVEMENTS_FILE, 'w') as f:
            json.dump(sorted(new_movements), f, indent=2)
        print(f"Saved {len(new_movements)} new movements to {NEW_MOVEMENTS_FILE}")

# --- Cleaning Logic ---

def is_valid_movement(name):
    name_lower = name.lower()
    for deny in DENY_LIST:
        if deny in name_lower: return False
    if len(name) < 3 or len(name) > 40: return False
    if name.strip().endswith('.'): return False
    return True

def run_clean():
    print("Starting Clean...")
    if not os.path.exists(NEW_MOVEMENTS_FILE):
        print("No new movements file found.")
        return

    with open(NEW_MOVEMENTS_FILE, 'r') as f:
        raw_movements = json.load(f)

    clean_movements = []
    for m in raw_movements:
        if is_valid_movement(m):
            clean_movements.append(m)
            
    with open(CLEAN_MOVEMENTS_FILE, 'w') as f:
        json.dump(sorted(clean_movements), f, indent=2)
    print(f"Filtered {len(raw_movements)} -> {len(clean_movements)} movements. Saved to {CLEAN_MOVEMENTS_FILE}")

# --- Ingestion Logic ---

def normalize_name(name):
    return name.lower().strip()

def clean_mov_name(name):
    n = name.strip()
    if n.lower().startswith("max- "): n = n[5:]
    if n.lower().startswith("second "): n = n[7:]
    return n

def guess_metadata(name):
    n = name.lower()
    meta = {
        "pattern": MovementPattern.CONDITIONING,
        "primary_muscle": PrimaryMuscle.FULL_BODY,
        "primary_region": PrimaryRegion.FULL_BODY,
        "metric_type": MetricType.REPS,
        "skill_level": SkillLevel.INTERMEDIATE,
        "cns_load": CNSLoad.MODERATE,
        "primary_discipline": "CrossFit"
    }
    
    if "squat" in n or "thruster" in n or "wall-ball" in n:
        meta.update({"pattern": MovementPattern.SQUAT, "primary_muscle": PrimaryMuscle.QUADRICEPS, "primary_region": PrimaryRegion.LOWER_BODY})
    elif "deadlift" in n or "clean" in n or "snatch" in n:
        meta.update({"pattern": MovementPattern.HINGE, "primary_muscle": PrimaryMuscle.HAMSTRINGS, "primary_region": PrimaryRegion.POSTERIOR_LOWER})
    elif "press" in n or "push-up" in n or "handstand" in n:
        is_vert = "press" in n or "handstand" in n
        meta.update({
            "pattern": MovementPattern.VERTICAL_PUSH if is_vert else MovementPattern.HORIZONTAL_PUSH,
            "primary_muscle": PrimaryMuscle.FRONT_DELTS if is_vert else PrimaryMuscle.CHEST,
            "primary_region": PrimaryRegion.UPPER_BODY
        })
    elif "pull-up" in n or "row" in n:
        is_vert = "pull-up" in n
        meta.update({
            "pattern": MovementPattern.VERTICAL_PULL if is_vert else MovementPattern.HORIZONTAL_PULL,
            "primary_muscle": PrimaryMuscle.LATS,
            "primary_region": PrimaryRegion.UPPER_BODY
        })
    elif any(x in n for x in ["run", "bike", "row", "double-under", "burpee"]):
        is_cardio = any(x in n for x in ["run", "bike", "row"])
        meta.update({
            "pattern": MovementPattern.CARDIO if is_cardio else MovementPattern.PLYOMETRIC,
            "metric_type": MetricType.DISTANCE if is_cardio else MetricType.REPS
        })
    return meta

async def run_ingest():
    print("Starting Ingestion...")
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Ingest Movements
        if os.path.exists(CLEAN_MOVEMENTS_FILE):
            with open(CLEAN_MOVEMENTS_FILE, 'r') as f:
                raw_movements = json.load(f)
            
            existing_result = await session.execute(select(Movement.name))
            existing_names = {n.lower() for n in existing_result.scalars().all()}
            
            movement_map = {}
            res = await session.execute(select(Movement))
            for m in res.scalars().all():
                movement_map[m.name.lower()] = m

            for name in raw_movements:
                clean = clean_mov_name(name)
                if clean.lower() in NAMED_WORKOUTS or clean.lower() in existing_names:
                    continue
                
                meta = guess_metadata(clean)
                new_mov = Movement(name=clean.title(), **meta)
                session.add(new_mov)
                existing_names.add(clean.lower())
                await session.flush()
                movement_map[clean.lower()] = new_mov
            
            await session.commit()
            print("Movements ingested.")

        # 2. Ingest Circuits
        if os.path.exists(SCRAPED_CIRCUITS_FILE):
            with open(SCRAPED_CIRCUITS_FILE, 'r') as f:
                circuits_data = json.load(f)
                
            for c_data in circuits_data:
                if not c_data['exercises']: continue
                
                # Build exercises
                exercises_list = []
                for ex in c_data['exercises']:
                    mov_name = ex.get('movement', '').lower()
                    if not mov_name: mov_name = clean_mov_name(ex.get('original', '')).lower()
                    if not mov_name or re.match(r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+\d{6}$', mov_name): continue
                    
                    matched_mov = movement_map.get(mov_name)
                    if not matched_mov:
                         for k, v in movement_map.items():
                             if k in mov_name or mov_name in k:
                                 matched_mov = v
                                 break
                    
                    exercises_list.append({
                        "reps": ex.get('reps'),
                        "distance_meters": ex.get('distance_meters'),
                        "duration_seconds": ex.get('duration_seconds'),
                        "rest_seconds": None,
                        "notes": ex.get('notes'),
                        "movement_name": matched_mov.name if matched_mov else (ex.get('movement') or ex.get('name')),
                        "movement_id": matched_mov.id if matched_mov else None,
                        "rx_weight_male": ex.get('rx_weight', {}).get('male') if ex.get('rx_weight') else None,
                        "rx_weight_female": ex.get('rx_weight', {}).get('female') if ex.get('rx_weight') else None,
                        "metric_type": ex.get('metric_type', 'unknown')
                    })
                
                ctype_str = c_data.get('circuit_type', 'rounds_for_time').lower()
                ctype_enum = CircuitType.ROUNDS_FOR_TIME
                if "amrap" in ctype_str: ctype_enum = CircuitType.AMRAP
                elif "emom" in ctype_str: ctype_enum = CircuitType.EMOM
                elif "ladder" in ctype_str: ctype_enum = CircuitType.LADDER
                elif "tabata" in ctype_str: ctype_enum = CircuitType.TABATA
                elif "chipper" in ctype_str: ctype_enum = CircuitType.CHIPPER

                # Metadata description
                base_desc = c_data.get('description', '')
                meta = c_data.get('metadata', {})
                meta_strs = []
                if meta.get('time_cap'): meta_strs.append(f"Time Cap: {meta['time_cap']}")
                if meta.get('rounds'): meta_strs.append(f"Rounds: {meta['rounds']}")
                full_desc = (" | ".join(meta_strs) + "\n\n" + base_desc).strip() if meta_strs else base_desc

                # Check if circuit already exists, update if it does
                existing_circuit = await session.execute(
                    select(CircuitTemplate).where(CircuitTemplate.name == c_data['name'])
                )
                circuit = existing_circuit.scalar_one_or_none()
                
                if circuit:
                    # Update existing circuit
                    circuit.description = full_desc
                    circuit.circuit_type = ctype_enum
                    circuit.exercises_json = exercises_list
                    circuit.tags = ["crossfit", "scraped"]
                    circuit.default_rounds = meta.get('rounds')
                else:
                    # Create new circuit
                    new_circuit = CircuitTemplate(
                        name=c_data['name'],
                        description=full_desc,
                        circuit_type=ctype_enum,
                        exercises_json=exercises_list,
                        tags=["crossfit", "scraped"],
                        default_rounds=meta.get('rounds')
                    )
                    session.add(new_circuit)
            
            await session.commit()
            print("Circuits ingested.")

# --- Verification Logic ---

async def run_verify():
    print("Starting Verification...")
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        stmt = select(CircuitTemplate)
        result = await session.execute(stmt)
        all_circuits = result.scalars().all()
        
        valid_circuits = [c for c in all_circuits if c.description and c.exercises_json and len(c.exercises_json) > 0]
        
        print(f"Total circuits: {len(all_circuits)}")
        print(f"Valid circuits (desc + exercises): {len(valid_circuits)}")
        
        # Check for duplicates
        name_counts = {}
        for c in all_circuits:
            name_counts[c.name] = name_counts.get(c.name, 0) + 1
            
        duplicates = {name: count for name, count in name_counts.items() if count > 1}
        
        if duplicates:
            print("\nWARNING: DUPLICATES FOUND:")
            for name, count in duplicates.items():
                print(f"  - {name}: {count} times")
        else:
            print("\nSUCCESS: No duplicate circuit names found.")
        
        # Sample Check
        print("\nSample Circuits:")
        for c in valid_circuits[:3]:
            print(f"ID: {c.id} | Name: {c.name}")
            print(f"Type: {c.circuit_type} | Rounds: {c.default_rounds}")
            print("Exercises:")
            for ex in c.exercises_json[:3]:
                print(f"  - {ex.get('reps') or ''} {ex.get('metric_type') or ''} {ex['movement_name']}")
            print("...")
            print("-" * 40)

# --- Main CLI ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage CrossFit Data Pipeline")
    parser.add_argument("action", choices=["scrape", "clean", "ingest", "verify", "all"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "scrape":
        run_scrape()
    elif args.action == "clean":
        run_clean()
    elif args.action == "ingest":
        asyncio.run(run_ingest())
    elif args.action == "verify":
        asyncio.run(run_verify())
    elif args.action == "all":
        run_scrape()
        run_clean()
        asyncio.run(run_ingest())
        asyncio.run(run_verify())
