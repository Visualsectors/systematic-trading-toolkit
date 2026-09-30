"""Additive dataset.v2 adapter; snapshot-only v1 remains unchanged."""
from copy import deepcopy
from .context_validation import exact, validate_packet
from .context_math import aligned, bars, mean, median, mad, period, sign


def member_aggregate(identity, candidate_series, group, caps, decision_time):
    """Compute only when supplied paths cover the declared full peer population."""
    from .context_validation import canonical_hash, validate_series
    members = [row for row in group["members"] if row["vs_security_id"] != identity["vs_security_id"]]
    if len(members) != group["eligible_member_count"]:
        raise ValueError("full peer aggregates require every eligible member, or an upstream aggregate; representatives are not the universe")
    for row in members:
        validate_series(row, decision_time[:10])
    rows = bars(candidate_series)
    result = {"candidate_id": identity["candidate_id"], "industry_id": group["industry_id"], "taxonomy_level": group["taxonomy_level"],
              "eligible_peer_count": len(members), "source_cutoff": decision_time,
              "membership_source_cutoff": group["effective_at"], "membership_release_fingerprint": canonical_hash({"release": group["membership_release"], "effective_at": group["effective_at"], "members": [row["vs_security_id"] for row in members]})}
    for window in (5, 10, 21):
        values = [value for row in members if (value := aligned(row, rows, window)) is not None]
        candidate_return = period(rows, window)
        result.update({f"observed_peer_count_{window}d": len(values), f"peer_median_return_{window}d": median(values),
                       f"peer_positive_breadth_{window}d": sum(value > 0 for value in values) / len(values) if values else None,
                       f"peer_dispersion_{window}d": mad(values),
                       f"direction_agreement_{window}d": sum(sign(value) == sign(candidate_return) for value in values) / len(values) if values and candidate_return is not None else None})
    capitalized = [row for row in members if row["vs_security_id"] in caps]
    if capitalized:
        total = sum(caps[row["vs_security_id"]]["market_cap"] for row in capitalized)
        weights = sorted([(row, caps[row["vs_security_id"]]["market_cap"] / total) for row in capitalized], key=lambda item: (-item[1], item[0]["ticker"]))
        weighting = {"market_cap_source_cutoff": max(caps[row["vs_security_id"]]["available_at"] for row in capitalized),
                     "capitalized_peer_count": len(capitalized), "largest_member_ticker": weights[0][0]["ticker"],
                     "largest_member_weight": weights[0][1], "top3_weight": sum(weight for _, weight in weights[:3]),
                     "effective_member_count": 1 / sum(weight * weight for _, weight in weights)}
        for window in (5, 10, 21):
            values = [(value, weight) for row, weight in weights if (value := aligned(row, rows, window)) is not None]
            weighting[f"equal_weight_return_{window}d"] = mean([value for value, _ in values])
            weighting[f"cap_weight_return_{window}d"] = sum(value * weight for value, weight in values) / sum(weight for _, weight in values) if values else None
        result["weighting"] = weighting
    return result


CONTEXT_FIELDS = ("bars", "market", "peers", "headlines", "headline_peers", "context_provenance")


def dataset_context(raw, ticker=None):
    if raw.get("schema_version") != "visualsectors-toolkit.dataset.v2":
        raise ValueError("snapshot-only dataset.v1 cannot supply context; use dataset.v2 or a context evidence packet")
    provenance = raw.get("context_provenance")
    if provenance is None:
        raise ValueError("context_provenance is not supplied; context needs source cutoffs and a frozen retrieval spec")
    exact(provenance, {"retrieval_spec", "source_cutoffs", "source_query_hashes", "source_result_hashes", "risk_codes"}, "context_provenance")
    spec = deepcopy(provenance["retrieval_spec"])
    if raw["decision_time"] != spec["decision_time"]:
        raise ValueError("context dataset decision time differs from its evidence")
    series = raw.get("bars") or {}
    peers = raw.get("peers") or {}
    if not isinstance(series, dict) or not isinstance(peers, dict):
        raise ValueError("bars and peers must be objects keyed by ticker")
    candidates, groups, aggregates = [], {}, []
    identities = {candidate["ticker"]: candidate for candidate in spec["candidates"]}
    if set(series) - set(identities) or set(peers) - set(identities):
        raise ValueError("context has bars or peers outside the frozen candidate population")
    for identity in spec["candidates"]:
        name = identity["ticker"]
        peer = peers.get(name, {})
        if peer:
            exact(peer, {"resolution"}, "dataset_peer", {"group", "aggregate", "capitalization"})
        resolution = peer.get("resolution", {
            "requested_industry_id": identity["industry_id"], "requested_industry_label": identity["industry_label"],
            "resolved_industry_id": None, "resolved_industry_label": None, "resolved_taxonomy_level": None, "status": "unresolved"})
        candidates.append({**identity, "industry_resolution": resolution,
                           "series": series.get(name, {"vs_security_id": identity["vs_security_id"], "ticker": name, "bars": []})})
        if peer.get("group") is not None:
            groups[peer["group"]["industry_id"]] = peer["group"]
        caps = peer.get("capitalization") or {}
        if not isinstance(caps, dict):
            raise ValueError("capitalization must map security IDs to point-in-time values")
        member_ids = {row["vs_security_id"] for row in (peer.get("group") or {}).get("members", [])}
        if set(caps) - member_ids:
            raise ValueError("capitalization contains a security outside the supplied peer membership")
        for capitalization in caps.values():
            from .context_validation import cutoff, number, timestamp
            exact(capitalization, {"market_cap", "available_at"}, "capitalization")
            cutoff(capitalization["available_at"], timestamp(raw["decision_time"]), "capitalization_after_decision", True)
            if not number(capitalization["market_cap"], False) or capitalization["market_cap"] <= 0:
                raise ValueError("point-in-time market capitalization must be positive")
        if peer.get("aggregate") is not None:
            aggregates.append(peer["aggregate"])
        elif peer.get("group") is not None:
            aggregates.append(member_aggregate(identity, candidates[-1]["series"], peer["group"], caps, raw["decision_time"]))
            provenance = deepcopy(provenance)
            provenance["risk_codes"] = list(dict.fromkeys([*provenance["risk_codes"], "PEER_AGGREGATES_CLIENT_DERIVED_MAD",
                *(["PEER_CAP_COVERAGE_PARTIAL"] if caps and len(caps) < peer["group"]["eligible_member_count"] else [])]))
    market = raw.get("market") or {}
    if market:
        exact(market, set(), "dataset_market", {"series", "breadth", "vix"})
    market_series = market.get("series", [{"vs_security_id": f"benchmark:{name}", "ticker": name, "bars": []} for name in ("SPY", "QQQ", "IWM", "RSP")])
    breadth = market.get("breadth", {"positive_10d_pct": None, "positive_21d_pct": None, "above_sma50_pct": None,
                                     "eligible_count_10d": 0, "eligible_count_21d": 0, "eligible_count_sma50": 0})
    packet = {"schema_version": "screener_context_evidence_packet.v2", "retrieval_release": spec["retrieval_release"],
              "retrieval_spec_hash": "", "decision_time": spec["decision_time"], "as_of_session": spec["as_of_session"],
              **{key: deepcopy(provenance[key]) for key in ("source_cutoffs", "source_query_hashes", "source_result_hashes", "risk_codes")},
              "candidates": candidates, "peer_groups": list(groups.values()), "peer_aggregates": aggregates,
              "market_series": market_series, "market_breadth": breadth, "vix": market.get("vix"),
              "headlines": raw.get("headlines") or []}
    from .context_validation import canonical_hash
    packet["retrieval_spec_hash"] = canonical_hash(spec)
    if raw.get("headline_peers") is not None:
        headline = raw["headline_peers"]
        if not isinstance(headline, dict) or set(headline) != set(identities):
            raise ValueError("headline_peers must have one row per frozen candidate")
        packet["headline_peers"] = [headline[identity["ticker"]] for identity in spec["candidates"]]
    validate_packet(spec, packet)
    if ticker is not None and ticker.upper() not in identities:
        raise ValueError("ticker is not in the frozen context dataset")
    # Validate the full population even when the caller requests just one card.
    return spec, packet
