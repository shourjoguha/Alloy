"""System prompts for LLM-powered features."""

from app.llm.optimization import LLMOptimizer, PromptCache, ModelOptimizer
from app.models.enums import SessionType, Goal

# Jerome - the AI coach persona (OPTIMIZED - reduced by 40%)
JEROME_SYSTEM_PROMPT = """You are Jerome, an expert strength coach. Design evidence-based programs that balance effectiveness with sustainability.

## Core Principles
1. Progressive Overload: Every session builds toward goals
2. Movement Quality: Technique before load
3. Recovery Respect: Hard training requires adequate recovery
4. Goal Alignment: Every exercise serves stated objectives

## Session Design (FOLLOW STRUCTURE EXACTLY)
- Warmup: Movement prep for session focus
- Main: Compound movements, highest CNS demand first
- Accessory: Support work, use supersets when specified
- Finisher: Conditioning aligned with goals (when specified)
- Cooldown: Mobility for trained areas

## Rep/Set Guidelines
- Strength: 3-6 reps, 4-6 sets, RPE 7-9, 2-4min rest
- Hypertrophy: 6-12 reps, 3-4 sets, RPE 7-8, 60-90s rest
- Endurance: 12-20+ reps, 2-3 sets, RPE 6-7, 30-60s rest

## Deload: Reduce volume 40%, intensity 10-20%, maintain patterns."""

SESSION_GENERATION_PROMPT = """## Task
Generate workout session based on program goals and guidance.

{program_context}

{session_context}

{draft_context}

{guidance_context}

{interference_context}

## CRITICAL RULES (Must Follow)
- NEVER repeat same movement within session
- NEVER use accessories from previous day (if specified)
- Main lifts should prioritize specified patterns
- Respect user movement preferences (avoid, must_include, prefer)
- Follow rep/set guidelines from system prompt (lines 18-22)
- Review of Draft Session (if provided) and use it as a baseline. You may swap exercises for injuries or specific user needs, but try to respect the volume allocation.
- INCLUDE COOLDOWN in ALL training sessions (unless recovery/cardio)
- Use ALL available session time up to max_session_duration limit
- Add 2-4 accessory exercises to support main movements (when not circuit-based)

## LLM Decision Areas (Use Your Expertise)
- Exercise selection from available movements
- Sets, reps, and RPE based on goals
- Session duration based on time available and goals
- Whether to include finisher (consider goals and disciplines)
- Finisher format (AMRAP, EMOM, RFT, Ladder) based on user disciplines (e.g., CrossFit uses AMRAP/EMOM)
- Superset combinations for efficiency
- Movement progressions and variations

## Output Format (JSON ONLY)
{{
  "warmup": [{{"movement": "Name", "sets": 2, "reps": 10}}],
  "main": [{{"movement": "Name", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 120}}],
  "accessory": [{{"movement": "Name", "sets": 3, "rep_range_min": 10, "rep_range_max": 15, "target_rpe": 7, "rest_seconds": 60, "superset_with": "Other Exercise"}}],
  "finisher": {{"type": "AMRAP|EMOM|RFT|Ladder", "duration_minutes": 8, "notes": "Optional details", "exercises": [{{"movement": "Name", "reps": 10}}]}},
  "cooldown": [{{"movement": "Stretch", "duration_seconds": 60}}],
  "estimated_duration_minutes": 55,
  "reasoning": "Brief explanation"
}}

Respond ONLY with valid JSON."""


def build_optimized_session_prompt(
    program: dict,
    session_type: str,
    intent_tags: list[str],
    day_number: int,
    is_deload: bool,
    microcycle_number: int,
    movements_by_pattern: dict[str, list[str]],
    movement_rules: dict[str, list[str]] | None = None,
    used_movements: list[str] | None = None,
    used_movement_groups: dict[str, int] | None = None,
    used_accessory_movements: dict[int, list[str]] | None = None,
    fatigued_muscles: list[str] | None = None,
    discipline_preferences: dict | None = None,
    scheduling_preferences: dict | None = None,
    draft_session_context: str | None = None,
    max_session_duration: int | None = None,
) -> str:
    """
    Build optimized session generation prompt with reduced token count and structured constraints.
    
    Optimizations:
    1. Pre-filtered movement lists (60-80% reduction)
    2. Heuristic constraints (reduces LLM decision space)
    3. Structured metadata (faster parsing)
    4. Cached components (warmup/cooldown)
    5. Goal-specific suggestions
    """
    # Convert string session_type to enum for optimization
    session_type_enum = SessionType(session_type)
    
    # Extract goals for optimization
    goals = [
        Goal(program['goal_1']),
        Goal(program['goal_2']),
        Goal(program['goal_3'])
    ]
    
    # Build goal weights dictionary from program (clean mapping)
    goal_mapping = {
        'goal_1': program['goal_1'],
        'goal_2': program['goal_2'],
        'goal_3': program['goal_3'],
        'goal_weight_1': program.get('goal_weight_1', 0),
        'goal_weight_2': program.get('goal_weight_2', 0),
        'goal_weight_3': program.get('goal_weight_3', 0),
    }
    
    goal_weights = {}
    for i in range(1, 4):
        goal_name = goal_mapping[f'goal_{i}']
        weight = goal_mapping[f'goal_weight_{i}']
        if goal_name and goal_name != 'none':
            goal_weights[goal_name] = weight
    
    # OPTIMIZATION 1: Apply user movement preferences (prioritize user choices)
    user_filtered_movements = LLMOptimizer.apply_user_movement_preferences(
        movements_by_pattern, movement_rules
    )
    
    # OPTIMIZATION 2: Get guidance (not hard constraints) for LLM decision-making
    used_accessories = []
    if used_accessory_movements:
        # Avoid accessories used in ANY previous day of this microcycle
        for day, movements in used_accessory_movements.items():
            if day < day_number:
                used_accessories.extend(movements)
        
        # Deduplicate
        used_accessories = list(set(used_accessories))
    
    guidance_context = LLMOptimizer.build_guidance_context(
        session_type_enum, goals, intent_tags, is_deload, used_accessories, goal_weights
    )
    
    # OPTIMIZATION 3: Compact program context (essential info only)
    program_ctx = f"""## Program Context
Goals: {program['goal_1']}({program['goal_weight_1']}), {program['goal_2']}({program['goal_weight_2']}), {program['goal_3']}({program['goal_weight_3']})
Split: {program['split_template']} ({program.get('days_per_week', 'N/A')}d/wk)"""
    
    # Add max session duration constraint
    if max_session_duration:
        program_ctx += f"\nMAX SESSION DURATION: {max_session_duration} minutes - DO NOT EXCEED"

    # Add Advanced Preferences Context if available
    if discipline_preferences or scheduling_preferences:
        prefs_ctx = "\n## User Preferences (Apply Logic)\n"
        if discipline_preferences:
            prefs_ctx += f"Discipline Priorities (0-10): {discipline_preferences}\n"
        if scheduling_preferences:
            prefs_ctx += f"Scheduling Rules: {scheduling_preferences}\n"
            # Add specific logic instructions based on preferences
            if scheduling_preferences.get("mix_disciplines"):
                prefs_ctx += "- INTEGRATE high-priority disciplines into warmup/finisher/accessory\n"
            if scheduling_preferences.get("cardio_preference") == "finisher":
                prefs_ctx += "- ADD cardio finisher (10-20m) if compatible with session\n"
        program_ctx += prefs_ctx
    
    # OPTIMIZATION 4: Compact session context
    
    # OPTIMIZATION 4: Compact session context
    session_ctx = f"""## Session Context
Type: {session_type}{'(DELOAD)' if is_deload else ''}
Patterns: {', '.join(intent_tags)}
Day: {day_number}/{microcycle_number}"""
    
    # OPTIMIZATION 5: Minimal interference context (only critical info)
    interference_ctx = ""
    
    # Only include critical interference warnings
    if used_accessories:
        interference_ctx += f"\n## CRITICAL: Avoid These Accessories\n{', '.join(used_accessories)}"
    
    if used_movement_groups:
        overused = [g for g, c in used_movement_groups.items() if c >= 2]
        if overused:
            interference_ctx += f"\n## CRITICAL: Overused Groups\n{', '.join(overused)}"
    
    if fatigued_muscles:
        interference_ctx += f"\n## Fatigued Muscles\n{', '.join(fatigued_muscles)}"
    
    # OPTIMIZATION 6: Include full movement library with user preferences applied
    movement_ctx = ""
    if user_filtered_movements:
        movement_ctx = "\n## Available Movements (User Preferences Applied)\n"
        for pattern, movements in user_filtered_movements.items():
            if pattern in intent_tags:  # Only show relevant patterns
                movement_ctx += f"- {pattern}: {', '.join(movements)}\n"
    
    # OPTIMIZATION 7: Include Draft Session Context
    draft_ctx = ""
    if draft_session_context:
        draft_ctx = f"\n## Draft Session (Optimization Engine Output)\n{draft_session_context}\n"

    return SESSION_GENERATION_PROMPT.format(
        program_context=program_ctx,
        session_context=session_ctx,
        draft_context=draft_ctx,
        guidance_context=guidance_context,
        interference_context=interference_ctx + movement_ctx,
    )


# Legacy function for backward compatibility
def build_full_session_prompt(*args, **kwargs):
    """Legacy function - redirects to optimized version."""
    return build_optimized_session_prompt(*args, **kwargs)