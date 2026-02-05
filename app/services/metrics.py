"""Metrics service for e1RM calculation and Pattern Strength Index."""
from typing import Literal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PatternExposure,
    Microcycle,
    MovementPattern,
    E1RMFormula,
)


class MetricsService:
    """Service for calculating training metrics."""
    
    @staticmethod
    def calculate_e1rm(
        weight: float,
        reps: int,
        formula: E1RMFormula = E1RMFormula.EPLEY
    ) -> float:
        """
        Calculate estimated 1RM from weight and reps.
        
        Args:
            weight: Weight lifted
            reps: Number of repetitions (must be >= 1)
            formula: Formula to use for calculation
            
        Returns:
            Estimated 1RM value
        """
        if reps < 1:
            raise ValueError("Reps must be at least 1")
        
        if reps == 1:
            return weight
        
        if formula == E1RMFormula.EPLEY:
            # Epley formula: weight × (1 + reps/30)
            return weight * (1 + reps / 30)
        
        elif formula == E1RMFormula.BRZYCKI:
            # Brzycki formula: weight × 36 / (37 - reps)
            # Note: becomes undefined as reps approaches 37
            if reps >= 37:
                return weight * 2.5  # Fallback for high reps
            return weight * (36 / (37 - reps))
        
        elif formula == E1RMFormula.LOMBARDI:
            # Lombardi formula: weight × reps^0.10
            return weight * (reps ** 0.10)
        
        elif formula == E1RMFormula.OCONNER:
            # O'Conner formula: weight × (1 + reps/40)
            return weight * (1 + reps / 40)
        
        else:
            # Default to Epley
            return weight * (1 + reps / 30)
    
    @staticmethod
    def calculate_e1rm_from_rpe(
        weight: float,
        reps: int,
        rpe: float,
        formula: E1RMFormula = E1RMFormula.EPLEY
    ) -> float:
        """
        Calculate estimated 1RM accounting for RPE.
        
        Adjusts the effective reps based on RPE (reps in reserve).
        RPE 10 = 0 RIR, RPE 9 = 1 RIR, etc.
        
        Args:
            weight: Weight lifted
            reps: Number of repetitions performed
            rpe: RPE rating (1-10)
            formula: Formula to use
            
        Returns:
            Estimated 1RM value
        """
        # Convert RPE to reps in reserve
        rir = 10 - rpe if rpe <= 10 else 0
        
        # Effective reps = actual reps + RIR
        effective_reps = reps + rir
        
        return MetricsService.calculate_e1rm(weight, effective_reps, formula)
    
    async def get_pattern_exposures(
        self,
        db: AsyncSession,
        user_id: int,
        pattern: MovementPattern,
        lookback_microcycles: int = 2
    ) -> list[PatternExposure]:
        """
        Get pattern exposures for PSI calculation.
        
        Args:
            db: Database session
            user_id: User ID
            pattern: Movement pattern to query
            lookback_microcycles: Number of recent microcycles to include
            
        Returns:
            List of pattern exposures
        """
        # Get recent microcycle IDs
        microcycle_query = (
            select(Microcycle.id)
            .where(Microcycle.program.has(user_id=user_id))
            .order_by(Microcycle.start_date.desc())
            .limit(lookback_microcycles)
        )
        result = await db.execute(microcycle_query)
        microcycle_ids = [row[0] for row in result.fetchall()]
        
        if not microcycle_ids:
            return []
        
        # Get exposures for these microcycles
        exposure_query = (
            select(PatternExposure)
            .where(
                and_(
                    PatternExposure.user_id == user_id,
                    PatternExposure.pattern == pattern,
                    PatternExposure.microcycle_id.in_(microcycle_ids)
                )
            )
            .order_by(PatternExposure.date.desc())
        )
        result = await db.execute(exposure_query)
        return list(result.scalars().all())
    
    async def calculate_psi(
        self,
        db: AsyncSession,
        user_id: int,
        pattern: MovementPattern,
        lookback_microcycles: int = 2
    ) -> float | None:
        """
        Calculate Pattern Strength Index (PSI).
        
        PSI is the unweighted average of all e1RM exposures for a pattern
        in the last N microcycles.
        
        Args:
            db: Database session
            user_id: User ID
            pattern: Movement pattern
            lookback_microcycles: Number of microcycles to include
            
        Returns:
            PSI value, or None if insufficient data
        """
        exposures = await self.get_pattern_exposures(
            db, user_id, pattern, lookback_microcycles
        )
        
        if len(exposures) < 2:  # Minimum exposures for valid PSI
            return None
        
        # Unweighted average of e1RM values
        total = sum(exp.e1rm_value for exp in exposures)
        return total / len(exposures)
    
    async def detect_psi_trend(
        self,
        db: AsyncSession,
        user_id: int,
        pattern: MovementPattern,
        window_microcycles: int = 4
    ) -> Literal["increasing", "decreasing", "stable", "insufficient_data"]:
        """
        Detect trend in PSI over time.
        
        Args:
            db: Database session
            user_id: User ID
            pattern: Movement pattern
            window_microcycles: Microcycles to analyze
            
        Returns:
            Trend direction string
        """
        # Get exposures over the full window
        exposures = await self.get_pattern_exposures(
            db, user_id, pattern, window_microcycles
        )
        
        if len(exposures) < 4:
            return "insufficient_data"
        
        # Split into two halves
        mid = len(exposures) // 2
        recent_avg = sum(e.e1rm_value for e in exposures[:mid]) / mid
        older_avg = sum(e.e1rm_value for e in exposures[mid:]) / (len(exposures) - mid)
        
        # Calculate percent change
        if older_avg == 0:
            return "insufficient_data"
        
        percent_change = ((recent_avg - older_avg) / older_avg) * 100
        
        # Threshold for significant change (default 5%)
        threshold = 5.0
        
        if percent_change > threshold:
            return "increasing"
        elif percent_change < -threshold:
            return "decreasing"
        else:
            return "stable"
    
    async def should_trigger_deload(
        self,
        db: AsyncSession,
        user_id: int,
        psi_drop_threshold: float = 10.0
    ) -> tuple[bool, list[MovementPattern]]:
        """
        Check if performance-based deload should be triggered.
        
        Args:
            db: Database session
            user_id: User ID
            psi_drop_threshold: Percent drop threshold to trigger
            
        Returns:
            Tuple of (should_deload, list of declining patterns)
        """
        declining_patterns = []
        
        for pattern in MovementPattern:
            trend = await self.detect_psi_trend(db, user_id, pattern)
            if trend == "decreasing":
                declining_patterns.append(pattern)
        
        # Trigger deload if multiple patterns are declining
        should_deload = len(declining_patterns) >= 2
        
        return should_deload, declining_patterns


    async def get_volume_load(
        self,
        db: AsyncSession,
        user_id: int,
        pattern: MovementPattern,
        lookback_days: int = 7,
    ) -> int:
        """
        Calculate total volume (sets × reps) for a pattern in recent period.
        
        Args:
            db: Database session
            user_id: User ID
            pattern: Movement pattern
            lookback_days: Days to look back (default 7)
        
        Returns:
            Total reps performed
        """
        from datetime import datetime, timedelta
        
        start_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        exposures = await self.get_pattern_exposures(db, user_id, pattern, lookback_microcycles=10)
        
        total_volume = 0
        for exp in exposures:
            if exp.date >= start_date.date():
                total_volume += exp.sets * exp.reps
        
        return total_volume
    
    async def get_recovery_status(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> dict:
        """
        Aggregate recent recovery signals into a status summary.
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            Dict with recovery metrics (sleep_avg, readiness_avg, hrv_avg)
        """
        from datetime import datetime, timedelta
        from app.models import RecoverySignal
        
        start_date = datetime.utcnow() - timedelta(days=7)
        
        signals_result = await db.execute(
            select(RecoverySignal)
            .where(
                and_(
                    RecoverySignal.user_id == user_id,
                    RecoverySignal.date >= start_date.date()
                )
            )
            .order_by(RecoverySignal.date.desc())
            .limit(7)
        )
        signals = list(signals_result.scalars().all())
        
        if not signals:
            return {
                "sleep_avg": None,
                "readiness_avg": None,
                "hrv_avg": None,
                "signal_count": 0,
            }
        
        sleep_scores = [s.sleep_score for s in signals if s.sleep_score is not None]
        readiness_scores = [s.readiness for s in signals if s.readiness is not None]
        hrv_scores = [s.hrv for s in signals if s.hrv is not None]
        
        return {
            "sleep_avg": sum(sleep_scores) / len(sleep_scores) if sleep_scores else None,
            "readiness_avg": sum(readiness_scores) / len(readiness_scores) if readiness_scores else None,
            "hrv_avg": sum(hrv_scores) / len(hrv_scores) if hrv_scores else None,
            "signal_count": len(signals),
        }


# Singleton instance
metrics_service = MetricsService()


# Standalone function exports for convenience
def calculate_e1rm(
    weight: float,
    reps: int,
    formula: E1RMFormula | str = E1RMFormula.EPLEY
) -> float:
    """Calculate estimated 1RM from weight and reps."""
    if isinstance(formula, str):
        formula = E1RMFormula(formula)
    return MetricsService.calculate_e1rm(weight, reps, formula)


def calculate_e1rm_from_rpe(
    weight: float,
    reps: int,
    rpe: float,
    formula: E1RMFormula | str = E1RMFormula.EPLEY
) -> float:
    """Calculate estimated 1RM accounting for RPE."""
    if isinstance(formula, str):
        formula = E1RMFormula(formula)
    return MetricsService.calculate_e1rm_from_rpe(weight, reps, rpe, formula)


# Formula string mapping for convenience
E1RM_FORMULAS = {
    "epley": E1RMFormula.EPLEY,
    "brzycki": E1RMFormula.BRZYCKI,
    "lombardi": E1RMFormula.LOMBARDI,
    "oconner": E1RMFormula.OCONNER,
}
