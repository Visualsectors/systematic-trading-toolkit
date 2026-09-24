"""Stateful change detection over deterministic risk registers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from .levels import LevelPlan
from .models import Severity, require_finite, require_iso_datetime, require_ticker
from .risk import RiskRegister

EventType = Literal[
    "new_flag",
    "severity_increased",
    "severity_decreased",
    "flag_changed",
    "resolved",
    "evaluation_failed",
    "evaluation_recovered",
    "invalidation_breached",
    "entered_entry_zone",
    "reached_reassessment_zone",
]

EVENT_TYPES = {
    "new_flag",
    "severity_increased",
    "severity_decreased",
    "flag_changed",
    "resolved",
    "evaluation_failed",
    "evaluation_recovered",
    "invalidation_breached",
    "entered_entry_zone",
    "reached_reassessment_zone",
}


@dataclass(frozen=True, slots=True)
class TrackedRisk:
    id: str
    severity: Severity
    statement: str

    def __post_init__(self) -> None:
        if self.severity not in ("low", "medium", "high"):
            raise ValueError("tracked risk severity is invalid")
        if not self.id.strip() or not self.statement.strip():
            raise ValueError("tracked risk id and statement are required")


@dataclass(frozen=True, slots=True)
class MonitorEvent:
    type: EventType
    observed_at: str
    risk_id: str | None
    message: str

    def __post_init__(self) -> None:
        require_iso_datetime(self.observed_at, "monitor_event.observed_at")
        if self.type not in EVENT_TYPES:
            raise ValueError("monitor event type is invalid")
        if not self.message.strip():
            raise ValueError("monitor event message is required")


@dataclass(frozen=True, slots=True)
class TrackedPlan:
    direction: Literal["long", "short"]
    entry_low: float
    entry_high: float
    invalidation_price: float
    reassessment_low: float | None = None
    reassessment_high: float | None = None

    def __post_init__(self) -> None:
        if self.direction not in ("long", "short"):
            raise ValueError("tracked plan direction is invalid")
        for name in ("entry_low", "entry_high", "invalidation_price"):
            require_finite(getattr(self, name), f"tracked_plan.{name}", positive=True)
        if self.entry_low > self.entry_high:
            raise ValueError("tracked plan entry zone is inverted")
        if (self.reassessment_low is None) != (self.reassessment_high is None):
            raise ValueError("tracked plan reassessment zone must have both bounds")
        if self.reassessment_low is not None and self.reassessment_high is not None:
            require_finite(self.reassessment_low, "tracked_plan.reassessment_low", positive=True)
            require_finite(self.reassessment_high, "tracked_plan.reassessment_high", positive=True)
            if self.reassessment_low > self.reassessment_high:
                raise ValueError("tracked plan reassessment zone is inverted")


@dataclass(frozen=True, slots=True)
class MonitorState:
    ticker: str
    evaluated_at: str
    active: tuple[TrackedRisk, ...] = ()
    failure: str | None = None
    plan: TrackedPlan | None = None
    invalidation_breached: bool = False
    inside_entry_zone: bool = False
    inside_reassessment_zone: bool = False

    def __post_init__(self) -> None:
        require_ticker(self.ticker)
        require_iso_datetime(self.evaluated_at, "monitor_state.evaluated_at")
        ids = [item.id for item in self.active]
        if len(ids) != len(set(ids)):
            raise ValueError("monitor state risk IDs must be unique")
        if self.failure is not None and not self.failure.strip():
            raise ValueError("monitor state failure must be non-empty")
        for name in ("invalidation_breached", "inside_entry_zone", "inside_reassessment_zone"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"monitor state {name} must be boolean")


@dataclass(frozen=True, slots=True)
class MonitorResult:
    state: MonitorState
    events: tuple[MonitorEvent, ...]


def _tracked_plan(plan: LevelPlan | None) -> TrackedPlan | None:
    if plan is None or plan.entry_zone is None or plan.invalidation_price is None:
        return None
    return TrackedPlan(
        direction=plan.direction,
        entry_low=plan.entry_zone.low,
        entry_high=plan.entry_zone.high,
        invalidation_price=plan.invalidation_price,
        reassessment_low=None if plan.reassessment_zone is None else plan.reassessment_zone.low,
        reassessment_high=None if plan.reassessment_zone is None else plan.reassessment_zone.high,
    )


def _inside(price: float, low: float | None, high: float | None) -> bool:
    return low is not None and high is not None and low <= price <= high


def evaluate_monitor(
    previous: MonitorState | None,
    *,
    observed_at: str,
    register: RiskRegister | None = None,
    failure: str | None = None,
    ticker: str | None = None,
    current_price: float | None = None,
    level_plan: LevelPlan | None = None,
) -> MonitorResult:
    """Compare risk state; a failed evaluation never emits a false all-clear."""
    require_iso_datetime(observed_at, "observed_at")
    if previous is not None:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        prior_time = datetime.fromisoformat(previous.evaluated_at.replace("Z", "+00:00"))
        if observed <= prior_time:
            raise ValueError("observed_at must be later than the previous evaluation")
    if (register is None) == (failure is None):
        raise ValueError("provide exactly one of register or failure")
    if failure is not None:
        clean = failure.strip()
        if not clean:
            raise ValueError("failure must be non-empty")
        state_ticker = previous.ticker if previous else require_ticker(ticker or "")
        active = previous.active if previous else ()
        events = () if previous and previous.failure == clean else (
            MonitorEvent("evaluation_failed", observed_at, None, f"Monitoring evaluation failed: {clean}"),
        )
        return MonitorResult(
            MonitorState(
                state_ticker,
                observed_at,
                active,
                clean,
                previous.plan if previous else _tracked_plan(level_plan),
                previous.invalidation_breached if previous else False,
                previous.inside_entry_zone if previous else False,
                previous.inside_reassessment_zone if previous else False,
            ),
            events,
        )

    assert register is not None
    if previous is not None and previous.ticker != register.ticker:
        raise ValueError("previous state ticker does not match register ticker")
    current = {
        flag.id: TrackedRisk(flag.id, flag.severity, flag.statement)
        for flag in register.flags
    }
    before = {item.id: item for item in previous.active} if previous else {}
    severity_rank = {"low": 1, "medium": 2, "high": 3}
    events: list[MonitorEvent] = []
    if previous and previous.failure:
        events.append(MonitorEvent("evaluation_recovered", observed_at, None, "Monitoring evaluation recovered."))
    for risk_id, item in sorted(current.items()):
        prior = before.get(risk_id)
        if prior is None:
            events.append(MonitorEvent("new_flag", observed_at, risk_id, item.statement))
        elif severity_rank[item.severity] > severity_rank[prior.severity]:
            events.append(
                MonitorEvent(
                    "severity_increased",
                    observed_at,
                    risk_id,
                    f"Severity increased from {prior.severity} to {item.severity}: {item.statement}",
                )
            )
        elif severity_rank[item.severity] < severity_rank[prior.severity]:
            events.append(
                MonitorEvent(
                    "severity_decreased",
                    observed_at,
                    risk_id,
                    f"Severity decreased from {prior.severity} to {item.severity}: {item.statement}",
                )
            )
        if prior is not None and item.statement != prior.statement:
            events.append(
                MonitorEvent("flag_changed", observed_at, risk_id, f"Flag statement changed: {item.statement}")
            )
    for risk_id, item in sorted(before.items()):
        if risk_id not in current:
            events.append(MonitorEvent("resolved", observed_at, risk_id, f"Flag no longer active: {item.statement}"))
    plan = previous.plan if previous and previous.plan is not None else _tracked_plan(level_plan)
    breached = previous.invalidation_breached if previous else False
    in_entry = previous.inside_entry_zone if previous else False
    in_reassessment = previous.inside_reassessment_zone if previous else False
    if current_price is not None:
        price = require_finite(current_price, "current_price", positive=True)
        if plan is not None:
            now_breached = (
                price <= plan.invalidation_price
                if plan.direction == "long"
                else price >= plan.invalidation_price
            )
            now_entry = _inside(price, plan.entry_low, plan.entry_high)
            now_reassessment = _inside(price, plan.reassessment_low, plan.reassessment_high)
            if now_breached and not breached:
                events.append(
                    MonitorEvent(
                        "invalidation_breached",
                        observed_at,
                        "level-invalidation",
                        f"Price {price:.2f} breached the saved {plan.direction} invalidation at "
                        f"{plan.invalidation_price:.2f}.",
                    )
                )
            if now_breached:
                events = [
                    event
                    for event in events
                    if not (event.type == "resolved" and event.risk_id == "level-invalidation")
                ]
            if now_entry and not in_entry:
                events.append(
                    MonitorEvent(
                        "entered_entry_zone",
                        observed_at,
                        None,
                        f"Price {price:.2f} entered the saved entry zone "
                        f"{plan.entry_low:.2f}-{plan.entry_high:.2f}.",
                    )
                )
            if now_reassessment and not in_reassessment:
                events.append(
                    MonitorEvent(
                        "reached_reassessment_zone",
                        observed_at,
                        None,
                        f"Price {price:.2f} reached the saved reassessment zone "
                        f"{plan.reassessment_low:.2f}-{plan.reassessment_high:.2f}.",
                    )
                )
            breached, in_entry, in_reassessment = now_breached, now_entry, now_reassessment
    state = MonitorState(
        register.ticker,
        observed_at,
        tuple(current[key] for key in sorted(current)),
        None,
        plan,
        breached,
        in_entry,
        in_reassessment,
    )
    return MonitorResult(state, tuple(events))
