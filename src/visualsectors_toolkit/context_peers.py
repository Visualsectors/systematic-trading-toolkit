"""Pure industry, capitalisation and headline-peer comparisons."""
import re
from .context_math import aligned, bars, median, pct, period, rounded, sign


def canonical_topic(value):
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def empty_peers(resolution, group, risks):
    result = {"data_quality": "insufficient", "requested_industry_id": resolution["requested_industry_id"],
              "requested_industry_label": resolution["requested_industry_label"],
              "industry_id": group["industry_id"] if group else None,
              "industry_label": group["industry_label"] if group else None,
              "taxonomy_level": group["taxonomy_level"] if group else None,
              "eligible_peer_count": 0, "representative_peer_count": 0,
              "move_scope": "insufficient", "representative_leaders": [], "representative_laggards": [], "risk_codes": risks}
    for window in (5, 10, 21):
        result[f"observed_peer_count_{window}d"] = 0
        for field in ("peer_median_return", "peer_positive_breadth", "peer_dispersion", "candidate_excess", "direction_agreement"):
            result[f"{field}_{window}d_pct"] = None
    return result


def build_peers(candidate, group, aggregate):
    resolution, rows = candidate["industry_resolution"], bars(candidate["series"])
    if group is None or resolution["resolved_industry_id"] is None:
        return empty_peers(resolution, None, ["PEER_MEMBERSHIP_MISSING"])
    if aggregate is None or aggregate["candidate_id"] != candidate["candidate_id"] or aggregate["industry_id"] != group["industry_id"]:
        return empty_peers(resolution, group, ["PEER_AGGREGATE_MISSING"])
    returns = {window: period(rows, window) for window in (5, 10, 21)}
    members = []
    for series in group["members"]:
        if series["vs_security_id"] == candidate["series"]["vs_security_id"]:
            continue
        values = {window: aligned(series, rows, window) for window in (5, 10, 21)}
        if values[10] is not None:
            members.append((series, values))
    if (returns[10] is None or aggregate["observed_peer_count_10d"] < 2
            or aggregate["peer_median_return_10d"] is None or aggregate["peer_positive_breadth_10d"] is None):
        return empty_peers(resolution, group, ["PEER_PRICE_HISTORY_INSUFFICIENT"])
    scopes = []
    for window in (5, 10, 21):
        value, centre = returns[window], aggregate.get(f"peer_median_return_{window}d")
        breadth, dispersion = aggregate.get(f"peer_positive_breadth_{window}d"), aggregate.get(f"peer_dispersion_{window}d")
        agreement = aggregate.get(f"direction_agreement_{window}d")
        if value is None or centre is None or breadth is None:
            continue
        broad_direction = 1 if breadth >= 0.67 else -1 if breadth <= 0.33 else 0
        specific = abs(value - centre) >= max(0.03, (dispersion or 0) * 2) and abs(value) >= max(0.06, abs(centre) * 2)
        confirmed = not specific and sign(value) != 0 and sign(value) == broad_direction and sign(centre) == sign(value) and (agreement is None or agreement >= 0.6)
        scopes.append("industry_wide" if confirmed else "candidate_specific" if specific else "mixed")
    scope = scopes[0] if len(scopes) == 3 and all(item == scopes[0] for item in scopes) and scopes[0] != "mixed" else "mixed"
    risks = []
    if aggregate["observed_peer_count_10d"] < 5:
        risks.append("PEER_AGGREGATE_SAMPLE_SMALL")
    if aggregate["eligible_peer_count"] > 0 and aggregate["observed_peer_count_10d"] / aggregate["eligible_peer_count"] < 0.8:
        risks.append("PEER_AGGREGATE_PRICE_COVERAGE_PARTIAL")
    if len(members) < 2:
        risks.append("PEER_REPRESENTATIVE_SERIES_THIN")
    if group["taxonomy_level"] == "sic2":
        risks.append("PEER_TAXONOMY_WIDENED")
    if len(scopes) < 3:
        risks.append("PEER_MULTI_WINDOW_COVERAGE_PARTIAL")
    ordered = sorted(members, key=lambda row: -row[1][10])

    def representative(row):
        return {"ticker": row[0]["ticker"], **{f"return_{window}d_pct": pct(row[1][window]) for window in (5, 10, 21)}}

    result = empty_peers(resolution, group, risks)
    result.update(data_quality="partial" if risks else "complete", eligible_peer_count=aggregate["eligible_peer_count"],
                  representative_peer_count=len(members), move_scope=scope,
                  representative_leaders=[representative(row) for row in ordered[:3]],
                  representative_laggards=[representative(row) for row in reversed(ordered[-3:])])
    for window in (5, 10, 21):
        result[f"observed_peer_count_{window}d"] = aggregate.get(f"observed_peer_count_{window}d", 0)
        for field in ("peer_median_return", "peer_positive_breadth", "peer_dispersion", "direction_agreement"):
            result[f"{field}_{window}d_pct"] = pct(aggregate.get(f"{field}_{window}d"))
        centre = aggregate.get(f"peer_median_return_{window}d")
        result[f"candidate_excess_{window}d_pct"] = None if returns[window] is None or centre is None else pct(returns[window] - centre)
    return result


def empty_weighting(status):
    fields = ("capitalized_peer_count", "cap_minus_equal_pct", "comparison_sessions", "candidate_excess_vs_equal_weight_pct",
              "candidate_excess_vs_cap_weight_pct", "largest_member_ticker", "largest_member_weight_pct", "top3_weight_pct", "effective_member_count")
    result = {"status": status, **dict.fromkeys(fields), "concentration": "unavailable", "weighting_split": "unavailable", "preferred_basis": "median"}
    for basis in ("equal", "cap"):
        for window in (5, 10, 21):
            result[f"{basis}_weight_return_{window}d_pct"] = None
    return result


def build_weighting(aggregate, rows):
    weighting = (aggregate or {}).get("weighting")
    if weighting is None:
        return empty_weighting("not_supplied")
    window = next((window for window in (21, 10) if weighting[f"cap_weight_return_{window}d"] is not None and weighting[f"equal_weight_return_{window}d"] is not None), None)
    if weighting["capitalized_peer_count"] < 2 or window is None:
        return empty_weighting("insufficient")
    cap, equal = weighting[f"cap_weight_return_{window}d"], weighting[f"equal_weight_return_{window}d"]
    gap, threshold = pct(cap - equal), 2 if window == 21 else 1.5
    largest, top3 = weighting["largest_member_weight"], weighting["top3_weight"]
    concentration = "unavailable" if largest is None and top3 is None else "dominated" if (largest or 0) >= 0.4 else "concentrated" if (top3 or 0) >= 0.6 else "broad"
    value = period(rows, window)
    result = empty_weighting("measured")
    result.update(capitalized_peer_count=weighting["capitalized_peer_count"], cap_minus_equal_pct=gap,
                  comparison_sessions=window, candidate_excess_vs_equal_weight_pct=None if value is None else pct(value - equal),
                  candidate_excess_vs_cap_weight_pct=None if value is None else pct(value - cap),
                  largest_member_ticker=weighting["largest_member_ticker"], largest_member_weight_pct=None if largest is None else rounded(largest * 100, 1),
                  top3_weight_pct=None if top3 is None else rounded(top3 * 100, 1), effective_member_count=rounded(weighting["effective_member_count"], 1),
                  concentration=concentration, weighting_split="largest_members_lead" if gap >= threshold else "largest_members_lag" if gap <= -threshold else "agree",
                  preferred_basis="equal_weight" if concentration in ("dominated", "concentrated") else "median")
    for basis in ("equal", "cap"):
        for horizon in (5, 10, 21):
            result[f"{basis}_weight_return_{horizon}d_pct"] = pct(weighting[f"{basis}_weight_return_{horizon}d"])
    return result


def empty_headline_peers(status):
    return {"status": status, "lookback_calendar_days": None, "candidate_headline_count": None,
            "peer_count": 0, "outside_industry_count": 0, "median_return_5d_pct": None,
            "median_return_10d_pct": None, "median_return_21d_pct": None, "positive_breadth_10d_pct": None,
            "candidate_excess_5d_pct": None, "candidate_excess_21d_pct": None,
            "relation": "unavailable", "themes": [], "business_lines_split": False, "peers": []}


def build_headline_peers(row, rows):
    if row is None:
        return empty_headline_peers("not_supplied")
    result = empty_headline_peers("none_found" if not row["peers"] else "insufficient")
    result.update(lookback_calendar_days=row["lookback_calendar_days"], candidate_headline_count=row["candidate_headline_count"])
    measured = []
    for peer in row["peers"]:
        returns = {window: aligned(peer["series"], rows, window) for window in (5, 10, 21)}
        if returns[10] is not None:
            measured.append((peer, returns))
    if len(measured) < 2:
        return result
    medians = {window: median([returns[window] for _, returns in measured if returns[window] is not None]) for window in (5, 10, 21)}
    excess = {window: None if period(rows, window) is None or medians[window] is None else period(rows, window) - medians[window] for window in (5, 10, 21)}
    primary = excess[21] if excess[21] is not None else excess[10]
    relation = "mixed" if excess[5] is not None and excess[21] is not None and abs(excess[5]) >= 0.02 and abs(excess[21]) >= 0.02 and sign(excess[5]) != sign(excess[21]) else "unavailable" if primary is None else "leads" if primary >= 0.02 else "lags" if primary <= -0.02 else "moves_with"
    theme_rows = {}
    for peer, returns in measured:
        for topic in peer["topics"]:
            key = canonical_topic(topic["topic"])
            if not key:
                continue
            theme = theme_rows.setdefault(key, {"tickers": set(), "count": 0, "returns": []})
            theme["tickers"].add(peer["ticker"])
            theme["count"] += topic["co_mention_count"]
            if returns[21] is not None:
                theme["returns"].append(returns[21])
    themes = [{"topic": key, "label": key.replace("_", " "), "tickers": sorted(theme["tickers"]),
               "co_mention_count": theme["count"], "median_return_21d_pct": pct(median(theme["returns"]))}
              for key, theme in sorted(theme_rows.items(), key=lambda item: (-item[1]["count"], item[0]))[:3]]
    peers = []
    for peer, returns in sorted(measured, key=lambda row: (-row[0]["co_mention_count"], row[0]["ticker"])):
        topics = sorted(peer["topics"], key=lambda topic: (-topic["co_mention_count"], topic["topic"]))
        peers.append({"ticker": peer["ticker"], "co_mention_count": peer["co_mention_count"], "same_industry": peer["same_industry"],
                      "top_topic": topics[0]["topic"] if topics else None, **{f"return_{window}d_pct": pct(returns[window]) for window in (5, 10, 21)}})
    result.update(status="measured", peer_count=len(measured), outside_industry_count=sum(not peer["same_industry"] for peer, _ in measured),
                  **{f"median_return_{window}d_pct": pct(medians[window]) for window in (5, 10, 21)},
                  positive_breadth_10d_pct=rounded(sum(returns[10] > 0 for _, returns in measured) / len(measured) * 100, 1),
                  candidate_excess_5d_pct=pct(excess[5]), candidate_excess_21d_pct=pct(excess[21]), relation=relation,
                  themes=themes, business_lines_split=any(not (set(left["tickers"]) & set(right["tickers"])) for index, left in enumerate(themes) for right in themes[index + 1:]), peers=peers)
    return result
