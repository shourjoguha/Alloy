import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.session_generator import SessionGeneratorService
from app.models.enums import SessionType

class TestSessionGeneratorRegression:
    
    @pytest.fixture
    def service(self):
        # SessionGeneratorService __init__ takes no arguments
        service = SessionGeneratorService()
        
        # Mock any other attributes if needed, e.g., optimizer
        service.optimizer = Mock()
        
        return service

    @pytest.mark.asyncio
    async def test_normalize_calls_validate(self, service):
        """
        Verify that _normalize_session_content correctly calls _validate_allocation_compliance.
        """
        # Setup
        content = {
            "warmup": [],
            "main": [],
            "cooldown": [],
            "finisher": [{"name": "burpees"}] 
        }
        session_type = SessionType.FULL_BODY
        intent_tags = ["prefer_finisher"]
        goal_weights = {"strength": 10}
        
        # Mock internal methods to isolate _normalize_session_content logic
        service._validate_and_complete_session = Mock(return_value=content)
        service._validate_mutual_exclusivity = Mock(return_value=content)
        service._validate_allocation_compliance = Mock(return_value=content)
        
        # Act
        await service._normalize_session_content(
            content=content,
            session_type=session_type,
            intent_tags=intent_tags,
            goal_weights=goal_weights
        )
        
        # Assert
        service._validate_allocation_compliance.assert_called_once()
        
        # Check arguments - note that intent_tags is converted to set inside normalize
        call_args = service._validate_allocation_compliance.call_args
        assert call_args[0][0] == content
        assert set(call_args[0][1]) == set(intent_tags)

    @pytest.mark.asyncio
    async def test_valid_session_passes_normalization(self, service):
        """
        Verify that a valid session (compliant with allocation) passes normalization.
        """
        # Setup - Valid case: prefer_finisher with finisher present
        content = {
            "warmup": [],
            "main": [],
            "cooldown": [],
            "finisher": [{"name": "burpees"}],
            "accessory": None
        }
        session_type = SessionType.FULL_BODY
        intent_tags = ["prefer_finisher"]
        goal_weights = {"strength": 10}
        
        # Mock validation to return content (pass through) or use real method?
        # The prompt asks to verify normalization passes, implying we should run the real logic if possible,
        # but _normalize_session_content calls _validate_allocation_compliance. 
        # If we mock _validate_allocation_compliance, we aren't testing that it *passes* the real validation.
        # So we should NOT mock _validate_allocation_compliance for this test, but mock other dependencies.
        
        service._validate_and_complete_session = Mock(return_value=content)
        service._validate_mutual_exclusivity = Mock(return_value=content)
        # We do NOT mock _validate_allocation_compliance to ensure it actually passes
        
        # Act
        result = await service._normalize_session_content(
            content=content,
            session_type=session_type,
            intent_tags=intent_tags,
            goal_weights=goal_weights
        )
        
        # Assert
        assert result == content

    @pytest.mark.asyncio
    async def test_invalid_session_raises_error(self, service):
        """
        Verify that an invalid session (violating allocation) raises ValueError with correct error code.
        """
        # Setup - Invalid case: prefer_finisher but has accessory instead
        content = {
            "warmup": [],
            "main": [],
            "cooldown": [],
            "finisher": None,
            "accessory": [{"name": "curls"}]
        }
        session_type = SessionType.FULL_BODY
        intent_tags = ["prefer_finisher"]
        goal_weights = {"strength": 10}
        
        service._validate_and_complete_session = Mock(return_value=content)
        service._validate_mutual_exclusivity = Mock(return_value=content)
        
        # Act & Assert
        with pytest.raises(ValueError) as excinfo:
            await service._normalize_session_content(
                content=content,
                session_type=session_type,
                intent_tags=intent_tags,
                goal_weights=goal_weights
            )
        
        # Check for specific error code mentioned in the code reading [ALLOCATION_VIOLATION_004]
        assert "[ALLOCATION_VIOLATION_004]" in str(excinfo.value)

    def test_prefer_finisher_logic(self, service):
        """
        Verify _prefer_finisher logic correctly handles the new tag system.
        """
        goal_weights = {"strength": 10}
        
        # Case 1: prefer_finisher tag present
        tags_finisher = {"prefer_finisher", "other_tag"}
        assert service._prefer_finisher(goal_weights, tags_finisher) is True
        
        # Case 2: prefer_accessory tag present
        tags_accessory = {"prefer_accessory", "other_tag"}
        assert service._prefer_finisher(goal_weights, tags_accessory) is False
        
        # Case 3: No valid tag present -> Should raise ValueError
        tags_none = {"other_tag"}
        with pytest.raises(ValueError) as excinfo:
            service._prefer_finisher(goal_weights, tags_none)
        
        assert "No allocation tags present" in str(excinfo.value)
