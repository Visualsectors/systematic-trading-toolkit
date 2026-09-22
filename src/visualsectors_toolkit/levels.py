"""Support/resistance geometry and conditional entry/exit planning.

Reimplements the pure behavior of Visual Sectors' ``level-zones`` package. A
zone is geometry around served observations. It is not a prediction that price
will hold, break, bounce, or reach another zone.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, Sequence

from .models import Level, LevelSide, require_finite, require_iso_datetime, require_ticker

DEFAULT_HALF_WIDTH_ATR = 0.25


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
class LevelPlan:
    ticker: str
    direction: Literal["long", "short"]
    as_of: str
    current_price: float
    entry_zone: Zone | None
    invalidation_price: float | None
    reassessment_zone: Zone | None
    risk_per_share: float | None
    status: Literal["ready", "insufficient_data"]
    notes: tuple[str, ...]


def _positive(value: float, name: str) -> float:
    return require_finite(value, name, positive=True)


def zone_for(level: Level, atr: float, *, half_width_atr: float = DEFAULT_HALF_WIDTH_ATR) -> tuple[float, float]:
    scale = _positive(atr, "atr")
    half = require_finite(half_width_atr, "half_width_atr")
    if half < 0:
        raise ValueError("half_width_atr must be non-negative")
    width = scale * half
    return level.price - width, level.price + width


def latest_levels(levels: Sequence[Level]) -> tuple[Level, ...]:
    if not levels:
        return ()
    latest = max(level.level_date for level in levels)
    return tuple(level for level in levels if level.level_date == latest)


def derive_atr(levels: Sequence[Level], reference_price: float) -> float | None:
    reference = _positive(reference_price, "reference_price")
    candidates: list[float] = []
    for level in levels:
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
    return Zone(
        low=low,
        high=high,
        mid=(low + high) / 2,
        width_atr=(high - low) / atr,
        side=_side(ordered),
        level_types=tuple(sorted({member.level_type for member in ordered})),
        member_count=len(ordered),
        confluence_count_max=_int_max([member.confluence_count for member in ordered]),
        score_max=_finite_max([member.score for member in ordered]),
        members=ordered,
    )


def cluster_levels(
    levels: Sequence[Level],
    atr: float,
    *,
    half_width_atr: float = DEFAULT_HALF_WIDTH_ATR,
    same_side_only: bool = True,
) -> tuple[Zone, ...]:
    scale = _positive(atr, "atr")
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
            if open_low is not None and open_high is not None and low <= open_high:
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
            status="insufficient_data",
            notes=("A positive ATR and dated levels are required; no levels were invented.",),
        )
    scale = _positive(atr, "atr")
    buffer = require_finite(invalidation_buffer_atr, "invalidation_buffer_atr")
    if buffer < 0:
        raise ValueError("invalidation_buffer_atr must be non-negative")
    latest = latest_levels(levels)
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
    notes = [
        "Zones are computed from dated level observations and an ATR grouping width; "
        "they are scenarios, not fill or outcome forecasts."
    ]
    if entry is not None:
        invalidation = entry.low - buffer * scale if direction == "long" else entry.high + buffer * scale
        reference_entry = entry.high if direction == "long" else entry.low
        risk = abs(reference_entry - invalidation)
    else:
        side_name = "support" if direction == "long" else "resistance"
        notes.append(f"No eligible {side_name} zone was available for an entry scenario.")
    if review is None:
        notes.append("No opposite-side reassessment zone was available; no target was fabricated.")
    return LevelPlan(
        ticker=normalized_ticker,
        direction=direction,
        as_of=as_of,
        current_price=current,
        entry_zone=entry,
        invalidation_price=invalidation,
        reassessment_zone=review,
        risk_per_share=risk,
        status="ready" if entry is not None else "insufficient_data",
        notes=tuple(notes),
    )
