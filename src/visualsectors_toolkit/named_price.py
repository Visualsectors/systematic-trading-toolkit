"""Measure provider-served levels from a user-named price; no position decision."""
from .levels import latest_levels
from .models import require_finite


def measure_named_price(snapshot, price, *, kind="entry"):
    price = require_finite(price, "named price", positive=True)
    if kind not in ("entry", "cost", "strike"):
        raise ValueError("named price kind must be entry, cost or strike")
    levels = latest_levels(snapshot.levels, not_after=snapshot.as_of)

    def measured(level):
        if level is None:
            return None
        delta = level.price - price
        rate = level.p_hold_7d_pct
        return {"evidence_id": f"level:{snapshot.ticker}:{level.level_date}:{level.side}:{level.level_type}:{level.price:g}",
                "date": level.level_date, "side": level.side, "type": level.level_type, "served_price": level.price,
                "distance_dollars": round(delta, 6), "distance_pct": round(delta / price * 100, 6),
                "distance_atr": round(delta / snapshot.atr14, 6) if snapshot.atr14 else None,
                "hold_rate_pct": rate if rate is not None and 0 <= rate <= 100 else None,
                "hold_rate_text": f"held on {rate:g}% of past tests" if rate is not None and 0 <= rate <= 100 else "not supplied"}

    above = sorted((level for level in levels if level.price > price), key=lambda level: (level.price, level.side, level.level_type))
    below = sorted((level for level in levels if level.price < price), key=lambda level: (-level.price, level.side, level.level_type))
    return {"schema_version": "toolkit.named-price.v1", "ticker": snapshot.ticker, "as_of": snapshot.as_of,
            "named_price": price, "kind": kind, "latest_close": snapshot.price, "atr14": snapshot.atr14,
            "nearest_above": measured(above[0] if above else None), "nearest_below": measured(below[0] if below else None),
            "exactly_at": [measured(level) for level in levels if level.price == price],
            "strike_distance_from_close_atr": round((price - snapshot.price) / snapshot.atr14, 6) if kind == "strike" and snapshot.atr14 else None,
            "coverage_notes": ["Distances are signed: above positive, below negative. Missing levels, ATR or rates remain null.",
                               "Hold rates are served historical measurements; upstream recomputation and hindsight limitations still apply.", *snapshot.warnings],
            "closing": f"These are the served levels measured from ${price:g}; this isn't advice on what to do with a position."}
