"""Evidence-first, deterministic research briefs.

The module separates observations from interpretations and preserves data gaps.
It does not call a model, network, clock, filesystem, or hidden data source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .levels import LevelPlan
from .models import Evidence, MarketSnapshot

FindingKind = Literal["fact", "interpretation", "contrary_evidence", "data_gap"]


@dataclass(frozen=True, slots=True)
class ResearchFinding:
    kind: FindingKind
    statement: str
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResearchBlock:
    title: str
    findings: tuple[ResearchFinding, ...]


@dataclass(frozen=True, slots=True)
class ResearchBrief:
    ticker: str
    as_of: str
    thesis: str | None
    blocks: tuple[ResearchBlock, ...]
    evidence: tuple[Evidence, ...]
    warnings: tuple[str, ...]


def _derived(snapshot: MarketSnapshot, suffix: str, category: str, statement: str) -> Evidence:
    return Evidence(
        id=f"derived:{snapshot.ticker}:{suffix}",
        category=category,
        statement=statement,
        as_of=snapshot.as_of,
        source="dataset fields; deterministic calculation",
    )


def build_research_brief(
    snapshot: MarketSnapshot,
    *,
    thesis: str | None = None,
    level_plan: LevelPlan | None = None,
) -> ResearchBrief:
    """Build a replayable brief whose claims cite supplied or derived evidence."""
    clean_thesis = thesis.strip() if thesis and thesis.strip() else None
    evidence = list(snapshot.evidence)
    price = _derived(snapshot, "price", "market", f"Observed price: {snapshot.price:.2f}.")
    evidence.append(price)

    thesis_findings: list[ResearchFinding] = []
    if clean_thesis:
        supplied = Evidence(
            id=f"input:{snapshot.ticker}:thesis",
            category="thesis",
            statement=clean_thesis,
            as_of=snapshot.as_of,
            source="user-supplied thesis",
        )
        evidence.append(supplied)
        thesis_findings.append(ResearchFinding("fact", "Thesis under review: " + clean_thesis, (supplied.id,)))
    else:
        thesis_findings.append(ResearchFinding("data_gap", "No thesis was supplied for falsification."))

    technical: list[ResearchFinding] = [ResearchFinding("fact", price.statement, (price.id,))]
    technical_values = (
        ("rsi14", "RSI(14)", snapshot.rsi14),
        ("sma20", "SMA(20)", snapshot.sma20),
        ("sma50", "SMA(50)", snapshot.sma50),
        ("sma200", "SMA(200)", snapshot.sma200),
        ("momentum20d", "20-session momentum (%)", snapshot.momentum_20d_pct),
        ("volatility20d", "20-session volatility (%)", snapshot.volatility_20d_pct),
    )
    for suffix, label, value in technical_values:
        if value is None:
            technical.append(ResearchFinding("data_gap", f"{label} is unavailable."))
            continue
        item = _derived(snapshot, suffix, "technical", f"{label}: {value:.2f}.")
        evidence.append(item)
        technical.append(ResearchFinding("fact", item.statement, (item.id,)))

    if level_plan is None or level_plan.status != "ready" or level_plan.entry_zone is None:
        technical.append(ResearchFinding("data_gap", "No eligible entry zone was available; none was inferred."))
    else:
        item = _derived(
            snapshot,
            "entry-zone",
            "levels",
            f"Conditional {level_plan.direction} entry zone: "
            f"{level_plan.entry_zone.low:.2f}-{level_plan.entry_zone.high:.2f}.",
        )
        evidence.append(item)
        technical.append(ResearchFinding("interpretation", item.statement, (item.id,)))
        if level_plan.invalidation_price is not None:
            stop = _derived(
                snapshot,
                "invalidation",
                "levels",
                f"Scenario invalidation level: {level_plan.invalidation_price:.2f}.",
            )
            evidence.append(stop)
            technical.append(ResearchFinding("interpretation", stop.statement, (stop.id,)))

    fundamental: list[ResearchFinding] = []
    for suffix, label, value in (
        ("pe", "P/E ratio", snapshot.pe_ratio),
        ("earnings-growth", "Earnings growth (%)", snapshot.earnings_growth_pct),
    ):
        if value is None:
            fundamental.append(ResearchFinding("data_gap", f"{label} is unavailable."))
        else:
            item = _derived(snapshot, suffix, "fundamental", f"{label}: {value:.2f}.")
            evidence.append(item)
            fundamental.append(ResearchFinding("fact", item.statement, (item.id,)))
    if snapshot.days_to_earnings is None:
        fundamental.append(ResearchFinding("data_gap", "Days to the next earnings event is unavailable."))
    else:
        item = _derived(
            snapshot,
            "earnings-window",
            "event",
            f"Next earnings event is {snapshot.days_to_earnings} day(s) away.",
        )
        evidence.append(item)
        fundamental.append(ResearchFinding("fact", item.statement, (item.id,)))

    supplied_findings = [
        ResearchFinding("fact", item.statement, (item.id,))
        for item in snapshot.evidence
        if item.stance != "opposition"
    ]
    if not supplied_findings:
        supplied_findings.append(ResearchFinding("data_gap", "No news, macro, or catalyst evidence was supplied."))
    contrary = [
        ResearchFinding("contrary_evidence", item.statement, (item.id,))
        for item in snapshot.evidence
        if item.stance == "opposition"
    ]
    if not contrary:
        contrary.append(
            ResearchFinding(
                "data_gap",
                "No contrary evidence was supplied. This is a coverage gap, not confirmation of the thesis.",
            )
        )

    gaps = [ResearchFinding("data_gap", warning) for warning in snapshot.warnings]
    if not gaps:
        gaps.append(ResearchFinding("fact", "The dataset declared no additional row-level warnings."))

    return ResearchBrief(
        ticker=snapshot.ticker,
        as_of=snapshot.as_of,
        thesis=clean_thesis,
        blocks=(
            ResearchBlock("Thesis under review", tuple(thesis_findings)),
            ResearchBlock("Technical and level context", tuple(technical)),
            ResearchBlock("Fundamental and event context", tuple(fundamental)),
            ResearchBlock("News, macro and catalysts", tuple(supplied_findings)),
            ResearchBlock("Contrary evidence", tuple(contrary)),
            ResearchBlock("Coverage and data gaps", tuple(gaps)),
        ),
        evidence=tuple(evidence),
        warnings=(
            "Facts and interpretations are labeled separately; missing evidence is never treated as neutral evidence.",
            "The brief is research support, not a recommendation, forecast, or suitability assessment.",
        ),
    )
