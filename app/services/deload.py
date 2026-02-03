"""
DeloadService - Manages deload scheduling and PSI trend tracking.

Responsible for:
- Tracking PSI (Perceived System Intensity) history
- Detecting fatigue trends and performance plateaus
- Determining optimal deload windows (time-based and performance-based)
- Recommending deload microcycles when triggered
- Managing deload recovery patterns
"""
from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Microcycle, RecoverySignal, Program
)
from app.config.heuristics import DELOAD_POLICY


class DeloadService:
    """
    Manages deload scheduling and recovery analysis.
    
    Deloads are triggered by:
    1. Time-based: Every 3-4 microcycles (enforced at program generation)
    2. Recovery-based: Low recovery signals (sleep, HRV, readiness)
    """
    pass
    
    
    
    async def should_trigger_deload(
        self,
        db: AsyncSession,
        user_id: int,
        program_id: int,
    ) -> Tuple[bool, str]:
        """
        Determine if deload should be triggered for current program.
        
        Checks:
        - Recovery signals (low sleep, HRV, readiness)
        - Time since last deload
        
        Args:
            db: Database session
            user_id: User ID
            program_id: Program ID
        
        Returns:
            Tuple of (should_deload: bool, reason: str)
        """
        reasons = []
        
        # Check recovery signals
        recovery = await self._get_recovery_status(db, user_id)
        if recovery.get("sleep_avg", 8) < 6:
            reasons.append("low sleep")
        if recovery.get("readiness_avg", 50) < 40:
            reasons.append("low readiness")
        
        # Check time since last deload
        time_since_deload = await self._days_since_last_deload(db, program_id)
        deload_every_microcycles = DELOAD_POLICY["default_deload_every_microcycles"]
        microcycle_days = deload_every_microcycles * 7
        if time_since_deload > microcycle_days:
            reasons.append("time-based (4+ weeks)")
        
        should_deload = len(reasons) >= 1
        reason = ", ".join(reasons) if reasons else "no trigger"
        
        return should_deload, reason
    
    
    async def _get_recovery_status(self, db: AsyncSession, user_id: int) -> dict:
        """
        Get recent recovery signal averages.
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            Dict with sleep_avg, readiness_avg, hrv_avg
        """
        result = await db.execute(
            select(RecoverySignal)
            .where(
                and_(
                    RecoverySignal.user_id == user_id,
                    RecoverySignal.date >= (datetime.utcnow() - timedelta(days=7)).date()
                )
            )
            .order_by(desc(RecoverySignal.date))
            .limit(7)
        )
        signals = list(result.scalars().all())
        
        if not signals:
            return {"sleep_avg": 8, "readiness_avg": 50, "hrv_avg": 50}
        
        sleep_scores = [s.sleep_hours for s in signals if s.sleep_hours]
        readiness_scores = [s.readiness for s in signals if s.readiness]
        hrv_scores = [s.hrv for s in signals if s.hrv]
        
        return {
            "sleep_avg": sum(sleep_scores) / len(sleep_scores) if sleep_scores else 8,
            "readiness_avg": sum(readiness_scores) / len(readiness_scores) if readiness_scores else 50,
            "hrv_avg": sum(hrv_scores) / len(hrv_scores) if hrv_scores else 50,
        }
    
    async def _days_since_last_deload(
        self,
        db: AsyncSession,
        program_id: int,
    ) -> int:
        """
        Calculate days since last deload microcycle in program.
        
        Args:
            db: Database session
            program_id: Program ID
        
        Returns:
            Days since last deload (or 999 if no deload yet)
        """
        result = await db.execute(
            select(Microcycle)
            .where(
                and_(
                    Microcycle.program_id == program_id,
                    Microcycle.is_deload.is_(True)
                )
            )
            .order_by(desc(Microcycle.start_date))
            .limit(1)
        )
        last_deload = result.scalar_one_or_none()
        
        if not last_deload:
            # Check program start date if no deload found
            program_result = await db.execute(select(Program).where(Program.id == program_id))
            program = program_result.scalar_one_or_none()
            if program:
                return (datetime.utcnow().date() - program.start_date).days
            return 999
        
        days_diff = (datetime.utcnow().date() - last_deload.start_date).days
        return max(0, days_diff)


# Singleton instance
deload_service = DeloadService()
