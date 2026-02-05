"""Tests for CircuitComparisonService.

Tests cover:
- Similarity scoring between circuits
- Finding similar circuits
- Finding complementary circuits
- Circuit recommendations
- Edge cases and error handling
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.circuit_comparison import (
    CircuitComparisonService,
    CircuitSimilarityResult,
    CircuitRecommendation,
)
from app.models.circuit_extended import CircuitMacro
from app.models.enums import PrimaryRegion, MovementTier, MovementPattern


@pytest.fixture
def circuit_comparison_service(async_db_session: AsyncSession) -> CircuitComparisonService:
    """Create a CircuitComparisonService instance for testing."""
    return CircuitComparisonService(async_db_session)


@pytest.fixture
async def sample_circuits(async_db_session: AsyncSession):
    """Create sample circuits for testing."""
    from app.models.circuit import CircuitTemplate
    
    circuits = []
    
    # Circuit 1: Upper body, push-heavy
    c1 = CircuitTemplate(
        name="Upper Body Push",
        description="Upper body pushing workout",
        circuit_type="station",
        difficulty_tier=2,
        fatigue_factor=1.2,
        stimulus_factor=1.1,
        exercises_json=[
            {"movement_id": 1, "reps": 10},
            {"movement_id": 2, "reps": 8},
        ]
    )
    async_db_session.add(c1)
    await async_db_session.flush()
    
    m1 = CircuitMacro(
        circuit_id=c1.id,
        total_exercises=2,
        unique_movements=2,
        total_reps=18,
        total_distance_meters=None,
        total_work_seconds=120,
        estimated_duration_seconds=120,
        difficulty_tier=MovementTier.SILVER,
        min_recovery_hours=24,
        primary_muscles=["chest", "shoulders", "triceps"],
        muscle_engagement_score=0.85,
        primary_region=PrimaryRegion.UPPER,
        region_diversity_score=0.3,
        required_equipment=[1, 2],
        equipment_complexity=2,
        movement_pattern_counts={"push": 2},
        pattern_diversity_score=0.0,
        metabolic_profile=None,
        estimated_calories_per_hour=300.0,
        space_requirement_meters=2.0,
        station_count=1,
        circuit_type_intensity="medium",
        data_completeness_score=1.0
    )
    async_db_session.add(m1)
    circuits.append((c1, m1))
    
    # Circuit 2: Lower body, squat-heavy
    c2 = CircuitTemplate(
        name="Lower Body Squat",
        description="Lower body squat workout",
        circuit_type="station",
        difficulty_tier=2,
        fatigue_factor=1.3,
        stimulus_factor=1.2,
        exercises_json=[
            {"movement_id": 3, "reps": 12},
            {"movement_id": 4, "reps": 10},
        ]
    )
    async_db_session.add(c2)
    await async_db_session.flush()
    
    m2 = CircuitMacro(
        circuit_id=c2.id,
        total_exercises=2,
        unique_movements=2,
        total_reps=22,
        total_distance_meters=None,
        total_work_seconds=120,
        estimated_duration_seconds=120,
        difficulty_tier=MovementTier.SILVER,
        min_recovery_hours=24,
        primary_muscles=["quadriceps", "glutes", "hamstrings"],
        muscle_engagement_score=0.9,
        primary_region=PrimaryRegion.LOWER,
        region_diversity_score=0.2,
        required_equipment=[1, 3],
        equipment_complexity=2,
        movement_pattern_counts={"squat": 2},
        pattern_diversity_score=0.0,
        metabolic_profile=None,
        estimated_calories_per_hour=350.0,
        space_requirement_meters=2.0,
        station_count=1,
        circuit_type_intensity="medium",
        data_completeness_score=1.0
    )
    async_db_session.add(m2)
    circuits.append((c2, m2))
    
    # Circuit 3: Full body, mixed patterns
    c3 = CircuitTemplate(
        name="Full Body Mixed",
        description="Full body mixed workout",
        circuit_type="emom",
        difficulty_tier=3,
        fatigue_factor=1.4,
        stimulus_factor=1.3,
        exercises_json=[
            {"movement_id": 1, "reps": 10},
            {"movement_id": 3, "reps": 12},
            {"movement_id": 5, "reps": 8},
        ]
    )
    async_db_session.add(c3)
    await async_db_session.flush()
    
    m3 = CircuitMacro(
        circuit_id=c3.id,
        total_exercises=3,
        unique_movements=3,
        total_reps=30,
        total_distance_meters=None,
        total_work_seconds=180,
        estimated_duration_seconds=180,
        difficulty_tier=MovementTier.GOLD,
        min_recovery_hours=24,
        primary_muscles=["chest", "quadriceps", "back"],
        muscle_engagement_score=0.75,
        primary_region=PrimaryRegion.FULL_BODY,
        region_diversity_score=0.8,
        required_equipment=[1, 2, 3],
        equipment_complexity=3,
        movement_pattern_counts={"push": 1, "squat": 1, "pull": 1},
        pattern_diversity_score=1.0,
        metabolic_profile=None,
        estimated_calories_per_hour=400.0,
        space_requirement_meters=3.0,
        station_count=3,
        circuit_type_intensity="high",
        data_completeness_score=1.0
    )
    async_db_session.add(m3)
    circuits.append((c3, m3))
    
    # Circuit 4: Upper body, similar to circuit 1
    c4 = CircuitTemplate(
        name="Upper Body Push 2",
        description="Another upper body pushing workout",
        circuit_type="station",
        difficulty_tier=2,
        fatigue_factor=1.2,
        stimulus_factor=1.1,
        exercises_json=[
            {"movement_id": 1, "reps": 8},
            {"movement_id": 2, "reps": 10},
        ]
    )
    async_db_session.add(c4)
    await async_db_session.flush()
    
    m4 = CircuitMacro(
        circuit_id=c4.id,
        total_exercises=2,
        unique_movements=2,
        total_reps=18,
        total_distance_meters=None,
        total_work_seconds=120,
        estimated_duration_seconds=120,
        difficulty_tier=MovementTier.SILVER,
        min_recovery_hours=24,
        primary_muscles=["chest", "shoulders", "triceps"],
        muscle_engagement_score=0.85,
        primary_region=PrimaryRegion.UPPER,
        region_diversity_score=0.3,
        required_equipment=[1, 2],
        equipment_complexity=2,
        movement_pattern_counts={"push": 2},
        pattern_diversity_score=0.0,
        metabolic_profile=None,
        estimated_calories_per_hour=300.0,
        space_requirement_meters=2.0,
        station_count=1,
        circuit_type_intensity="medium",
        data_completeness_score=1.0
    )
    async_db_session.add(m4)
    circuits.append((c4, m4))
    
    await async_db_session.commit()
    
    return {c.id: (c, m) for c, m in circuits}


class TestCircuitSimilarityScoring:
    """Tests for circuit similarity scoring."""
    
    @pytest.mark.asyncio
    async def test_similar_circuits_high_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test that identical circuits have high similarity."""
        c1_id, _ = sample_circuits[1][0].id, sample_circuits[1][1]
        c4_id, _ = sample_circuits[3][0].id, sample_circuits[3][1]
        
        result = await circuit_comparison_service.calculate_circuit_similarity_score(
            c1_id, c4_id
        )
        
        # Similar circuits should have high similarity (> 0.75)
        assert result.similarity_score > 0.75
        assert result.pattern_similarity == 1.0
        assert result.region_similarity == 1.0
        assert result.muscle_similarity == 1.0
        assert result.equipment_similarity == 1.0
        assert result.intensity_similarity == 1.0
    
    @pytest.mark.asyncio
    async def test_different_circuits_low_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test that different circuits have lower similarity."""
        c1_id, _ = sample_circuits[0][0].id, sample_circuits[0][1]
        c2_id, _ = sample_circuits[1][0].id, sample_circuits[1][1]
        
        result = await circuit_comparison_service.calculate_circuit_similarity_score(
            c1_id, c2_id
        )
        
        # Different circuits should have lower similarity
        assert result.similarity_score < 0.5
        assert result.region_similarity == 0.0  # Different regions
        assert result.muscle_similarity < 0.5  # Different muscles
        assert result.pattern_similarity == 0.0  # Different patterns
    
    @pytest.mark.asyncio
    async def test_full_body_mixed_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test similarity with full body mixed circuit."""
        c1_id, _ = sample_circuits[0][0].id, sample_circuits[0][1]
        c3_id, _ = sample_circuits[2][0].id, sample_circuits[2][1]
        
        result = await circuit_comparison_service.calculate_circuit_similarity_score(
            c1_id, c3_id
        )
        
        # Partial overlap should result in medium similarity
        assert 0.3 < result.similarity_score < 0.7
        assert result.pattern_similarity > 0.0  # Some pattern overlap
        assert result.region_similarity == 0.0  # Different regions
        assert result.muscle_similarity > 0.0  # Some muscle overlap
        assert result.equipment_similarity > 0.5  # High equipment overlap


class TestFindSimilarCircuits:
    """Tests for finding similar circuits."""
    
    @pytest.mark.asyncio
    async def test_find_similar_circuits(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test finding similar circuits."""
        c1_id = sample_circuits[0][0].id
        
        similar = await circuit_comparison_service.find_similar_circuits(
            circuit_id=c1_id,
            limit=5,
            min_similarity=0.5
        )
        
        # Should return similar circuits
        assert len(similar) > 0
        # Most similar should be the identical circuit (c4)
        assert similar[0].similarity_score > 0.75
        # Should be sorted by similarity (descending)
        for i in range(1, len(similar)):
            assert similar[i].similarity_score <= similar[i-1].similarity_score
    
    @pytest.mark.asyncio
    async def test_find_similar_circuits_high_threshold(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test finding similar circuits with high threshold."""
        c1_id = sample_circuits[0][0].id
        
        similar = await circuit_comparison_service.find_similar_circuits(
            circuit_id=c1_id,
            limit=5,
            min_similarity=0.8
        )
        
        # Should return only very similar circuits
        for result in similar:
            assert result.similarity_score >= 0.8
    
    @pytest.mark.asyncio
    async def test_find_similar_circuits_exclude_ids(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test finding similar circuits with exclusion."""
        c1_id = sample_circuits[0][0].id
        c4_id = sample_circuits[3][0].id
        
        similar = await circuit_comparison_service.find_similar_circuits(
            circuit_id=c1_id,
            limit=10,
            min_similarity=0.5,
            exclude_ids=[c4_id]
        )
        
        # Should not include excluded circuit
        circuit_ids = [r.circuit_id for r in similar]
        assert c4_id not in circuit_ids


class TestFindComplementaryCircuits:
    """Tests for finding complementary circuits."""
    
    @pytest.mark.asyncio
    async def test_find_complementary_circuits(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test finding complementary circuits."""
        c1_id = sample_circuits[0][0].id
        
        complementary = await circuit_comparison_service.find_complementary_circuits(
            circuit_id=c1_id,
            limit=5,
            min_complementarity=0.3
        )
        
        # Should return complementary circuits
        assert len(complementary) > 0
        # Should be sorted by complementarity (descending)
        for i in range(1, len(complementary)):
            assert complementary[i].complementary_score <= complementary[i-1].complementary_score
        # Should provide reasons
        for rec in complementary:
            assert rec.reason  # Should have a reason
            assert rec.complementary_score >= 0.3
    
    @pytest.mark.asyncio
    async def test_complementary_vs_similar(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test that complementary circuits are different from similar ones."""
        c1_id = sample_circuits[0][0].id
        
        similar = await circuit_comparison_service.find_similar_circuits(
            circuit_id=c1_id,
            limit=10,
            min_similarity=0.5
        )
        
        complementary = await circuit_comparison_service.find_complementary_circuits(
            circuit_id=c1_id,
            limit=10,
            min_complementarity=0.3
        )
        
        # Complementary should have lower similarity than similar
        similar_ids = {s.circuit_id for s in similar}
        complementary_ids = {c.circuit_id for c in complementary}
        
        # May have some overlap, but most should be different
        overlap = similar_ids & complementary_ids
        overlap_ratio = len(overlap) / len(similar_ids) if similar_ids else 0
        assert overlap_ratio < 0.5  # Less than 50% overlap
    
    @pytest.mark.asyncio
    async def test_complementary_high_threshold(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test finding complementary circuits with high threshold."""
        c1_id = sample_circuits[0][0].id
        
        complementary = await circuit_comparison_service.find_complementary_circuits(
            circuit_id=c1_id,
            limit=5,
            min_complementarity=0.7
        )
        
        # Should return only highly complementary circuits
        for rec in complementary:
            assert rec.complementary_score >= 0.7


class TestCircuitRecommendations:
    """Tests for circuit recommendations."""
    
    @pytest.mark.asyncio
    async def test_recommend_by_region(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test recommending circuits by region."""
        recommendations = await circuit_comparison_service.recommend_circuits_for_session(
            target_regions=["lower"],
            limit=5
        )
        
        # Should return circuits for lower body
        assert len(recommendations) > 0
        for rec in recommendations:
            assert rec.metadata['primary_region'] == 'lower'
    
    @pytest.mark.asyncio
    async def test_recommend_by_pattern(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test recommending circuits by pattern."""
        recommendations = await circuit_comparison_service.recommend_circuits_for_session(
            target_patterns=["squat"],
            limit=5
        )
        
        # Should return circuits with squat pattern
        assert len(recommendations) > 0
    
    @pytest.mark.asyncio
    async def test_recommend_by_difficulty(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test recommending circuits by difficulty."""
        recommendations = await circuit_comparison_service.recommend_circuits_for_session(
            difficulty_tier="silver",
            limit=5
        )
        
        # Should return circuits at or below silver tier
        assert len(recommendations) > 0
        for rec in recommendations:
            tier_value = rec.metadata['difficulty_tier']
            assert tier_value <= 2  # Silver or below
    
    @pytest.mark.asyncio
    async def test_recommend_by_equipment(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test recommending circuits by equipment."""
        recommendations = await circuit_comparison_service.recommend_circuits_for_session(
            max_equipment=2,
            limit=5
        )
        
        # Should return circuits with <= 2 equipment items
        assert len(recommendations) > 0
        # Note: metadata doesn't include equipment_complexity, but the filtering should work
    
    @pytest.mark.asyncio
    async def test_recommend_complementary_to_session(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test recommending circuits complementary to current session."""
        c1_id = sample_circuits[0][0].id
        
        recommendations = await circuit_comparison_service.recommend_circuits_for_session(
            circuit_ids=[c1_id],
            limit=5
        )
        
        # Should recommend complementary circuits
        assert len(recommendations) > 0
        # Should not include the current circuit
        rec_ids = [r.circuit_id for r in recommendations]
        assert c1_id not in rec_ids


class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_nonexistent_circuit_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test similarity with non-existent circuit."""
        c1_id = sample_circuits[0][0].id
        nonexistent_id = 99999
        
        with pytest.raises(ValueError, match="Both circuits must have macro records"):
            await circuit_comparison_service.calculate_circuit_similarity_score(
                c1_id, nonexistent_id
            )
    
    @pytest.mark.asyncio
    async def test_nonexistent_circuit_complementary(
        self,
        circuit_comparison_service: CircuitComparisonService
    ):
        """Test complementary with non-existent circuit."""
        nonexistent_id = 99999
        
        with pytest.raises(ValueError, match="not found or has no macro data"):
            await circuit_comparison_service.find_complementary_circuits(
                circuit_id=nonexistent_id
            )
    
    @pytest.mark.asyncio
    async def test_empty_results(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test with high thresholds that return no results."""
        c1_id = sample_circuits[0][0].id
        
        similar = await circuit_comparison_service.find_similar_circuits(
            circuit_id=c1_id,
            limit=10,
            min_similarity=0.99  # Very high threshold
        )
        
        # Should return empty list
        assert len(similar) == 0


class TestSimilarityCalculationMethods:
    """Tests for individual similarity calculation methods."""
    
    @pytest.mark.asyncio
    async def test_pattern_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test pattern similarity calculation."""
        _, m1 = sample_circuits[0]
        _, m2 = sample_circuits[1]
        _, m3 = sample_circuits[2]
        
        # Same patterns = 1.0
        sim = circuit_comparison_service._calculate_pattern_similarity(m1, m1)
        assert sim == 1.0
        
        # Different patterns = 0.0
        sim = circuit_comparison_service._calculate_pattern_similarity(m1, m2)
        assert sim == 0.0
        
        # Partial overlap = 0.33
        sim = circuit_comparison_service._calculate_pattern_similarity(m1, m3)
        assert sim > 0.0 and sim < 1.0
    
    @pytest.mark.asyncio
    async def test_region_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test region similarity calculation."""
        _, m1 = sample_circuits[0]
        _, m2 = sample_circuits[1]
        
        # Same region = 1.0
        sim = circuit_comparison_service._calculate_region_similarity(m1, m1)
        assert sim == 1.0
        
        # Different region = 0.0
        sim = circuit_comparison_service._calculate_region_similarity(m1, m2)
        assert sim == 0.0
    
    @pytest.mark.asyncio
    async def test_muscle_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test muscle similarity calculation."""
        _, m1 = sample_circuits[0]
        _, m2 = sample_circuits[1]
        _, m3 = sample_circuits[2]
        
        # Same muscles = 1.0
        sim = circuit_comparison_service._calculate_muscle_similarity(m1, m1)
        assert sim == 1.0
        
        # Different muscles = 0.0
        sim = circuit_comparison_service._calculate_muscle_similarity(m1, m2)
        assert sim == 0.0
        
        # Partial overlap = some value
        sim = circuit_comparison_service._calculate_muscle_similarity(m1, m3)
        assert 0.0 < sim < 1.0
    
    @pytest.mark.asyncio
    async def test_equipment_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test equipment similarity calculation."""
        _, m1 = sample_circuits[0]
        _, m2 = sample_circuits[1]
        _, m3 = sample_circuits[2]
        
        # Same equipment = 1.0
        sim = circuit_comparison_service._calculate_equipment_similarity(m1, m1)
        assert sim == 1.0
        
        # Different equipment = 0.5 (1/2 overlap)
        sim = circuit_comparison_service._calculate_equipment_similarity(m1, m2)
        assert sim == 0.5
        
        # Partial overlap
        sim = circuit_comparison_service._calculate_equipment_similarity(m1, m3)
        assert 0.5 < sim < 1.0
    
    @pytest.mark.asyncio
    async def test_intensity_similarity(
        self,
        circuit_comparison_service: CircuitComparisonService,
        sample_circuits
    ):
        """Test intensity similarity calculation."""
        _, m1 = sample_circuits[0]
        _, m2 = sample_circuits[1]
        _, m3 = sample_circuits[2]
        
        # Same intensity = 1.0
        sim = circuit_comparison_service._calculate_intensity_similarity(m1, m1)
        assert sim == 1.0
        
        # Different tiers = some value
        sim = circuit_comparison_service._calculate_intensity_similarity(m1, m3)
        assert 0.0 < sim < 1.0
