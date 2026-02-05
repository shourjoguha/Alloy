"""
LLM optimization utilities for faster session generation.

DEPRECATED: This module is legacy from when LLM directly generated sessions.
Session generation now uses the Optimization Engine (OR-Tools) via app/services/optimization.py.
The duration_targets below are deprecated and not used in the active codebase.
"""
import warnings
from typing import Dict, List, Any
from app.models.enums import SessionType, Goal


class LLMOptimizer:
    """
    DEPRECATED: Optimizes LLM calls through heuristics, caching, and structured metadata.

    This class is legacy from when LLM directly generated session content.
    The current architecture uses the Optimization Engine (OR-Tools) for session generation,
    which respects max_session_duration from the Program model.

    The build_guidance_context and get_guidance_structure methods are deprecated and not called
    in the active session generation flow.
    """

    # Cached heuristic rules to reduce LLM decision-making
    HEURISTIC_RULES = {
        "main_lift_counts": {
            SessionType.FULL_BODY: 2,  # Always 2 main lifts for full body
            SessionType.UPPER: 2,
            SessionType.LOWER: 2,
            SessionType.PUSH: 2,
            SessionType.PULL: 2,
            SessionType.LEGS: 2,
        },
        "accessory_counts": {
            SessionType.FULL_BODY: 4,  # Consistent accessory counts
            SessionType.UPPER: 4,
            SessionType.LOWER: 3,
            SessionType.PUSH: 3,
            SessionType.PULL: 3,
            SessionType.LEGS: 3,
        },
        # DEPRECATED: duration_targets are no longer used. Session duration is controlled by
        # Program.max_session_duration which flows through to OptimizationRequest.session_duration_minutes
        "duration_targets": {
            SessionType.FULL_BODY: 60,  # Target durations (DEPRECATED)
            SessionType.UPPER: 55,
            SessionType.LOWER: 50,
            SessionType.PUSH: 45,
            SessionType.PULL: 45,
            SessionType.LEGS: 50,
        }
    }
    
    # Pre-filtered movement selections by pattern (USER PREFERENCES OVERRIDE THESE)
    # These are fallback priorities when no user preferences exist
    FALLBACK_PRIORITY_MOVEMENTS = {
        "squat": ["Back Squat", "Front Squat", "Goblet Squat", "Bulgarian Split Squat"],
        "hinge": ["Romanian Deadlift", "Conventional Deadlift", "Good Morning", "Hip Thrust"],
        "lunge": ["Walking Lunge", "Reverse Lunge", "Bulgarian Split Squat", "Lateral Lunge"],
        "horizontal_push": ["Barbell Bench Press", "Dumbbell Bench Press", "Push-Up", "Incline Bench Press"],
        "vertical_push": ["Overhead Press", "Dumbbell Shoulder Press", "Pike Push-Up", "Arnold Press"],
        "horizontal_pull": ["Barbell Row", "Dumbbell Row", "Cable Row", "Inverted Row"],
        "vertical_pull": ["Pull-Up", "Lat Pulldown", "Chin-Up", "High Pull"],
    }
    
    # Goal-based accessory priorities (reduces LLM decision space)
    GOAL_ACCESSORIES = {
        Goal.STRENGTH: ["Close-Grip Bench Press", "Pause Squat", "Deficit Deadlift"],
        Goal.HYPERTROPHY: ["Lateral Raise", "Face Pull", "Leg Extension", "Leg Curl", "Bicep Curl", "Tricep Extension"],
        Goal.ENDURANCE: ["High Rep Push-Up", "Plank", "Mountain Climber", "Burpee"],
        Goal.FAT_LOSS: ["Kettlebell Swing", "Battle Rope", "Jump Squat", "High Knees"],
    }
    
    @classmethod
    def apply_user_movement_preferences(
        cls, 
        movements_by_pattern: Dict[str, List[str]], 
        movement_rules: Dict[str, List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Apply user movement preferences to movement lists.
        User preferences (must_include, prefer, avoid) override fallback priorities.
        
        Args:
            movements_by_pattern: Full movement library by pattern
            movement_rules: User preferences (avoid, must_include, prefer)
            
        Returns:
            Movement lists with user preferences applied (still shows all movements)
        """
        if not movement_rules:
            return movements_by_pattern
        
        # Get user preferences
        avoid_movements = set(movement_rules.get("avoid", []))
        must_include = set(movement_rules.get("must_include", []))
        prefer_movements = set(movement_rules.get("prefer", []))
        
        # Apply preferences to each pattern
        filtered_patterns = {}
        for pattern, movements in movements_by_pattern.items():
            # Remove avoided movements
            available_movements = [m for m in movements if m not in avoid_movements]
            
            # Prioritize preferred and must-include movements at the top
            priority_movements = []
            regular_movements = []
            
            for movement in available_movements:
                if movement in must_include or movement in prefer_movements:
                    priority_movements.append(movement)
                else:
                    regular_movements.append(movement)
            
            # Combine: priority movements first, then regular movements
            filtered_patterns[pattern] = priority_movements + regular_movements
        
        return filtered_patterns
    
    @classmethod
    def get_guidance_structure(
        cls,
        session_type: SessionType,
        goals: List[Goal],
        is_deload: bool,
        goal_weights: Dict[str, int] = None
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Generate guidance structure for LLM decision-making.

        This method is legacy from when LLM directly generated sessions.
        Session generation now uses Optimization Engine (OR-Tools) via app/services/optimization.py.
        """
        warnings.warn(
            "LLMOptimizer.get_guidance_structure() is deprecated and not used in active codebase. "
            "Session generation uses Optimization Engine (OR-Tools) which respects max_session_duration.",
            DeprecationWarning,
            stacklevel=2
        )
        main_count = cls.HEURISTIC_RULES["main_lift_counts"].get(session_type, 2)
        accessory_count = cls.HEURISTIC_RULES["accessory_counts"].get(session_type, 3)
        target_duration = cls.HEURISTIC_RULES["duration_targets"].get(session_type, 55)

        # Adjust for deload (guidance only)
        if is_deload:
            main_count = max(1, main_count - 1)
            accessory_count = max(2, accessory_count - 1)
            target_duration = int(target_duration * 0.8)

        # Default goal weights if not provided
        if not goal_weights:
            goal_weights = {
                'strength':1,
                'hypertrophy':1,
                'endurance':1,
                'fat_loss':1,
                'mobility':1
            }

        guidance = {
            "suggested_main_lifts": main_count,
            "suggested_accessories": accessory_count,
            "target_duration": target_duration,
            "finisher_guidance": "Consider finisher for fat_loss/endurance goals or crossfit disciplines",
            "superset_guidance": "Use supersets for hypertrophy goals to increase volume efficiency",
        }

        # Goal-specific guidance with weight-aware logic
        if goal_weights.get('hypertrophy', 0) >= 5:
            guidance["accessory_note"] = "Consider additional accessories for muscle growth"
        if goal_weights.get('strength', 0) >= 5:
            guidance["main_lift_note"] = "Focus on compound movements with progressive overload"

        # Endurance goal logic (weight >= 6 = high priority)
        if goal_weights.get('endurance', 0) >= 6:
            guidance["cardio_note"] = "Include cardio block (10-15min) for endurance - running, rowing, or cycling"
            guidance["high_rep_note"] = "Use higher rep ranges (15-20+) for endurance adaptation"
        elif goal_weights.get('endurance', 0) >= 4:
            guidance["conditioning_note"] = "Include finisher for metabolic conditioning"

        # Mobility goal logic (weight >= 5 = medium-high priority)
        if goal_weights.get('mobility', 0) >= 5:
            guidance["mobility_note"] = "Add dedicated mobility work (5-10min) to cooldown: stretching, foam rolling"
            guidance["dynamic_stretch_note"] = "Include dynamic stretching in warmup for mobility goals"
        elif goal_weights.get('mobility', 0) >= 3:
            guidance["mobility_light_note"] = "Consider adding brief mobility work to cooldown"

        # Fat loss goal logic
        if goal_weights.get('fat_loss', 0) >= 5:
            guidance["metabolic_note"] = "Include metabolic finisher or cardio block for fat loss"

        return guidance
    
    @classmethod
    def get_goal_specific_accessories(
        cls, 
        goals: List[Goal], 
        session_type: SessionType
    ) -> List[str]:
        """
        Pre-select accessories based on goals to reduce LLM decision-making.
        """
        primary_goal = goals[0] if goals else Goal.STRENGTH
        base_accessories = cls.GOAL_ACCESSORIES.get(primary_goal, [])
        
        # Session-type specific filtering
        if session_type in [SessionType.UPPER, SessionType.PUSH, SessionType.PULL]:
            # Filter to upper body accessories
            upper_accessories = [
                "Lateral Raise", "Face Pull", "Bicep Curl", "Tricep Extension", 
                "Close-Grip Bench Press", "Overhead Press"
            ]
            base_accessories = [a for a in base_accessories if a in upper_accessories]
        elif session_type in [SessionType.LOWER, SessionType.LEGS]:
            # Filter to lower body accessories
            lower_accessories = [
                "Leg Extension", "Leg Curl", "Calf Raise", "Hip Thrust", 
                "Pause Squat", "Deficit Deadlift"
            ]
            base_accessories = [a for a in base_accessories if a in lower_accessories]
        
        return base_accessories[:4]  # Max 4 suggestions
    
    @classmethod
    def build_guidance_context(
        cls,
        session_type: SessionType,
        goals: List[Goal],
        intent_tags: List[str],
        is_deload: bool,
        used_accessories: List[str] = None,
        goal_weights: Dict[str, int] = None,
    ) -> str:
        """
        DEPRECATED: Build guidance context (suggestions, not hard constraints) for LLM.

        This method is legacy from when LLM directly generated sessions.
        Session generation now uses Optimization Engine (OR-Tools) via app/services/optimization.py.
        """
        warnings.warn(
            "LLMOptimizer.build_guidance_context() is deprecated and not used in active codebase. "
            "Session generation uses Optimization Engine (OR-Tools) which respects max_session_duration.",
            DeprecationWarning,
            stacklevel=2
        )
        guidance = cls.get_guidance_structure(session_type, goals, is_deload, goal_weights)
        suggested_accessories = cls.get_goal_specific_accessories(goals, session_type)

        # Filter out used accessories from suggestions
        if used_accessories:
            suggested_accessories = [a for a in suggested_accessories if a not in used_accessories]

        guidance_text = f"""## Guidance & Suggestions (Use Your Judgment)
- Main lifts: ~{guidance['suggested_main_lifts']} exercises from patterns: {', '.join(intent_tags[:2])}
- Accessories: ~{guidance['suggested_accessories']} exercises, consider: {', '.join(suggested_accessories[:guidance['suggested_accessories']])}
- Target duration: ~{guidance['target_duration']} minutes (flexible based on needs)
- {guidance['finisher_guidance']}
- {guidance['superset_guidance']}"""

        # Add goal-specific notes
        for key, value in guidance.items():
            if key.endswith('_note'):
                guidance_text += f"\n- {value}"

        return guidance_text


class PromptCache:
    """
    Provides intelligent warmup/cooldown suggestions based on session patterns.
    """
    
    _cache: Dict[str, str] = {}
    
    @classmethod
    def get_pattern_based_warmup(cls, intent_tags: List[str], session_type: SessionType) -> List[Dict[str, Any]]:
        """
        Generate warmup based on patterns used in session.
        Prepares joints and muscles for specific movements.
        
        Provides flexibility while offering intelligent defaults.
        
        NOTE: Returns empty list - warmup generation is now handled by
        SessionGenerator._generate_warmup_cooldown() which selects real
        movements from the database.
        """
        return []
    
    @classmethod
    def get_cached_warmup(cls, session_type: SessionType) -> List[Dict[str, Any]]:
        """Return basic warmup for session type (fallback)."""
        return []
    
    @classmethod
    def get_pattern_based_cooldown(cls, intent_tags: List[str]) -> List[Dict[str, Any]]:
        """
        Generate cooldown based on patterns used in session.
        Targets muscles/areas that were trained.
        
        NOTE: Returns empty list - cooldown generation is now handled by
        SessionGenerator._generate_warmup_cooldown() which selects real
        movements from the database.
        """
        return []
    
    @classmethod
    def get_cached_cooldown(cls) -> List[Dict[str, Any]]:
        """Return standard cooldown (fallback)."""
        return []


class ModelOptimizer:
    """
    Optimizes model parameters for faster inference.
    """
    
    @classmethod
    def get_optimized_config(cls, session_complexity: str = "standard") -> Dict[str, Any]:
        """
        Return optimized model configuration based on session complexity.
        
        Temperature: Controls randomness (0.3=deterministic/fast, 0.7=creative/slower)
        Top-p: Nucleus sampling (0.8=top 80% tokens/fast, 0.95=more options/slower)
        Max tokens: Upper limit, but LLM can use less if sufficient
        """
        configs = {
            "simple": {
                "temperature": 0.3,  # More deterministic for simple sessions
                "max_tokens": 1200,  # Sufficient for basic sessions
                "top_p": 0.8,        # Focus on high-probability tokens
            },
            "standard": {
                "temperature": 0.5,  # Balanced creativity and speed
                "max_tokens": 1800,  # Room for detailed sessions
                "top_p": 0.9,        # Good balance of options
            },
            "complex": {
                "temperature": 0.7,  # More creativity for complex sessions
                "max_tokens": 2500,  # Full flexibility for complex needs
                "top_p": 0.95,       # Maximum token options
            }
        }
        return configs.get(session_complexity, configs["standard"])