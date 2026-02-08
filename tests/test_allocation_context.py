import pytest
from app.services.allocation_context import AllocationResult, SessionIntent

class TestAllocationResultValidation:
    @pytest.fixture
    def allocation_result(self):
        """Create a basic AllocationResult with intents for different types."""
        intents = {
            1: SessionIntent(session_id=1, session_type="finisher"),
            2: SessionIntent(session_id=2, session_type="accessory"),
            3: SessionIntent(session_id=3, session_type="cardio_day"),
        }
        return AllocationResult(
            microcycle_id=1,
            session_intents=intents,
            targets={}
        )

    def test_valid_finisher_session(self, allocation_result):
        """Test valid finisher session (has finisher, no accessory)."""
        content = {
            "finisher": {"some": "data"},
            "main": [{"movement": "squat"}]
        }
        assert allocation_result.validate_session_content(1, content) is True

    def test_valid_accessory_session(self, allocation_result):
        """Test valid accessory session (has accessory, no finisher)."""
        content = {
            "accessory": {"some": "data"},
            "main": [{"movement": "bench"}]
        }
        assert allocation_result.validate_session_content(2, content) is True

    def test_valid_cardio_session(self, allocation_result):
        """Test valid cardio session (has cardio in main, no finisher/accessory)."""
        content = {
            "main": [{"movement": "Zone 2 Cardio"}],
            "warmup": []
        }
        assert allocation_result.validate_session_content(3, content) is True

    def test_finisher_session_with_accessory_fails(self, allocation_result):
        """Test failure when finisher session has accessory."""
        content = {
            "finisher": {"some": "data"},
            "accessory": {"some": "data"},
            "main": [{"movement": "squat"}]
        }
        assert allocation_result.validate_session_content(1, content) is False

    def test_accessory_session_with_finisher_fails(self, allocation_result):
        """Test failure when accessory session has finisher."""
        content = {
            "accessory": {"some": "data"},
            "finisher": {"some": "data"},
            "main": [{"movement": "bench"}]
        }
        assert allocation_result.validate_session_content(2, content) is False

    def test_cardio_session_with_extras_fails(self, allocation_result):
        """Test failure when cardio session has finisher or accessory."""
        # Case 1: Cardio + Finisher
        content_with_finisher = {
            "main": [{"movement": "Cardio"}],
            "finisher": {"some": "data"}
        }
        assert allocation_result.validate_session_content(3, content_with_finisher) is False

        # Case 2: Cardio + Accessory
        content_with_accessory = {
            "main": [{"movement": "Cardio"}],
            "accessory": {"some": "data"}
        }
        assert allocation_result.validate_session_content(3, content_with_accessory) is False

    def test_empty_content_fails(self, allocation_result):
        """Test failure with empty content."""
        content = {}
        # Should fail for all types as they require specific content
        assert allocation_result.validate_session_content(1, content) is False
        assert allocation_result.validate_session_content(2, content) is False
        assert allocation_result.validate_session_content(3, content) is False

    def test_cardio_detection_logic(self, allocation_result):
        """Test specific logic for cardio block detection in main."""
        # Valid: "cardio" in value (List format)
        assert allocation_result.validate_session_content(3, {
            "main": [{"movement": "Steady state cardio"}]
        }) is True
        
        # Valid: "conditioning" in value (List format)
        assert allocation_result.validate_session_content(3, {
            "main": [{"movement": "Metabolic conditioning"}]
        }) is True
        
        # Valid: Legacy Dict format support
        assert allocation_result.validate_session_content(3, {
            "main": {"b1": "Steady state cardio"}
        }) is True
        
        # Invalid: No cardio keyword
        assert allocation_result.validate_session_content(3, {
            "main": [{"movement": "Heavy Squats"}]
        }) is False
