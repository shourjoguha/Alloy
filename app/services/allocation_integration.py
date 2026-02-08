import logging
from typing import Any
from app.models.session_allocation import (
    CardioPreferenceMode,
    SessionTypePreferences,
    GoalBucketWeights,
)
from app.models.enums import Goal
from app.config.activity_distribution import (
    SESSION_TYPE_CALCULATOR_CONFIG,
    SESSION_TYPE_DISTRIBUTOR_CONFIG,
)
from app.services.allocation_context import (
    AllocationContext,
    AllocationResult,
    GoalWeights,
    SessionIntent,
    UserSettings,
)
from app.services.session_type_calculator import SessionTypeCalculator
from app.services.session_type_distributor import SessionTypeDistributor

logger = logging.getLogger(__name__)


class AllocationIntegrationService:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.calculator_config = SESSION_TYPE_CALCULATOR_CONFIG
        self.distributor_config = SESSION_TYPE_DISTRIBUTOR_CONFIG

    def create_allocation_context(
        self,
        user_settings: dict | None = None,
        wizard_goals: list[Any] | None = None,
        microcycle_id: int = 0,
    ) -> AllocationContext:
        base_settings = self._get_base_settings(user_settings)
        merged_preferences = self._merge_preferences(base_settings, wizard_goals)
        goal_weights_list = self._extract_goal_weights(wizard_goals)

        context = AllocationContext(
            user_settings=base_settings,
            goal_weights=goal_weights_list,
            preferences=merged_preferences,
            microcycle_id=microcycle_id,
        )

        logger.info(
            f"[AllocationIntegration] Created context for microcycle {microcycle_id}: "
            f"cardio_pref={merged_preferences.cardio_preference.value}, "
            f"max_finishers={merged_preferences.max_finishers_per_week}, "
            f"max_cardio={merged_preferences.max_cardio_days_per_week}"
        )

        return context

    def allocate_session_types(
        self,
        context: AllocationContext,
        session_ids: list[int],
        session_types: list[str],
    ) -> AllocationResult:
        calculator = SessionTypeCalculator(self.calculator_config)

        goal_weights_dict = {gw.value: gw.weight for gw in context.goal_weights}
        
        # Filter out any goals that aren't fields in GoalBucketWeights to avoid TypeError
        valid_fields = set(GoalBucketWeights.__annotations__.keys())
        filtered_weights = {k: v for k, v in goal_weights_dict.items() if k in valid_fields}
        goal_bucket_weights = GoalBucketWeights(**filtered_weights)

        targets = calculator.calculate_session_type_targets(
            total_sessions=len(session_ids),
            goal_weights=goal_bucket_weights,
            preferences=context.preferences,
        )

        distributor_config = self.distributor_config.copy()
        if context.user_settings:
            distributor_config["strict_validation"] = context.user_settings.strict_validation

        distributor = SessionTypeDistributor(distributor_config)
        allocation = distributor.distribute_session_types(
            session_ids=session_ids,
            session_types=session_types,
            targets=targets,
            preferences=context.preferences,
        )

        session_intents: dict[int, SessionIntent] = {}
        for session_id in session_ids:
            allocated_type = allocation.assigned_session_types.get(
                session_id, "accessory"
            )

            # Refine cardio_day based on endurance_type
            if allocated_type == "cardio_day":
                endurance_type = context.user_settings.endurance_type
                avoid_cardio = context.user_settings.avoid_cardio_days

                if avoid_cardio:
                    # If avoiding cardio, force conditioning for any allocated cardio days
                    allocated_type = "conditioning_day"
                elif endurance_type == "endurance_only":
                    # endurance_only maps to conditioning (metabolic/circuit)
                    allocated_type = "conditioning_day"
                elif endurance_type == "auto":
                    # If Fat Loss > Endurance -> Conditioning
                    fat_loss_weight = next((gw.weight for gw in context.goal_weights if gw.value == "fat_loss"), 0)
                    endurance_weight = next((gw.weight for gw in context.goal_weights if gw.value == "endurance"), 0)
                    if fat_loss_weight > endurance_weight:
                        allocated_type = "conditioning_day"

            intent = SessionIntent(
                session_id=session_id,
                session_type=allocated_type,
                movement_patterns=[],
                auxiliary_tags=set(),
            )

            if allocated_type == "finisher":
                intent.add_auxiliary_tag("prefer_finisher")
            elif allocated_type == "accessory":
                intent.add_auxiliary_tag("prefer_accessory")

            session_intents[session_id] = intent

        result = AllocationResult(
            microcycle_id=context.microcycle_id,
            session_intents=session_intents,
            targets={
                "accessory": targets.target_accessory_count,
                "finisher": targets.target_finisher_count,
                "cardio_day": targets.target_cardio_day_count,
            },
        )

        logger.info(
            f"[AllocationIntegration] Allocated session types: "
            f"accessory={len([i for i in session_intents.values() if i.session_type == 'accessory'])}, "
            f"finisher={len([i for i in session_intents.values() if i.session_type == 'finisher'])}, "
            f"cardio={len([i for i in session_intents.values() if i.session_type == 'cardio_day'])}, "
            f"conditioning={len([i for i in session_intents.values() if i.session_type == 'conditioning_day'])}"
        )

        return result

    def apply_movement_patterns_to_intents(
        self,
        result: AllocationResult,
        session_patterns: dict[int, list[str]],
    ) -> AllocationResult:
        for session_id, patterns in session_patterns.items():
            if session_id in result.session_intents:
                intent = result.session_intents[session_id]
                for pattern in patterns:
                    intent.add_movement_pattern(pattern)

        logger.info(
            f"[AllocationIntegration] Applied movement patterns to {len(session_patterns)} sessions"
        )

        return result

    def resolve_pattern_interference(
        self,
        result: AllocationResult,
        used_patterns: dict[int, list[str]],
        pattern_alternatives: dict[str, list[str]],
    ) -> AllocationResult:
        for session_id, intent in result.session_intents.items():
            if not intent.movement_patterns:
                continue

            current_day = session_id
            conflicting_patterns = []

            for pattern in intent.movement_patterns[:2]:
                if self._has_pattern_conflict(pattern, current_day, used_patterns):
                    conflicting_patterns.append(pattern)

            for pattern in conflicting_patterns:
                if pattern in intent.movement_patterns:
                    idx = intent.movement_patterns.index(pattern)
                    alternative = self._find_alternative_pattern(
                        pattern, current_day, used_patterns, pattern_alternatives
                    )
                    if alternative:
                        intent.movement_patterns[idx] = alternative
                        logger.info(
                            f"[AllocationIntegration] Session {session_id}: Replaced conflicting pattern "
                            f"'{pattern}' with '{alternative}'"
                        )

        return result

    def _get_base_settings(self, user_settings: dict | None) -> UserSettings:
        if user_settings is None:
            return UserSettings()

        return UserSettings(
            cardio_preference=CardioPreferenceMode(
                user_settings.get("cardio_preference", "finisher")
            ),
            max_finishers_per_week=user_settings.get("max_finishers_per_week", 3),
            max_cardio_days_per_week=user_settings.get("max_cardio_days_per_week", 2),
            min_finisher_gap_days=user_settings.get("min_finisher_gap_days", 2),
            max_cardio_gap_days=user_settings.get("max_cardio_gap_days", 3),
            strict_validation=user_settings.get("strict_validation", False),
            endurance_type=user_settings.get("endurance_type", "auto"),
            avoid_cardio_days=user_settings.get("avoid_cardio_days", False),
        )

    def _merge_preferences(
        self,
        base_settings: UserSettings,
        wizard_goals: list[Any] | None,
    ) -> SessionTypePreferences:
        cardio_pref = base_settings.cardio_preference
        
        # If avoid_cardio_days is True, and high endurance demand, override "finisher" pref
        # to ensure we allocate days (which will be converted to conditioning later).
        if base_settings.avoid_cardio_days and wizard_goals:
            endurance_weight = 0
            for goal in wizard_goals:
                g_val = getattr(getattr(goal, "goal", None), "value", None)
                w_val = getattr(goal, "weight", 0)
                if g_val == Goal.ENDURANCE.value:
                    endurance_weight = w_val
                    break
            
            if endurance_weight >= 6 and cardio_pref == CardioPreferenceMode.FINISHER:
                logger.info("[AllocationIntegration] Overriding 'finisher' preference to 'dedicated_day' due to high endurance + avoid_cardio_days")
                cardio_pref = CardioPreferenceMode.DEDICATED_DAY

        return SessionTypePreferences(
            cardio_preference=cardio_pref,
            max_finishers_per_week=base_settings.max_finishers_per_week,
            max_cardio_days_per_week=base_settings.max_cardio_days_per_week,
        )

    def _extract_goal_weights(
        self, wizard_goals: list[Any] | None
    ) -> list[GoalWeights]:
        if not wizard_goals:
            return []

        goal_weights = []
        for goal in wizard_goals:
            goal_value = getattr(getattr(goal, "goal", None), "value", None)
            weight_value = getattr(goal, "weight", None)

            if goal_value and isinstance(weight_value, int):
                goal_weights.append(GoalWeights(weight=weight_value, value=goal_value))

        return goal_weights

    def _has_pattern_conflict(
        self,
        pattern: str,
        current_day: int,
        used_patterns: dict[int, list[str]],
    ) -> bool:
        for day, patterns in used_patterns.items():
            if abs(day - current_day) <= 1:
                if pattern in patterns:
                    return True
        return False

    def _find_alternative_pattern(
        self,
        pattern: str,
        current_day: int,
        used_patterns: dict[int, list[str]],
        pattern_alternatives: dict[str, list[str]],
    ) -> str | None:
        if pattern not in pattern_alternatives:
            return None

        for alternative in pattern_alternatives[pattern]:
            if not self._has_pattern_conflict(alternative, current_day, used_patterns):
                return alternative

        return None
