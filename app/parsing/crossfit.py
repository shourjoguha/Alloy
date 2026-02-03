import re
from typing import Any, Dict, List, Optional, Set, Tuple

class CrossFitParser:
    """
    Parser for CrossFit workout text into structured ExerciseBlocks.
    """
    
    def __init__(self, existing_movements: Set[str]):
        """
        Args:
            existing_movements: Set of known movement names (lowercase) for fuzzy matching.
        """
        self.existing_movements = existing_movements

    def parse_workout(self, raw_text: str) -> Dict[str, Any]:
        """
        Parse raw workout text into a structure containing metadata and exercises.
        
        Returns:
            Dict with keys:
            - exercises: List[Dict]
            - circuit_type: str (AMRAP, EMOM, RFT, etc.)
            - time_cap: str | None
            - rounds: int | None
            - interval_notes: str | None
        """
        exercises = []
        lines = raw_text.split('\n')
        
        # 1. Extract Metadata from the full text (or header lines)
        metadata = self._extract_metadata(raw_text)
        
        # Rx weights often appear at the end of the workout text
        # We try to extract global Rx weights first if they apply to the whole workout (less common)
        # or parse them line-by-line.
        # But commonly in CF.com text: "♂ 50 lb ♀ 35 lb" appears on its own line or at the bottom.
        # We'll scan for these global/footer weights and try to associate them if exercises don't have their own.
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            rounds_match = re.match(r'^(\d+)\s+rounds\b', line, re.IGNORECASE)
            if rounds_match:
                if metadata.get("rounds") is None:
                    metadata["rounds"] = int(rounds_match.group(1))
                continue
            
            if self._is_junk_line(line):
                continue
                
            exercise = self._parse_line(line)
            
            if exercise:
                exercises.append(exercise)
        
        # Post-process to merge orphan weights
        exercises = self._merge_orphan_weights(exercises)
                
        return {
            "exercises": exercises,
            **metadata
        }

    def _extract_metadata(self, text: str) -> Dict[str, Any]:
        """
        Analyze text to find circuit type, time caps, and rounds.
        """
        text_lower = text.lower()
        meta = {
            "circuit_type": "unknown",
            "time_cap": None,
            "rounds": None,
            "interval_notes": None
        }
        
        # Circuit Type & Time Cap
        if "amrap" in text_lower or "complete as many rounds" in text_lower:
            meta["circuit_type"] = "AMRAP"
            # Look for time cap "in 20 minutes"
            time_match = re.search(r'in (\d+)\s*[- ]?(minute|min)', text_lower)
            if time_match:
                meta["time_cap"] = f"{time_match.group(1)} min"
                
        elif "emom" in text_lower or "every minute" in text_lower or "on a" in text_lower and "clock" in text_lower:
            meta["circuit_type"] = "EMOM"
            # Look for interval "On a 90-second clock"
            interval_match = re.search(r'on a (\d+)\s*[- ]?(second|minute|sec|min)', text_lower)
            if interval_match:
                meta["interval_notes"] = f"Interval: {interval_match.group(1)} {interval_match.group(2)}"
                
        elif "rounds for time" in text_lower or "rounds of" in text_lower:
            meta["circuit_type"] = "Rounds For Time"
            # Look for rounds "3 rounds for time"
            rounds_match = re.search(r'^(\d+)\s+rounds', text_lower, re.MULTILINE)
            if rounds_match:
                meta["rounds"] = int(rounds_match.group(1))
                
        elif "for time" in text_lower:
            meta["circuit_type"] = "For Time"
            
        return meta


    def _merge_orphan_weights(self, exercises: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge exercises that are just weight specifications into the previous valid exercise.
        """
        if not exercises:
            return []
            
        merged = []
        for ex in exercises:
            # Check if this is a weight-only line (has weight, no metrics, generic name)
            is_weight_line = (
                ex['rx_weight'] is not None 
                and ex['metric_type'] == 'unknown'
                and (not ex['movement'] or len(ex['movement']) < 20) # arbitrary length check for "dumbbells" etc
            )
            
            if is_weight_line and merged:
                # Try to find best target
                target = None
                
                # 1. Look for matching equipment name backwards
                if ex['movement']:
                    equip_keyword = ex['movement'].lower().replace('s', '') # simple singularize
                    for i in range(len(merged) - 1, -1, -1):
                        cand = merged[i]
                        if equip_keyword in cand['movement'].lower() or equip_keyword in (cand.get('original') or '').lower():
                            target = cand
                            break
                
                # 2. Fallback to immediate predecessor
                if not target:
                    target = merged[-1]
                
                # Merge logic
                if target['rx_weight'] is None:
                    target['rx_weight'] = ex['rx_weight']
                    # Append original text to notes for audit
                    old_notes = target['notes'] or ""
                    target['notes'] = (old_notes + f" ({ex['original']})").strip()
                elif target['rx_weight'] and ex['rx_weight']:
                    # If target already has weight (e.g. from Female line), and this is Male line, merge them
                    t_w = target['rx_weight']
                    s_w = ex['rx_weight']
                    
                    if s_w['male'] and not t_w['male']:
                        t_w['male'] = s_w['male']
                    if s_w['female'] and not t_w['female']:
                        t_w['female'] = s_w['female']
                    
                    # Update notes too
                    old_notes = target['notes'] or ""
                    if ex['original'] not in old_notes:
                        target['notes'] = (old_notes + f" ({ex['original']})").strip()
                        
                continue # Skip adding this weight-line to merged list
                
            merged.append(ex)
            
        return merged

    def _is_junk_line(self, line: str) -> bool:
        line_lower = line.lower()
        
        if line_lower.startswith(("post time", "post rounds", "post score", "compare to", "stimulus", "scaling")):
            return True
            
        if "crossfit affiliate programming" in line_lower:
            return True

        if line_lower.startswith("complete as many rounds"):
            return True
        
        if re.match(r'on a \d+\s*[- ]?(second|seconds|minute|minutes|min|sec|secs)\s+clock', line_lower):
            return True
            
        if len(line) < 3:
            return True
            
        return False

    def _extract_footer_weights(self, text: str) -> Dict[str, Any]:
        """
        Scan for patterns like:
        "♀ 35-lb dumbbells"
        "♂ 50-lb dumbbells"
        Returns a dict of found weights to potentially apply to relevant movements.
        """
        # This is a bit complex because weights map to specific equipment (DB vs KB vs Barbell).
        # For now, we'll rely on line-parsing, but this is a placeholder if we need global context.
        return {}

    def _parse_line(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single line into an exercise structure.
        Schema:
        {
            "original": str,
            "movement": str,
            "movement_id": int | None,  # To be filled by caller or fuzzy matcher
            "is_new": bool,
            "sets": int | None,
            "reps": int | None,
            "duration_seconds": int | None,
            "distance_meters": int | None,
            "rx_weight": { "male": float | None, "female": float | None, "unit": "lb" | "kg" } | None,
            "metric_type": "reps" | "time" | "distance" | "calories" | "unknown",
            "notes": str | None
        }
        """
        # Initialize result
        result = {
            "original": line,
            "movement": "",
            "movement_id": None,
            "is_new": True,
            "sets": None,
            "reps": None,
            "duration_seconds": None,
            "distance_meters": None,
            "rx_weight": None,
            "metric_type": "unknown",
            "notes": None
        }

        clean_line = line
        
        dist_match = re.search(r'(\d+(?:,\d+)?)\s*[- ]?\b(meter|meters|m|ft|foot|feet|km|row|run|swim|yard|yards)\b', clean_line, re.IGNORECASE)
        
        if dist_match:
            val_str = dist_match.group(1).replace(',', '')
            unit = dist_match.group(2).lower()
            val = float(val_str)
            
            if 'km' in unit:
                result['distance_meters'] = int(val * 1000)
            elif 'ft' in unit or 'foot' in unit or 'feet' in unit:
                result['distance_meters'] = int(val * 0.3048)
            elif 'yard' in unit:
                 result['distance_meters'] = int(val * 0.9144)
            else:
                result['distance_meters'] = int(val)
            
            result['metric_type'] = 'distance'
            # Strip the whole matched pattern including trailing hyphens
            clean_line = re.sub(r'\d+(?:,\d+)?\s*[- ]?\b(meter|meters|m|ft|foot|feet|km|yard|yards)\b[- ]?', '', clean_line, flags=re.IGNORECASE)

        time_match = re.search(r'(\d+)\s*[- ]?\b(minute|minutes|min|mins|second|seconds|sec|secs|s)\b', clean_line, re.IGNORECASE)
        if time_match:
            val = int(time_match.group(1))
            unit = time_match.group(2).lower()
            if 'min' in unit:
                result['duration_seconds'] = val * 60
            else:
                result['duration_seconds'] = val
            result['metric_type'] = 'time'
            clean_line = re.sub(r'\d+\s*[- ]?\b(minute|minutes|min|mins|second|seconds|sec|secs|s)\b[- ]?', '', clean_line, flags=re.IGNORECASE)

        cal_match = re.search(r'(\d+)(?:/(\d+))?\s*[- ]?(calorie|cal|cals)', clean_line, re.IGNORECASE)
        if cal_match:
            m_cals = int(cal_match.group(1))
            f_cals = int(cal_match.group(2)) if cal_match.group(2) else None
            
            result['reps'] = m_cals
            result['metric_type'] = 'calories'
            result['notes'] = f"Calories: M {m_cals}" + (f" / F {f_cals}" if f_cals else "")
            
            # Fix: regex to capture trailing hyphen before "calorie"
            clean_line = re.sub(r'(\d+)(?:/(\d+))?\s*[- ]+(calorie|cal|cals)', '', clean_line, flags=re.IGNORECASE)

        if result['metric_type'] == 'unknown':
            reps_match = re.search(r'^(\d+)\s*[- ]*\s*', clean_line)
            ladder_match = re.search(r'^(\d+(?:-\d+)+)\s+', clean_line)
            
            if ladder_match:
                result['notes'] = f"Rep scheme: {ladder_match.group(1)}"
                result['metric_type'] = 'reps'
                clean_line = re.sub(r'^(\d+(?:-\d+)+)\s+', '', clean_line)
            elif reps_match:
                result['reps'] = int(reps_match.group(1))
                result['metric_type'] = 'reps'
                # Strip number and potential trailing hyphen/space
                clean_line = re.sub(r'^(\d+)\s*[- ]*\s*', '', clean_line)


        weight_data = {"male": None, "female": None, "unit": "lb"}
        found_weight = False
        
        # Gender symbol pattern - Combined
        gender_match = re.search(r'[♀|Women]\s*(\d+)\s*[- ]?(lb|kg).*?[♂|Men]\s*(\d+)\s*[- ]?(lb|kg)', line, re.IGNORECASE)
        if not gender_match:
             gender_match = re.search(r'[♂|Men]\s*(\d+)\s*[- ]?(lb|kg).*?[♀|Women]\s*(\d+)\s*[- ]?(lb|kg)', line, re.IGNORECASE)
        
        if gender_match:
             # Try to determine which group is which based on label proximity
             full_match = gender_match.group(0)
             if re.match(r'[♀|Women]', full_match, re.IGNORECASE):
                 weight_data["female"] = float(gender_match.group(1))
                 weight_data["male"] = float(gender_match.group(3))
                 weight_data["unit"] = 'kg' if 'kg' in gender_match.group(2).lower() else 'lb'
             else:
                 weight_data["male"] = float(gender_match.group(1))
                 weight_data["female"] = float(gender_match.group(3))
                 weight_data["unit"] = 'kg' if 'kg' in gender_match.group(2).lower() else 'lb'
             found_weight = True 
        else:
            # Try single gender patterns
            female_match = re.search(r'[♀|Women]\s*(\d+)\s*[- ]?(lb|kg)', line, re.IGNORECASE)
            male_match = re.search(r'[♂|Men]\s*(\d+)\s*[- ]?(lb|kg)', line, re.IGNORECASE)
            
            if female_match:
                weight_data["female"] = float(female_match.group(1))
                weight_data["unit"] = 'kg' if 'kg' in female_match.group(2).lower() else 'lb'
                found_weight = True
            
            if male_match:
                weight_data["male"] = float(male_match.group(1))
                weight_data["unit"] = 'kg' if 'kg' in male_match.group(2).lower() else 'lb'
                found_weight = True

        if found_weight:
            result['rx_weight'] = weight_data
            # Remove weight info from clean_line for name matching
            clean_line = re.sub(r'\(.*?\)', '', clean_line)
            clean_line = re.sub(r'@[^,]+', '', clean_line)
            # Remove gender patterns
            clean_line = re.sub(r'[♀♂|Women|Men]\s*\d+\s*[- ]?(lb|kg)', '', clean_line, flags=re.IGNORECASE)
        
        parens_match = re.search(r'\((\d+)/(\d+)\s*(lb|kg|lbs)?\)', line)
        if parens_match:
            weight_data["male"] = float(parens_match.group(1))
            weight_data["female"] = float(parens_match.group(2))
            if parens_match.group(3):
                weight_data["unit"] = 'kg' if 'kg' in parens_match.group(3).lower() else 'lb'
            found_weight = True
            
        if not found_weight:
            single_match = re.search(r'[@\(]\s*(\d+)\s*(lb|kg|lbs)', line, re.IGNORECASE)
            if single_match:
                weight_data["male"] = float(single_match.group(1)) # Assume single is M or universal
                weight_data["unit"] = 'kg' if 'kg' in single_match.group(2).lower() else 'lb'
                found_weight = True

        if found_weight:
            result['rx_weight'] = weight_data
            # Remove weight info from clean_line for name matching
            clean_line = re.sub(r'\(.*?\)', '', clean_line)
            clean_line = re.sub(r'@[^,]+', '', clean_line)

        name = clean_line.strip()
        name = re.sub(r'[-–—]', ' ', name) # dash to space
        name = re.sub(r'\s+', ' ', name)
        name = re.sub(r'^max[-\s]+reps?\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'^max\s+', '', name, flags=re.IGNORECASE)
        
        name = re.sub(r'\b(reps|rep|calories|cal)\b', '', name, flags=re.IGNORECASE).strip()
        
        result['movement'] = name
        
        matched_id, matched_name = self._fuzzy_match_movement(name)
        if matched_id:
            result['movement_id'] = matched_id
            result['movement'] = matched_name # Use canonical name
            result['is_new'] = False
        else:
            result['is_new'] = True
        
        line_lower = line.lower()
        if line_lower.startswith("max-reps") or line_lower.startswith("max reps") or line_lower.startswith("max-") or line_lower.startswith("max "):
            result['metric_type'] = 'reps'
            if result['reps'] is None:
                result['reps'] = 999
            if result['notes']:
                if "max" not in result['notes'].lower():
                    result['notes'] = (result['notes'] + " max").strip()
            else:
                result['notes'] = "max"
        
        return result

    def _fuzzy_match_movement(self, candidate: str) -> Tuple[Optional[int], str]:
        """
        Match candidate string against existing movement set.
        Returns (id, name) or (None, candidate).
        For now, since we don't have IDs in the set passed to __init__, we return None ID.
        In a real app, we'd pass a dict mapping names to IDs.
        """
        # Simple inclusion check
        candidate_norm = self._normalize(candidate)
        
        # Try exact match
        if candidate_norm in self.existing_movements:
            return (None, candidate_norm) # ID would be looked up later
            
        # Try "contains"
        for exist in self.existing_movements:
            if exist in candidate_norm or candidate_norm in exist:
                # Basic safety: don't match "press" to "bench press" too eagerly
                # But for now, simple is better than nothing
                return (None, exist)
                
        return (None, candidate)

    def _normalize(self, text: str) -> str:
        return re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()
