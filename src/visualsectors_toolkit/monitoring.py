"""Stateful change detection over deterministic risk registers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import Severity, require_iso_datetime, require_ticker
from .risk import RiskRegister

EventType = Literal["new_flag", "severity_increased", "resolved", "evaluation_failed", "evaluation_recovered"]


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
        if self.type not in ("new_flag", "severity_increased", "resolved", "evaluation_failed", "evaluation_recovered"):
            raise ValueError("monitor event type is invalid")
        if not self.message.strip():
            raise ValueError("monitor event message is required")


@dataclass(frozen=True, slots=True)
class MonitorState:
    ticker: str
    evaluated_at: str
    active: tuple[TrackedRisk, ...] = ()
    failure: str | None = None

    def __post_init__(self) -> None:
        require_ticker(self.ticker)
        require_iso_datetime(self.evaluated_at, "monitor_state.evaluated_at")
        ids = [item.id for item in self.active]
        if len(ids) != len(set(ids)):
            raise ValueError("monitor state risk IDs must be unique")
        if self.failure is not None and not self.failure.strip():
            raise ValueError("monitor state failure must be non-empty")


@dataclass(frozen=True, slots=True)
class MonitorResult:
    state: MonitorState
    events: tuple[MonitorEvent, ...]


def evaluate_monitor(
    previous: MonitorState | None,
    *,
    observed_at: str,
    register: RiskRegister | None = None,
    failure: str | None = None,
) -> MonitorResult:
    """Compare risk state; a failed evaluation never emits a false all-clear."""
    require_iso_datetime(observed_at, "observed_at")
    if (register is None) == (failure is None):
        raise ValueError("provide exactly one of register or failure")
    if failure is not None:
        clean = failure.strip()
        if not clean:
            raise ValueError("failure must be non-empty")
        ticker = previous.ticker if previous else "UNKNOWN"
        active = previous.active if previous else ()
        events = () if previous and previous.failure == clean else (
            MonitorEvent("evaluation_failed", observed_at, None, f"Monitoring evaluation failed: {clean}"),
        )
        return MonitorResult(MonitorState(ticker, observed_at, active, clean), events)

    assert register is not None
    if previous is not None and previous.ticker != register.ticker:
        raise ValueError("previous state ticker does not match register ticker")
    current = {
        flag.id: TrackedRisk(flag.id, flag.severity, flag.statement)
        for flag in register.flags
        if flag.kind != "tailwind"
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
    for risk_id, item in sorted(before.items()):
        if risk_id not in current:
            events.append(MonitorEvent("resolved", observed_at, risk_id, f"Flag no longer active: {item.statement}"))
    state = MonitorState(register.ticker, observed_at, tuple(current[key] for key in sorted(current)), None)
    return MonitorResult(state, tuple(events))
