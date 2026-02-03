"""
Movement query optimization and substitution service.

Provides optimized query functions for tiering, biomechanics, and metabolic demand,
along with a safety-first substitution service based on biomechanics profiles.
"""
from typing import Optional, Any, Dict, List
from sqlalchemy import select, and_, Float, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.models.movement import Movement, MovementDiscipline, MovementEquipment, MovementTag, Equipment
from app.models.enums import MovementTier, MetabolicDemand, DisciplineType


class MovementQueryService:
    """Optimized query functions for movement attributes."""
    
    @staticmethod
    async def get_movements_by_tier(
        db: AsyncSession,
        tier: MovementTier
    ) -> List[Movement]:
        """Get movements by tier (uses indexed tier column)."""
        result = await db.execute(
            select(Movement).where(Movement.tier == tier)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_movements_by_disciplines(
        db: AsyncSession,
        disciplines: List[DisciplineType],
        match_all: bool = False
    ) -> List[Movement]:
        """
        Get movements by disciplines using PostgreSQL array operators.
        
        Args:
            db: Database session
            disciplines: List of discipline types to filter by
            match_all: If True, require all disciplines; if False, require any (array overlap)
        
        Returns:
            List of movements matching the discipline criteria
        """
        discipline_values = [d.value for d in disciplines]
        
        if match_all:
            subquery = (
                select(MovementDiscipline.movement_id)
                .where(MovementDiscipline.discipline.in_(discipline_values))
                .group_by(MovementDiscipline.movement_id)
                .having(func.count(MovementDiscipline.discipline) == len(discipline_values))
            )
        else:
            subquery = (
                select(MovementDiscipline.movement_id)
                .where(MovementDiscipline.discipline.in_(discipline_values))
                .distinct()
            )
        
        result = await db.execute(
            select(Movement).where(Movement.id.in_(subquery))
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_powerlifting_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get all powerlifting movements (squat, bench, deadlift patterns)."""
        return await MovementQueryService.get_movements_by_disciplines(
            db, [DisciplineType.POWERLIFTING]
        )
    
    @staticmethod
    async def get_olympic_weightlifting_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get all Olympic weightlifting movements (snatch, clean & jerk)."""
        return await MovementQueryService.get_movements_by_disciplines(
            db, [DisciplineType.OLYMPIC_WEIGHTLIFTING]
        )
    
    @staticmethod
    async def get_crossfit_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get all CrossFit movements."""
        return await MovementQueryService.get_movements_by_disciplines(
            db, [DisciplineType.CROSSFIT]
        )
    
    @staticmethod
    async def get_bodybuilding_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get all bodybuilding movements."""
        return await MovementQueryService.get_movements_by_disciplines(
            db, [DisciplineType.BODYBUILDING]
        )
    
    @staticmethod
    async def get_movements_by_equipment(
        db: AsyncSession,
        equipment_names: List[str],
        match_all: bool = False
    ) -> List[Movement]:
        """
        Get movements by equipment names using PostgreSQL array-like containment logic.
        
        Args:
            db: Database session
            equipment_names: List of equipment names to filter by
            match_all: If True, require all equipment; if False, require any
        
        Returns:
            List of movements matching the equipment criteria
        """
        if match_all:
            subquery = (
                select(MovementEquipment.movement_id)
                .join(MovementEquipment.equipment)
                .where(Equipment.name.in_(equipment_names))
                .group_by(MovementEquipment.movement_id)
                .having(func.count(MovementEquipment.equipment_id) == len(equipment_names))
            )
        else:
            subquery = (
                select(MovementEquipment.movement_id)
                .join(MovementEquipment.equipment)
                .where(Equipment.name.in_(equipment_names))
                .distinct()
            )
        
        result = await db.execute(
            select(Movement).where(Movement.id.in_(subquery))
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_barbell_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get movements requiring a barbell."""
        return await MovementQueryService.get_movements_by_equipment(
            db, ["barbell"]
        )
    
    @staticmethod
    async def get_dumbbell_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get movements requiring dumbbells."""
        return await MovementQueryService.get_movements_by_equipment(
            db, ["dumbbell"]
        )
    
    @staticmethod
    async def get_movements_by_tags(
        db: AsyncSession,
        tag_names: List[str],
        match_all: bool = False
    ) -> List[Movement]:
        """
        Get movements by tag names using PostgreSQL array-like containment logic.
        
        Args:
            db: Database session
            tag_names: List of tag names to filter by
            match_all: If True, require all tags; if False, require any
        
        Returns:
            List of movements matching the tag criteria
        """
        from app.models.movement import Tag
        
        if match_all:
            subquery = (
                select(MovementTag.movement_id)
                .join(MovementTag.tag)
                .where(Tag.name.in_(tag_names))
                .group_by(MovementTag.movement_id)
                .having(func.count(MovementTag.tag_id) == len(tag_names))
            )
        else:
            subquery = (
                select(MovementTag.movement_id)
                .join(MovementTag.tag)
                .where(Tag.name.in_(tag_names))
                .distinct()
            )
        
        result = await db.execute(
            select(Movement).where(Movement.id.in_(subquery))
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_compound_lifts(
        db: AsyncSession
    ) -> List[Movement]:
        """Get movements tagged as compound lifts."""
        return await MovementQueryService.get_movements_by_tags(
            db, ["compound"]
        )
    
    @staticmethod
    async def get_kettlebell_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get movements requiring kettlebells."""
        return await MovementQueryService.get_movements_by_equipment(
            db, ["kettlebell"]
        )
    
    @staticmethod
    async def get_gymnastics_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get calisthenics/gymnastics movements."""
        return await MovementQueryService.get_movements_by_disciplines(
            db, [DisciplineType.CALISTHENICS]
        )
    
    @staticmethod
    async def get_multi_discipline_movements(
        db: AsyncSession,
        min_disciplines: int = 2
    ) -> List[Movement]:
        """
        Get movements that belong to multiple disciplines.
        
        Uses GROUP BY and HAVING to count junction table entries.
        
        Args:
            db: Database session
            min_disciplines: Minimum number of disciplines required
        
        Returns:
            List of movements with multiple discipline classifications
        """
        subquery = (
            select(MovementDiscipline.movement_id)
            .group_by(MovementDiscipline.movement_id)
            .having(func.count(MovementDiscipline.discipline) >= min_disciplines)
        )
        
        result = await db.execute(
            select(Movement).where(Movement.id.in_(subquery))
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_movement_disciplines(
        db: AsyncSession,
        movement_id: int
    ) -> List[str]:
        """
        Get all disciplines for a specific movement.
        
        Args:
            db: Database session
            movement_id: Movement ID
        
        Returns:
            List of discipline values
        """
        result = await db.execute(
            select(MovementDiscipline.discipline)
            .where(MovementDiscipline.movement_id == movement_id)
        )
        return [row[0] for row in result.all()]
    
    @staticmethod
    async def get_movement_equipment(
        db: AsyncSession,
        movement_id: int
    ) -> List[str]:
        """
        Get all equipment for a specific movement.
        
        Args:
            db: Database session
            movement_id: Movement ID
        
        Returns:
            List of equipment names
        """
        from app.models.movement import Equipment
        
        result = await db.execute(
            select(Equipment.name)
            .join(MovementEquipment, Equipment.id == MovementEquipment.equipment_id)
            .where(MovementEquipment.movement_id == movement_id)
        )
        return [row[0] for row in result.all()]
    
    @staticmethod
    async def get_movement_tags(
        db: AsyncSession,
        movement_id: int
    ) -> List[str]:
        """
        Get all tags for a specific movement.
        
        Args:
            db: Database session
            movement_id: Movement ID
        
        Returns:
            List of tag names
        """
        from app.models.movement import Tag
        
        result = await db.execute(
            select(Tag.name)
            .join(MovementTag, Tag.id == MovementTag.tag_id)
            .where(MovementTag.movement_id == movement_id)
        )
        return [row[0] for row in result.all()]
    
    @staticmethod
    async def filter_by_disciplines_and_equipment(
        db: AsyncSession,
        disciplines: Optional[List[DisciplineType]] = None,
        equipment_names: Optional[List[str]] = None,
        match_all_disciplines: bool = False,
        match_all_equipment: bool = False
    ) -> List[Movement]:
        """
        Complex filter combining disciplines and equipment requirements.
        
        Uses EXISTS subqueries for optimal performance.
        
        Args:
            db: Database session
            disciplines: List of discipline types to filter by (optional)
            equipment_names: List of equipment names to filter by (optional)
            match_all_disciplines: Require all disciplines if True, any if False
            match_all_equipment: Require all equipment if True, any if False
        
        Returns:
            List of movements matching all criteria
        """
        query = select(Movement)
        
        if disciplines:
            discipline_values = [d.value for d in disciplines]
            
            if match_all_disciplines:
                for disc in discipline_values:
                    query = query.where(
                        select(MovementDiscipline.movement_id)
                        .where(
                            and_(
                                MovementDiscipline.movement_id == Movement.id,
                                MovementDiscipline.discipline == disc
                            )
                        )
                        .exists()
                    )
            else:
                query = query.where(
                    select(MovementDiscipline.movement_id)
                    .where(
                        and_(
                            MovementDiscipline.movement_id == Movement.id,
                            MovementDiscipline.discipline.in_(discipline_values)
                        )
                    )
                    .exists()
                )
        
        if equipment_names:
            from app.models.movement import Equipment
            
            if match_all_equipment:
                for eq_name in equipment_names:
                    query = query.where(
                        select(MovementEquipment.movement_id)
                        .where(
                            and_(
                                MovementEquipment.movement_id == Movement.id,
                                select(Equipment.id)
                                .where(Equipment.name == eq_name)
                                .scalar_subquery() == MovementEquipment.equipment_id
                            )
                        )
                        .exists()
                    )
            else:
                query = query.where(
                    select(MovementEquipment.movement_id)
                    .where(
                        and_(
                            MovementEquipment.movement_id == Movement.id,
                            select(Equipment.id)
                            .where(Equipment.name.in_(equipment_names))
                            .scalar_subquery() == MovementEquipment.equipment_id
                        )
                    )
                    .exists()
                )
        
        result = await db.execute(query)
        return list(result.scalars().all())
    

    
    @staticmethod
    async def get_movements_by_embedding_similarity(
        db: AsyncSession,
        reference_vector: List[float],
        limit: int = 10,
        min_similarity: Optional[float] = None
    ) -> List[tuple[Movement, float]]:
        """
        Find movements by cosine similarity of embedding vectors.

        Uses PostgreSQL pgvector's <=> operator for optimal performance.

        Args:
            db: Database session
            reference_vector: Reference embedding vector
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of (Movement, similarity_score) tuples, sorted by similarity descending
        """
        vector_str = "[" + ",".join(str(v) for v in reference_vector) + "]"

        if min_similarity is not None:
            query = text("""
                SELECT 
                    m.id,
                    m.name,
                    m.pattern,
                    m.primary_muscle,
                    m.primary_region,
                    m.tier,
                    m.metabolic_demand,
                    m.cns_load,
                    m.skill_level,
                    m.compound,
                    m.is_complex_lift,
                    m.is_unilateral,
                    m.fatigue_factor,
                    m.stimulus_factor,
                    m.injury_risk_factor,
                    m.min_recovery_hours,
                    m.spinal_compression,
                    m.metric_type,
                    m.description,
                    m.substitution_group,
                    m.user_id,
                    m.embedding_description,
                    m.embedding_vector,
                    (m.embedding_vector <=> :reference_vector) as distance
                FROM movements m
                WHERE m.embedding_vector IS NOT NULL
                AND (m.embedding_vector <=> :reference_vector) <= :max_distance
                ORDER BY distance ASC
                LIMIT :limit
            """)
            result = await db.execute(
                query,
                {"reference_vector": vector_str, "max_distance": 1.0 - min_similarity, "limit": limit}
            )
        else:
            query = text("""
                SELECT 
                    m.id,
                    m.name,
                    m.pattern,
                    m.primary_muscle,
                    m.primary_region,
                    m.tier,
                    m.metabolic_demand,
                    m.cns_load,
                    m.skill_level,
                    m.compound,
                    m.is_complex_lift,
                    m.is_unilateral,
                    m.fatigue_factor,
                    m.stimulus_factor,
                    m.injury_risk_factor,
                    m.min_recovery_hours,
                    m.spinal_compression,
                    m.metric_type,
                    m.description,
                    m.substitution_group,
                    m.user_id,
                    m.embedding_description,
                    m.embedding_vector,
                    (embedding_vector <=> :reference_vector) as distance
                FROM movements m
                WHERE m.embedding_vector IS NOT NULL
                ORDER BY distance ASC
                LIMIT :limit
            """)
            result = await db.execute(
                query,
                {"reference_vector": vector_str, "limit": limit}
            )

        rows = result.all()
        movements = []

        for row in rows:
            movement_data = {
                "id": row.id,
                "name": row.name,
                "pattern": row.pattern,
                "primary_muscle": row.primary_muscle,
                "primary_region": row.primary_region,
                "tier": row.tier,
                "metabolic_demand": row.metabolic_demand,
                "cns_load": row.cns_load,
                "skill_level": row.skill_level,
                "compound": row.compound,
                "is_complex_lift": row.is_complex_lift,
                "is_unilateral": row.is_unilateral,
                "fatigue_factor": row.fatigue_factor,
                "stimulus_factor": row.stimulus_factor,
                "injury_risk_factor": row.injury_risk_factor,
                "min_recovery_hours": row.min_recovery_hours,
                "spinal_compression": row.spinal_compression,
                "metric_type": row.metric_type,
                "description": row.description,
                "substitution_group": row.substitution_group,
                "user_id": row.user_id,
                "embedding_description": row.embedding_description,
                "embedding_vector": row.embedding_vector,
            }

            movement = Movement(**movement_data)
            similarity = 1.0 - row.distance
            movements.append((movement, similarity))

        return movements
    
    @staticmethod
    async def get_semantic_similar_movements(
        db: AsyncSession,
        movement_id: int,
        limit: int = 10,
        min_similarity: Optional[float] = None
    ) -> List[tuple[Movement, float]]:
        """
        Find movements semantically similar to a given movement by embedding vector.
        
        Args:
            db: Database session
            movement_id: Reference movement ID
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            List of (Movement, similarity_score) tuples
        """
        movement = await db.get(Movement, movement_id)
        if not movement or not movement.embedding_vector:
            return []
        
        return await MovementQueryService.get_movements_by_embedding_similarity(
            db, movement.embedding_vector, limit, min_similarity
        )
    
    @staticmethod
    async def get_movements_with_embeddings(
        db: AsyncSession,
        limit: Optional[int] = None
    ) -> List[Movement]:
        """
        Get all movements that have embedding vectors.
        
        Args:
            db: Database session
            limit: Optional limit on number of results
        
        Returns:
            List of movements with embeddings
        """
        query = select(Movement).where(Movement.embedding_vector.isnot(None))
        
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def count_movements_by_discipline(
        db: AsyncSession
    ) -> Dict[str, int]:
        """
        Count movements grouped by discipline.
        
        Uses GROUP BY aggregation on junction table.
        
        Args:
            db: Database session
        
        Returns:
            Dictionary mapping discipline values to movement counts
        """
        result = await db.execute(
            select(
                MovementDiscipline.discipline,
                func.count(MovementDiscipline.movement_id).label('count')
            )
            .group_by(MovementDiscipline.discipline)
        )
        
        return {row.discipline: row.count for row in result.all()}
    
    @staticmethod
    async def count_movements_by_equipment(
        db: AsyncSession
    ) -> Dict[str, int]:
        """
        Count movements grouped by equipment.
        
        Args:
            db: Database session
        
        Returns:
            Dictionary mapping equipment names to movement counts
        """
        from app.models.movement import Equipment
        
        result = await db.execute(
            select(
                Equipment.name,
                func.count(MovementEquipment.movement_id).label('count')
            )
            .join(MovementEquipment, Equipment.id == MovementEquipment.equipment_id)
            .group_by(Equipment.name)
        )
        
        return {row.name: row.count for row in result.all()}
    
    @staticmethod
    async def get_movements_without_disciplines(
        db: AsyncSession
    ) -> List[Movement]:
        """
        Get movements that are not associated with any discipline.
        
        Uses NOT EXISTS with junction table.
        
        Args:
            db: Database session
        
        Returns:
            List of movements without discipline classifications
        """
        result = await db.execute(
            select(Movement).where(
                ~select(MovementDiscipline.movement_id)
                .where(MovementDiscipline.movement_id == Movement.id)
                .exists()
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_movements_without_equipment(
        db: AsyncSession
    ) -> List[Movement]:
        """
        Get movements that don't require any equipment (bodyweight).
        
        Args:
            db: Database session
        
        Returns:
            List of equipment-free movements
        """
        result = await db.execute(
            select(Movement).where(
                ~select(MovementEquipment.movement_id)
                .where(MovementEquipment.movement_id == Movement.id)
                .exists()
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_premium_tier_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get diamond and gold tier movements."""
        result = await db.execute(
            select(Movement).where(
                Movement.tier.in_([MovementTier.DIAMOND, MovementTier.GOLD])
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_metabolic_demand_movements(
        db: AsyncSession,
        demand: MetabolicDemand
    ) -> List[Movement]:
        """Get movements by metabolic demand (uses indexed metabolic_demand column)."""
        result = await db.execute(
            select(Movement).where(Movement.metabolic_demand == demand)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_anabolic_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get anabolic movements (good for hypertrophy)."""
        result = await db.execute(
            select(Movement).where(
                Movement.metabolic_demand == MetabolicDemand.ANABOLIC
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_movements_by_archetype(
        db: AsyncSession,
        archetype: str
    ) -> List[Movement]:
        """Get movements by biomechanics archetype (uses GIN index)."""
        result = await db.execute(
            select(Movement).where(
                Movement.biomechanics_profile['archetype'].astext == archetype
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_low_spinal_load_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get movements with none or low spinal load (uses GIN index)."""
        result = await db.execute(
            select(Movement).where(
                Movement.biomechanics_profile['loading_pattern']['spinal_load'].astext.in_(['none', 'low'])
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_joint_dominant_movements(
        db: AsyncSession,
        joint: str,
        min_score: float = 7.0
    ) -> List[Movement]:
        """Get movements with high involvement for a specific joint (uses GIN index)."""
        result = await db.execute(
            select(Movement).where(
                Movement.biomechanics_profile['joint_involvement'][joint].astext.cast(Float) >= min_score
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_knee_dominant_movements(
        db: AsyncSession,
        min_score: float = 7.0
    ) -> List[Movement]:
        """Get knee-dominant movements (high knee involvement)."""
        return await MovementQueryService.get_joint_dominant_movements(
            db, 'knee', min_score
        )
    
    @staticmethod
    async def get_hip_dominant_movements(
        db: AsyncSession,
        min_score: float = 7.0
    ) -> List[Movement]:
        """Get hip-dominant movements (high hip involvement)."""
        return await MovementQueryService.get_joint_dominant_movements(
            db, 'hip', min_score
        )
    
    @staticmethod
    async def get_shoulder_dominant_movements(
        db: AsyncSession,
        min_score: float = 7.0
    ) -> List[Movement]:
        """Get shoulder-dominant movements (high shoulder involvement)."""
        return await MovementQueryService.get_joint_dominant_movements(
            db, 'shoulder', min_score
        )
    
    @staticmethod
    async def get_knee_dominant_low_spinal_movements(
        db: AsyncSession,
        min_knee: float = 7.0,
        max_spinal: List[str] = ['none', 'low']
    ) -> List[Movement]:
        """Get knee-dominant movements with low spinal load (uses GIN index)."""
        result = await db.execute(
            select(Movement).where(
                and_(
                    Movement.biomechanics_profile['joint_involvement']['knee'].astext.cast(Float) >= min_knee,
                    Movement.biomechanics_profile['loading_pattern']['spinal_load'].astext.in_(max_spinal)
                )
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_unilateral_compound_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get unilateral compound movements (good for imbalances)."""
        result = await db.execute(
            select(Movement).where(
                Movement.biomechanics_profile['archetype'].astext == 'unilateral_compound'
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_by_primary_plane(
        db: AsyncSession,
        plane: str
    ) -> List[Movement]:
        """Get movements by primary movement plane (uses GIN index)."""
        result = await db.execute(
            select(Movement).where(
                Movement.biomechanics_profile['movement_vectors']['primary'].astext == plane
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_multi_plane_movements(
        db: AsyncSession
    ) -> List[Movement]:
        """Get movements with secondary movement planes (complex movements)."""
        result = await db.execute(
            select(Movement).where(
                Movement.biomechanics_profile['movement_vectors']['secondary'].astext.isnot(None)
            )
        )
        return list(result.scalars().all())


class MovementSubstitutionService:
    """Biomechanics-aware movement substitution service."""
    
    def __init__(self, query_service: Optional[MovementQueryService] = None):
        """Initialize substitution service with optional query service."""
        self.query_service = query_service or MovementQueryService()
    
    async def find_safest_substitution(
        self,
        db: AsyncSession,
        original_movement: Movement,
        user_spinal_tolerance: str = "moderate",
        user_joint_health: Optional[Dict[str, int]] = None
    ) -> Optional[Movement]:
        """
        Find the safest movement substitution based on biomechanics profile.
        
        Args:
            db: Database session
            original_movement: Movement to substitute
            user_spinal_tolerance: User's spinal load tolerance (none, low, moderate, high)
            user_joint_health: User's joint health limits (joint: max_intensity 0-10)
        
        Returns:
            Safest alternative movement or None
        """
        if not user_joint_health:
            user_joint_health = {
                "ankle": 10, "knee": 10, "hip": 10, "lumbar": 10,
                "shoulder": 10, "elbow": 10, "wrist": 10
            }
        
        spinal_load_order = {"none": 0, "low": 1, "moderate": 2, "high": 3}
        max_spinal = spinal_load_order.get(user_spinal_tolerance, 2)
        
        tolerance_levels = [level for level, score in spinal_load_order.items() if score <= max_spinal]
        
        query = (
            select(Movement)
            .where(
                and_(
                    Movement.substitution_group == original_movement.substitution_group,
                    Movement.id != original_movement.id,
                    Movement.biomechanics_profile['loading_pattern']['spinal_load'].astext.in_(tolerance_levels)
                )
            )
        )
        
        result = await db.execute(query)
        candidates = list(result.scalars().all())
        
        if not candidates:
            return None
        
        def calculate_safety_score(movement: Movement) -> float:
            """Calculate safety score based on user joint health."""
            profile = movement.biomechanics_profile or {}
            joint_scores = profile.get('joint_involvement', {})
            
            score = 100.0
            for joint, user_limit in user_joint_health.items():
                movement_score = joint_scores.get(joint, 0)
                if movement_score > user_limit:
                    score -= (movement_score - user_limit) * 10
            
            spinal_load = profile.get('loading_pattern', {}).get('spinal_load', 'moderate')
            if spinal_load in spinal_load_order:
                score -= spinal_load_order[spinal_load] * 5
            
            return max(0, score)
        
        safest = max(candidates, key=calculate_safety_score)
        
        if calculate_safety_score(safest) < 50:
            return None
        
        return safest
    
    async def find_similar_biomechanics_substitution(
        self,
        db: AsyncSession,
        original_movement: Movement,
        preferred_tier: Optional[MovementTier] = None,
        exclude_ids: Optional[List[int]] = None
    ) -> Optional[Movement]:
        """
        Find substitution with similar biomechanics profile.
        
        Args:
            db: Database session
            original_movement: Movement to substitute
            preferred_tier: Filter by tier (optional)
            exclude_ids: Exclude specific movement IDs
        
        Returns:
            Best matching movement or None
        """
        original_profile = original_movement.biomechanics_profile or {}
        
        query = (
            select(Movement)
            .where(
                and_(
                    Movement.id != original_movement.id,
                    Movement.pattern == original_movement.pattern
                )
            )
        )
        
        if preferred_tier:
            query = query.where(Movement.tier == preferred_tier)
        
        if exclude_ids:
            query = query.where(~Movement.id.in_(exclude_ids))
        
        result = await db.execute(query)
        candidates = list(result.scalars().all())
        
        if not candidates:
            return None
        
        def calculate_similarity(candidate: Movement) -> float:
            """Calculate biomechanics similarity score."""
            candidate_profile = candidate.biomechanics_profile or {}
            
            similarity = 0.0
            
            original_archetype = original_profile.get('archetype')
            candidate_archetype = candidate_profile.get('archetype')
            if original_archetype and candidate_archetype:
                similarity += 50.0 if original_archetype == candidate_archetype else 0.0
            
            original_primary_plane = original_profile.get('movement_vectors', {}).get('primary')
            candidate_primary_plane = candidate_profile.get('movement_vectors', {}).get('primary')
            if original_primary_plane and candidate_primary_plane:
                similarity += 25.0 if original_primary_plane == candidate_primary_plane else 0.0
            
            original_spinal = original_profile.get('loading_pattern', {}).get('spinal_load')
            candidate_spinal = candidate_profile.get('loading_pattern', {}).get('spinal_load')
            if original_spinal and candidate_spinal:
                spinal_order = {"none": 0, "low": 1, "moderate": 2, "high": 3}
                orig_idx = spinal_order.get(original_spinal, 2)
                cand_idx = spinal_order.get(candidate_spinal, 2)
                similarity += max(0, 25.0 - abs(orig_idx - cand_idx) * 10)
            
            if original_movement.tier and candidate.tier:
                similarity += 25.0 if original_movement.tier == candidate.tier else 10.0
            
            return similarity
        
        best_match = max(candidates, key=calculate_similarity)
        
        return best_match if calculate_similarity(best_match) >= 50 else None
    
    async def find_progression_path(
        self,
        db: AsyncSession,
        movement_id: int,
        user_skill_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find progression path for a movement based on skill and biomechanics.
        
        Args:
            db: Database session
            movement_id: Starting movement ID
            user_skill_level: User's skill level (optional)
        
        Returns:
            List of progression steps with metadata
        """
        from app.models.movement import MovementRelationship
        from app.models.enums import RelationshipType
        
        movement = await db.get(Movement, movement_id)
        if not movement:
            return []
        
        result = await db.execute(
            select(MovementRelationship)
            .where(
                and_(
                    MovementRelationship.source_movement_id == movement_id,
                    MovementRelationship.relationship_type == RelationshipType.PROGRESSION
                )
            )
            .order_by(MovementRelationship.id)
        )
        relationships = result.scalars().all()
        
        if not relationships:
            return []
        
        target_ids = [r.target_movement_id for r in relationships]
        targets_result = await db.execute(
            select(Movement).where(Movement.id.in_(target_ids))
        )
        targets = {m.id: m for m in targets_result.scalars().all()}
        
        progression = []
        skill_order = {"beginner": 1, "intermediate": 2, "advanced": 3}
        
        for rel in relationships:
            target = targets.get(rel.target_movement_id)
            if not target:
                continue
            
            profile = target.biomechanics_profile or {}
            spinal_load = profile.get('loading_pattern', {}).get('spinal_load', 'moderate')
            archetype = profile.get('archetype', 'unknown')
            
            progression.append({
                "movement_id": target.id,
                "movement_name": target.name,
                "skill_level": target.skill_level.value if target.skill_level else "intermediate",
                "skill_order": skill_order.get(target.skill_level.value if target.skill_level else "intermediate", 2),
                "tier": target.tier.value if target.tier else "bronze",
                "cns_load": target.cns_load.value if target.cns_load else "moderate",
                "spinal_load": spinal_load,
                "archetype": archetype,
                "notes": rel.notes
            })
        
        progression.sort(key=lambda x: x["skill_order"])
        
        return progression
    
    async def find_regression_options(
        self,
        db: AsyncSession,
        movement_id: int,
        injury_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find regression options based on injury context or biomechanics.
        
        Args:
            db: Database session
            movement_id: Movement to regress
            injury_context: Injury context (e.g., {"joint": "knee", "severity": "high"})
        
        Returns:
            List of regression options with safety metadata
        """
        from app.models.movement import MovementRelationship
        from app.models.enums import RelationshipType
        
        movement = await db.get(Movement, movement_id)
        if not movement:
            return []
        
        result = await db.execute(
            select(MovementRelationship)
            .where(
                and_(
                    MovementRelationship.source_movement_id == movement_id,
                    MovementRelationship.relationship_type == RelationshipType.REGRESSION
                )
            )
        )
        relationships = result.scalars().all()
        
        if not relationships:
            profile = movement.biomechanics_profile or {}
            
            archetype = profile.get('archetype', '')
            if 'compound' in archetype:
                low_spinal = await MovementQueryService.get_low_spinal_load_movements(db)
                regressions = [
                    r for r in low_spinal
                    if r.pattern == movement.pattern and r.id != movement_id
                ]
                
                if regressions:
                    return [
                        {
                            "movement_id": r.id,
                            "movement_name": r.name,
                            "reason": "Lower spinal load alternative",
                            "safety_score": 80.0
                        }
                        for r in regressions[:3]
                    ]
            
            return []
        
        target_ids = [r.target_movement_id for r in relationships]
        targets_result = await db.execute(
            select(Movement).where(Movement.id.in_(target_ids))
        )
        targets = {m.id: m for m in targets_result.scalars().all()}
        
        regressions = []
        for rel in relationships:
            target = targets.get(rel.target_movement_id)
            if not target:
                continue
            
            profile = target.biomechanics_profile or {}
            spinal_load = profile.get('loading_pattern', {}).get('spinal_load', 'moderate')
            archetype = profile.get('archetype', 'unknown')
            
            safety_score = 100.0
            if injury_context:
                joint_involvement = profile.get('joint_involvement', {})
                injured_joint = injury_context.get('joint')
                severity = injury_context.get('severity', 'moderate')
                
                if injured_joint and injured_joint in joint_involvement:
                    score = joint_involvement[injured_joint]
                    if severity == 'high' and score > 5:
                        safety_score -= 50.0
                    elif severity == 'moderate' and score > 7:
                        safety_score -= 30.0
            
            regressions.append({
                "movement_id": target.id,
                "movement_name": target.name,
                "reason": rel.notes or "Regression option",
                "safety_score": max(0, safety_score),
                "spinal_load": spinal_load,
                "archetype": archetype
            })
        
        regressions.sort(key=lambda x: (-x["safety_score"]))
        
        return regressions[:5]
