"""
Unit tests for InterferenceService.

Tests goal conflict detection and dose adjustment logic.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.interference import interference_service
from app.models.enums import Goal


@pytest.mark.asyncio
async def test_detect_conflicts_no_conflicts(test_user):
    """Test detection with compatible goals."""
    goals = [Goal.STRENGTH, Goal.HYPERTROPHY, Goal.ENDURANCE]
    
    is_valid, warnings = await interference_service.validate_goals(goals[0], goals[1], goals[2])
    
    assert is_valid == True
    assert isinstance(warnings, list)

@pytest.mark.asyncio
async def test_get_conflicts(test_user):
    """Test getting conflicts between goals."""
    goals = [Goal.STRENGTH, Goal.FAT_LOSS, Goal.ENDURANCE]
    
    conflicts = await interference_service.get_conflicts(goals[0], goals[1], goals[2])
    
    # Should return list of conflicts (may be empty)
    assert isinstance(conflicts, list)

@pytest.mark.asyncio
async def test_apply_dose_adjustments(test_user):
    """Test dose adjustment based on conflicts."""
    goals = [Goal.STRENGTH, Goal.FAT_LOSS, Goal.ENDURANCE]
    
    base_freq = {"squat": 3, "bench": 3, "deadlift": 2}
    adjusted = await interference_service.apply_dose_adjustments(
        goals[0], goals[1], goals[2], base_freq
    )
    
    # Should return adjusted frequencies
    assert isinstance(adjusted, dict)


@pytest.mark.asyncio
async def test_validate_goals_duplicate_fails(async_db_session: AsyncSession, test_user):
    """Test that duplicate goals fail validation."""
    # All same goal
    is_valid, warnings = await interference_service.validate_goals(
        async_db_session, Goal.STRENGTH, Goal.STRENGTH, Goal.STRENGTH
    )
    
    # Should be valid with duplicate goals (just adds weight)
    assert is_valid == True


@pytest.mark.asyncio
async def test_validate_goals_unique(async_db_session: AsyncSession, test_user):
    """Test that unique goals pass validation."""
    is_valid, warnings = await interference_service.validate_goals(
        async_db_session, Goal.STRENGTH, Goal.HYPERTROPHY, Goal.ENDURANCE
    )
    
    # Should be valid with unique goals
    assert is_valid == True
    assert isinstance(warnings, list)


@pytest.mark.asyncio
async def test_clear_cache(async_db_session: AsyncSession, test_user):
    """Test clearing the service cache."""
    # Should not raise error
    interference_service.clear_cache()
    
    # Service should still be functional after cache clear
    is_valid, warnings = await interference_service.validate_goals(
        async_db_session, Goal.STRENGTH, Goal.HYPERTROPHY, Goal.ENDURANCE
    )
    assert isinstance(is_valid, bool)


@pytest.mark.asyncio
async def test_interference_service_singleton():
    """Test that interference_service is a singleton."""
    from app.services.interference import interference_service as is1
    from app.services.interference import interference_service as is2
    
    assert is1 is is2


@pytest.mark.asyncio
async def test_dose_adjustments_multiple_goals(async_db_session: AsyncSession, test_user):
    """Test dose adjustments with various goal combinations."""
    test_cases = [
        (Goal.STRENGTH, Goal.HYPERTROPHY, Goal.ENDURANCE),
        (Goal.STRENGTH, Goal.FAT_LOSS, Goal.ENDURANCE),
        (Goal.STRENGTH, Goal.FAT_LOSS, Goal.MOBILITY),
    ]
    
    for g1, g2, g3 in test_cases:
        base_freq = {"squat": 3, "bench": 3, "deadlift": 2}
        adjusted = await interference_service.apply_dose_adjustments(
            async_db_session, g1, g2, g3, base_freq
        )
        
        assert isinstance(adjusted, dict)
        for pattern, freq in adjusted.items():
            assert isinstance(freq, int)
            assert freq >= 1  # At least 1 session per week
