import math
import logging
from typing import Optional
from app.models.session_allocation import (
    SessionTypeTargets,
    SessionTypePreferences,
    GoalBucketWeights,
    CardioPreferenceMode,
    RoundingStrategy,
)

logger = logging.getLogger(__name__)


class SessionTypeCalculator:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.min_lifting_days = self.config.get("min_lifting_days", 1)
        self.max_cardio_pct = self.config.get("max_cardio_pct", 0.5)
        self.min_allocation_accuracy = self.config.get("min_allocation_accuracy", 0.85)
        self.rounding_drift_threshold = self.config.get("rounding_drift_threshold", 0.15)

    def calculate_session_type_targets(
        self,
        total_sessions: int,
        goal_weights: GoalBucketWeights,
        preferences: SessionTypePreferences,
    ) -> SessionTypeTargets:
        logger.info(
            f"[SessionTypeCalculator] Calculating targets for {total_sessions} sessions, "
            f"goal_weights={goal_weights.__dict__}, preferences={preferences.__dict__}"
        )

        if total_sessions == 0:
            logger.warning("[SessionTypeCalculator] Zero sessions requested, returning empty targets")
            return SessionTypeTargets(0, 0, 0, 0)

        raw_targets = self._calculate_proportional_allocation(
            total_sessions, goal_weights, preferences
        )

        rounded_targets = self._apply_rounding_rules(
            raw_targets, preferences, total_sessions
        )

        adjusted_targets = self._apply_user_preferences(
            rounded_targets, preferences, total_sessions
        )

        final_targets = self._handle_edge_cases(
            adjusted_targets, goal_weights, preferences, total_sessions
        )

        self._validate_targets(final_targets, total_sessions)

        logger.info(
            f"[SessionTypeCalculator] Final targets: accessory={final_targets.target_accessory_count}, "
            f"finisher={final_targets.target_finisher_count}, "
            f"cardio_days={final_targets.target_cardio_day_count}, "
            f"accuracy={final_targets.allocation_accuracy:.2%}"
        )

        return final_targets

    def _calculate_proportional_allocation(
        self,
        total_sessions: int,
        goal_weights: GoalBucketWeights,
        preferences: SessionTypePreferences,
    ) -> SessionTypeTargets:
        w_total = goal_weights.total
        if w_total == 0:
            logger.warning("[SessionTypeCalculator] All goal weights are zero, using equal distribution")
            w_total = 1.0
            goal_weights = GoalBucketWeights(strength=0.33, hypertrophy=0.33, endurance=0.34)

        w_conditioning = goal_weights.conditioning_weight
        w_hypertrophy = goal_weights.hypertrophy_weight

        rf = w_conditioning / w_total if w_total > 0 else 0.0
        rc = (goal_weights.endurance + 0.5 * goal_weights.fat_loss) / 10.0 if w_total > 0 else 0.0
        ra = w_hypertrophy / w_total if w_total > 0 else 0.0

        raw_finisher_count = rf * total_sessions
        raw_cardio_day_count = rc * total_sessions
        raw_accessory_count = ra * total_sessions

        logger.info(
            f"[SessionTypeCalculator] Raw allocation: "
            f"RF={rf:.3f}, RC={rc:.3f}, RA={ra:.3f}, "
            f"finisher={raw_finisher_count:.2f}, cardio={raw_cardio_day_count:.2f}, "
            f"accessory={raw_accessory_count:.2f}"
        )

        return SessionTypeTargets(
            target_accessory_count=int(raw_accessory_count),
            target_finisher_count=int(raw_finisher_count),
            target_cardio_day_count=int(raw_cardio_day_count),
            total_sessions=total_sessions,
            raw_accessory_ratio=ra,
            raw_finisher_ratio=rf,
            raw_cardio_day_ratio=rc,
        )

    def _apply_rounding_rules(
        self,
        raw_targets: SessionTypeTargets,
        preferences: SessionTypePreferences,
        total_sessions: int,
    ) -> SessionTypeTargets:
        logger.info("[SessionTypeCalculator] Applying rounding rules")

        finisher_strategy = self._get_rounding_strategy("finisher")
        cardio_strategy = self._get_rounding_strategy("cardio_day")
        accessory_strategy = self._get_rounding_strategy("accessory")

        rounded_finisher = self._round_value(
            raw_targets.raw_finisher_ratio * total_sessions,
            finisher_strategy,
        )

        rounded_cardio = self._round_value(
            raw_targets.raw_cardio_day_ratio * total_sessions,
            cardio_strategy,
        )

        rounded_accessory = self._round_value(
            raw_targets.raw_accessory_ratio * total_sessions,
            accessory_strategy,
        )

        total_assigned = rounded_accessory + rounded_finisher + rounded_cardio

        if total_assigned > total_sessions:
            excess = total_assigned - total_sessions
            if rounded_finisher > 0:
                rounded_finisher = max(0, rounded_finisher - excess)
            elif rounded_accessory > 0:
                rounded_accessory = max(0, rounded_accessory - excess)
            elif rounded_cardio > 0:
                rounded_cardio = max(0, rounded_cardio - excess)
        elif total_assigned < total_sessions:
            deficit = total_sessions - total_assigned
            rounded_accessory += deficit

        logger.info(
            f"[SessionTypeCalculator] Rounded: accessory={rounded_accessory}, "
            f"finisher={rounded_finisher}, cardio={rounded_cardio}, "
            f"total={rounded_accessory + rounded_finisher + rounded_cardio}/{total_sessions}"
        )

        return SessionTypeTargets(
            target_accessory_count=rounded_accessory,
            target_finisher_count=rounded_finisher,
            target_cardio_day_count=rounded_cardio,
            total_sessions=total_sessions,
        )

    def _get_rounding_strategy(self, session_type: str) -> RoundingStrategy:
        strategies = self.config.get("rounding_strategies", {})
        strategy_name = strategies.get(session_type, "round")

        if session_type == "finisher":
            return RoundingStrategy.CEIL
        elif session_type == "cardio_day":
            return RoundingStrategy.FLOOR
        else:
            return RoundingStrategy(strategy_name)

    def _round_value(self, value: float, strategy: RoundingStrategy) -> int:
        if strategy == RoundingStrategy.CEIL:
            return math.ceil(value)
        elif strategy == RoundingStrategy.FLOOR:
            return math.floor(value)
        else:
            return round(value)

    def _apply_user_preferences(
        self,
        targets: SessionTypeTargets,
        preferences: SessionTypePreferences,
        total_sessions: int,
    ) -> SessionTypeTargets:
        logger.info(
            f"[SessionTypeCalculator] Applying cardio preference: {preferences.cardio_preference}"
        )

        cardio_preference = preferences.cardio_preference

        if cardio_preference == CardioPreferenceMode.FINISHER:
            new_targets = SessionTypeTargets(
                target_accessory_count=targets.target_accessory_count,
                target_finisher_count=targets.target_finisher_count + targets.target_cardio_day_count,
                target_cardio_day_count=0,
                total_sessions=total_sessions,
            )
        elif cardio_preference == CardioPreferenceMode.DEDICATED_DAY:
            new_targets = SessionTypeTargets(
                target_accessory_count=targets.target_accessory_count,
                target_finisher_count=0,
                target_cardio_day_count=targets.target_finisher_count + targets.target_cardio_day_count,
                total_sessions=total_sessions,
            )
        elif (
            cardio_preference == CardioPreferenceMode.BOTH_FINISHERS_AND_CARDIO_DAYS
            or cardio_preference == CardioPreferenceMode.MIXED
        ):
            new_targets = targets
        elif cardio_preference == CardioPreferenceMode.NONE:
            new_targets = SessionTypeTargets(
                target_accessory_count=targets.target_accessory_count + targets.target_finisher_count + targets.target_cardio_day_count,
                target_finisher_count=0,
                target_cardio_day_count=0,
                total_sessions=total_sessions,
            )
        else:
            logger.warning(f"[SessionTypeCalculator] Unknown cardio preference: {cardio_preference}")
            new_targets = targets

        logger.info(
            f"[SessionTypeCalculator] After preferences: accessory={new_targets.target_accessory_count}, "
            f"finisher={new_targets.target_finisher_count}, cardio={new_targets.target_cardio_day_count}"
        )

        return new_targets

    def _handle_edge_cases(
        self,
        targets: SessionTypeTargets,
        goal_weights: GoalBucketWeights,
        preferences: SessionTypePreferences,
        total_sessions: int,
    ) -> SessionTypeTargets:
        logger.info("[SessionTypeCalculator] Handling edge cases")

        accessory_count = targets.target_accessory_count
        finisher_count = targets.target_finisher_count
        cardio_count = targets.target_cardio_day_count

        if accessory_count < self.min_lifting_days:
            deficit = self.min_lifting_days - accessory_count
            if finisher_count > 0:
                finisher_count = max(0, finisher_count - deficit)
            elif cardio_count > 0:
                cardio_count = max(0, cardio_count - deficit)
            accessory_count = self.min_lifting_days
            logger.info(
                f"[SessionTypeCalculator] Enforced minimum lifting days: {accessory_count}"
            )

        max_cardio_allowed = int(total_sessions * self.max_cardio_pct)
        if cardio_count > max_cardio_allowed:
            excess = cardio_count - max_cardio_allowed
            cardio_count = max_cardio_allowed
            finisher_count += excess
            logger.info(
                f"[SessionTypeCalculator] Limited cardio days to {max_cardio_allowed}, "
                f"added {excess} finishers"
            )

        max_finishers_allowed = preferences.max_finishers_per_week
        if finisher_count > max_finishers_allowed:
            excess = finisher_count - max_finishers_allowed
            finisher_count = max_finishers_allowed
            accessory_count += excess
            logger.info(
                f"[SessionTypeCalculator] Limited finishers to {max_finishers_allowed}, "
                f"added {excess} accessories"
            )

        return SessionTypeTargets(
            target_accessory_count=accessory_count,
            target_finisher_count=finisher_count,
            target_cardio_day_count=cardio_count,
            total_sessions=total_sessions,
        )

    def _validate_targets(self, targets: SessionTypeTargets, total_sessions: int):
        total_assigned = (
            targets.target_accessory_count
            + targets.target_finisher_count
            + targets.target_cardio_day_count
        )

        if total_assigned != total_sessions:
            logger.warning(
                f"[SessionTypeCalculator] Allocation mismatch: assigned={total_assigned}, "
                f"total={total_sessions}"
            )

        if targets.allocation_accuracy < self.min_allocation_accuracy:
            logger.warning(
                f"[SessionTypeCalculator] Low allocation accuracy: {targets.allocation_accuracy:.2%} "
                f"(threshold: {self.min_allocation_accuracy:.2%})"
            )

        if any(
            abs(error) > self.rounding_drift_threshold
            for error in targets.rounding_errors.values()
        ):
            logger.warning(
                f"[SessionTypeCalculator] Significant rounding errors: {targets.rounding_errors}"
            )

        if targets.target_accessory_count < self.min_lifting_days:
            logger.warning(
                f"[SessionTypeCalculator] Insufficient lifting days: {targets.target_accessory_count} "
                f"(minimum: {self.min_lifting_days})"
            )
