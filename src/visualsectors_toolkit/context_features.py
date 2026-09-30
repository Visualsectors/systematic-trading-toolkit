"""Python port of preset-skills 0.5.0's complete deterministic feature packet."""
from copy import deepcopy
from .context_evidence import candidate_evidence, market_evidence
from .context_math import aligned, bars, pct, period
from .context_market import build_market, build_narratives, co_movement
from .context_peers import build_headline_peers, build_peers, build_weighting, empty_headline_peers, empty_peers, empty_weighting
from .context_price import build_price, empty_price
from .context_validation import validate_packet


def compute_context(spec, packet):
    """Return released features without I/O, wall-clock reads or input mutation."""
    try:
        validate_packet(spec, packet)
    except (TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise ValueError("screener_context_malformed_evidence") from exc
    packet = deepcopy(packet)
    market = build_market(packet)
    evidence = market_evidence(market)
    benchmarks = {row["ticker"]: row for row in packet["market_series"]}
    groups = {row["industry_id"]: row for row in packet["peer_groups"]}
    aggregates = {row["candidate_id"]: row for row in packet["peer_aggregates"]}
    headline_peers = {row["candidate_id"]: row for row in packet.get("headline_peers", [])}
    candidates = []
    for candidate in packet["candidates"]:
        identity, rows = candidate["candidate_id"], bars(candidate["series"])
        current = bool(rows) and rows[-1]["session"] == packet["as_of_session"]
        price = build_price(candidate["series"]) if current else empty_price(min(len(rows), 23), ["PRICE_SESSION_STALE"])
        resolution = candidate["industry_resolution"]
        group, aggregate = groups.get(resolution["resolved_industry_id"]), aggregates.get(identity)
        peers = build_peers(candidate, group, aggregate) if current else empty_peers(resolution, group, ["PEER_CANDIDATE_SERIES_STALE"])
        stock_headlines = build_narratives([row for row in packet["headlines"] if row["scope"] == "candidate" and identity in row["candidate_ids"]], "candidate", packet["decision_time"])
        industry_headlines = build_narratives([row for row in packet["headlines"] if row["scope"] == "industry" and resolution["resolved_industry_id"] in row["industry_ids"]], "industry", packet["decision_time"]) if resolution["resolved_industry_id"] is not None else []
        computed = {"candidate_id": identity, "ticker": candidate["ticker"], "price": price, "peers": peers,
                    "stock_headlines": stock_headlines, "industry_headlines": industry_headlines}
        for benchmark in ("SPY", "QQQ"):
            series = benchmarks.get(benchmark)
            for window in (5, 10, 21):
                candidate_return = period(rows, window) if current else None
                benchmark_return = aligned(series, rows, window) if current and series and series["bars"] and series["bars"][-1]["session"] == packet["as_of_session"] else None
                computed[f"relative_to_{benchmark.lower()}_{window}d_pct"] = None if candidate_return is None or benchmark_return is None else pct(candidate_return - benchmark_return)
        computed["peer_weighting"] = build_weighting(aggregate, rows) if current and peers["data_quality"] != "insufficient" else empty_weighting("not_supplied" if not aggregate or "weighting" not in aggregate else "insufficient")
        computed["headline_peers"] = empty_headline_peers("not_supplied") if "headline_peers" not in packet else build_headline_peers(headline_peers.get(identity), rows) if current else empty_headline_peers("insufficient")
        spy = benchmarks.get("SPY")
        computed["market_co_movement"] = co_movement(rows if current else [], spy if spy and spy["bars"] and spy["bars"][-1]["session"] == packet["as_of_session"] else None, market["narrative_roles"], [*stock_headlines, *industry_headlines])
        evidence.extend(candidate_evidence(computed))
        candidates.append(computed)
    if len({row["evidence_id"] for row in evidence}) != len(evidence):
        raise ValueError("screener_context_evidence_id_duplicate")
    return {"schema_version": "computed_screener_context.v2", "feature_release": "screener-context-features-v2.4.0",
            "screen": deepcopy(spec["screen"]), "retrieval_spec_hash": packet["retrieval_spec_hash"],
            "decision_time": packet["decision_time"], "as_of_session": packet["as_of_session"],
            "candidates": candidates, "market": market, "evidence_index": evidence, "risk_codes": list(dict.fromkeys(packet["risk_codes"]))}
