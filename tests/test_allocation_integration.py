import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any

from app.services.allocation_integration import AllocationIntegrationService
from app.services.allocation_context import (
    AllocationContext,
    AllocationResult,
    SessionIntent,
    UserSettings,
    GoalWeights,
)
from app.models.session_allocation import (
    CardioPreferenceMode,
    SessionTypePreferences,
    SessionTypeTargets,
    MicrocycleAllocation,
    GoalBucketWeights,
)

# Mock classes for Wizard Goals
@dataclass
class MockGoal:
    value: str

@dataclass
class MockWizardGoal:
    goal: MockGoal
    weight: int

@pytest.fixture
def service():
    return AllocationIntegrationService()

@pytest.fixture
def mock_wizard_goals():
    return [
        MockWizardGoal(goal=MockGoal(value="hypertrophy"), weight=6),
        MockWizardGoal(goal=MockGoal(value="fat_loss"), weight=4),
    ]

@pytest.fixture
def mock_context(mock_wizard_goals):
    return AllocationContext(
        user_settings=UserSettings(),
        goal_weights=[
            GoalWeights(weight=6, value="hypertrophy"),
            GoalWeights(weight=4, value="fat_loss"),
        ],
        preferences=SessionTypePreferences(
            cardio_preference=CardioPreferenceMode.FINISHER,
            max_finishers_per_week=3,
            max_cardio_days_per_week=2,
        ),
        microcycle_id=1,
    )

def test_create_allocation_context_merges_settings(service, mock_wizard_goals):
    """
    Test that create_allocation_context correctly merges wizard goals with user settings.
    """
    user_settings = {
        "max_finishers_per_week": 5,
        "cardio_preference": "dedicated_day",
    }
    
    # "fat_loss" in wizard goals should override cardio_preference to FINISHER
    # based on _merge_preferences logic
    
    context = service.create_allocation_context(
        user_settings=user_settings,
        wizard_goals=mock_wizard_goals,
        microcycle_id=101
    )
    
    assert context.microcycle_id == 101
    assert context.user_settings.max_finishers_per_week == 5
    # Logic in _merge_preferences: if any goal is fat_loss/endurance/cardio, pref becomes FINISHER
    assert context.preferences.cardio_preference == CardioPreferenceMode.FINISHER
    assert context.preferences.max_finishers_per_week == 5
    
    # Verify goal weights extraction
    assert len(context.goal_weights) == 2
    assert context.goal_weights[0].value == "hypertrophy"
    assert context.goal_weights[0].weight == 6

def test_allocate_session_types_distributes_correctly(service, mock_context):
    """
    Test that allocate_session_types correctly distributes sessions based on targets.
    """
    session_ids = [1, 2, 3, 4]
    session_types = ["strength", "strength", "strength", "strength"]
    
    # Mock Calculator and Distributor
    with patch("app.services.allocation_integration.SessionTypeCalculator") as MockCalc, \
         patch("app.services.allocation_integration.SessionTypeDistributor") as MockDist:
        
        # Setup mocks
        mock_calc_instance = MockCalc.return_value
        mock_dist_instance = MockDist.return_value
        
        mock_targets = SessionTypeTargets(
            target_accessory_count=2,
            target_finisher_count=2,
            target_cardio_day_count=0,
            total_sessions=4
        )
        mock_calc_instance.calculate_session_type_targets.return_value = mock_targets
        
        mock_allocation = MicrocycleAllocation(
            microcycle_id=mock_context.microcycle_id,
            targets=mock_targets,
            preferences=mock_context.preferences,
            assigned_session_types={
                1: "accessory",
                2: "finisher",
                3: "accessory",
                4: "finisher"
            }
        )
        mock_dist_instance.distribute_session_types.return_value = mock_allocation
        
        # Execute
        result = service.allocate_session_types(mock_context, session_ids, session_types)
        
        # Verify interactions
        MockCalc.assert_called_once()
        mock_calc_instance.calculate_session_type_targets.assert_called_once()
        
        MockDist.assert_called_once()
        mock_dist_instance.distribute_session_types.assert_called_once()
        
        # Verify result
        assert isinstance(result, AllocationResult)
        assert len(result.session_intents) == 4
        assert result.session_intents[1].session_type == "accessory"
        assert result.session_intents[2].session_type == "finisher"
        assert "prefer_accessory" in result.session_intents[1].auxiliary_tags
        assert "prefer_finisher" in result.session_intents[2].auxiliary_tags
        assert result.targets["accessory"] == 2
        assert result.targets["finisher"] == 2

def test_resolve_pattern_interference_swaps_conflicts(service):
    """
    Test that resolve_pattern_interference correctly identifies and swaps conflicting patterns.
    """
    # Setup initial result with a conflict
    # Day 1 has "squat", and previous day (Day 0) also had "squat"
    intent = SessionIntent(session_id=1, session_type="accessory")
    intent.add_movement_pattern("squat")
    
    result = AllocationResult(
        microcycle_id=1,
        session_intents={1: intent},
        targets={}
    )
    
    used_patterns = {
        0: ["squat"] # Conflict with day 1
    }
    
    pattern_alternatives = {
        "squat": ["lunge", "hinge"]
    }
    
    # Execute
    updated_result = service.resolve_pattern_interference(
        result, used_patterns, pattern_alternatives
    )
    
    # Verify
    updated_intent = updated_result.session_intents[1]
    assert "squat" not in updated_intent.movement_patterns
    assert "lunge" in updated_intent.movement_patterns # First valid alternative

def test_full_flow_end_to_end(service, mock_wizard_goals):
    """
    Test the full flow from context creation to result generation.
    """
    # 1. Create Context
    user_settings = {"cardio_preference": "finisher"}
    context = service.create_allocation_context(
        user_settings=user_settings,
        wizard_goals=mock_wizard_goals,
        microcycle_id=5
    )
    
    # 2. Allocate Session Types
    # We'll mock the internal calculator/distributor again for stability, 
    # effectively testing the integration glue code
    session_ids = [10, 11]
    session_types = ["strength", "strength"]
    
    with patch("app.services.allocation_integration.SessionTypeCalculator") as MockCalc, \
         patch("app.services.allocation_integration.SessionTypeDistributor") as MockDist:
             
        mock_targets = SessionTypeTargets(
            target_accessory_count=1,
            target_finisher_count=1,
            target_cardio_day_count=0,
            total_sessions=2
        )
        MockCalc.return_value.calculate_session_type_targets.return_value = mock_targets
        
        mock_allocation = MicrocycleAllocation(
            microcycle_id=5,
            targets=mock_targets,
            preferences=context.preferences,
            assigned_session_types={
                10: "accessory",
                11: "finisher"
            }
        )
        MockDist.return_value.distribute_session_types.return_value = mock_allocation
        
        allocation_result = service.allocate_session_types(
            context, session_ids, session_types
        )
    
    # 3. Apply Patterns (Simulate some patterns being added)
    session_patterns = {
        10: ["horizontal_push"],
        11: ["vertical_pull"]
    }
    allocation_result = service.apply_movement_patterns_to_intents(
        allocation_result, session_patterns
    )
    
    # 4. Resolve Interference
    # Assume day 9 had horizontal_push, so day 10 conflicts
    used_patterns = {9: ["horizontal_push"]}
    pattern_alternatives = {"horizontal_push": ["vertical_push"]}
    
    final_result = service.resolve_pattern_interference(
        allocation_result, used_patterns, pattern_alternatives
    )
    
    # Verification
    # Day 10 should have swapped horizontal_push -> vertical_push
    intent_10 = final_result.session_intents[10]
    assert "horizontal_push" not in intent_10.movement_patterns
    assert "vertical_push" in intent_10.movement_patterns
    assert intent_10.session_type == "accessory"
    
    # Day 11 should be unchanged
    intent_11 = final_result.session_intents[11]
    assert "vertical_pull" in intent_11.movement_patterns
    assert intent_11.session_type == "finisher"
