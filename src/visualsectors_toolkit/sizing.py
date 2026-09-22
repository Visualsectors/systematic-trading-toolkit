"""Two explicit, deterministic position-sizing methods.

``stop_risk/v1`` answers "how many shares fit this planned loss and allocation
cap?". ``portfolio_slots/v1`` reimplements Visual Sectors' established
portfolio-slot/inverse-volatility behavior. The methods are never blended.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from math import isfinite
from typing import Literal, Sequence

from .models import require_ticker


def _decimal(value: float, name: str, *, positive: bool = True) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be finite")
    result = Decimal(str(value))
    if positive and result <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _fraction(part: Decimal, whole: Decimal) -> float:
    if whole == 0:
        return 0.0
    return float((part / whole).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True, slots=True)
class StopRiskSize:
    method: Literal["stop_risk/v1"]
    side: Literal["long", "short"]
    shares: int
    entry: float
    stop: float
    notional: float
    planned_loss_at_stop: float
    risk_budget: float
    allocation_cap: float
    risk_limited_shares: int
    allocation_limited_shares: int
    binding_constraint: Literal["risk_budget", "allocation_cap", "both"]
    warnings: tuple[str, ...]


def size_by_stop_risk(
    *,
    capital: float,
    risk_fraction: float,
    entry: float,
    stop: float,
    max_allocation_fraction: float,
    side: Literal["long", "short"] = "long",
) -> StopRiskSize:
    portfolio = _decimal(capital, "capital")
    risk_pct = _decimal(risk_fraction, "risk_fraction")
    cap_pct = _decimal(max_allocation_fraction, "max_allocation_fraction")
    entry_price = _decimal(entry, "entry")
    stop_price = _decimal(stop, "stop")
    if risk_pct > 1 or cap_pct > 1:
        raise ValueError("risk_fraction and max_allocation_fraction must be at most 1")
    if side == "long" and stop_price >= entry_price:
        raise ValueError("a long stop must be below entry")
    if side == "short" and stop_price <= entry_price:
        raise ValueError("a short stop must be above entry")
    if side not in ("long", "short"):
        raise ValueError("side must be long or short")
    per_share = abs(entry_price - stop_price)
    risk_budget = portfolio * risk_pct
    allocation_cap = portfolio * cap_pct
    risk_shares = int((risk_budget / per_share).to_integral_value(rounding=ROUND_FLOOR))
    allocation_shares = int((allocation_cap / entry_price).to_integral_value(rounding=ROUND_FLOOR))
    shares = min(risk_shares, allocation_shares)
    if shares < 1:
        raise ValueError("the supplied limits cannot fund one share")
    binding = "both" if risk_shares == allocation_shares else (
        "risk_budget" if risk_shares < allocation_shares else "allocation_cap"
    )
    warnings = (
        "Planned loss excludes commissions, slippage, taxes and borrow costs.",
        "A gap through the stop can produce a larger loss than planned.",
        "This calculation is arithmetic, not a suitability assessment or order.",
    )
    return StopRiskSize(
        method="stop_risk/v1",
        side=side,
        shares=shares,
        entry=float(entry_price),
        stop=float(stop_price),
        notional=_money(entry_price * shares),
        planned_loss_at_stop=_money(per_share * shares),
        risk_budget=_money(risk_budget),
        allocation_cap=_money(allocation_cap),
        risk_limited_shares=risk_shares,
        allocation_limited_shares=allocation_shares,
        binding_constraint=binding,
        warnings=warnings,
    )


@dataclass(frozen=True, slots=True)
class SizingPick:
    ticker: str
    close: float | None
    volatility_pct: float | None
    side: Literal["long", "short"] = "long"

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", require_ticker(self.ticker))
        if self.side not in ("long", "short"):
            raise ValueError("pick.side must be long or short")


@dataclass(frozen=True, slots=True)
class SizedPosition:
    ticker: str
    side: Literal["long", "short"]
    close: float | None
    volatility_pct: float | None
    target: float
    shares: int
    notional: float
    tilt: Literal["tilted", "equal", "no_price", "min_share", "too_expensive"]
    batch_share: float
    portfolio_share: float
    note: str | None


@dataclass(frozen=True, slots=True)
class PortfolioSlotSize:
    method: Literal["portfolio_slots/v1"]
    slot: float
    batch_budget: float
    positions: tuple[SizedPosition, ...]
    gross_long: float
    gross_short: float
    net: float
    deployed: float
    unallocated: float
    portfolio_share_of_batch: float
    notes: tuple[str, ...]


def size_by_portfolio_slots(
    *, portfolio: float, intended_holdings: int, picks: Sequence[SizingPick]
) -> PortfolioSlotSize:
    capital = _decimal(portfolio, "portfolio")
    if isinstance(intended_holdings, bool) or not isinstance(intended_holdings, int) or intended_holdings < 1:
        raise ValueError("intended_holdings must be a positive integer")
    if not picks:
        raise ValueError("at least one pick is required")
    if len(picks) > intended_holdings:
        raise ValueError("picks cannot exceed intended_holdings")
    tickers = [pick.ticker for pick in picks]
    if len(tickers) != len(set(tickers)):
        raise ValueError("duplicate ticker in picks")

    slot = Decimal(str(_money(capital / intended_holdings)))
    budget = slot * len(picks)
    sizable = [pick for pick in picks if pick.close is not None and isfinite(pick.close) and pick.close > 0]
    missing_vol = [
        pick
        for pick in sizable
        if pick.volatility_pct is None
        or not isfinite(pick.volatility_pct)
        or pick.volatility_pct <= 0
    ]
    tilted = bool(sizable) and not missing_vol
    sizable_budget = slot * len(sizable)
    targets: dict[str, Decimal] = {}
    notes: list[str] = []
    if tilted:
        inverse = [Decimal(1) / _decimal(pick.volatility_pct or 0, "volatility_pct") for pick in sizable]
        total = sum(inverse, Decimal(0))
        for pick, weight in zip(sizable, inverse, strict=True):
            targets[pick.ticker] = sizable_budget * weight / total
    else:
        for pick in sizable:
            targets[pick.ticker] = slot
        if missing_vol:
            names = ", ".join(p.ticker for p in missing_vol)
            notes.append(f"Volatility missing for {names}; equal slots used for all priced names.")

    partial: list[tuple[SizingPick, Decimal, int, Decimal, str, str | None]] = []
    for pick in picks:
        if pick.close is None or not isfinite(pick.close) or pick.close <= 0:
            partial.append(
                (pick, Decimal(0), 0, Decimal(0), "no_price", "No valid close; its slot remains unallocated.")
            )
            continue
        price = _decimal(pick.close, "close")
        target = targets.get(pick.ticker, Decimal(0))
        shares = int((target / price).to_integral_value(rounding=ROUND_FLOOR))
        tilt = "tilted" if tilted else "equal"
        note = None
        if shares == 0 and price > budget:
            tilt, note = "too_expensive", "One share exceeds the whole batch budget; not sized."
        elif shares == 0:
            shares, tilt, note = 1, "min_share", "One share exceeds this name's target; the overshoot is reported."
        partial.append((pick, target, shares, price * shares, tilt, note))

    gross_long = sum(
        (notional for pick, _target, _shares, notional, _tilt, _note in partial if pick.side == "long"),
        Decimal(0),
    )
    gross_short = sum(
        (notional for pick, _target, _shares, notional, _tilt, _note in partial if pick.side == "short"),
        Decimal(0),
    )
    deployed = gross_long + gross_short
    positions = tuple(
        SizedPosition(
            ticker=pick.ticker,
            side=pick.side,
            close=pick.close,
            volatility_pct=pick.volatility_pct,
            target=_money(target),
            shares=shares,
            notional=_money(notional),
            tilt=tilt,  # type: ignore[arg-type]
            batch_share=_fraction(notional, deployed),
            portfolio_share=_fraction(notional, capital),
            note=note,
        )
        for pick, target, shares, notional, tilt, note in partial
    )
    return PortfolioSlotSize(
        method="portfolio_slots/v1",
        slot=_money(slot),
        batch_budget=_money(budget),
        positions=positions,
        gross_long=_money(gross_long),
        gross_short=_money(gross_short),
        net=_money(gross_long - gross_short),
        deployed=_money(deployed),
        unallocated=_money(budget - deployed),
        portfolio_share_of_batch=_fraction(deployed, capital),
        notes=tuple(notes),
    )
