"""
Session Content Utilities - Shared utilities for session content manipulation.

Extracted from session_generator.py to reduce code bloat and improve maintainability.
"""

import logging
from typing import Any, TYPE_CHECKING

from app.models.enums import SessionType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DuplicateRemover:
    """Handles removal and replacement of duplicate exercises in session content."""

    # Muscle group alternatives for intelligent replacement
    MUSCLE_ALTERNATIVES = {
        "rear_delts": ["Face Pull", "Reverse Fly", "Band Pull-Apart", "Prone Y Raise", "Cable Reverse Fly"],
        "chest": ["Push-Up", "Dumbbell Fly", "Cable Fly", "Incline Push-Up", "Chest Dip"],
        "lats": ["Lat Pulldown", "Pull-Up", "Chin-Up", "Cable Row", "T-Bar Row"],
        "upper_back": ["Face Pull", "Shrug", "Upright Row", "High Pull", "Band Pull-Apart"],
        "front_delts": ["Front Raise", "Arnold Press", "Pike Push-Up", "Handstand Push-Up"],
        "side_delts": ["Lateral Raise", "Upright Row", "Cable Lateral Raise", "Dumbbell Lateral Raise"],
        "biceps": ["Bicep Curl", "Hammer Curl", "Cable Curl", "Chin-Up", "Preacher Curl"],
        "triceps": ["Tricep Extension", "Close-Grip Push-Up", "Tricep Dip", "Overhead Extension"],
        "quadriceps": ["Leg Extension", "Lunge", "Step-Up", "Wall Sit", "Jump Squat"],
        "hamstrings": ["Leg Curl", "Romanian Deadlift", "Good Morning", "Glute Ham Raise"],
        "glutes": ["Hip Thrust", "Glute Bridge", "Clamshell", "Monster Walk", "Bulgarian Split Squat"],
        "calves": ["Calf Raise", "Jump Rope", "Calf Press", "Single Leg Calf Raise"],
    }

    # Movement pattern alternatives
    PATTERN_ALTERNATIVES = {
        "horizontal_push": ["Push-Up", "Dumbbell Fly", "Cable Fly"],
        "horizontal_pull": ["Cable Row", "Band Pull-Apart", "Inverted Row"],
        "vertical_push": ["Pike Push-Up", "Handstand Push-Up", "Arnold Press"],
        "vertical_pull": ["Pull-Up", "Lat Pulldown", "High Pull"],
    }

    # Movement to muscle group mapping
    MOVEMENT_TO_MUSCLES = {
        "Face Pull": ["rear_delts", "upper_back"],
        "Lateral Raise": ["side_delts"],
        "Bicep Curl": ["biceps"],
        "Tricep Extension": ["triceps"],
        "Leg Extension": ["quadriceps"],
        "Leg Curl": ["hamstrings"],
        "Calf Raise": ["calves"],
        "Push-Up": ["chest", "front_delts", "triceps"],
        "Pull-Up": ["lats", "biceps"],
        "Barbell Row": ["lats", "upper_back", "rear_delts"],
        "Barbell Bench Press": ["chest", "front_delts", "triceps"],
    }

    # Movement to pattern mapping
    MOVEMENT_TO_PATTERN = {
        "Face Pull": "horizontal_pull",
        "Barbell Row": "horizontal_pull",
        "Push-Up": "horizontal_push",
        "Barbell Bench Press": "horizontal_push",
        "Pull-Up": "vertical_pull",
        "Overhead Press": "vertical_push",
    }

    @staticmethod
    def remove_intra_session_duplicates(
        content: dict[str, Any], session_type: SessionType
    ) -> dict[str, Any]:
        """
        Remove duplicate movements within a single session across all sections.
        Intelligently replaces removed exercises to preserve muscle group coverage.

        Priority order: main > accessory > finisher > warmup > cooldown
        If a movement appears in multiple sections, keep it in highest priority section
        and replace it in lower priority sections with similar muscle group exercises.

        Args:
            content: Session content dict
            session_type: Type of session

        Returns:
            Session content with duplicates removed and intelligent replacements
        """
        used_movements = set()
        removed_exercises = []

        sections_priority = [
            ("main", content.get("main", [])),
            ("accessory", content.get("accessory", [])),
            ("finisher", DuplicateRemover._extract_finisher_exercises(content.get("finisher"))),
            ("warmup", content.get("warmup", [])),
            ("cooldown", content.get("cooldown", [])),
        ]

        for section_name, exercises in sections_priority:
            if not exercises:
                continue

            filtered_exercises = []
            for exercise in exercises:
                movement_name = exercise.get("movement", "").strip()
                if movement_name and movement_name not in used_movements:
                    filtered_exercises.append(exercise)
                    used_movements.add(movement_name)
                elif movement_name in used_movements:
                    logger.warning(
                        f"Removed duplicate movement '{movement_name}' from {section_name} section "
                        f"(already exists in higher priority section)"
                    )
                    removed_exercises.append({
                        "section": section_name,
                        "exercise": exercise,
                        "original_movement": movement_name
                    })

            if section_name == "finisher":
                if content.get("finisher"):
                    if filtered_exercises:
                        content["finisher"]["exercises"] = filtered_exercises
                    else:
                        content["finisher"]["exercises"] = []
            else:
                content[section_name] = filtered_exercises

        if removed_exercises:
            content = DuplicateRemover._replace_removed_exercises(
                content, removed_exercises, used_movements, session_type
            )

        if content.get("finisher") and not content["finisher"].get("exercises"):
            content["finisher"] = None

        if not content.get("main"):
            logger.error(f"All main exercises were duplicates! Adding fallback for {session_type}")

        return content

    @staticmethod
    def _extract_finisher_exercises(finisher_data: Any) -> list[dict]:
        """Extract exercises list from finisher structure."""
        if finisher_data and isinstance(finisher_data, dict):
            return finisher_data.get("exercises", [])
        return []

    @staticmethod
    def _replace_removed_exercises(
        content: dict[str, Any],
        removed_exercises: list[dict],
        used_movements: set[str],
        session_type: SessionType,
    ) -> dict[str, Any]:
        """
        Intelligently replace removed duplicate exercises to preserve muscle group coverage.

        Replacement hierarchy:
        1. Same primary muscle, different movement
        2. Same secondary muscle, different movement
        3. Same movement pattern, different movement
        4. Complementary muscle (antagonist)
        5. Skip if no suitable replacement found
        """
        for removed_info in removed_exercises:
            section_name = removed_info["section"]
            original_exercise = removed_info["exercise"]
            original_movement = removed_info["original_movement"]

            if section_name == "finisher" and not content.get("finisher"):
                continue

            replacement_movement = DuplicateRemover._find_replacement_movement(
                original_movement, used_movements
            )

            if replacement_movement:
                replacement_exercise = DuplicateRemover._create_replacement_exercise(
                    original_exercise, replacement_movement, section_name
                )

                if section_name == "finisher":
                    if content.get("finisher"):
                        if "exercises" not in content["finisher"]:
                            content["finisher"]["exercises"] = []
                        content["finisher"]["exercises"].append(replacement_exercise)
                else:
                    if section_name not in content:
                        content[section_name] = []
                    content[section_name].append(replacement_exercise)

                used_movements.add(replacement_movement)

                logger.info(
                    f"Replaced removed '{original_movement}' in {section_name} section "
                    f"with '{replacement_movement}' to preserve muscle group coverage"
                )
            else:
                logger.warning(
                    f"Could not find suitable replacement for '{original_movement}' "
                    f"in {section_name} section - muscle group coverage may be reduced"
                )

        return content

    @staticmethod
    def _find_replacement_movement(
        original_movement: str,
        used_movements: set[str],
    ) -> str | None:
        """Find best replacement movement using hierarchy of muscle/pattern matching."""
        original_muscles = DuplicateRemover.MOVEMENT_TO_MUSCLES.get(original_movement, [])

        for muscle in original_muscles:
            if muscle in DuplicateRemover.MUSCLE_ALTERNATIVES:
                for alternative in DuplicateRemover.MUSCLE_ALTERNATIVES[muscle]:
                    if alternative not in used_movements and alternative != original_movement:
                        return alternative

        if not original_muscles:
            original_pattern = DuplicateRemover.MOVEMENT_TO_PATTERN.get(original_movement)
            if original_pattern and original_pattern in DuplicateRemover.PATTERN_ALTERNATIVES:
                for alternative in DuplicateRemover.PATTERN_ALTERNATIVES[original_pattern]:
                    if alternative not in used_movements and alternative != original_movement:
                        return alternative

        return None

    @staticmethod
    def _create_replacement_exercise(
        original_exercise: dict,
        replacement_movement: str,
        section_name: str,
    ) -> dict:
        """Create a replacement exercise with appropriate parameters for section."""
        replacement = {
            "movement": replacement_movement,
            "notes": "Replacement for duplicate exercise"
        }

        if section_name in ["main"]:
            replacement.update({
                "sets": original_exercise.get("sets", 4),
                "rep_range_min": original_exercise.get("rep_range_min", 6),
                "rep_range_max": original_exercise.get("rep_range_max", 8),
                "target_rpe": original_exercise.get("target_rpe", 7.5),
                "rest_seconds": original_exercise.get("rest_seconds", 120),
            })
        elif section_name in ["accessory"]:
            replacement.update({
                "sets": original_exercise.get("sets", 3),
                "rep_range_min": original_exercise.get("rep_range_min", 8),
                "rep_range_max": original_exercise.get("rep_range_max", 12),
                "target_rpe": original_exercise.get("target_rpe", 7),
                "rest_seconds": original_exercise.get("rest_seconds", 60),
            })
        elif section_name in ["finisher"]:
            replacement.update({
                "sets": original_exercise.get("sets", 2),
                "rep_range_min": original_exercise.get("rep_range_min", 10),
                "rep_range_max": original_exercise.get("rep_range_max", 15),
                "target_rpe": original_exercise.get("target_rpe", 8),
                "rest_seconds": original_exercise.get("rest_seconds", 45),
            })
        elif section_name in ["warmup"]:
            replacement.update({
                "sets": original_exercise.get("sets", 1),
                "rep_range_min": original_exercise.get("rep_range_min", 10),
                "rep_range_max": original_exercise.get("rep_range_max", 12),
                "target_rpe": original_exercise.get("target_rpe", 5),
                "rest_seconds": original_exercise.get("rest_seconds", 30),
            })
        elif section_name in ["cooldown"]:
            replacement.update({
                "duration_seconds": original_exercise.get("duration_seconds", 60),
                "rest_seconds": 0,
            })

        return replacement

    @staticmethod
    def remove_cross_session_accessory_duplicates(
        content: dict[str, Any],
        previous_accessories: set[str],
        session_type: SessionType,
    ) -> dict[str, Any]:
        """
        Remove accessory/finisher exercises that were used in previous sessions.

        Args:
            content: Current session content
            previous_accessories: Set of accessory/finisher movements used previously
            session_type: Type of session

        Returns:
            Updated content with duplicates removed
        """
        used_movements_session: set[str] = set()

        for section_name in ["main", "accessory", "warmup", "cooldown"]:
            for ex in content.get(section_name) or []:
                name = (ex.get("movement") or "").strip()
                if name:
                    used_movements_session.add(name)

        finisher_struct = content.get("finisher")
        finisher_exercises = []
        if finisher_struct and isinstance(finisher_struct, dict):
            for ex in finisher_struct.get("exercises") or []:
                name = (ex.get("movement") or "").strip()
                if name:
                    used_movements_session.add(name)
                    finisher_exercises.append(ex)

        used_movements_session.update(previous_accessories)

        removed_exercises: list[dict] = []
        new_accessories: list[dict] = []

        for ex in content.get("accessory") or []:
            movement_name = (ex.get("movement") or "").strip()
            if movement_name and movement_name in previous_accessories:
                removed_exercises.append({
                    "section": "accessory",
                    "exercise": ex,
                    "original_movement": movement_name,
                })
            else:
                new_accessories.append(ex)

        content["accessory"] = new_accessories

        new_finisher_exercises: list[dict] = []
        for ex in finisher_exercises:
            movement_name = (ex.get("movement") or "").strip()
            if movement_name and movement_name in previous_accessories:
                removed_exercises.append({
                    "section": "finisher",
                    "exercise": ex,
                    "original_movement": movement_name,
                })
            else:
                new_finisher_exercises.append(ex)

        if finisher_struct and isinstance(finisher_struct, dict):
            finisher_struct["exercises"] = new_finisher_exercises
            content["finisher"] = finisher_struct

        if removed_exercises:
            content = DuplicateRemover._replace_removed_exercises(
                content, removed_exercises, used_movements_session, session_type
            )

        return content
