"""Circuit Comparison Service.

This service provides circuit comparison and recommendation functionality
based on patterns, regions, muscles, equipment, and intensity.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.circuit_extended import CircuitMacro
from app.models.enums import MovementTier

logger = logging.getLogger(__name__)


@dataclass
class CircuitSimilarityResult:
    """Result of circuit similarity calculation.
    
    Attributes:
        circuit_id: ID of the compared circuit
        similarity_score: Overall similarity score (0-1)
        pattern_similarity: Similarity in movement patterns (0-1)
        region_similarity: Similarity in primary region (0-1)
        muscle_similarity: Similarity in muscle engagement (0-1)
        equipment_similarity: Similarity in required equipment (0-1)
        intensity_similarity: Similarity in intensity (0-1)
    """
    circuit_id: int
    similarity_score: float
    pattern_similarity: float
    region_similarity: float
    muscle_similarity: float
    equipment_similarity: float
    intensity_similarity: float


@dataclass
class CircuitRecommendation:
    """Circuit recommendation result.
    
    Attributes:
        circuit_id: ID of recommended circuit
        reason: Primary reason for recommendation
        similarity_score: How similar (0-1)
        complementary_score: How complementary (0-1)
        metadata: Additional metadata
    """
    circuit_id: int
    reason: str
    similarity_score: float
    complementary_score: float
    metadata: Dict[str, str]


class CircuitComparisonService:
    """Service for comparing and recommending circuits.
    
    This service analyzes circuits based on:
    - Movement patterns (squat, hinge, push, pull, etc.)
    - Body regions (upper, lower, full_body)
    - Muscle engagement (primary muscles)
    - Equipment requirements
    - Intensity metrics (difficulty tier, duration)
    
    Similarity is calculated using weighted overlap of these dimensions.
    """
    
    # Similarity weights (must sum to 1.0)
    WEIGHT_PATTERN = 0.25
    WEIGHT_REGION = 0.20
    WEIGHT_MUSCLE = 0.25
    WEIGHT_EQUIPMENT = 0.15
    WEIGHT_INTENSITY = 0.15
    
    # Complementarity weights (for variety - different is better)
    COMPLEMENTARY_PATTERN = 0.30
    COMPLEMENTARY_REGION = 0.30
    COMPLEMENTARY_MUSCLE = 0.30
    COMPLEMENTARY_EQUIPMENT = 0.10
    
    # Similarity weights (for finishers - same is better)
    SIMILARITY_PATTERN = 0.30
    SIMILARITY_REGION = 0.30
    SIMILARITY_MUSCLE = 0.30
    SIMILARITY_EQUIPMENT = 0.10
    
    # Similarity thresholds
    MIN_SIMILARITY_THRESHOLD = 0.5
    HIGH_SIMILARITY_THRESHOLD = 0.75
    
    def __init__(self, db: AsyncSession):
        """Initialize the service with a database session.
        
        Args:
            db: Async SQLAlchemy session for database queries
        """
        self.db = db
    
    async def calculate_circuit_similarity_score(
        self,
        circuit_a_id: int,
        circuit_b_id: int
    ) -> CircuitSimilarityResult:
        """Calculate similarity score between two circuits.
        
        Similarity is based on:
        1. Pattern similarity: Overlap in movement patterns
        2. Region similarity: Primary region match
        3. Muscle similarity: Overlap in primary muscles
        4. Equipment similarity: Overlap in required equipment
        5. Intensity similarity: Difference in difficulty and duration
        
        Args:
            circuit_a_id: ID of first circuit
            circuit_b_id: ID of second circuit
            
        Returns:
            CircuitSimilarityResult with detailed similarity metrics
            
        Example:
            >>> service = CircuitComparisonService(db)
            >>> result = await service.calculate_circuit_similarity_score(1, 2)
            >>> print(f"Similarity: {result.similarity_score:.2%}")
        """
        # Get both circuit macro records
        stmt = select(CircuitMacro).where(CircuitMacro.circuit_id.in_([circuit_a_id, circuit_b_id]))
        result = await self.db.execute(stmt)
        macros = {m.circuit_id: m for m in result.scalars().all()}
        
        if circuit_a_id not in macros or circuit_b_id not in macros:
            raise ValueError("Both circuits must have macro records")
        
        macro_a = macros[circuit_a_id]
        macro_b = macros[circuit_b_id]
        
        # Calculate individual similarity scores
        pattern_sim = self._calculate_pattern_similarity(macro_a, macro_b)
        region_sim = self._calculate_region_similarity(macro_a, macro_b)
        muscle_sim = self._calculate_muscle_similarity(macro_a, macro_b)
        equipment_sim = self._calculate_equipment_similarity(macro_a, macro_b)
        intensity_sim = self._calculate_intensity_similarity(macro_a, macro_b)
        
        # Calculate weighted overall similarity
        overall_similarity = (
            pattern_sim * self.WEIGHT_PATTERN +
            region_sim * self.WEIGHT_REGION +
            muscle_sim * self.WEIGHT_MUSCLE +
            equipment_sim * self.WEIGHT_EQUIPMENT +
            intensity_sim * self.WEIGHT_INTENSITY
        )
        
        return CircuitSimilarityResult(
            circuit_id=circuit_b_id,
            similarity_score=overall_similarity,
            pattern_similarity=pattern_sim,
            region_similarity=region_sim,
            muscle_similarity=muscle_sim,
            equipment_similarity=equipment_sim,
            intensity_similarity=intensity_sim
        )
    
    def _calculate_pattern_similarity(
        self,
        macro_a: CircuitMacro,
        macro_b: CircuitMacro
    ) -> float:
        """Calculate similarity in movement patterns.
        
        Uses Jaccard similarity on pattern counts.
        
        Args:
            macro_a: First circuit's macro data
            macro_b: Second circuit's macro data
            
        Returns:
            Similarity score (0-1)
        """
        patterns_a = set(macro_a.movement_pattern_counts.keys())
        patterns_b = set(macro_b.movement_pattern_counts.keys())
        
        if not patterns_a and not patterns_b:
            return 1.0
        if not patterns_a or not patterns_b:
            return 0.0
        
        # Jaccard similarity
        intersection = len(patterns_a & patterns_b)
        union = len(patterns_a | patterns_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_region_similarity(
        self,
        macro_a: CircuitMacro,
        macro_b: CircuitMacro
    ) -> float:
        """Calculate similarity in primary region.
        
        Exact match = 1.0, otherwise = 0.0.
        Could be extended to allow partial matching.
        
        Args:
            macro_a: First circuit's macro data
            macro_b: Second circuit's macro data
            
        Returns:
            Similarity score (0-1)
        """
        return 1.0 if macro_a.primary_region == macro_b.primary_region else 0.0
    
    def _calculate_muscle_similarity(
        self,
        macro_a: CircuitMacro,
        macro_b: CircuitMacro
    ) -> float:
        """Calculate similarity in muscle engagement.
        
        Uses Jaccard similarity on primary muscles.
        
        Args:
            macro_a: First circuit's macro data
            macro_b: Second circuit's macro data
            
        Returns:
            Similarity score (0-1)
        """
        muscles_a = set(macro_a.primary_muscles)
        muscles_b = set(macro_b.primary_muscles)
        
        if not muscles_a and not muscles_b:
            return 1.0
        if not muscles_a or not muscles_b:
            return 0.0
        
        # Jaccard similarity
        intersection = len(muscles_a & muscles_b)
        union = len(muscles_a | muscles_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_equipment_similarity(
        self,
        macro_a: CircuitMacro,
        macro_b: CircuitMacro
    ) -> float:
        """Calculate similarity in equipment requirements.
        
        Uses Jaccard similarity on required equipment.
        
        Args:
            macro_a: First circuit's macro data
            macro_b: Second circuit's macro data
            
        Returns:
            Similarity score (0-1)
        """
        equipment_a = set(macro_a.required_equipment)
        equipment_b = set(macro_b.required_equipment)
        
        if not equipment_a and not equipment_b:
            return 1.0
        if not equipment_a or not equipment_b:
            return 0.0
        
        # Jaccard similarity
        intersection = len(equipment_a & equipment_b)
        union = len(equipment_a | equipment_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_intensity_similarity(
        self,
        macro_a: CircuitMacro,
        macro_b: CircuitMacro
    ) -> float:
        """Calculate similarity in intensity.
        
        Based on:
        1. Difficulty tier difference
        2. Duration difference
        
        Args:
            macro_a: First circuit's macro data
            macro_b: Second circuit's macro data
            
        Returns:
            Similarity score (0-1)
        """
        # Difficulty tier similarity
        tier_a = macro_a.difficulty_tier.value
        tier_b = macro_b.difficulty_tier.value
        tier_diff = abs(tier_a - tier_b) / 3.0  # Normalize by max diff (3)
        
        # Duration similarity
        duration_a = macro_a.estimated_duration_seconds or 0
        duration_b = macro_b.estimated_duration_seconds or 0
        
        if duration_a == 0 and duration_b == 0:
            duration_sim = 1.0
        elif duration_a == 0 or duration_b == 0:
            duration_sim = 0.0
        else:
            # Use relative difference
            max_duration = max(duration_a, duration_b)
            duration_diff = abs(duration_a - duration_b) / max_duration
            duration_sim = 1.0 - duration_diff
        
        # Average the two components
        return (1.0 - tier_diff + duration_sim) / 2.0
    
    async def find_similar_circuits(
        self,
        circuit_id: int,
        limit: int = 10,
        min_similarity: float = None,
        exclude_ids: Optional[List[int]] = None
    ) -> List[CircuitSimilarityResult]:
        """Find circuits similar to a given circuit.
        
        Args:
            circuit_id: ID of reference circuit
            limit: Maximum number of similar circuits to return
            min_similarity: Minimum similarity threshold (default: MIN_SIMILARITY_THRESHOLD)
            exclude_ids: Circuit IDs to exclude from results
            
        Returns:
            List of CircuitSimilarityResult sorted by similarity (descending)
            
        Example:
            >>> service = CircuitComparisonService(db)
            >>> similar = await service.find_similar_circuits(1, limit=5)
            >>> for result in similar:
            >>>     print(f"Circuit {result.circuit_id}: {result.similarity_score:.2%}")
        """
        if min_similarity is None:
            min_similarity = self.MIN_SIMILARITY_THRESHOLD
        
        if exclude_ids is None:
            exclude_ids = []
        else:
            exclude_ids = exclude_ids.copy()
        exclude_ids.append(circuit_id)  # Always exclude reference circuit
        
        # Get all candidate circuits
        stmt = select(CircuitMacro.circuit_id).where(
            CircuitMacro.circuit_id.notin_(exclude_ids)
        )
        result = await self.db.execute(stmt)
        candidate_ids = [row[0] for row in result]
        
        # Calculate similarity for each candidate
        similarities = []
        for candidate_id in candidate_ids:
            similarity = await self.calculate_circuit_similarity_score(
                circuit_id, candidate_id
            )
            if similarity.similarity_score >= min_similarity:
                similarities.append(similarity)
        
        # Sort by similarity (descending) and limit
        similarities.sort(key=lambda x: x.similarity_score, reverse=True)
        return similarities[:limit]
    
    async def find_complementary_circuits(
        self,
        circuit_id: int,
        limit: int = 10,
        min_complementarity: float = 0.3,
        exclude_ids: Optional[List[int]] = None
    ) -> List[CircuitRecommendation]:
        """Find circuits that complement a given circuit.
        
        Complementary circuits target different muscles, regions, and patterns,
        making them good choices for variety in training programs.
        
        Args:
            circuit_id: ID of reference circuit
            limit: Maximum number of complementary circuits to return
            min_complementarity: Minimum complementarity score (0-1)
            exclude_ids: Circuit IDs to exclude from results
            
        Returns:
            List of CircuitRecommendation sorted by complementarity (descending)
            
        Example:
            >>> service = CircuitComparisonService(db)
            >>> complementary = await service.find_complementary_circuits(1, limit=5)
            >>> for rec in complementary:
            >>>     print(f"Circuit {rec.circuit_id}: {rec.reason}")
        """
        if exclude_ids is None:
            exclude_ids = []
        else:
            exclude_ids = exclude_ids.copy()
        exclude_ids.append(circuit_id)
        
        # Get reference circuit
        stmt = select(CircuitMacro).where(CircuitMacro.circuit_id == circuit_id)
        result = await self.db.execute(stmt)
        reference = result.scalar_one_or_none()
        
        if not reference:
            raise ValueError(f"Circuit {circuit_id} not found or has no macro data")
        
        # Get all candidate circuits
        stmt = select(CircuitMacro).where(
            CircuitMacro.circuit_id.notin_(exclude_ids)
        )
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()
        
        # Calculate complementarity for each candidate
        recommendations = []
        for candidate in candidates:
            complementarity = self._calculate_complementarity_score(
                reference, candidate
            )
            
            if complementarity >= min_complementarity:
                reason = self._generate_complementarity_reason(
                    reference, candidate, complementarity
                )
                
                # Also calculate similarity for context
                similarity = await self.calculate_circuit_similarity_score(
                    circuit_id, candidate.circuit_id
                )
                
                recommendations.append(CircuitRecommendation(
                    circuit_id=candidate.circuit_id,
                    reason=reason,
                    similarity_score=similarity.similarity_score,
                    complementary_score=complementarity,
                    metadata={
                        'primary_region': candidate.primary_region.value,
                        'difficulty_tier': candidate.difficulty_tier.value
                    }
                ))
        
        # Sort by complementarity (descending) and limit
        recommendations.sort(key=lambda x: x.complementary_score, reverse=True)
        return recommendations[:limit]
    
    def _calculate_complementarity_score(
        self,
        reference: CircuitMacro,
        candidate: CircuitMacro
    ) -> float:
        """Calculate complementarity score between circuits.
        
        Complementarity is based on:
        1. Pattern diversity: Different movement patterns
        2. Region diversity: Different primary regions
        3. Muscle diversity: Different primary muscles
        4. Equipment overlap: Some shared equipment is good
        
        Args:
            reference: Reference circuit's macro data
            candidate: Candidate circuit's macro data
            
        Returns:
            Complementarity score (0-1)
        """
        # Pattern diversity (different is better)
        patterns_ref = set(reference.movement_pattern_counts.keys())
        patterns_cand = set(candidate.movement_pattern_counts.keys())
        pattern_overlap = len(patterns_ref & patterns_cand) / len(patterns_ref | patterns_cand) if (patterns_ref | patterns_cand) else 0
        pattern_diversity = 1.0 - pattern_overlap
        
        # Region diversity (different is better)
        region_diversity = 0.0 if reference.primary_region == candidate.primary_region else 1.0
        
        # Muscle diversity (different is better)
        muscles_ref = set(reference.primary_muscles)
        muscles_cand = set(candidate.primary_muscles)
        muscle_overlap = len(muscles_ref & muscles_cand) / len(muscles_ref | muscles_cand) if (muscles_ref | muscles_cand) else 0
        muscle_diversity = 1.0 - muscle_overlap
        
        # Equipment overlap (some shared is better)
        equipment_ref = set(reference.required_equipment)
        equipment_cand = set(candidate.required_equipment)
        if not equipment_ref and not equipment_cand:
            equipment_overlap = 1.0
        elif not equipment_ref or not equipment_cand:
            equipment_overlap = 0.0
        else:
            equipment_overlap = len(equipment_ref & equipment_cand) / len(equipment_ref | equipment_cand)
        
        # Weighted complementarity
        complementarity = (
            pattern_diversity * self.COMPLEMENTARY_PATTERN +
            region_diversity * self.COMPLEMENTARY_REGION +
            muscle_diversity * self.COMPLEMENTARY_MUSCLE +
            equipment_overlap * self.COMPLEMENTARY_EQUIPMENT
        )
        
        logger.debug(f"[_calculate_complementarity_score] Ref circuit {reference.circuit_id} vs Cand circuit {candidate.circuit_id}")
        logger.debug(f"[_calculate_complementarity_score] Pattern diversity: {pattern_diversity:.3f} (overlap: {pattern_overlap:.3f})")
        logger.debug(f"[_calculate_complementarity_score] Region diversity: {region_diversity:.3f} (ref={reference.primary_region.value}, cand={candidate.primary_region.value})")
        logger.debug(f"[_calculate_complementarity_score] Muscle diversity: {muscle_diversity:.3f} (overlap: {muscle_overlap:.3f})")
        logger.debug(f"[_calculate_complementarity_score] Equipment overlap: {equipment_overlap:.3f}")
        logger.debug(f"[_calculate_complementarity_score] Final complementarity: {complementarity:.3f}")
        
        return complementarity
    
    def _calculate_finisher_similarity_score(
        self,
        reference: CircuitMacro,
        candidate: CircuitMacro
    ) -> float:
        """Calculate similarity score for finisher selection.
        
        For finishers, we want circuits that are SIMILAR to the main lifts
        to act as a burner on the same muscles. This uses similarity weights
        instead of complementarity weights.
        
        Similarity is based on:
        1. Pattern similarity: Same movement patterns
        2. Region similarity: Same primary region
        3. Muscle similarity: Same primary muscles
        4. Equipment overlap: Shared equipment is good
        
        Args:
            reference: Reference circuit's macro data (from main lifts)
            candidate: Candidate circuit's macro data
            
        Returns:
            Similarity score (0-1) where higher is more similar
        """
        # Pattern similarity (same is better)
        patterns_ref = set(reference.movement_pattern_counts.keys())
        patterns_cand = set(candidate.movement_pattern_counts.keys())
        pattern_overlap = len(patterns_ref & patterns_cand) / len(patterns_ref | patterns_cand) if (patterns_ref | patterns_cand) else 0
        
        # Region similarity (same is better)
        region_similarity = 1.0 if reference.primary_region == candidate.primary_region else 0.0
        
        # Muscle similarity (same is better)
        muscles_ref = set(reference.primary_muscles)
        muscles_cand = set(candidate.primary_muscles)
        muscle_overlap = len(muscles_ref & muscles_cand) / len(muscles_ref | muscles_cand) if (muscles_ref | muscles_cand) else 0
        
        # Equipment overlap (some shared is better)
        equipment_ref = set(reference.required_equipment)
        equipment_cand = set(candidate.required_equipment)
        if not equipment_ref and not equipment_cand:
            equipment_overlap = 1.0
        elif not equipment_ref or not equipment_cand:
            equipment_overlap = 0.0
        else:
            equipment_overlap = len(equipment_ref & equipment_cand) / len(equipment_ref | equipment_cand)
        
        # Weighted similarity (same is better)
        similarity = (
            pattern_overlap * self.SIMILARITY_PATTERN +
            region_similarity * self.SIMILARITY_REGION +
            muscle_overlap * self.SIMILARITY_MUSCLE +
            equipment_overlap * self.SIMILARITY_EQUIPMENT
        )
        
        logger.debug(f"[_calculate_finisher_similarity_score] Ref circuit {reference.circuit_id} vs Cand circuit {candidate.circuit_id}")
        logger.debug(f"[_calculate_finisher_similarity_score] Pattern similarity: {pattern_overlap:.3f}")
        logger.debug(f"[_calculate_finisher_similarity_score] Region similarity: {region_similarity:.3f} (ref={reference.primary_region.value}, cand={candidate.primary_region.value})")
        logger.debug(f"[_calculate_finisher_similarity_score] Muscle similarity: {muscle_overlap:.3f}")
        logger.debug(f"[_calculate_finisher_similarity_score] Equipment overlap: {equipment_overlap:.3f}")
        logger.debug(f"[_calculate_finisher_similarity_score] Final similarity: {similarity:.3f}")
        
        return similarity
    
    def _generate_complementarity_reason(
        self,
        reference: CircuitMacro,
        candidate: CircuitMacro,
        score: float
    ) -> str:
        """Generate human-readable reason for complementarity.
        
        Args:
            reference: Reference circuit
            candidate: Candidate circuit
            score: Complementarity score
            
        Returns:
            Human-readable reason string
        """
        reasons = []
        
        if reference.primary_region != candidate.primary_region:
            reasons.append(f"targets {candidate.primary_region.value} body region")
        
        patterns_ref = set(reference.movement_pattern_counts.keys())
        patterns_cand = set(candidate.movement_pattern_counts.keys())
        if not patterns_ref & patterns_cand:
            reasons.append("uses different movement patterns")
        elif patterns_ref - patterns_cand:
            reasons.append(f"adds {', '.join(patterns_cand - patterns_ref)} patterns")
        
        muscles_ref = set(reference.primary_muscles)
        muscles_cand = set(candidate.primary_muscles)
        if not muscles_ref & muscles_cand:
            reasons.append("targets different muscle groups")
        elif muscles_ref - muscles_cand:
            reasons.append(f"adds {', '.join(muscles_cand - muscles_ref)} muscles")
        
        if not reasons:
            reasons.append("provides variety in training")
        
        return "; ".join(reasons)
    
    async def recommend_circuits_for_session(
        self,
        circuit_ids: Optional[List[int]] = None,
        target_regions: Optional[List[str]] = None,
        target_patterns: Optional[List[str]] = None,
        difficulty_tier: Optional[str] = None,
        max_equipment: int = None,
        limit: int = 10,
        is_finisher: bool = False
    ) -> List[CircuitRecommendation]:
        """Recommend circuits for a training session.
        
        This is a more flexible recommendation system that considers
        multiple constraints and preferences.
        
        Args:
            circuit_ids: Current circuits in session (for complementarity/similarity)
            target_regions: Preferred body regions
            target_patterns: Preferred movement patterns
            difficulty_tier: Maximum difficulty tier
            max_equipment: Maximum number of equipment items
            limit: Maximum number of recommendations
            is_finisher: If True, use similarity scoring (for finishers);
                         if False, use complementarity scoring (for variety)
            
        Returns:
            List of CircuitRecommendation sorted by relevance
            
        Example:
            >>> service = CircuitComparisonService(db)
            >>> recommendations = await service.recommend_circuits_for_session(
            >>>     target_regions=['lower'],
            >>>     difficulty_tier='silver',
            >>>     limit=5
            >>> )
        """
        logger.info("=" * 80)
        logger.info("[CircuitComparisonService.recommend_circuits_for_session] ENTRY POINT")
        logger.info("[CircuitComparisonService] circuit_ids={circuit_ids}")
        logger.info(f"[CircuitComparisonService] target_regions={target_regions}")
        logger.info(f"[CircuitComparisonService] target_patterns={target_patterns}")
        logger.info(f"[CircuitComparisonService] difficulty_tier={difficulty_tier}")
        logger.info(f"[CircuitComparisonService] max_equipment={max_equipment}")
        logger.info(f"[CircuitComparisonService] limit={limit}")
        logger.info(f"[CircuitComparisonService] is_finisher={is_finisher}")
        logger.info("=" * 80)
        
        try:
            # Build query with filters
            stmt = select(CircuitMacro)
            
            # Apply filters
            filters_applied = []
            if target_regions:
                stmt = stmt.where(CircuitMacro.primary_region.in_(target_regions))
                filters_applied.append(f"target_regions={target_regions}")
                logger.info(f"[CircuitComparisonService] Applied filter: target_regions={target_regions}")
            
            if difficulty_tier:
                tier_value = MovementTier(difficulty_tier).value
                stmt = stmt.where(CircuitMacro.difficulty_tier <= tier_value)
                filters_applied.append(f"difficulty_tier={difficulty_tier} (value={tier_value})")
                logger.info(f"[CircuitComparisonService] Applied filter: difficulty_tier={difficulty_tier} (value={tier_value})")
            
            if max_equipment is not None:
                stmt = stmt.where(CircuitMacro.equipment_complexity <= max_equipment)
                filters_applied.append(f"max_equipment={max_equipment}")
                logger.info(f"[CircuitComparisonService] Applied filter: max_equipment={max_equipment}")
            
            if circuit_ids:
                stmt = stmt.where(CircuitMacro.circuit_id.notin_(circuit_ids))
                filters_applied.append(f"excluding circuit_ids={circuit_ids}")
                logger.info(f"[CircuitComparisonService] Applied filter: excluding circuit_ids={circuit_ids}")
            
            logger.info(f"[CircuitComparisonService] Filters applied: {filters_applied if filters_applied else 'none'}")
            
            # Execute query
            logger.info("[CircuitComparisonService] Executing database query...")
            result = await self.db.execute(stmt)
            candidates = result.scalars().all()
            logger.info(f"[CircuitComparisonService] Database query returned {len(candidates)} candidate circuits")
            
            if len(candidates) > 0:
                # Log details of first few candidates for debugging
                for i, c in enumerate(candidates[:3]):
                    logger.info(f"[CircuitComparisonService] Candidate {i+1}: circuit_id={c.circuit_id}, primary_region={c.primary_region.value}, difficulty_tier={c.difficulty_tier.value}, total_exercises={c.total_exercises}")
            
            # Filter by target patterns (JSONB filtering is complex, do in Python)
            if target_patterns:
                candidates_before_filter = len(candidates)
                candidates = [
                    c for c in candidates
                    if any(p in c.movement_pattern_counts for p in target_patterns)
                ]
                logger.info(
                    f"[CircuitComparisonService] After target_patterns filter ({target_patterns}): "
                    f"{len(candidates)} candidates (was {candidates_before_filter})"
                )
                
                if len(candidates) > 0:
                    # Log which patterns matched for first candidate
                    for i, c in enumerate(candidates[:3]):
                        matched_patterns = [p for p in target_patterns if p in c.movement_pattern_counts]
                        logger.info(f"[CircuitComparisonService] Candidate {c.circuit_id} matched patterns: {matched_patterns}")
            
            if len(candidates) == 0:
                logger.warning("[CircuitComparisonService] No candidates remaining after filters, returning empty list")
                logger.info("=" * 80)
                return []
            
            # Score candidates
            logger.info(f"[CircuitComparisonService] Scoring {len(candidates)} candidates...")
            recommendations = []
            
            # Get reference circuit if provided
            reference = None
            if circuit_ids:
                logger.info(f"[CircuitComparisonService] Fetching reference circuit with id={circuit_ids[0]}")
                reference_stmt = select(CircuitMacro).where(
                    CircuitMacro.circuit_id == circuit_ids[0]
                )
                result = await self.db.execute(reference_stmt)
                reference = result.scalar_one_or_none()
                if reference:
                    logger.info(f"[CircuitComparisonService] Reference circuit found: circuit_id={reference.circuit_id}, primary_region={reference.primary_region.value}, difficulty_tier={reference.difficulty_tier.value}")
                    logger.info(f"[CircuitComparisonService] Reference primary_muscles: {reference.primary_muscles}")
                else:
                    logger.warning(f"[CircuitComparisonService] Reference circuit {circuit_ids[0]} not found in database")
            
            scoring_method = "finisher_similarity" if (is_finisher and reference) else ("complementarity" if reference else "default")
            logger.info(f"[CircuitComparisonService] Scoring method: {scoring_method}")
            
            for candidate in candidates:
                score = 0.0
                
                if reference:
                    if is_finisher:
                        # Similarity score for finishers (same muscles/region is better)
                        score = self._calculate_finisher_similarity_score(
                            reference, candidate
                        )
                        logger.debug(
                            f"[CircuitComparisonService] Calculated finisher similarity for circuit {candidate.circuit_id}: "
                            f"score={score:.3f}"
                        )
                    else:
                        # Complementarity score for variety (different is better)
                        score = self._calculate_complementarity_score(
                            reference, candidate
                        )
                        logger.debug(
                        f"[CircuitComparisonService] Calculated complementarity for circuit {candidate.circuit_id}: "
                        f"score={score:.3f}"
                    )
                else:
                    # Relevance score based on filters
                    score = 1.0  # Default for unfiltered queries
                    logger.debug("[CircuitComparisonService] No circuit_ids provided, using default score=1.0")
                
                recommendations.append(CircuitRecommendation(
                    circuit_id=candidate.circuit_id,
                    reason="matches session criteria",
                    similarity_score=score if is_finisher else 0.0,
                    complementary_score=0.0 if is_finisher else score,
                    metadata={
                        'primary_region': candidate.primary_region.value,
                        'difficulty_tier': candidate.difficulty_tier.value,
                        'total_exercises': candidate.total_exercises
                    }
                ))
            
            # Log scored recommendations
            for i, rec in enumerate(recommendations[:5]):
                logger.info(
                    f"[CircuitComparisonService] Scored recommendation {i+1}: circuit_id={rec.circuit_id}, "
                    f"similarity_score={rec.similarity_score:.3f}, complementary_score={rec.complementary_score:.3f}, "
                    f"region={rec.metadata['primary_region']}, tier={rec.metadata['difficulty_tier']}"
                )
            
            # Sort by score (descending) and limit
            if is_finisher:
                recommendations.sort(key=lambda x: x.similarity_score, reverse=True)
                logger.info("[CircuitComparisonService] Sorted by similarity_score (descending)")
            else:
                recommendations.sort(key=lambda x: x.complementary_score, reverse=True)
                logger.info("[CircuitComparisonService] Sorted by complementary_score (descending)")
            
            final_recommendations = recommendations[:limit]
            logger.info(
                f"[CircuitComparisonService] RETURN - {len(final_recommendations)} recommendations "
                f"(requested limit={limit}, is_finisher={is_finisher})"
            )
            
            # Log final recommendations
            for i, rec in enumerate(final_recommendations):
                logger.info(
                    f"[CircuitComparisonService] Final recommendation {i+1}: circuit_id={rec.circuit_id}, "
                    f"reason={rec.reason}, similarity={rec.similarity_score:.3f}, complementary={rec.complementary_score:.3f}, "
                    f"metadata={rec.metadata}"
                )
            
            logger.info("=" * 80)
            return final_recommendations
            
        except Exception as e:
            logger.error(
                f"[CircuitComparisonService] ERROR in recommend_circuits_for_session: {e}",
                exc_info=True
            )
            logger.info("=" * 80)
            raise


# Convenience function for single-use comparison
async def find_similar_circuits(
    db: AsyncSession,
    circuit_id: int,
    limit: int = 10
) -> List[CircuitSimilarityResult]:
    """Convenience function to find similar circuits.
    
    Args:
        db: Async SQLAlchemy session
        circuit_id: ID of reference circuit
        limit: Maximum number of results
        
    Returns:
        List of CircuitSimilarityResult
        
    Example:
        >>> similar = await find_similar_circuits(db, circuit_id=1, limit=5)
        >>> for result in similar:
        >>>     print(f"Circuit {result.circuit_id}: {result.similarity_score:.2%}")
    """
    service = CircuitComparisonService(db)
    return await service.find_similar_circuits(circuit_id, limit)
