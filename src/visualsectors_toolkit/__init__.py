"""Visual Sectors Systematic Trading Toolkit.

The public surface is deliberately small. Provider I/O lives behind
``MarketDataProvider``; every calculation below is deterministic over inputs.
"""

from .levels import build_level_plan, cluster_levels, nearest_zones
from .monitoring import MonitorState, evaluate_monitor
from .providers import JsonFileProvider, MarketDataProvider, SyntheticFixtureProvider
from .research import build_research_brief
from .risk import build_risk_register
from .screening import PRESETS, run_screen
from .sizing import size_by_portfolio_slots, size_by_stop_risk

__all__ = [
    "JsonFileProvider",
    "MarketDataProvider",
    "MonitorState",
    "PRESETS",
    "SyntheticFixtureProvider",
    "build_level_plan",
    "build_research_brief",
    "build_risk_register",
    "cluster_levels",
    "evaluate_monitor",
    "nearest_zones",
    "run_screen",
    "size_by_portfolio_slots",
    "size_by_stop_risk",
]

__version__ = "0.1.0"
