"""Closed, disclosed screen grammar. Research vocabulary is not an execution DSL."""
from __future__ import annotations

import json
import re
from importlib.resources import files
from .screening import _support_distance


def vocabulary():
    return json.loads(files("visualsectors_toolkit").joinpath("fixtures/trader_jargon.json").read_text(encoding="utf-8"))


def compile_screen(ask: str) -> dict:
    if not isinstance(ask, str) or not ask.strip() or len(ask) > 1000:
        raise ValueError("--ask must contain 1–1000 characters")
    text = ask.lower().replace("–", "-").replace("’", "'")
    conditions, interpretations = [], []

    def consume(pattern, build):
        nonlocal text
        def replace(match):
            condition, explanation = build(match)
            conditions.extend(condition)
            interpretations.append({"phrase": match.group(0), "condition": explanation})
            return " "
        text = re.sub(pattern, replace, text)

    def fixed(conditions, explanation):
        return lambda _match: (conditions, explanation)

    def scalar(field, op, value):
        return {"field": field, "op": op, "value": value}

    consume(r"\bgolden cross state\b", fixed([scalar("sma50", "gt_field", "sma200")], "SMA50 > SMA200; state only, not a crossing event."))
    consume(r"\b(?:above (?:the )?200(?:-day)?|above sma200)\b", fixed([scalar("price", "gt_field", "sma200")], "price > SMA200; 200-session simple moving average."))
    consume(r"\boversold\b", fixed([scalar("rsi14", "lte", 30)], "Disclosed default: RSI(14) <= 30; not a reversal signal."))
    consume(r"\boverbought\b", fixed([scalar("rsi14", "gte", 70)], "Disclosed default: RSI(14) >= 70; not a reversal signal."))
    consume(r"\blow p/?e\b", fixed([scalar("pe_ratio", "gt", 0), scalar("pe_ratio", "lte", 15)], "Disclosed heuristic: 0 < P/E <= 15; not a valuation or suitability conclusion."))
    consume(r"\buptrend\b", fixed([scalar("price", "gt_field", "sma50"), scalar("sma50", "gt_field", "sma200")], "Disclosed structural default: price > SMA50 > SMA200; not a crossing event."))
    consume(r"\bat support\b", fixed([scalar("support_distance_atr", "lte", 1.5)], "Disclosed default: nearest served support-band edge within 1.5 ATR; dated observations only."))
    consume(r"\bpullback to (?:the )?20(?:-day)?(?: sma)? within (\d+(?:\.\d+)?) atr\b", lambda m: ([scalar("sma20_distance_atr", "lte", float(m[1]))], f"abs(price - SMA20) / ATR14 <= {float(m[1]):g}; user-supplied distance."))
    amount = r"\$?(\d+(?:\.\d+)?)\s*([kmb]?)"

    def numeric(field, op, m):
        value = float(m[1]) * {"": 1, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[m[2]]
        if value <= 0:
            raise ValueError("price and liquidity thresholds must be positive")
        return [scalar(field, op, value)], f"{field} {op} {value:g}; user-supplied threshold."

    consume(r"\bprice (?:above|over|>)\s*" + amount + r"\b", lambda m: numeric("price", "gt", m))
    consume(r"\b(?:average dollar volume|adv20) (?:above|over|>)\s*" + amount + r"\b", lambda m: numeric("average_dollar_volume_20d", "gt", m))
    consume(r"\bliquid\b", fixed([scalar("average_dollar_volume_20d", "gte", 5_000_000)], "Disclosed dollar-liquidity default: 20-session average dollar volume >= $5,000,000; not average share volume."))
    residual = re.sub(r"\b(?:and|with|stocks|shares|that|are|show|find|me)\b|[,;]", " ", text)
    residual = " ".join(residual.split())
    refusals = []
    if residual:
        matches = []
        for entry in vocabulary():
            names = [entry["phrase"], *entry.get("variants", [])]
            if any(name.lower() == residual or (len(name) >= 5 and name.lower() in residual) for name in names):
                matches.append(entry)
        reasons = [str(entry.get("needs") or entry.get("ambiguity") or "Specify a numeric definition and provide its required dataset fields.") for entry in matches]
        refusals.append({"phrase": residual, "reason": "Not executable in the current closed grammar. " + " ".join(dict.fromkeys(reasons)) if reasons else "Unknown or ambiguous condition; specify its exact field, period, threshold and required data. Nothing will run."})
    if not conditions and not refusals:
        refusals.append({"phrase": ask, "reason": "No measurable condition was supplied."})
    return {"schema_version": "toolkit.screen-interpretation.v1", "ask": ask,
            "status": "refused" if refusals else "resolved", "conditions": conditions,
            "interpretations": interpretations, "refusals": refusals,
            "substitutes": ["Williams %R(14) < -80 is exactly fast Stoch %K(14,1,3) < 20 for identical bars and nonzero range; neither field is wired into this screen.", "Slow %K(14,3) equals fast %D(14,1,3) only with the same 3-session SMA smoothing. These are not RSI substitutes."],
            "scope": "All rows in a local dataset, or an explicitly supplied bounded live watchlist. Never a whole-market claim."}


def run_composed_screen(rows, interpretation, *, limit=25):
    if interpretation["status"] != "resolved":
        raise ValueError("refused screen must not execute")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be from 1 to 100")
    candidates, exclusions = [], []
    for row in rows:
        reasons = []
        for condition in interpretation["conditions"]:
            field, op, right = condition["field"], condition["op"], condition["value"]
            if field == "support_distance_atr":
                left, _issue = _support_distance(row)
            elif field == "sma20_distance_atr":
                left = abs(row.price - row.sma20) / row.atr14 if row.sma20 is not None and row.atr14 is not None and row.atr14 > 0 else None
            else:
                left = getattr(row, field)
            if op == "gt_field":
                right = getattr(row, right)
            if left is None or right is None:
                reasons.append(f"{field}: required field not supplied")
            elif not {"gt": lambda: left > right, "gt_field": lambda: left > right, "gte": lambda: left >= right, "lte": lambda: left <= right}[op]():
                reasons.append(f"{field}: disclosed condition not met")
        if reasons:
            exclusions.append({"ticker": row.ticker, "reasons": reasons})
        else:
            candidates.append({"ticker": row.ticker, "as_of": row.as_of, "price": row.price})
    candidates.sort(key=lambda row: row["ticker"])
    return {**interpretation, "ranking_method": "Ticker order; no performance ranking.",
            "coverage": len(rows), "candidates": candidates[:limit], "exclusions": sorted(exclusions, key=lambda row: row["ticker"]),
            "omitted_candidates": max(0, len(candidates) - limit), "warnings": list(dict.fromkeys(warning for row in rows for warning in row.warnings))}
