import logging
from typing import List, Set, Optional
from app.models.session_allocation import (
    MicrocycleAllocation,
    SessionTypeTargets,
    SessionTypePreferences,
)

logger = logging.getLogger(__name__)


class SessionTypeDistributor:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.min_finisher_gap_days = self.config.get("min_finisher_gap_days", 2)
        self.max_cardio_gap_days = self.config.get("max_cardio_gap_days", 3)
        self.strict_validation = self.config.get("strict_validation", True)

        if self.min_finisher_gap_days < 0:
            raise ValueError(f"min_finisher_gap_days must be >= 0, got {self.min_finisher_gap_days}")
        if self.max_cardio_gap_days < 0:
            raise ValueError(f"max_cardio_gap_days must be >= 0, got {self.max_cardio_gap_days}")

    def distribute_session_types(
        self,
        session_ids: List[int],
        session_types: List[str],
        targets: SessionTypeTargets,
        preferences: SessionTypePreferences,
    ) -> MicrocycleAllocation:
        microcycle_id = session_ids[0] if session_ids else 0
        logger.info(
            f"[SessionTypeDistributor] Distributing session types for microcycle {microcycle_id}, "
            f"{len(session_ids)} sessions, targets: "
            f"accessory={targets.target_accessory_count}, "
            f"finisher={targets.target_finisher_count}, "
            f"cardio={targets.target_cardio_day_count}"
        )

        allocation = MicrocycleAllocation(
            microcycle_id=microcycle_id,
            targets=targets,
            preferences=preferences,
        )

        if not session_ids:
            logger.warning("[SessionTypeDistributor] No sessions to distribute")
            return allocation

        finisher_indices = self._distribute_finishers(
            session_ids, session_types, targets, preferences
        )

        cardio_day_indices = self._distribute_dedicated_cardio_days(
            session_ids, session_types, targets, finisher_indices
        )

        accessory_indices = self._assign_accessories(
            session_ids, finisher_indices, cardio_day_indices
        )

        self._assign_finisher_accessory_tags(
            allocation,
            session_ids,
            finisher_indices,
            accessory_indices,
        )

        for idx, session_id in enumerate(session_ids):
            if idx in finisher_indices:
                allocation.assigned_session_types[session_id] = "finisher"
                allocation.finisher_session_indices.append(idx)
            elif idx in cardio_day_indices:
                allocation.assigned_session_types[session_id] = "cardio_day"
                allocation.cardio_day_indices.append(idx)
            elif idx in accessory_indices:
                allocation.assigned_session_types[session_id] = "accessory"
                allocation.accessory_session_indices.append(idx)
            else:
                allocation.assigned_session_types[session_id] = "accessory"
                allocation.accessory_session_indices.append(idx)

        self._validate_allocation(allocation, session_ids)

        logger.info(
            f"[SessionTypeDistributor] Distribution complete: "
            f"accessory={len(allocation.accessory_session_indices)}, "
            f"finisher={len(allocation.finisher_session_indices)}, "
            f"cardio={len(allocation.cardio_day_indices)}"
        )

        return allocation

    def _distribute_finishers(
        self,
        session_ids: List[int],
        session_types: List[str],
        targets: SessionTypeTargets,
        preferences: SessionTypePreferences,
    ) -> Set[int]:
        target_count = targets.target_finisher_count
        if target_count == 0:
            logger.debug("[SessionTypeDistributor] No finishers to distribute")
            return set()

        logger.info(f"[SessionTypeDistributor] Distributing {target_count} finishers")

        valid_indices = [
            idx
            for idx, stype in enumerate(session_types)
            if stype not in ["CARDIO", "RECOVERY"]
        ]

        if len(valid_indices) < target_count:
            logger.warning(
                f"[SessionTypeDistributor] Not enough valid sessions for finishers: "
                f"requested={target_count}, available={len(valid_indices)}"
            )
            target_count = len(valid_indices)

        if target_count == 0:
            return set()

        finisher_indices = set()
        step = len(valid_indices) // target_count if target_count > 0 else 0
        step = max(step, 1)

        current_idx = 0
        for _ in range(target_count):
            if current_idx >= len(valid_indices):
                break

            idx = valid_indices[current_idx]

            if finisher_indices:
                last_finisher = max(finisher_indices)
                if idx - last_finisher < self.min_finisher_gap_days:
                    next_available = next(
                        (i for i in valid_indices if i > last_finisher + self.min_finisher_gap_days - 1),
                        idx,
                    )
                    idx = next_available

            finisher_indices.add(idx)
            current_idx += step

        logger.info(f"[SessionTypeDistributor] Finisher indices: {sorted(finisher_indices)}")

        return finisher_indices

    def _distribute_dedicated_cardio_days(
        self,
        session_ids: List[int],
        session_types: List[str],
        targets: SessionTypeTargets,
        existing_finisher_indices: set,
    ) -> set:
        target_count = targets.target_cardio_day_count
        if target_count == 0:
            logger.debug("[SessionTypeDistributor] No cardio days to distribute")
            return set()

        logger.info(f"[SessionTypeDistributor] Distributing {target_count} cardio days")

        cardio_indices = set()

        cardio_session_indices = [
            idx for idx, stype in enumerate(session_types) if stype == "CARDIO"
        ]

        for idx in cardio_session_indices:
            if len(cardio_indices) >= target_count:
                break

            if idx in existing_finisher_indices:
                continue

            cardio_indices.add(idx)

        remaining_needed = target_count - len(cardio_indices)
        if remaining_needed > 0:
            lifting_indices = [
                idx for idx, stype in enumerate(session_types)
                if stype not in ["CARDIO", "RECOVERY", "MOBILITY", "CONDITIONING"]
                and idx not in existing_finisher_indices
                and idx not in cardio_indices
            ]

            if lifting_indices:
                step = max(1, len(lifting_indices) // remaining_needed)
                for i in range(0, len(lifting_indices), step):
                    if len(cardio_indices) >= target_count:
                        break
                    cardio_indices.add(lifting_indices[i])

        logger.info(f"[SessionTypeDistributor] Cardio day indices: {sorted(cardio_indices)}")

        return cardio_indices

    def _assign_accessories(
        self,
        session_ids: List[int],
        finisher_indices: set,
        cardio_day_indices: set,
    ) -> set:
        reserved_indices = finisher_indices | cardio_day_indices
        accessory_indices = set(
            idx for idx in range(len(session_ids)) if idx not in reserved_indices
        )

        logger.debug(
            f"[SessionTypeDistributor] Assigned {len(accessory_indices)} accessory sessions"
        )

        return accessory_indices

    def _assign_finisher_accessory_tags(
        self,
        allocation: MicrocycleAllocation,
        session_ids: List[int],
        finisher_indices: set,
        accessory_indices: set,
    ):
        for idx, session_id in enumerate(session_ids):
            allocation.assigned_session_types[session_id] = "accessory"

            if idx in finisher_indices:
                allocation.assigned_session_types[session_id] = "finisher"

        logger.debug(
            f"[SessionTypeDistributor] Assigned intent tags: "
            f"{len(finisher_indices)} finisher, {len(accessory_indices)} accessory"
        )

    def _validate_allocation(
        self, allocation: MicrocycleAllocation, session_ids: List[int]
    ):
        total_assigned = len(allocation.assigned_session_types)
        total_sessions = len(session_ids)

        if total_assigned != total_sessions:
            msg = (
                f"[SessionTypeDistributor] Allocation mismatch: assigned={total_assigned}, "
                f"total={total_sessions}"
            )
            if self.strict_validation:
                raise ValueError(msg)
            logger.warning(msg)

        actual_finishers = len(allocation.finisher_session_indices)
        actual_cardio = len(allocation.cardio_day_indices)
        actual_accessories = len(allocation.accessory_session_indices)

        target_finishers = allocation.targets.target_finisher_count
        target_cardio = allocation.targets.target_cardio_day_count
        target_accessories = allocation.targets.target_accessory_count

        mismatches = []
        if actual_finishers != target_finishers:
            mismatches.append(f"finisher: {actual_finishers} vs {target_finishers}")
        if actual_cardio != target_cardio:
            mismatches.append(f"cardio: {actual_cardio} vs {target_cardio}")
        if actual_accessories != target_accessories:
            mismatches.append(f"accessory: {actual_accessories} vs {target_accessories}")

        if mismatches:
            msg = (
                f"[SessionTypeDistributor] Target mismatches: {', '.join(mismatches)}"
            )
            if self.strict_validation:
                raise ValueError(msg)
            logger.warning(msg)

        finisher_sorted = sorted(allocation.finisher_session_indices)
        for i in range(1, len(finisher_sorted)):
            gap = finisher_sorted[i] - finisher_sorted[i - 1]
            if gap < self.min_finisher_gap_days:
                msg = (
                    f"[SessionTypeDistributor] Finishers too close: gap={gap}, "
                    f"indices={finisher_sorted[i-1]}, {finisher_sorted[i]}"
                )
                if self.strict_validation:
                    raise ValueError(msg)
                logger.warning(msg)
