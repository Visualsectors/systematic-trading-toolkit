"""Support/resistance geometry and conditional entry/exit planning.

Reimplements the pure behavior of Visual Sectors' ``level-zones`` package. A
zone is geometry around served observations. It is not a prediction that price
will hold, break, bounce, or reach another zone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Literal, Sequence

from .models import (
    Level, LevelSide, is_usable_level, level_data_gap_warnings,
    require_finite, require_iso_datetime, require_ticker,
)

DEFAULT_HALF_WIDTH_ATR = 0.25
PRICE_TICK = Decimal("0.01")


def _price(value: float) -> float:
    rounded = Decimal(str(value)).quantize(PRICE_TICK, rounding=ROUND_HALF_UP)
    return float(max(PRICE_TICK, rounded))


@dataclass(frozen=True, slots=True)
class Zone:
    low: float
    high: float
    mid: float
    width_atr: float
    side: LevelSide | Literal["Mixed"]
    level_types: tuple[str, ...]
    member_count: int
    confluence_count_max: int | None
    score_max: float | None
    members: tuple[Level, ...]


@dataclass(frozen=True, slots=True)
class NearestZone:
    zone: Zone
    state: Literal["below", "inside", "above"]
    distance_price: float
    distance_atr: float


@dataclass(frozen=True, slots=True)
class NearestZones:
    support: NearestZone | None
    resistance: NearestZone | None
    inside: tuple[NearestZone, ...]


@dataclass(frozen=True, slots=True)
class HistoricalBaseRate:
    """A provider-served historical statistic, not a forecast for this setup."""

    label: Literal["historical_base_rate"]
    side: LevelSide
    level_type: str
    level_price: float
    p_hold_7d_pct: float | None
    exp_bounce_pct: float | None
    hard_break_pct: float | None
    approaches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LevelPlan:
    ticker: str
    direction: Literal["long", "short"]
    as_of: str
    current_price: float
    entry_zone: Zone | None
    invalidation_price: float | None
    reassessment_zone: Zone | None
    risk_per_share: float | None
    reward_to_reassessment_R: float | None
    stop_distance_atr: float | None
    entry_historical_base_rates: tuple[HistoricalBaseRate, ...]
    reassessment_historical_base_rates: tuple[HistoricalBaseRate, ...]
    status: Literal["ready", "insufficient_data"]
    notes: tuple[str, ...]


def _positive(value: float, name: str) -> float:
    return require_finite(value, name, positive=True)


def zone_for(level: Level, atr: float, *, half_width_atr: float = DEFAULT_HALF_WIDTH_ATR) -> tuple[float, float]:
    if not is_usable_level(level):
        raise ValueError(level_data_gap_warnings((level,))[0])
    scale = _positive(atr, "atr")
    half = require_finite(half_width_atr, "half_width_atr")
    if half < 0:
        raise ValueError("half_width_atr must be non-negative")
    width = scale * half
    return _price(level.price - width), _price(level.price + width)


def latest_levels(
    levels: Sequence[Level], *, not_after: str | date | datetime | None = None
) -> tuple[Level, ...]:
    cutoff: date | None
    if isinstance(not_after, datetime):
        cutoff = not_after.date()
    elif isinstance(not_after, date):
        cutoff = not_after
    elif isinstance(not_after, str):
        try:
            cutoff = datetime.fromisoformat(not_after.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                cutoff = date.fromisoformat(not_after)
            except ValueError as exc:
                raise ValueError("not_after must be an ISO date or datetime") from exc
    elif not_after is None:
        cutoff = None
    else:
        raise ValueError("not_after must be an ISO date or datetime")
    eligible = tuple(
        level for level in levels if cutoff is None or date.fromisoformat(level.level_date) <= cutoff
    )
    if not eligible:
        return ()
    latest = max(level.level_date for level in eligible)
    # Choose the newest date before excluding bad rows: never resurrect older
    # levels when the entire latest session fails the quality gate.
    return tuple(level for level in eligible if level.level_date == latest and is_usable_level(level))


def derive_atr(levels: Sequence[Level], reference_price: float) -> float | None:
    reference = _positive(reference_price, "reference_price")
    candidates: list[float] = []
    for level in levels:
        if not is_usable_level(level):
            continue
        distance = level.dist_atr
        if distance is None or not isfinite(distance) or distance == 0:
            continue
        candidate = abs(level.price - reference) / abs(distance)
        if isfinite(candidate) and candidate > 0:
            candidates.append(candidate)
    if not candidates:
        return None
    candidates.sort()
    middle = len(candidates) // 2
    if len(candidates) % 2:
        return candidates[middle]
    return (candidates[middle - 1] + candidates[middle]) / 2


def _side(members: Sequence[Level]) -> LevelSide | Literal["Mixed"]:
    if not members:
        return "Mixed"
    first = members[0].side
    return first if all(member.side == first for member in members) else "Mixed"


def _finite_max(values: Sequence[float | None]) -> float | None:
    finite = [value for value in values if value is not None and isfinite(value)]
    return max(finite) if finite else None


def _int_max(values: Sequence[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _finish(low: float, high: float, members: Sequence[Level], atr: float) -> Zone:
    ordered = tuple(members)
    rounded_low = _price(low)
    rounded_high = max(rounded_low, _price(high))
    return Zone(
        low=rounded_low,
        high=rounded_high,
        mid=_price((rounded_low + rounded_high) / 2),
        width_atr=(rounded_high - rounded_low) / atr,
        side=_side(ordered),
        level_types=tuple(sorted({member.level_type for member in ordered})),
        member_count=len(ordered),
        confluence_count_max=_int_max([member.confluence_count for member in ordered]),
        score_max=_finite_max([member.score for member in ordered]),
        members=ordered,
    )


def _base_rates(zone: Zone | None, notes: list[str]) -> tuple[HistoricalBaseRate, ...]:
    if zone is None:
        return ()
    groups: dict[tuple[LevelSide, str, float], list[Level]] = {}
    for member in zone.members:
        if is_usable_level(member):
            groups.setdefault((member.side, member.level_type, member.price), []).append(member)
    rates: list[HistoricalBaseRate] = []
    fields = ("p_hold_7d_pct", "exp_bounce_pct", "hard_break_pct")
    for (side, level_type, level_price), members in sorted(groups.items()):
        values = {field: {getattr(member, field) for member in members
                          if getattr(member, field) is not None} for field in fields}
        if not any(values.values()):
            continue
        conflicts = [field for field in fields if len(values[field]) > 1]
        if conflicts:
            notes.append(
                f"Data gap: conflicting historical base rates for {side} {level_type} at {level_price:.15g}; "
                f"{', '.join(conflicts)} remain null. Approach statistics were not averaged or ranked."
            )
        common = {field: next(iter(values[field])) if len(values[field]) == 1 else None for field in fields}
        rates.append(HistoricalBaseRate(
            label="historical_base_rate",
            side=side,
            level_type=level_type,
            level_price=level_price,
            p_hold_7d_pct=common["p_hold_7d_pct"],
            exp_bounce_pct=common["exp_bounce_pct"],
            hard_break_pct=common["hard_break_pct"],
            approaches=tuple(sorted({member.approach for member in members
                                    if isinstance(member.approach, str) and member.approach.strip()})),
        ))
    return tuple(rates)


def cluster_levels(
    levels: Sequence[Level],
    atr: float,
    *,
    half_width_atr: float = DEFAULT_HALF_WIDTH_ATR,
    same_side_only: bool = True,
    max_zone_width_atr: float = 1.0,
) -> tuple[Zone, ...]:
    scale = _positive(atr, "atr")
    max_width = _positive(max_zone_width_atr, "max_zone_width_atr") * scale
    levels = tuple(level for level in levels if is_usable_level(level))
    if not levels:
        return ()
    entries = []
    for index, level in enumerate(levels):
        low, high = zone_for(level, scale, half_width_atr=half_width_atr)
        entries.append((low, high, level.side, level.level_type, level.level_date, index, level))

    groups = (
        [
            [entry for entry in entries if entry[2] == "Support"],
            [entry for entry in entries if entry[2] == "Resistance"],
        ]
        if same_side_only
        else [entries]
    )
    zones: list[Zone] = []
    for group in groups:
        group.sort(key=lambda entry: entry[:6])
        open_low: float | None = None
        open_high: float | None = None
        members: list[Level] = []
        for low, high, _side_name, _kind, _date, _index, level in group:
            if (
                open_low is not None
                and open_high is not None
                and low <= open_high
                and max(open_high, high) - min(open_low, low) <= max_width
            ):
                open_low = min(open_low, low)
                open_high = max(open_high, high)
                members.append(level)
                continue
            if open_low is not None and open_high is not None:
                zones.append(_finish(open_low, open_high, members, scale))
            open_low, open_high, members = low, high, [level]
        if open_low is not None and open_high is not None:
            zones.append(_finish(open_low, open_high, members, scale))
    return tuple(sorted(zones, key=lambda zone: (zone.low, zone.high, zone.side)))


def nearest_zones(
    price: float,
    levels: Sequence[Level],
    atr: float,
    *,
    half_width_atr: float = DEFAULT_HALF_WIDTH_ATR,
) -> NearestZones:
    current = _positive(price, "price")
    scale = _positive(atr, "atr")
    zones = cluster_levels(levels, scale, half_width_atr=half_width_atr)
    inside: list[NearestZone] = []
    support: Zone | None = None
    resistance: Zone | None = None
    for zone in zones:
        if zone.low <= current <= zone.high:
            inside.append(NearestZone(zone, "inside", 0, 0))
        elif zone.high < current and any(member.side == "Support" for member in zone.members):
            if support is None or zone.high > support.high:
                support = zone
        elif zone.low > current and any(member.side == "Resistance" for member in zone.members):
            if resistance is None or zone.low < resistance.low:
                resistance = zone
    return NearestZones(
        support=None
        if support is None
        else NearestZone(support, "above", current - support.high, (current - support.high) / scale),
        resistance=None
        if resistance is None
        else NearestZone(resistance, "below", resistance.low - current, (resistance.low - current) / scale),
        inside=tuple(inside),
    )


def build_level_plan(
    *,
    ticker: str,
    as_of: str,
    direction: Literal["long", "short"],
    current_price: float,
    atr: float | None,
    levels: Sequence[Level],
    invalidation_buffer_atr: float = 0.25,
) -> LevelPlan:
    """Build conditional planning zones; never a price forecast or order."""
    normalized_ticker = require_ticker(ticker)
    require_iso_datetime(as_of, "as_of")
    current = _positive(current_price, "current_price")
    if direction not in ("long", "short"):
        raise ValueError("direction must be long or short")
    data_gaps = level_data_gap_warnings(levels, ticker=normalized_ticker)
    if atr is None or not levels:
        return LevelPlan(
            ticker=normalized_ticker,
            direction=direction,
            as_of=as_of,
            current_price=current,
            entry_zone=None,
            invalidation_price=None,
            reassessment_zone=None,
            risk_per_share=None,
            reward_to_reassessment_R=None,
            stop_distance_atr=None,
            entry_historical_base_rates=(),
            reassessment_historical_base_rates=(),
            status="insufficient_data",
            notes=("A positive ATR and dated levels are required; no levels were invented.", *data_gaps),
        )
    scale = require_finite(atr, "atr")
    if scale <= 0:
        return LevelPlan(
            ticker=normalized_ticker,
            direction=direction,
            as_of=as_of,
            current_price=current,
            entry_zone=None,
            invalidation_price=None,
            reassessment_zone=None,
            risk_per_share=None,
            reward_to_reassessment_R=None,
            stop_distance_atr=None,
            entry_historical_base_rates=(),
            reassessment_historical_base_rates=(),
            status="insufficient_data",
            notes=("A positive ATR and dated levels are required; no levels were invented.", *data_gaps),
        )
    buffer = require_finite(invalidation_buffer_atr, "invalidation_buffer_atr")
    if buffer < 0:
        raise ValueError("invalidation_buffer_atr must be non-negative")
    latest = latest_levels(levels, not_after=as_of)
    if not latest:
        return LevelPlan(
            ticker=normalized_ticker,
            direction=direction,
            as_of=as_of,
            current_price=current,
            entry_zone=None,
            invalidation_price=None,
            reassessment_zone=None,
            risk_per_share=None,
            reward_to_reassessment_R=None,
            stop_distance_atr=None,
            entry_historical_base_rates=(),
            reassessment_historical_base_rates=(),
            status="insufficient_data",
            notes=("No usable level dated on or before the decision time was available.", *data_gaps),
        )
    nearest = nearest_zones(current, latest, scale)
    entry_side = "Support" if direction == "long" else "Resistance"
    review_side = "Resistance" if direction == "long" else "Support"
    containing = next(
        (item.zone for item in nearest.inside if any(member.side == entry_side for member in item.zone.members)),
        None,
    )
    review_containing = next(
        (item.zone for item in nearest.inside if any(member.side == review_side for member in item.zone.members)),
        None,
    )
    entry = containing or (nearest.support.zone if direction == "long" and nearest.support else None) or (
        nearest.resistance.zone if direction == "short" and nearest.resistance else None
    )
    review = review_containing or (nearest.resistance.zone if direction == "long" and nearest.resistance else (
        nearest.support.zone if direction == "short" and nearest.support else None
    ))
    invalidation = None
    risk = None
    reward_r = None
    stop_distance_atr = None
    notes = [
        "Zones are computed from dated level observations and an ATR grouping width; "
        "they are scenarios, not fill or outcome forecasts.",
        *data_gaps,
    ]
    if entry is not None:
        invalidation = _price(
            entry.low - buffer * scale if direction == "long" else entry.high + buffer * scale
        )
        reference_entry = entry.high if direction == "long" else entry.low
        risk = _price(abs(reference_entry - invalidation))
        stop_distance_atr = risk / scale
    else:
        side_name = "support" if direction == "long" else "resistance"
        notes.append(f"No eligible {side_name} zone was available for an entry scenario.")
    if entry is not None and review is not None:
        beyond_entry = review.low > entry.high if direction == "long" else review.high < entry.low
        if not beyond_entry:
            review = None
            notes.append(
                "The opposite-side zone was not beyond the entry zone, so it was not presented as reassessment."
            )
    if review is None:
        notes.append("No opposite-side reassessment zone was available; no price objective was fabricated.")
    elif entry is not None and risk is not None and risk > 0:
        reference_entry = entry.high if direction == "long" else entry.low
        reward = review.low - reference_entry if direction == "long" else reference_entry - review.high
        reward_r = round(reward / risk, 4)
    return LevelPlan(
        ticker=normalized_ticker,
        direction=direction,
        as_of=as_of,
        current_price=current,
        entry_zone=entry,
        invalidation_price=invalidation,
        reassessment_zone=review,
        risk_per_share=risk,
        reward_to_reassessment_R=reward_r,
        stop_distance_atr=stop_distance_atr,
        entry_historical_base_rates=_base_rates(entry, notes),
        reassessment_historical_base_rates=_base_rates(review, notes),
        status="ready" if entry is not None else "insufficient_data",
        notes=tuple(notes),
    )
