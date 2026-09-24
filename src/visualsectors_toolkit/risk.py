"""Deterministic, evidence-linked tailwind/headwind risk registers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .levels import LevelPlan
from .models import MarketSnapshot, RiskKind, Severity, require_iso_datetime, require_ticker


@dataclass(frozen=True, slots=True)
class RiskFlag:
    id: str
    kind: RiskKind
    severity: Severity
    statement: str
    trigger: str
    reassessment_action: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in ("headwind", "tailwind", "uncertainty"):
            raise ValueError("risk kind is invalid")
        if self.severity not in ("low", "medium", "high"):
            raise ValueError("risk severity is invalid")
        if any(not isinstance(item, str) or not item.strip() for item in (
            self.id, self.statement, self.trigger, self.reassessment_action
        )):
            raise ValueError("risk id, statement, trigger and reassessment action are required")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence_ids):
            raise ValueError("risk evidence IDs must be non-empty strings")


@dataclass(frozen=True, slots=True)
class RiskRegister:
    ticker: str
    as_of: str
    flags: tuple[RiskFlag, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        require_ticker(self.ticker)
        require_iso_datetime(self.as_of, "risk_register.as_of")
        ids = [flag.id for flag in self.flags]
        if len(ids) != len(set(ids)):
            raise ValueError("risk flag IDs must be unique")


def build_risk_register(snapshot: MarketSnapshot, *, level_plan: LevelPlan | None = None) -> RiskRegister:
    """Create explicit conditions to monitor without inventing unavailable risks."""
    flags: list[RiskFlag] = []
    if level_plan and level_plan.invalidation_price is not None:
        relation = "below" if level_plan.direction == "long" else "above"
        flags.append(
            RiskFlag(
                id="level-invalidation",
                kind="headwind",
                severity="high",
                statement="The planned level scenario has a defined invalidation boundary.",
                trigger=f"Price closes {relation} {level_plan.invalidation_price:.2f}.",
                reassessment_action="Reassess or retire the level-based thesis; do not move the boundary silently.",
                evidence_ids=(f"derived:{snapshot.ticker}:invalidation",),
            )
        )
    if snapshot.days_to_earnings is not None and 0 <= snapshot.days_to_earnings <= 21:
        severity: Severity = "high" if snapshot.days_to_earnings <= 7 else "medium"
        flags.append(
            RiskFlag(
                id="earnings-window",
                kind="uncertainty",
                severity=severity,
                statement=f"A scheduled earnings event is {snapshot.days_to_earnings} day(s) away.",
                trigger="The earnings date or released results change the information set.",
                reassessment_action="Recheck the thesis, gap risk, position size, and invalidation plan.",
                evidence_ids=(f"derived:{snapshot.ticker}:earnings-window",),
            )
        )
    if snapshot.sma200 is not None and snapshot.price < snapshot.sma200:
        flags.append(
            RiskFlag(
                id="below-sma200",
                kind="headwind",
                severity="medium",
                statement="Observed price is below the 200-session moving average.",
                trigger=f"Price remains below {snapshot.sma200:.2f} at the next review.",
                reassessment_action="Review whether the thesis depends on a long-term uptrend.",
                evidence_ids=(f"derived:{snapshot.ticker}:sma200", f"derived:{snapshot.ticker}:price"),
            )
        )
    if snapshot.volatility_20d_pct is not None and snapshot.volatility_20d_pct >= 30:
        severity = "high" if snapshot.volatility_20d_pct >= 45 else "medium"
        flags.append(
            RiskFlag(
                id="elevated-volatility",
                kind="uncertainty",
                severity=severity,
                statement=f"20-session volatility is {snapshot.volatility_20d_pct:.2f}%.",
                trigger="Volatility rises further or invalidates the assumptions used for sizing.",
                reassessment_action="Recalculate size with current inputs and review gap/slippage tolerance.",
                evidence_ids=(f"derived:{snapshot.ticker}:volatility20d",),
            )
        )
    for item in snapshot.evidence:
        if item.stance == "neutral":
            continue
        kind: RiskKind = "tailwind" if item.stance == "support" else "headwind"
        flags.append(
            RiskFlag(
                id=f"evidence-{item.id}",
                kind=kind,
                severity="low" if kind == "tailwind" else "medium",
                statement=item.statement,
                trigger="The cited evidence changes, expires, or is contradicted by a newer source.",
                reassessment_action="Refresh the evidence and reconsider its bearing on the thesis.",
                evidence_ids=(item.id,),
            )
        )
    for warning in snapshot.warnings:
        warning_id = sha256(warning.encode("utf-8")).hexdigest()[:12]
        flags.append(
            RiskFlag(
                id=f"data-warning-{warning_id}",
                kind="uncertainty",
                severity="medium",
                statement=warning,
                trigger="The missing or stale field is needed for the next decision.",
                reassessment_action="Acquire and validate the field; do not substitute zero or a neutral value.",
            )
        )
    flags.sort(key=lambda item: ({"high": 0, "medium": 1, "low": 2}[item.severity], item.id))
    return RiskRegister(
        ticker=snapshot.ticker,
        as_of=snapshot.as_of,
        flags=tuple(flags),
        warnings=(
            "Flags are review conditions, not predictions or automated execution instructions.",
            "Absence of a flag means absence of supplied evidence, not absence of risk.",
        ),
    )
