"""Pure, bounded Price-lane features; no I/O, clock, credentials or model."""
from math import log1p
from .context_math import bars, deviation, mean, pct, percentile, period, rounded, sign


PRICE_FIELDS = ("return_5d_pct", "return_10d_pct", "return_21d_pct", "return_60d_pct",
                "maximum_drawdown_pct", "maximum_runup_pct", "trend_efficiency",
                "recent_acceleration_pct", "return_21d_percentile_1y",
                "realized_volatility_percentile_1y", "largest_gap_up_pct", "largest_gap_down_pct",
                "largest_gap_atr_multiple", "gap_follow_through_pct", "latest_close_in_month_range_pct",
                "latest_range_vs_prior_10", "latest_volume_vs_20d")


def empty_price(count, risks):
    return {"data_quality": "insufficient", "session_count": count,
            **dict.fromkeys(PRICE_FIELDS), "material_gaps": [], "patterns": [], "risk_codes": risks}


def gaps(rows):
    ranges = [bar["high"] - bar["low"] if index == 0 else max(
        bar["high"] - bar["low"], abs(bar["high"] - rows[index - 1]["close"]),
        abs(bar["low"] - rows[index - 1]["close"])) for index, bar in enumerate(rows)]
    result = []
    for index in range(1, len(rows)):
        bar, prior_close = rows[index], rows[index - 1]["close"]
        gap, day_return = bar["open"] / prior_close - 1, bar["close"] / bar["open"] - 1
        atr = mean(ranges[max(0, index - 20):index]) or 0
        multiple = abs(bar["open"] - prior_close) / atr if atr else 0
        direction = "up" if gap > 0 else "down"
        fill = next((offset for offset in range(index, min(index + 5, len(rows) - 1) + 1)
                     if (rows[offset]["low"] <= prior_close if direction == "up"
                         else rows[offset]["high"] >= prior_close)), None)
        complete = index + 5 < len(rows)
        sessions = None if fill is None else fill - index
        observation = {"observed_on": bar["session"], "direction": direction,
                       "gap_pct": pct(gap), "atr_multiple": rounded(multiple, 2),
                       "same_day_return_pct": pct(day_return),
                       "fill_status": "filled_same_session" if sessions == 0 else
                           "filled_within_5_sessions" if sessions is not None else
                           "open_after_5_sessions" if complete else "observation_incomplete",
                       "sessions_to_fill": sessions,
                       "five_session_follow_through_pct": pct(rows[index + 5]["close"] / prior_close - 1) if complete else None}
        result.append((gap, multiple, day_return, observation))
    return result


def patterns(rows, r5, r21, acceleration, rank):
    result = []
    latest, prior = rows[-1], rows[-2]
    width = latest["high"] - latest["low"]
    body = abs(latest["close"] - latest["open"])
    upper = latest["high"] - max(latest["open"], latest["close"])
    lower = min(latest["open"], latest["close"]) - latest["low"]

    def add(code, direction, strength, description, invalidation=None):
        result.append({"code": code, "direction": direction, "strength": strength,
                       "observed_on": latest["session"], "description": description, "invalidation": invalidation})

    if width > 0 and body / width <= 0.12:
        add("DOJI", "neutral", "weak", "Latest session closed near its open, signalling indecision.")
    if width > 0 and lower >= max(body * 2, width * 0.45) and upper <= width * 0.2:
        add("HAMMER", "bullish", "moderate", "Long lower shadow shows intraday rejection of lower prices.", f"Close below {latest['low']:.2f}")
    if width > 0 and upper >= max(body * 2, width * 0.45) and lower <= width * 0.2:
        add("SHOOTING_STAR", "bearish", "moderate", "Long upper shadow shows intraday rejection of higher prices.", f"Close above {latest['high']:.2f}")
    if latest["close"] > latest["open"] and prior["close"] < prior["open"] and latest["open"] <= prior["close"] and latest["close"] >= prior["open"]:
        add("BULLISH_ENGULFING", "bullish", "strong", "Latest real body engulfed the prior bearish body.", f"Close below {latest['low']:.2f}")
    if latest["close"] < latest["open"] and prior["close"] > prior["open"] and latest["open"] >= prior["close"] and latest["close"] <= prior["open"]:
        add("BEARISH_ENGULFING", "bearish", "strong", "Latest real body engulfed the prior bullish body.", f"Close above {latest['high']:.2f}")
    if latest["high"] < prior["high"] and latest["low"] > prior["low"]:
        add("INSIDE_BAR", "neutral", "weak", "Latest range sits inside the prior session, indicating compression.")
    if latest["high"] > prior["high"] and latest["low"] < prior["low"]:
        add("OUTSIDE_BAR", "bullish" if latest["close"] >= latest["open"] else "bearish", "moderate", "Latest session expanded beyond both sides of the prior range.")
    recent = rows[-5:]
    if len(recent) == 5 and all(bar["low"] > recent[index]["low"] for index, bar in enumerate(recent[1:])):
        add("HIGHER_LOW_SEQUENCE", "bullish", "moderate", "Five-session sequence retained progressively higher lows.", f"Close below {min(bar['low'] for bar in recent):.2f}")
    if len(recent) == 5 and all(bar["high"] < recent[index]["high"] for index, bar in enumerate(recent[1:])):
        add("LOWER_HIGH_SEQUENCE", "bearish", "moderate", "Five-session sequence formed progressively lower highs.", f"Close above {max(bar['high'] for bar in recent):.2f}")
    prior_ten = rows[-15:-5]
    if len(recent) == 5 and len(prior_ten) >= 5:
        recent_width = max(bar["high"] for bar in recent) - min(bar["low"] for bar in recent)
        prior_width = max(bar["high"] for bar in prior_ten) - min(bar["low"] for bar in prior_ten)
        if prior_width > 0 and recent_width / prior_width <= 0.5:
            add("CONSOLIDATION", "neutral", "moderate", "Five-session range compressed versus the preceding ten sessions.")
    base = rows[-12:-2]
    if len(base) >= 5 and prior["close"] > max(bar["high"] for bar in base) and latest["close"] < max(bar["high"] for bar in base):
        add("FAILED_BREAKOUT", "bearish", "strong", "A close above the prior range was followed by a close back inside it.", f"Close above {prior['high']:.2f}")
    if r21 is not None and r21 > 0 and r5 is not None and r5 <= -0.02:
        add("ROLLING_OVER", "bearish", "moderate", "The positive monthly path weakened over the latest five sessions.", f"Close above {max(bar['high'] for bar in recent):.2f}")
    if r21 is not None and r21 > 0.03 and r5 is not None and r5 > 0.02 and (acceleration or 0) > 0:
        add("TREND_REACCELERATION", "bullish", "moderate", "The established monthly advance accelerated over the latest five sessions.", f"Close below {min(bar['low'] for bar in recent):.2f}")
    if r21 is not None and rank is not None and rank >= 0.95:
        add("UNUSUAL_UPWARD_PACE", "bearish", "strong" if abs(r21) >= 0.5 else "moderate", "The 21-session advance ranks in the most extreme 5% of its one-year observations; extension risk is elevated.")
    if r21 is not None and rank is not None and rank <= 0.05:
        add("UNUSUAL_DOWNWARD_PACE", "bearish", "strong" if abs(r21) >= 0.5 else "moderate", "The 21-session decline ranks in the most extreme 5% of its one-year observations.")
    return result[:10]


def build_price(series):
    rows = bars(series)
    analysis = rows[-23:]
    risks = []
    if len(analysis) < 20:
        risks.append("PRICE_HISTORY_INSUFFICIENT")
    if len(rows) < 253:
        risks.append("PRICE_BASELINE_THIN")
    if any(bar["volume"] is None for bar in analysis):
        risks.append("PRICE_VOLUME_PARTIAL")
    if len(analysis) < 20:
        return empty_price(len(analysis), risks)
    daily = [bar["close"] / rows[index]["close"] - 1 for index, bar in enumerate(rows[1:])]
    analysis_returns = [bar["close"] / analysis[index]["close"] - 1 for index, bar in enumerate(analysis[1:])]
    r5, r10, r21, r60 = period(analysis, 5), period(analysis, 10), period(analysis, 21), period(rows, 60)
    rolling = [bar["close"] / rows[index]["close"] - 1 for index, bar in enumerate(rows[21:])]
    vol = deviation(analysis_returns[-21:])
    rolling_vol = [deviation(daily[index:index + 21]) for index in range(len(daily) - 20)]
    rank = None if r21 is None else percentile(rolling[:-1], r21)
    vol_rank = None if vol is None else percentile(rolling_vol[:-1], vol)
    acceleration = None if r5 is None or r21 is None else r5 - r21 * (5 / 21)
    length = sum(abs(log1p(value)) for value in analysis_returns)
    efficiency = None if r21 is None or length == 0 else abs(log1p(r21)) / length
    sessions = {bar["session"] for bar in analysis[1:]}
    observed_gaps = [gap for gap in gaps(rows) if gap[3]["observed_on"] in sessions]
    material = [gap for gap in observed_gaps if abs(gap[0]) >= 0.01 or gap[1] >= 0.75]
    selected = sorted(material, key=lambda gap: (-abs(gap[1]), -abs(gap[0]), gap[3]["observed_on"]))[:5]
    follow = sum(sign(gap[0]) == sign(gap[2]) for gap in material) / len(material) if material else None
    largest_up = max([0] + [gap[0] for gap in observed_gaps]) if observed_gaps else None
    largest_down = min([0] + [gap[0] for gap in observed_gaps]) if observed_gaps else None
    largest_atr = max(gap[1] for gap in observed_gaps) if observed_gaps else None
    month_high, month_low = max(bar["high"] for bar in analysis), min(bar["low"] for bar in analysis)
    latest = analysis[-1]
    location = 0.5 if month_high == month_low else (latest["close"] - month_low) / (month_high - month_low)
    prior_range = mean([bar["high"] - bar["low"] for bar in analysis[-11:-1]])
    range_ratio = (latest["high"] - latest["low"]) / prior_range if prior_range else None
    average_volume = mean([bar["volume"] for bar in analysis[-21:-1] if bar["volume"] is not None])
    volume_ratio = latest["volume"] / average_volume if latest["volume"] is not None and average_volume else None
    peak = trough = analysis[0]["close"]
    drawdown = runup = 0
    for bar in analysis:
        peak, trough = max(peak, bar["close"]), min(trough, bar["close"])
        drawdown, runup = min(drawdown, bar["close"] / peak - 1), max(runup, bar["close"] / trough - 1)
    pattern_rows = patterns(analysis, r5, r21, acceleration, rank)
    if rank is not None and (rank >= 0.95 or rank <= 0.05):
        risks.append("PRICE_MONTHLY_PACE_UNUSUAL")
    if r21 is not None and abs(r21) >= 0.5:
        risks.append("PRICE_MONTHLY_MOVE_EXTREME")
    if vol_rank is not None and vol_rank >= 0.90:
        risks.append("PRICE_VOLATILITY_ELEVATED")
    if (largest_up or 0) >= 0.05 or (largest_down or 0) <= -0.05 or (largest_atr or 0) >= 2:
        risks.append("PRICE_EVENT_SIZED_GAP")
    if (volume_ratio or 0) >= 2:
        risks.append("PRICE_VOLUME_SPIKE")
    values = [pct(r5), pct(r10), pct(r21), pct(r60), pct(drawdown), pct(runup), rounded(efficiency, 3),
              pct(acceleration), pct(rank), pct(vol_rank), pct(largest_up), pct(largest_down), rounded(largest_atr, 2),
              pct(follow), pct(min(1, max(0, location))), rounded(range_ratio, 2), rounded(volume_ratio, 2)]
    return {"data_quality": "partial" if "PRICE_BASELINE_THIN" in risks or "PRICE_VOLUME_PARTIAL" in risks else "complete",
            "session_count": len(analysis), **dict(zip(PRICE_FIELDS, values)),
            "material_gaps": [gap[3] for gap in selected], "patterns": pattern_rows, "risk_codes": risks}
