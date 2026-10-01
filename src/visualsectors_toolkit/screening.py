"""Disclosed screens that return candidates and explicit exclusions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Sequence

from .levels import latest_levels, nearest_zones
from .models import MarketSnapshot

PresetName = Literal["near_support", "oversold_at_support", "trend_continuation"]


@dataclass(frozen=True, slots=True)
class ScreenConfig:
    name: PresetName
    description: str
    minimum_price: float = 5.0
    minimum_average_dollar_volume: float = 5_000_000
    maximum_support_distance_atr: float = 1.5


@dataclass(frozen=True, slots=True)
class ScreenCandidate:
    ticker: str
    as_of: str
    price: float
    support_distance_atr: float | None
    matched_criteria: tuple[str, ...]
    rank_key: tuple[float | str, ...]


@dataclass(frozen=True, slots=True)
class ScreenExclusion:
    ticker: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScreenResult:
    preset: PresetName
    description: str
    ranking_method: str
    candidates: tuple[ScreenCandidate, ...]
    exclusions: tuple[ScreenExclusion, ...]
    coverage: int
    omitted_candidates: int
    warnings: tuple[str, ...]


PRESETS: dict[PresetName, ScreenConfig] = {
    "near_support": ScreenConfig(
        name="near_support",
        description="Liquid shares trading within 1.5 ATR of the nearest served support band.",
    ),
    "oversold_at_support": ScreenConfig(
        name="oversold_at_support",
        description="The near-support screen with RSI(14) at or below 35.",
    ),
    "trend_continuation": ScreenConfig(
        name="trend_continuation",
        description=(
            "Liquid shares with price, 50-session average, and 200-session average structurally ordered, "
            "near the 20-session average, "
            "with positive 20-session momentum."
        ),
    ),
}


def _base_reasons(row: MarketSnapshot, config: ScreenConfig) -> list[str]:
    reasons: list[str] = []
    if row.price < config.minimum_price:
        reasons.append(f"price_below_{config.minimum_price:g}")
    if row.average_dollar_volume_20d is None:
        reasons.append("average_dollar_volume_missing")
    elif row.average_dollar_volume_20d < config.minimum_average_dollar_volume:
        reasons.append(f"average_dollar_volume_below_{config.minimum_average_dollar_volume:g}")
    if row.atr14 is None or row.atr14 <= 0:
        reasons.append("atr14_missing")
    return reasons


def _support_distance(row: MarketSnapshot) -> tuple[float | None, str | None]:
    if row.atr14 is None or row.atr14 <= 0:
        return None, "atr14_missing"
    levels = latest_levels(row.levels, not_after=row.as_of)
    if not levels:
        return None, "levels_missing"
    nearest = nearest_zones(row.price, levels, row.atr14)
    support_inside = next(
        (zone for zone in nearest.inside if any(level.side == "Support" for level in zone.zone.members)),
        None,
    )
    if support_inside is not None:
        return 0.0, None
    if nearest.support is None:
        return None, "eligible_support_missing"
    return nearest.support.distance_atr, None


def _near_support(row: MarketSnapshot, config: ScreenConfig) -> tuple[list[str], list[str], tuple[float | str, ...]]:
    reasons = _base_reasons(row, config)
    matched = [
        f"price_at_least_{config.minimum_price:g}",
        f"average_dollar_volume_at_least_{config.minimum_average_dollar_volume:g}",
    ] if not reasons else []
    distance, issue = _support_distance(row)
    if issue:
        reasons.append(issue)
    elif distance is not None and distance > config.maximum_support_distance_atr:
        reasons.append(f"support_farther_than_{config.maximum_support_distance_atr:g}_atr")
    else:
        matched.append(f"support_within_{config.maximum_support_distance_atr:g}_atr")
    return reasons, matched, (distance if distance is not None else float("inf"), row.ticker)


def _oversold(row: MarketSnapshot, config: ScreenConfig) -> tuple[list[str], list[str], tuple[float | str, ...]]:
    reasons, matched, base_key = _near_support(row, config)
    if row.rsi14 is None:
        reasons.append("rsi14_missing")
    elif row.rsi14 > 35:
        reasons.append("rsi14_above_35")
    else:
        matched.append("rsi14_at_or_below_35")
    return reasons, matched, (row.rsi14 if row.rsi14 is not None else float("inf"), *base_key)


def _trend(row: MarketSnapshot, config: ScreenConfig) -> tuple[list[str], list[str], tuple[float | str, ...]]:
    reasons = _base_reasons(row, config)
    matched: list[str] = []
    if row.sma20 is None or row.sma50 is None or row.sma200 is None:
        reasons.append("moving_average_missing")
    else:
        if not (row.price > row.sma50 > row.sma200):
            reasons.append("price_sma50_sma200_not_ordered")
        else:
            matched.append("price_above_sma50_above_sma200")
        if row.atr14 is not None and row.atr14 > 0:
            if abs(row.price - row.sma20) / row.atr14 <= 1.5:
                matched.append("price_within_1_5_atr_of_sma20")
            else:
                reasons.append("price_farther_than_1_5_atr_from_sma20")
    if row.momentum_20d_pct is None:
        reasons.append("momentum_20d_missing")
    elif row.momentum_20d_pct <= 0:
        reasons.append("momentum_20d_not_positive")
    else:
        matched.append("momentum_20d_positive")
    if not reasons:
        matched.extend([
            f"price_at_least_{config.minimum_price:g}",
            f"average_dollar_volume_at_least_{config.minimum_average_dollar_volume:g}",
        ])
    momentum = row.momentum_20d_pct if row.momentum_20d_pct is not None else float("-inf")
    return reasons, matched, (-momentum, row.ticker)


ScreenFunction = Callable[
    [MarketSnapshot, ScreenConfig],
    tuple[list[str], list[str], tuple[float | str, ...]],
]


_SCREENERS: dict[PresetName, ScreenFunction] = {
    "near_support": _near_support,
    "oversold_at_support": _oversold,
    "trend_continuation": _trend,
}


def run_screen(
    snapshots: Sequence[MarketSnapshot],
    preset: PresetName,
    *,
    limit: int = 25,
) -> ScreenResult:
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset}")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")
    config = PRESETS[preset]
    candidates: list[ScreenCandidate] = []
    exclusions: list[ScreenExclusion] = []
    for row in snapshots:
        reasons, matched, rank_key = _SCREENERS[preset](row, config)
        reasons = list(dict.fromkeys(reasons))
        if reasons:
            exclusions.append(ScreenExclusion(row.ticker, tuple(reasons)))
            continue
        distance, _issue = _support_distance(row)
        candidates.append(
            ScreenCandidate(
                ticker=row.ticker,
                as_of=row.as_of,
                price=row.price,
                support_distance_atr=distance,
                matched_criteria=tuple(matched),
                rank_key=rank_key,
            )
        )
    candidates.sort(key=lambda row: row.rank_key)
    exclusions.sort(key=lambda row: row.ticker)
    ranking = {
        "near_support": "Nearest support-band edge in ATR units, then ticker.",
        "oversold_at_support": "Lowest RSI(14), then nearest support-band edge in ATR units, then ticker.",
        "trend_continuation": "Highest 20-session momentum percentage, then ticker.",
    }[preset]
    returned = tuple(candidates[:limit])
    return ScreenResult(
        preset=preset,
        description=config.description,
        ranking_method=ranking,
        candidates=returned,
        exclusions=tuple(exclusions),
        coverage=len(snapshots),
        omitted_candidates=max(0, len(candidates) - len(returned)),
        warnings=(
            "Candidates meet disclosed filters; the screen does not predict returns or suitability.",
            "Historical level metrics are not used as cross-instrument probabilities.",
            "Support distance is measured to the computed zone edge, not to the source level midpoint.",
            *sorted({warning for row in snapshots for warning in row.warnings}),
        ),
    )
