"""Composable reference workflow for the bundled offline demonstration."""

from __future__ import annotations

from dataclasses import dataclass

from .levels import LevelPlan, build_level_plan
from .models import DatasetManifest, MarketSnapshot
from .providers import MarketDataProvider
from .research import ResearchBrief, build_research_brief
from .risk import RiskRegister, build_risk_register
from .screening import ScreenResult, run_screen
from .sizing import PortfolioSlotSize, SizingPick, StopRiskSize, size_by_portfolio_slots, size_by_stop_risk


@dataclass(frozen=True, slots=True)
class ToolkitRun:
    manifest: DatasetManifest
    screen: ScreenResult
    selected: MarketSnapshot
    level_plan: LevelPlan
    stop_risk_size: StopRiskSize
    portfolio_slot_size: PortfolioSlotSize
    research: ResearchBrief
    risk: RiskRegister


def run_reference_workflow(
    provider: MarketDataProvider,
    *,
    portfolio: float = 100_000,
    intended_holdings: int = 10,
    risk_fraction: float = 0.005,
    max_allocation_fraction: float = 0.10,
    thesis: str = "Price weakness near served support may merit research if the contrary evidence is contained.",
) -> ToolkitRun:
    screen = run_screen(provider.universe(), "oversold_at_support", limit=10)
    if not screen.candidates:
        raise ValueError("reference workflow requires at least one screen candidate")
    selected = provider.get(screen.candidates[0].ticker)
    plan = build_level_plan(
        ticker=selected.ticker,
        as_of=selected.as_of,
        direction="long",
        current_price=selected.price,
        atr=selected.atr14,
        levels=selected.levels,
    )
    if plan.entry_zone is None or plan.invalidation_price is None:
        raise ValueError("selected candidate has no complete level plan")
    stop_size = size_by_stop_risk(
        capital=portfolio,
        risk_fraction=risk_fraction,
        entry=plan.entry_zone.high,
        stop=plan.invalidation_price,
        max_allocation_fraction=max_allocation_fraction,
    )
    picks = [
        SizingPick(row.ticker, row.price, row.volatility_20d_pct)
        for row in provider.universe()
        if row.ticker in {item.ticker for item in screen.candidates}
    ]
    slot_size = size_by_portfolio_slots(
        portfolio=portfolio,
        intended_holdings=intended_holdings,
        picks=picks,
    )
    research = build_research_brief(selected, thesis=thesis, level_plan=plan)
    risk = build_risk_register(selected, level_plan=plan)
    return ToolkitRun(provider.manifest, screen, selected, plan, stop_size, slot_size, research, risk)
