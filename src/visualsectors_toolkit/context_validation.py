"""Closed evidence contracts, identities, lineage and temporal validation."""
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import re
from .context_math import bars, period
from .context_peers import canonical_topic
from .context_market import new_york_close


RETRIEVAL_RELEASE = "screener-context-retrieval-v2.2.0"
POLICIES = {
    "price_policy": {"basis": "raw_ohlcv_pit_split_normalized", "analysis_window_sessions": 23,
                     "minimum_analysis_sessions": 20, "baseline_sessions": 252,
                     "fields": ["session", "open", "high", "low", "close", "volume"]},
    "peer_policy": {"taxonomy": "sic4_then_sic2", "universe": "paper_common_stock_pit", "comparison_sessions": [5, 10, 21],
                    "minimum_eligible_members": 5, "maximum_members_per_industry": 30, "exclude_candidate": True},
    "market_policy": {"benchmark_tickers": ["SPY", "QQQ", "IWM", "RSP"], "primary_benchmark": "SPY", "breadth_universe": "paper_common_stock_pit", "include_vix": True},
    "news_policy": {"lookback_calendar_days": 14, "maximum_candidate_headlines": 8, "maximum_industry_headlines": 12,
                    "maximum_market_headlines": 24, "minimum_ticker_relevance": 0.5, "require_cutoff": True},
}
IDENTITY_FIELDS = {"candidate_id", "vs_security_id", "ticker", "company_name", "industry_id", "industry_label"}
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
HASH = re.compile(r"[a-f0-9]{64}\Z")


def fail(code):
    raise ValueError("screener_context_" + code)


def exact(value, fields, label, optional=()):
    if not isinstance(value, dict) or set(value) - set(fields) - set(optional) or set(fields) - set(value):
        fail(label + "_fields_invalid")


def number(value, nullable=True):
    return value is None and nullable or type(value) in (int, float) and isfinite(value)


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def text(value, maximum=180, nullable=False):
    return value is None and nullable or isinstance(value, str) and 0 < len(value) <= maximum and not CONTROL.search(value)


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value):
        fail("timestamp_invalid")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail("timestamp_invalid")


def session(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        fail("session_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError:
        fail("session_invalid")


def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def validate_spec(spec):
    exact(spec, {"schema_version", "retrieval_release", "decision_time", "as_of_session", "screen", "candidates", *POLICIES}, "retrieval")
    if spec["schema_version"] != "screener_context_retrieval_spec.v2" or spec["retrieval_release"] != RETRIEVAL_RELEASE:
        fail("retrieval_identity_invalid")
    decision = timestamp(spec["decision_time"])
    if datetime.combine(session(spec["as_of_session"]), datetime.min.time(), timezone.utc) > decision:
        fail("retrieval_as_of_after_decision_time")
    if new_york_close(spec["as_of_session"]) > decision:
        fail("retrieval_session_not_closed_at_decision")
    exact(spec["screen"], {"kind", "screen_id", "screen_release", "definition_hash"}, "screen")
    if spec["screen"]["kind"] not in ("preset", "custom") or not HASH.fullmatch(spec["screen"]["definition_hash"]) or not all(text(spec["screen"][key]) for key in ("screen_id", "screen_release")):
        fail("screen_identity_invalid")
    if not isinstance(spec["candidates"], list) or not 1 <= len(spec["candidates"]) <= 100:
        fail("retrieval_candidate_cap_exceeded")
    ids, securities = set(), set()
    for candidate in spec["candidates"]:
        exact(candidate, IDENTITY_FIELDS, "candidate")
        if not all(text(candidate[key]) for key in ("candidate_id", "vs_security_id", "ticker")) or candidate["candidate_id"] in ids or candidate["vs_security_id"] in securities:
            fail("candidate_identity_invalid")
        ids.add(candidate["candidate_id"])
        securities.add(candidate["vs_security_id"])
    if any(spec[key] != value for key, value in POLICIES.items()):
        fail("retrieval_policy_not_allowlisted")
    return decision


def validate_series(series, as_of):
    exact(series, {"vs_security_id", "ticker", "bars"}, "series")
    if not text(series["vs_security_id"]) or not text(series["ticker"], 32) or not isinstance(series["bars"], list) or len(series["bars"]) > 253:
        fail("series_invalid")
    previous = ""
    for bar in series["bars"]:
        exact(bar, {"session", "open", "high", "low", "close", "volume"}, "bar")
        session(bar["session"])
        if (bar["session"] <= previous or bar["session"] > as_of
                or not all(number(bar[key], False) and bar[key] > 0 for key in ("open", "high", "low", "close"))
                or bar["high"] < max(bar["open"], bar["close"]) or bar["low"] > min(bar["open"], bar["close"])
                or bar["high"] < bar["low"] or not number(bar["volume"]) or bar["volume"] is not None and bar["volume"] < 0):
            fail("bar_invalid")
        previous = bar["session"]


def cutoff(value, decision, code, required=False):
    if value is None:
        if required:
            fail(code)
        return
    if timestamp(value) > decision:
        fail(code)


def unit(value):
    return number(value) and (value is None or 0 <= value <= 1)


def validate_weighting(weighting, eligible, decision):
    fields = {"market_cap_source_cutoff", "capitalized_peer_count", "largest_member_ticker", "largest_member_weight", "top3_weight", "effective_member_count"}
    fields.update(f"{basis}_weight_return_{window}d" for basis in ("equal", "cap") for window in (5, 10, 21))
    exact(weighting, fields, "weighting")
    cutoff(weighting["market_cap_source_cutoff"], decision, "peer_aggregate_invalid__weighting", True)
    count = weighting["capitalized_peer_count"]
    largest, top3, effective = weighting["largest_member_weight"], weighting["top3_weight"], weighting["effective_member_count"]
    returns = [weighting[f"{basis}_weight_return_{window}d"] for basis in ("equal", "cap") for window in (5, 10, 21)]
    if (not integer(count) or count > eligible or not unit(largest) or not unit(top3)
            or not all(number(value) and (value is None or value > -1) for value in returns)
            or (largest is None) != (weighting["largest_member_ticker"] is None)
            or not text(weighting["largest_member_ticker"], 32, True)
            or largest is not None and top3 is not None and top3 + 1e-9 < largest
            or not number(effective) or effective is not None and not 1 - 1e-9 <= effective <= count + 1e-9
            or count == 0 and any(value is not None for value in [*returns, largest, top3, effective, weighting["largest_member_ticker"]])):
        fail("peer_aggregate_invalid__weighting")


def validate_packet(spec, packet):
    decision = validate_spec(spec)
    fields = {"schema_version", "retrieval_release", "retrieval_spec_hash", "decision_time", "as_of_session", "source_cutoffs", "source_query_hashes", "source_result_hashes", "candidates", "peer_groups", "peer_aggregates", "market_series", "market_breadth", "vix", "headlines", "risk_codes"}
    exact(packet, fields, "packet", {"headline_peers"})
    if (packet["schema_version"] != "screener_context_evidence_packet.v2" or packet["retrieval_release"] != spec["retrieval_release"]
            or packet["decision_time"] != spec["decision_time"] or packet["as_of_session"] != spec["as_of_session"]
            or packet["retrieval_spec_hash"] != canonical_hash(spec)):
        fail("packet_identity_invalid")
    lanes = {"headlines", "market_breadth", "peer_aggregates", "peer_membership", "price_paths"}
    if "headline_peers" in packet:
        lanes.add("headline_peers")
    for label in ("source_query_hashes", "source_result_hashes"):
        exact(packet[label], lanes, "source_provenance")
        if any(not isinstance(value, str) or not HASH.fullmatch(value) for value in packet[label].values()):
            fail("source_provenance_invalid")
    exact(packet["source_cutoffs"], {"prices", "peer_membership", "market", "headlines"}, "source_cutoffs")
    for value in packet["source_cutoffs"].values():
        cutoff(value, decision, "source_cutoff_after_decision")
    for label in ("candidates", "peer_groups", "peer_aggregates", "market_series", "headlines", "risk_codes"):
        if not isinstance(packet[label], list):
            fail(label + "_invalid")
    if not all(text(code) for code in packet["risk_codes"]):
        fail("risk_codes_invalid")
    if len(packet["candidates"]) != len(spec["candidates"]):
        fail("candidate_population_mismatch")
    candidates = {}
    for candidate, expected in zip(packet["candidates"], spec["candidates"]):
        exact(candidate, IDENTITY_FIELDS | {"industry_resolution", "series"}, "candidate_evidence")
        if any(candidate[key] != expected[key] for key in ("candidate_id", "vs_security_id", "ticker", "industry_id", "industry_label")):
            fail("candidate_identity_or_order_mismatch")
        validate_series(candidate["series"], packet["as_of_session"])
        if any(candidate["series"][key] != candidate[key] for key in ("vs_security_id", "ticker")):
            fail("candidate_series_identity_mismatch")
        resolution = candidate["industry_resolution"]
        exact(resolution, {"requested_industry_id", "requested_industry_label", "resolved_industry_id", "resolved_industry_label", "resolved_taxonomy_level", "status"}, "resolution")
        resolved = resolution["status"] == "resolved_from_point_in_time_sic"
        if (resolution["status"] not in ("unresolved", "resolved_from_point_in_time_sic")
                or resolution["requested_industry_id"] != expected["industry_id"] or resolution["requested_industry_label"] != expected["industry_label"]
                or not resolved and any(resolution[key] is not None for key in ("resolved_industry_id", "resolved_industry_label", "resolved_taxonomy_level"))
                or resolved and (resolution["resolved_taxonomy_level"] not in ("sic4", "sic2") or not text(resolution["resolved_industry_label"])
                    or not isinstance(resolution["resolved_industry_id"], str) or not resolution["resolved_industry_id"].startswith(resolution["resolved_taxonomy_level"] + ":"))):
            fail("candidate_industry_resolution_invalid")
        candidates[candidate["candidate_id"]] = candidate
    groups = {}
    for group in packet["peer_groups"]:
        exact(group, {"industry_id", "industry_label", "taxonomy_level", "membership_release", "effective_at", "eligible_member_count", "members"}, "peer_group")
        cutoff(group["effective_at"], decision, "peer_group_invalid", True)
        owners = [row for row in candidates.values() if row["industry_resolution"]["resolved_industry_id"] == group["industry_id"]]
        if (group["industry_id"] in groups or group["taxonomy_level"] not in ("sic4", "sic2") or not group["industry_id"].startswith(group["taxonomy_level"] + ":")
                or not owners or any(row["industry_resolution"]["resolved_industry_label"] != group["industry_label"] or row["industry_resolution"]["resolved_taxonomy_level"] != group["taxonomy_level"] for row in owners)
                or not isinstance(group["members"], list) or len(group["members"]) > 30 or not integer(group["eligible_member_count"], len(group["members"]))):
            fail("peer_group_invalid")
        groups[group["industry_id"]] = group
        for member in group["members"]:
            validate_series(member, packet["as_of_session"])
        if len({member["vs_security_id"] for member in group["members"]}) != len(group["members"]):
            fail("peer_group_invalid")
    if any(row["industry_resolution"]["resolved_industry_id"] is not None and row["industry_resolution"]["resolved_industry_id"] not in groups for row in candidates.values()):
        fail("candidate_industry_group_missing")
    aggregate_ids = set()
    for aggregate in packet["peer_aggregates"]:
        base = {"candidate_id", "industry_id", "taxonomy_level", "eligible_peer_count", "observed_peer_count_10d", "observed_peer_count_21d", "peer_median_return_10d", "peer_median_return_21d", "peer_positive_breadth_10d", "peer_dispersion_10d", "direction_agreement_10d", "source_cutoff", "membership_source_cutoff", "membership_release_fingerprint"}
        optional = {"weighting"}
        optional.update(f"{field}_{window}d" for window in (5, 21) for field in ("observed_peer_count", "peer_median_return", "peer_positive_breadth", "peer_dispersion", "direction_agreement"))
        optional.update(f"candidate_{field}_{window}d" for field in ("return", "excess_return") for window in (5, 10, 21))
        exact(aggregate, base, "peer_aggregate", optional)
        candidate = candidates.get(aggregate["candidate_id"])
        group = groups.get(aggregate["industry_id"])
        if candidate is None or group is None or aggregate["candidate_id"] in aggregate_ids or candidate["industry_resolution"]["resolved_industry_id"] != aggregate["industry_id"] or aggregate["taxonomy_level"] != group["taxonomy_level"]:
            fail("peer_aggregate_invalid__identity")
        aggregate_ids.add(aggregate["candidate_id"])
        eligible = aggregate["eligible_peer_count"]
        if not integer(eligible) or eligible != group["eligible_member_count"]:
            fail("peer_aggregate_invalid__eligible_count")
        total = 0
        for window in (5, 10, 21):
            count = aggregate.get(f"observed_peer_count_{window}d")
            if count is None and window == 5:
                continue
            if not integer(count) or count > eligible:
                fail("peer_aggregate_invalid__observed_counts")
            total += count
            for field in ("peer_median_return", "peer_positive_breadth", "peer_dispersion", "direction_agreement"):
                key = f"{field}_{window}d"
                if key not in aggregate:
                    continue
                value = aggregate[key]
                if (not number(value) or count == 0 and value is not None
                        or count > 0 and value is None and field != "direction_agreement"
                        or field == "peer_median_return" and value is not None and value <= -1
                        or field == "peer_dispersion" and value is not None and value < 0
                        or field in ("peer_positive_breadth", "direction_agreement") and not unit(value)):
                    fail("peer_aggregate_invalid__metrics_" + str(window) + "d")
        cutoff(aggregate["source_cutoff"], decision, "peer_aggregate_invalid__source_cutoff", total > 0)
        cutoff(aggregate["membership_source_cutoff"], decision, "peer_aggregate_invalid__membership", True)
        if not HASH.fullmatch(aggregate["membership_release_fingerprint"]):
            fail("peer_aggregate_invalid__membership")
        for window in (5, 10, 21):
            expected = period(bars(candidate["series"]), window)
            median_value = aggregate.get(f"peer_median_return_{window}d")
            for field, measured in (("return", expected), ("excess_return", None if expected is None or median_value is None else expected - median_value)):
                key = f"candidate_{field}_{window}d"
                if key in aggregate and (not number(aggregate[key]) or (aggregate[key] is None) != (measured is None) or measured is not None and abs(aggregate[key] - measured) > 1e-8):
                    fail("peer_aggregate_invalid__candidate_returns")
        if "weighting" in aggregate:
            validate_weighting(aggregate["weighting"], eligible, decision)
    if sorted(row["ticker"] for row in packet["market_series"]) != ["IWM", "QQQ", "RSP", "SPY"]:
        fail("market_series_invalid")
    for series in packet["market_series"]:
        validate_series(series, packet["as_of_session"])
    breadth = packet["market_breadth"]
    exact(breadth, {"positive_10d_pct", "positive_21d_pct", "above_sma50_pct", "eligible_count_10d", "eligible_count_21d", "eligible_count_sma50"}, "market_breadth")
    for metric, count_name in (("positive_10d_pct", "eligible_count_10d"), ("positive_21d_pct", "eligible_count_21d"), ("above_sma50_pct", "eligible_count_sma50")):
        value, eligible = breadth[metric], breadth[count_name]
        if not integer(eligible) or not number(value) or value is not None and not 0 <= value <= 100 or (eligible == 0) != (value is None):
            fail("market_breadth_invalid")
    if packet["vix"] is not None:
        exact(packet["vix"], {"value", "sma50", "sma200", "term_structure", "available_at"}, "vix")
        cutoff(packet["vix"]["available_at"], decision, "market_vix_invalid", True)
        if not number(packet["vix"]["value"], False) or packet["vix"]["value"] < 0:
            fail("market_vix_invalid")
    if (any(row["series"]["bars"] for row in candidates.values()) and packet["source_cutoffs"]["prices"] is None
            or groups and packet["source_cutoffs"]["peer_membership"] is None
            or (any(row["bars"] for row in packet["market_series"]) or any(breadth[key] > 0 for key in breadth if key.startswith("eligible")) or packet["vix"] is not None) and packet["source_cutoffs"]["market"] is None
            or packet["headlines"] and packet["source_cutoffs"]["headlines"] is None):
        fail("source_lineage_missing")
    validate_headlines(spec, packet, decision, candidates, groups)
    validate_headline_peers(packet, decision, candidates)
    return packet


def validate_headlines(spec, packet, decision, candidates, groups):
    seen = set()
    caps = {"candidate": 8 * len(candidates), "industry": 12 * max(1, len(groups)), "market": 24}
    for scope, cap in caps.items():
        if any(not isinstance(row, dict) for row in packet["headlines"]) or sum(row.get("scope") == scope for row in packet["headlines"]) > cap:
            fail("headline_cap_exceeded")
    for row in packet["headlines"]:
        exact(row, {"headline_id", "scope", "candidate_ids", "industry_ids", "title", "teaser", "url", "topics", "sentiment_score", "created_at", "availability_semantics"}, "headline", {"linked_tickers", "relevance_score"})
        created = timestamp(row["created_at"])
        if not all(isinstance(row[key], list) and all(text(value) for value in row[key]) for key in ("candidate_ids", "industry_ids")):
            fail("headline_links_invalid")
        if "linked_tickers" in row:
            if not isinstance(row["linked_tickers"], list):
                fail("headline_links_invalid")
            for linked in row["linked_tickers"]:
                exact(linked, {"ticker", "relevance_score"}, "headline_ticker_link")
                if not text(linked["ticker"], 32) or not unit(linked["relevance_score"]) or linked["relevance_score"] is None:
                    fail("headline_links_invalid")
        if (created > decision or (decision - created).total_seconds() > 14 * 86400 or row["availability_semantics"] != "created_at_proxy"
                or row["scope"] not in caps or row["headline_id"] in seen
                or not text(row["headline_id"]) or not text(row["title"], 1000) or not text(row["url"], 2048) or not text(row["teaser"], 2000, True)
                or not isinstance(row["topics"], list) or len(row["topics"]) > 8 or not all(text(topic, 80) for topic in row["topics"])
                or not number(row["sentiment_score"]) or row["sentiment_score"] is not None and not -1 <= row["sentiment_score"] <= 1
                or row["scope"] == "candidate" and (not row["candidate_ids"] or any(key not in candidates for key in row["candidate_ids"]))
                or row["scope"] == "industry" and (not row["industry_ids"] or any(key not in groups for key in row["industry_ids"]))
                or row["scope"] == "market" and (row["candidate_ids"] or row["industry_ids"])
                or len(set(row["candidate_ids"])) != len(row["candidate_ids"]) or len(set(row["industry_ids"])) != len(row["industry_ids"])
                or "relevance_score" in row and (not unit(row["relevance_score"]) or row["scope"] == "candidate" and row["relevance_score"] is not None and row["relevance_score"] < 0.5)):
            fail("headline_cutoff_invalid")
        seen.add(row["headline_id"])
    if packet["headlines"] and "HEADLINE_AVAILABILITY_CREATED_AT_PROXY" not in packet["risk_codes"]:
        fail("headline_availability_risk_missing")


def validate_headline_peers(packet, decision, candidates):
    if "headline_peers" not in packet:
        return
    rows = packet["headline_peers"]
    if not isinstance(rows, list) or len(rows) != len(candidates) or {row.get("candidate_id") for row in rows} != set(candidates):
        fail("headline_peers_invalid__population")
    for row in rows:
        exact(row, {"candidate_id", "lookback_calendar_days", "source_cutoff", "candidate_headline_count", "peers"}, "headline_peers")
        if row["lookback_calendar_days"] != 90 or not isinstance(row["peers"], list) or len(row["peers"]) > 8 or not integer(row["candidate_headline_count"]):
            fail("headline_peers_invalid__policy")
        cutoff(row["source_cutoff"], decision, "headline_peers_invalid__source_cutoff", bool(row["peers"]))
        seen = {candidates[row["candidate_id"]]["vs_security_id"]}
        for peer in row["peers"]:
            exact(peer, {"vs_security_id", "ticker", "co_mention_count", "topics", "same_industry", "series"}, "headline_peer")
            if peer["vs_security_id"] in seen or type(peer["same_industry"]) is not bool or not integer(peer["co_mention_count"], 2) or peer["co_mention_count"] > row["candidate_headline_count"]:
                fail("headline_peers_invalid__counts")
            seen.add(peer["vs_security_id"])
            validate_series(peer["series"], packet["as_of_session"])
            if any(peer["series"][key] != peer[key] for key in ("ticker", "vs_security_id")):
                fail("headline_peers_invalid__identity")
            if len(peer["topics"]) > 4 or len({canonical_topic(topic["topic"]) for topic in peer["topics"]}) != len(peer["topics"]):
                fail("headline_peers_invalid__topics")
            for topic in peer["topics"]:
                exact(topic, {"topic", "co_mention_count"}, "headline_peer_topic")
                if not text(topic["topic"], 80) or not canonical_topic(topic["topic"]) or not integer(topic["co_mention_count"], 1) or topic["co_mention_count"] > peer["co_mention_count"]:
                    fail("headline_peers_invalid__topics")
