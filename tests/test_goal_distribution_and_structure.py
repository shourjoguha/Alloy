import pytest

from app.models.enums import SessionType, Goal
from app.schemas.program import GoalWeight
from app.services.program import ProgramService
from app.services.session_generator import SessionGeneratorService


@pytest.mark.asyncio
async def test_build_goal_finisher_uses_config():
    svc = SessionGeneratorService()
    finisher = await svc._build_goal_finisher({"fat_loss": 6, "endurance": 0, "strength": 0, "hypertrophy": 4, "mobility": 0})
    assert finisher is not None
    assert finisher.get("type") == "circuit"

    finisher2 = await svc._build_goal_finisher({"fat_loss": 0, "endurance": 6, "strength": 4, "hypertrophy": 0, "mobility": 0})
    assert finisher2 is not None
    assert finisher2.get("type") == "circuit"
    assert finisher2.get("circuit_type") == "EMOM"


@pytest.mark.asyncio
async def test_normalize_session_enforces_accessory_xor_finisher():
    svc = SessionGeneratorService()
    content = {
        "warmup": [{"movement": "Warmup", "duration_seconds": 60}],
        "main": [{"movement": "Bench Press", "sets": 3}],
        "accessory": [{"movement": "Curl", "sets": 3}],
        "finisher": {"type": "circuit", "duration_minutes": 8, "exercises": [{"movement": "Burpee", "reps": 10}]},
        "cooldown": [{"movement": "Cooldown", "duration_seconds": 60}],
    }
    normalized = await svc._normalize_session_content(content, SessionType.UPPER, ["prefer_accessory"], {"strength": 6, "hypertrophy": 4, "fat_loss": 0, "endurance": 0, "mobility": 0})
    assert normalized.get("accessory")
    assert normalized.get("finisher") is None

    normalized2 = await svc._normalize_session_content(content, SessionType.UPPER, ["prefer_finisher"], {"strength": 0, "hypertrophy": 0, "fat_loss": 6, "endurance": 4, "mobility": 0})
    assert normalized2.get("finisher") is not None
    assert normalized2.get("accessory") is None


@pytest.mark.asyncio
async def test_normalize_session_converts_accessory_to_finisher_when_preferred():
    svc = SessionGeneratorService()
    content = {
        "warmup": [{"movement": "Warmup", "duration_seconds": 60}],
        "main": [{"movement": "Bench Press", "sets": 3}],
        "accessory": [{"movement": "Curl", "sets": 3}],
        "finisher": None,
        "cooldown": [{"movement": "Cooldown", "duration_seconds": 60}],
    }
    normalized = await svc._normalize_session_content(
        content,
        SessionType.UPPER,
        ["prefer_finisher"],
        {"strength": 0, "hypertrophy": 4, "fat_loss": 0, "endurance": 6, "mobility": 0},
    )
    assert normalized.get("finisher") is not None
    assert normalized.get("accessory") is None


@pytest.mark.asyncio
async def test_conditioning_only_session_has_no_accessory_or_finisher():
    svc = SessionGeneratorService()
    content = {
        "warmup": [{"movement": "Warmup", "duration_seconds": 60}],
        "main": [{"movement": "Sled Push", "duration_seconds": 120}],
        "accessory": [{"movement": "Curl", "sets": 3}],
        "finisher": {"type": "circuit", "duration_minutes": 8, "exercises": [{"movement": "Burpee", "reps": 10}]},
        "cooldown": [{"movement": "Cooldown", "duration_seconds": 60}],
    }
    normalized = await svc._normalize_session_content(content, SessionType.CUSTOM, ["conditioning"], {"fat_loss": 6, "endurance": 0, "strength": 4, "hypertrophy": 0, "mobility": 0})
    assert normalized.get("accessory") is None
    assert normalized.get("finisher") is None


def test_goal_based_weekly_distribution_tags_days():
    svc = ProgramService()
    split_config = {
        "days_per_cycle": 7,
        "structure": [
            {"day": 1, "type": "upper", "focus": ["horizontal_push"]},
            {"day": 2, "type": "rest"},
            {"day": 3, "type": "lower", "focus": ["squat"]},
            {"day": 4, "type": "rest"},
            {"day": 5, "type": "upper", "focus": ["vertical_push"]},
            {"day": 6, "type": "lower", "focus": ["hinge"]},
            {"day": 7, "type": "rest"},
        ],
        "training_days": 4,
        "rest_days": 3,
    }
    goals = [
        GoalWeight(goal=Goal.FAT_LOSS, weight=6),
        GoalWeight(goal=Goal.STRENGTH, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=7,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={"allow_cardio_only_days": False, "allow_conditioning_only_days": False},
    )
    focus_tags = []
    for d in out["structure"]:
        if d.get("type") in {"upper", "lower", "push", "pull", "legs", "full_body"}:
            focus = d.get("focus") or []
            if isinstance(focus, list):
                focus_tags.extend(focus)
    assert ("prefer_finisher" in focus_tags) or ("prefer_accessory" in focus_tags)


@pytest.mark.parametrize("cardio_preference", ["dedicated_day", "mixed"])
def test_dedicated_day_or_mixed_adds_cardio_day(cardio_preference):
    """Test that cardio_preference='dedicated_day' or 'mixed' adds cardio days."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=7, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=6),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=7,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={"cardio_preference": cardio_preference},
    )
    assert any((d.get("type") == "cardio") for d in out["structure"])


def test_finisher_preference_does_not_create_cardio_days():
    """Test that cardio_preference='finisher' does not create dedicated cardio days."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=7, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=6),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=7,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={"cardio_preference": "finisher"},
    )
    # finisher preference should not create dedicated cardio days
    assert not any((d.get("type") == "cardio") for d in out["structure"])


def test_cardio_preference_none_excludes_all_cardio():
    """Test that cardio_preference='none' excludes all cardio days regardless of endurance goals."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=7, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=6),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=7,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={
            "cardio_preference": "none",
        },
    )
    assert not any((d.get("type") == "cardio") for d in out["structure"])


def test_dedicated_day_auto_chooses_conditioning_when_fat_loss_dominant():
    """Test that endurance_type='auto' prefers conditioning when fat_loss is dominant."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=10, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.FAT_LOSS, weight=6),
        GoalWeight(goal=Goal.ENDURANCE, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=10,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={
            "cardio_preference": "dedicated_day",
            "endurance_type": "auto",
        },
    )
    assert any((d.get("type") == "conditioning") for d in out["structure"])
    assert not any((d.get("type") == "cardio") for d in out["structure"])


def test_dedicated_day_auto_chooses_cardio_when_endurance_dominant():
    """Test that endurance_type='auto' prefers cardio when endurance is dominant."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=10, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=6),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=10,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={
            "cardio_preference": "dedicated_day",
            "endurance_type": "auto",
        },
    )
    assert any((d.get("type") == "cardio") for d in out["structure"])


def test_avoid_cardio_days_uses_conditioning_for_endurance_heavy_force():
    """Test that avoid_cardio_days forces conditioning instead of cardio for endurance-heavy programs."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=7, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=6),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=7,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={
            "cardio_preference": "finisher",
            "avoid_cardio_days": True,
        },
    )
    assert any((d.get("type") == "conditioning") for d in out["structure"])


# Note: test_jerome_notes_are_trimmed removed - _generate_jerome_notes function was moved
# to batched microcycle-level generation in program.py (_generate_microcycle_jerome_notes)


def test_endurance_only_creates_conditioning_sessions():
    """Test that endurance_type='endurance_only' creates conditioning sessions."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=7, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=6),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=7,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={"cardio_preference": "dedicated_day", "endurance_type": "endurance_only"},
    )
    assert any((d.get("type") == "conditioning") for d in out["structure"])
    assert not any((d.get("type") == "cardio") for d in out["structure"])


def test_cardio_only_creates_cardio_sessions():
    """Test that endurance_type='cardio_only' creates cardio sessions."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=7, days_per_week=4)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=4)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=6),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=4),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=4,
        cycle_length_days=7,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={"cardio_preference": "dedicated_day", "endurance_type": "cardio_only"},
    )
    assert any((d.get("type") == "cardio") for d in out["structure"])
    assert not any((d.get("type") == "conditioning") for d in out["structure"])


def test_endurance_dedicated_cardio_policy_never_respects_endurance_type():
    """Test that endurance_dedicated_cardio_day_policy='never' respects endurance_type choice when cardio_preference is mixed."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=14, days_per_week=5)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=5)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=8),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=2),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=5,
        cycle_length_days=14,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={
            "cardio_preference": "mixed",
            "endurance_type": "endurance_only",  # Only want conditioning
            "endurance_dedicated_cardio_day_policy": "never",
        },
    )
    # With 'never' policy and endurance_only, should only create conditioning days, not cardio days
    assert any((d.get("type") == "conditioning") for d in out["structure"])
    assert not any((d.get("type") == "cardio") for d in out["structure"])


def test_endurance_dedicated_cardio_policy_always_forces_cardio_day():
    """Test that endurance_dedicated_cardio_day_policy='always' forces a cardio day for endurance-heavy programs."""
    svc = ProgramService()
    split_config = svc._build_freeform_split_config(cycle_length_days=14, days_per_week=5)
    split_config = svc._assign_freeform_day_types_and_focus(split_config, days_per_week=5)
    goals = [
        GoalWeight(goal=Goal.ENDURANCE, weight=8),
        GoalWeight(goal=Goal.HYPERTROPHY, weight=2),
    ]
    out = svc._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=5,
        cycle_length_days=14,
        max_session_duration=60,
        user_experience_level="intermediate",
        scheduling_prefs={
            "cardio_preference": "dedicated_day",
            "endurance_type": "auto",
            "endurance_dedicated_cardio_day_policy": "always",
        },
    )
    # With 'always' policy, should force a cardio day for endurance-heavy programs
    assert any((d.get("type") == "cardio") for d in out["structure"])
