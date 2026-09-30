"""Pure benchmark, narrative and co-movement features with explicit cutoffs."""
from datetime import date, datetime, timedelta, timezone
from math import ceil, sqrt
import re
from urllib.parse import urlsplit
from .context_math import aligned, bars, mad, mean, pct, period, rounded, sign
from .context_peers import canonical_topic
from .context_price import build_price, empty_price


TOPIC_RULES = (
    ("monetary_policy", r"\bfed(?:eral reserve)?\b|interest rate|central bank"),
    ("inflation", r"inflation|\bcpi\b|consumer price|\bppi\b"),
    ("growth_recession", r"recession|economic growth|\bgdp\b|soft landing|hard landing"),
    ("labor_market", r"employment|jobs report|nonfarm payroll|unemployment|jobless claims"),
    ("rates_credit", r"treasury yield|bond yield|credit spread|credit market"),
    ("equity_risk", r"stock market|\bstocks\b|s&p 500|nasdaq|dow jones|risk[- ]off|volatility|\bvix\b"),
    ("fiscal_policy", r"fiscal|government shutdown|debt ceiling|budget deficit"),
    ("currency", r"us dollar|\bdollar\b|\bdxy\b|foreign exchange"),
    ("consumer", r"consumer spending|retail sales|consumer confidence"),
    ("earnings", r"earnings|revenue|profit|guidance|quarterly result"),
    ("ai_capex", r"artificial intelligence|\bai\b|data cent(?:er|re)|semiconductor"),
    ("regulation", r"regulat|antitrust|justice department|\bsec\b"),
    ("geopolitics", r"tariff|sanction|\bwar\b|geopolit|trade conflict"),
    ("energy", r"crude oil|natural gas|\bopec\b|oil price"),
)


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def topic_groups(headlines):
    groups = {}
    for headline in headlines:
        codes = headline["topics"] or [code for code, pattern in TOPIC_RULES if re.search(pattern, headline["title"].lower())]
        for code in (codes or ["other"])[:4]:
            groups.setdefault(canonical_topic(code), []).append(headline)
    return groups


def source_host(url):
    try:
        parsed = urlsplit(url.strip())
        hostname = (parsed.hostname or "").lower().removeprefix("www.")
        if parsed.scheme not in ("http", "https") or parsed.port is not None and parsed.port > 65535:
            return None
        return hostname if 0 < len(hostname) <= 253 and all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in hostname.split(".")) else None
    except ValueError:
        return None


def build_narratives(headlines, scope, decision_time):
    result = []
    for label, rows in topic_groups(headlines).items():
        unique = sorted({row["headline_id"]: row for row in rows}.values(), key=lambda row: row["created_at"], reverse=True)
        scores = [row["sentiment_score"] for row in unique if row["sentiment_score"] is not None]
        positive, negative = any(score >= 0.2 for score in scores), any(score <= -0.2 for score in scores)
        latest = max(instant(row["created_at"]) for row in unique)
        sources = {source_host(row["url"]) for row in unique} - {None}
        result.append({"cluster_id": f"{scope}:{label}", "label": label.replace("_", " "), "scope": scope,
                       "article_count": len(unique), "source_count": len(sources) or None,
                       "freshness_hours": rounded(max(0, (instant(decision_time) - latest).total_seconds()) / 3600, 1),
                       "sentiment": "mixed" if positive and negative else "positive" if positive else "negative" if negative else "unknown" if not scores else "neutral",
                       "headline_ids": [row["headline_id"] for row in unique][:8],
                       "representative_headlines": [{"headline_id": row["headline_id"], "title": row["title"][:240],
                                                     "url": row["url"], "created_at": row["created_at"]} for row in unique[:3]]})
    return sorted(result, key=lambda row: (-row["article_count"], row["freshness_hours"]))[:6]


def market_direction(value, threshold):
    return "unavailable" if value is None else "up" if value > threshold else "down" if value < -threshold else "flat"


def sentiment_direction(value):
    return 1 if value == "positive" else -1 if value == "negative" else 0


def new_york_close(session):
    """The released regular-close policy, US Eastern DST rules since 2007."""
    day = date.fromisoformat(session)
    first = date(day.year, day.month, 1)
    first_sunday = 1 + (6 - first.weekday()) % 7
    daylight = (3 < day.month < 11 or day.month == 3 and day.day >= first_sunday + 7
                or day.month == 11 and day.day < first_sunday)
    return datetime(day.year, day.month, day.day, 20 if daylight else 21, tzinfo=timezone.utc)


def narrative_roles(narratives, headlines, spy, r21, r5, decision_time):
    direction21, direction5 = market_direction(r21, 1), market_direction(r5, 0.5)
    shift = direction21 == "up" and direction5 == "down" or direction21 == "down" and direction5 == "up"
    decision = instant(decision_time)
    grouped = topic_groups(headlines)
    spy_bars = bars(spy) if spy else []
    start = (decision - timedelta(days=14)).date().isoformat()
    returns = [(bar["session"], bar["close"] / spy_bars[index]["close"] - 1)
               for index, bar in enumerate(spy_bars[1:]) if bar["session"] >= start]
    roles = []
    for narrative in narratives:
        key = narrative["cluster_id"].split(":", 1)[1]
        if key == "other":
            continue
        rows = list({row["headline_id"]: row for row in grouped.get(key, [])}.values())
        recent = sum(instant(row["created_at"]) >= decision - timedelta(hours=72) for row in rows)
        share = recent / len(rows) if rows else 0
        reaction_sessions = set()
        for row in rows:
            created = instant(row["created_at"])
            bar = next((bar for bar in spy_bars if new_york_close(bar["session"]) > created), None)
            if bar:
                reaction_sessions.add(bar["session"])
        on = [value for session, value in returns if session in reaction_sessions]
        other = [value for session, value in returns if session not in reaction_sessions]
        on_mean, other_mean = pct(mean(on)), pct(mean(other))
        sentiment_sign = sentiment_direction(narrative["sentiment"])
        market_sign = 1 if direction21 == "up" else -1 if direction21 == "down" else 0
        roles.append({"cluster_id": narrative["cluster_id"], "label": narrative["label"], "sentiment": narrative["sentiment"],
                      "alignment": "unaligned" if not sentiment_sign or not market_sign else "with_market" if sentiment_sign == market_sign else "against_market",
                      "article_count": narrative["article_count"], "recent_article_share_pct": rounded(share * 100, 1),
                      "momentum": "rising" if len(rows) >= 2 and share >= 0.5 else "fading" if len(rows) >= 3 and recent == 0 else "steady",
                      "reaction_session_count": len(on), "spy_mean_return_on_narrative_sessions_pct": on_mean,
                      "spy_mean_return_other_sessions_pct": other_mean,
                      "reaction_gap_pct": None if on_mean is None or other_mean is None else rounded(on_mean - other_mean, 2)})
    top = roles[0] if roles else None
    leading = next((role for role in roles if role["alignment"] == "with_market" and role["article_count"] >= max(2, ceil(top["article_count"] / 2))), top) if top else None
    lead_sign = sentiment_direction(leading["sentiment"]) if leading else 0
    market_sign = 1 if direction21 == "up" else -1 if direction21 == "down" else 0
    against = -lead_sign if lead_sign else -market_sign
    challengers = sorted([role for role in roles if role is not leading and role["article_count"] >= 2 and sentiment_direction(role["sentiment"]) == against],
                         key=lambda role: (-int(role["momentum"] == "rising"), -role["recent_article_share_pct"], -role["article_count"], role["cluster_id"])) if against else []
    return {"market_direction_21d": direction21, "market_direction_5d": direction5, "direction_shift": shift,
            "leading": leading, "challenging": challengers[0] if challengers else None}


def co_movement(candidate_bars, spy, roles, clusters):
    keys = {row["cluster_id"].split(":", 1)[1] for row in clusters}
    leading = roles["leading"] is not None and roles["leading"]["cluster_id"].split(":", 1)[1] in keys
    challenging = roles["challenging"] is not None and roles["challenging"]["cluster_id"].split(":", 1)[1] in keys
    link = "unavailable" if roles["leading"] is None and roles["challenging"] is None or not clusters else "both" if leading and challenging else "leading" if leading else "challenging" if challenging else "neither"
    result = {"return_session_count": 0, "correlation_60d": None, "beta_60d": None, "state": "unavailable", "direction_vs_market_21d": "unavailable", "narrative_link": link}
    if spy is None or len(candidate_bars) < 2:
        return result
    closes = {bar["session"]: bar["close"] for bar in bars(spy)}
    pairs = []
    for index in range(len(candidate_bars) - 1, 0, -1):
        current, previous = candidate_bars[index], candidate_bars[index - 1]
        if current["session"] not in closes or previous["session"] not in closes:
            continue
        pairs.append((current["close"] / previous["close"] - 1, closes[current["session"]] / closes[previous["session"]] - 1))
        if len(pairs) == 60:
            break
    correlation = beta = None
    if len(pairs) >= 20:
        candidate_mean, spy_mean = mean([a for a, _ in pairs]), mean([b for _, b in pairs])
        covariance = sum((a - candidate_mean) * (b - spy_mean) for a, b in pairs)
        candidate_variance = sum((a - candidate_mean) ** 2 for a, _ in pairs)
        spy_variance = sum((b - spy_mean) ** 2 for _, b in pairs)
        if candidate_variance > 0 and spy_variance > 0:
            correlation, beta = rounded(covariance / sqrt(candidate_variance * spy_variance), 2), rounded(covariance / spy_variance, 2)
    candidate21, spy21 = period(candidate_bars, 21), aligned(spy, candidate_bars, 21)
    direction = "unavailable" if candidate21 is None or spy21 is None else "flat" if abs(candidate21) < 0.01 or abs(spy21) < 0.01 else "same" if sign(candidate21) == sign(spy21) else "opposite"
    result.update(return_session_count=len(pairs), correlation_60d=correlation, beta_60d=beta,
                  state="unavailable" if correlation is None else "tracks_market" if correlation >= 0.5 else "loosely_tracks" if correlation >= 0.2 else "independent",
                  direction_vs_market_21d=direction)
    return result


def build_market(packet):
    actions = [(series, build_price(series) if series["bars"] and series["bars"][-1]["session"] == packet["as_of_session"]
                else empty_price(min(len(series["bars"]), 23), ["MARKET_BENCHMARK_STALE"])) for series in packet["market_series"]]
    usable = [(series, price) for series, price in actions if series["bars"] and series["bars"][-1]["session"] == packet["as_of_session"] and all(price[f"return_{window}d_pct"] is not None for window in (5, 10, 21))]
    risks = []
    if len(usable) < len(actions):
        risks.append("MARKET_BENCHMARK_COVERAGE_THIN")
    if any(series["bars"] and series["bars"][-1]["session"] != packet["as_of_session"] for series, _ in actions):
        risks.append("MARKET_BENCHMARK_STALE")
    if any(not series["bars"] or series["bars"][-1]["session"] == packet["as_of_session"] and price["return_21d_pct"] is None for series, price in actions):
        risks.append("MARKET_BENCHMARK_MISSING")
    benchmark_returns = []
    for ticker in ("SPY", "QQQ", "IWM", "RSP"):
        price = next((price for series, price in actions if series["ticker"] == ticker), {})
        benchmark_returns.append({"ticker": ticker, **{f"return_{window}d_pct": price.get(f"return_{window}d_pct") for window in (5, 10, 21)}})
    primary = next(((series, price) for series, price in actions if series["ticker"] == "SPY"), None)
    headlines = [row for row in packet["headlines"] if row["scope"] == "market"]
    narratives = build_narratives(headlines, "market", packet["decision_time"])
    current = primary if primary and primary[0]["bars"] and primary[0]["bars"][-1]["session"] == packet["as_of_session"] else None
    roles = narrative_roles(narratives, headlines, current[0] if current else None,
                            current[1]["return_21d_pct"] if current else None, current[1]["return_5d_pct"] if current else None, packet["decision_time"])
    result = {"data_quality": "insufficient", "regime": "insufficient", "primary_benchmark": "SPY",
              "benchmark_return_5d_pct": None, "benchmark_return_10d_pct": None, "benchmark_return_21d_pct": None,
              "benchmark_returns": benchmark_returns, "benchmark_dispersion_10d_pct": None,
              "breadth": packet["market_breadth"], "vix": packet["vix"], "narratives": narratives, "narrative_roles": roles}
    if primary is None or primary[1]["return_21d_pct"] is None:
        result["risk_codes"] = list(dict.fromkeys([*risks, "MARKET_BENCHMARK_MISSING"]))
        return result
    return10s = [price["return_10d_pct"] for _, price in usable]
    breadth = packet["market_breadth"]
    b10, b21, above = breadth["positive_10d_pct"], breadth["positive_21d_pct"], breadth["above_sma50_pct"]
    vix = packet["vix"]["value"] if packet["vix"] else None
    r21, r5 = primary[1]["return_21d_pct"], primary[1]["return_5d_pct"] or 0
    breadth_off = any(value is not None and value <= 35 for value in (b10, b21, above))
    broad_off = len(return10s) >= 3 and sum(value < 0 for value in return10s) >= 3
    volatility_off = vix is not None and vix >= 25
    regime = "risk_off" if r21 <= -5 and (volatility_off or breadth_off or broad_off) else "volatile_rebound" if r21 < 0 and r5 >= 3 and (volatility_off or breadth_off) else "risk_on_broad" if r21 >= 3 and (b10 if b10 is not None else -1) >= 60 and (above if above is not None else -1) >= 55 else "risk_on_narrow" if r21 >= 3 else "range" if abs(r21) < 3 and (vix is None or vix < 22) and not breadth_off else "mixed"
    if any(value is None for value in (b10, b21, above)):
        risks.append("MARKET_BREADTH_MISSING")
    if packet["vix"] is None:
        risks.append("MARKET_VIX_MISSING")
    if regime == "risk_off":
        risks.append("MARKET_RISK_OFF")
    if regime == "risk_on_narrow":
        risks.append("MARKET_PARTICIPATION_NARROW")
    critical = {"MARKET_BREADTH_MISSING", "MARKET_BENCHMARK_MISSING", "MARKET_BENCHMARK_STALE", "MARKET_BENCHMARK_COVERAGE_THIN"}
    result.update(data_quality="partial" if critical.intersection(risks) else "complete", regime=regime,
                  **{f"benchmark_return_{window}d_pct": primary[1][f"return_{window}d_pct"] for window in (5, 10, 21)},
                  benchmark_dispersion_10d_pct=rounded(mad(return10s), 2), risk_codes=risks)
    return result
