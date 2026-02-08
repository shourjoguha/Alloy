from dataclasses import dataclass, field
from typing import Literal
from app.models.session_allocation import SessionTypePreferences, CardioPreferenceMode


@dataclass(frozen=True)
class GoalWeights:
    weight: int
    value: str


@dataclass(frozen=True)
class UserSettings:
    cardio_preference: CardioPreferenceMode = CardioPreferenceMode.FINISHER
    max_finishers_per_week: int = 3
    max_cardio_days_per_week: int = 2
    min_finisher_gap_days: int = 2
    max_cardio_gap_days: int = 3
    strict_validation: bool = True
    endurance_type: str = "auto"
    avoid_cardio_days: bool = False


@dataclass(frozen=True)
class AllocationContext:
    user_settings: UserSettings
    goal_weights: list[GoalWeights]
    preferences: SessionTypePreferences
    microcycle_id: int = 0


@dataclass
class SessionIntent:
    session_id: int
    session_type: Literal["finisher", "accessory", "cardio_day", "conditioning_day"]
    movement_patterns: list[str] = field(default_factory=list)
    auxiliary_tags: set[str] = field(default_factory=set)

    def add_movement_pattern(self, pattern: str) -> None:
        if pattern not in self.movement_patterns:
            self.movement_patterns.append(pattern)

    def add_auxiliary_tag(self, tag: str) -> None:
        self.auxiliary_tags.add(tag)

    def remove_auxiliary_tag(self, tag: str) -> None:
        self.auxiliary_tags.discard(tag)

    def to_flat_tags(self) -> list[str]:
        return self.movement_patterns + list(self.auxiliary_tags)

    @classmethod
    def from_flat_tags(
        cls, session_id: int, flat_tags: list[str], session_type: str = "accessory"
    ) -> "SessionIntent":
        auxiliary_tags = {"prefer_finisher", "prefer_accessory", "prefer_circuit"}
        movement_patterns = [t for t in flat_tags if t not in auxiliary_tags]
        auxiliary = {t for t in flat_tags if t in auxiliary_tags}
        return cls(
            session_id=session_id,
            session_type=session_type,
            movement_patterns=movement_patterns,
            auxiliary_tags=auxiliary,
        )


@dataclass
class AllocationResult:
    microcycle_id: int
    session_intents: dict[int, SessionIntent]
    targets: dict[str, int]

    def get_session_intent(self, session_id: int) -> SessionIntent:
        if session_id not in self.session_intents:
            raise ValueError(f"No allocation found for session_id {session_id}")
        return self.session_intents[session_id]

    def get_allocated_type(self, session_id: int) -> str:
        intent = self.get_session_intent(session_id)
        return intent.session_type

    def validate_session_content(self, session_id: int, content: dict) -> bool:
        intent = self.get_session_intent(session_id)
        allocated_type = intent.session_type

        has_finisher = bool(content.get("finisher"))
        has_accessory = bool(content.get("accessory"))
        main_content = content.get("main")
        main_items = []
        if isinstance(main_content, dict):
            main_items = main_content.values()
        elif isinstance(main_content, list):
            main_items = main_content

        has_cardio_block = bool(
            main_content
            and any(
                "cardio" in str(b).lower() or "conditioning" in str(b).lower()
                for b in main_items
            )
        )

        if allocated_type == "finisher":
            return has_finisher and not has_accessory
        elif allocated_type == "accessory":
            return has_accessory and not has_finisher
        elif allocated_type == "cardio_day":
            return has_cardio_block and not has_finisher and not has_accessory
        return False
