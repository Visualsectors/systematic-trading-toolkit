"""Public API context adapter. No guessed peers, breadth or news relevance."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from .context_market import instant, new_york_close
from .context_validation import canonical_hash, POLICIES, RETRIEVAL_RELEASE
from .models import require_ticker
from .providers.visualsectors import ApiResponseError, _iso_datetime, _number, _rows


def live_context(provider, ticker):
    ticker = require_ticker(ticker)
    requested_at = datetime.now(timezone.utc)
    today = requested_at.date()
    responses, requests = {}, []
    warnings = ["LIVE_API_NON_POINT_IN_TIME", "PEER_MEMBERSHIP_NOT_SUPPLIED", "MARKET_BREADTH_NOT_SUPPLIED",
                "MARKET_CAP_NOT_SUPPLIED", "HEADLINE_PEERS_NOT_SUPPLIED", "NEWS_LINKAGE_RELEVANCE_NOT_SUPPLIED",
                "MARKET_NEWS_IS_SPY_LINKED_PROXY", "API_LINEAGE_HASHES_ARE_CLIENT_READ_FINGERPRINTS"]
    for name in dict.fromkeys((ticker, "SPY", "QQQ", "IWM", "RSP")):
        query = {"ticker": name, "view": "daily", "from": (today - timedelta(days=370)).isoformat(),
                 "to": today.isoformat(), "limit": "100"}
        try:
            responses[name] = provider._get_pages("/v1/timeseries/history", query)
        except ApiResponseError as exc:
            if name == ticker or exc.status == 401:
                raise
            responses[name] = {"rows": []}
            warnings.append(f"BENCHMARK_{name}_NOT_SUPPLIED")
        requests.append({"path": "/v1/timeseries/history", "query": query})
    news = {}
    for name in dict.fromkeys((ticker, "SPY")):
        query = {"ticker": name, "view": "headlines", "limit": "24"}
        requests.append({"path": "/v1/news", "query": query})
        try:
            news[name] = provider._get_pages("/v1/news", query)
        except ApiResponseError as exc:
            if exc.status == 401:
                raise
            news[name] = {"rows": []}
            warnings.append("NEWS_NOT_SUPPLIED")
    source_times = [instant(row["as_of"]) for row in [*responses.values(), *news.values()] if isinstance(row.get("as_of"), str)]
    if not source_times:
        raise ApiResponseError(None, "context source responses have no as_of timestamp")
    cutoff = min([requested_at, *source_times])
    decision_time = cutoff.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def normalize(name, payload):
        raw = sorted(_rows(payload, "context daily bars"), key=lambda row: str(row.get("date", "")))
        eligible = [row for row in raw if isinstance(row.get("date"), str) and new_york_close(row["date"][:10]) <= cutoff]
        result, factor = [], 1.0
        for row in reversed(eligible):
            values = {key: _number(row.get(key)) for key in ("open", "high", "low", "close", "volume")}
            if (any(values[key] is None or values[key] <= 0 for key in ("open", "high", "low", "close"))
                    or values["high"] < max(values["open"], values["close"]) or values["low"] > min(values["open"], values["close"])
                    or values["volume"] is not None and values["volume"] < 0):
                warnings.append("PRICE_ROWS_INVALID_OMITTED")
                continue
            result.append({"session": row["date"][:10],
                           **{key: values[key] / factor for key in ("open", "high", "low", "close")},
                           "volume": values["volume"] * factor if values["volume"] is not None else None})
            split = _number(row.get("split_coefficient"))
            if split is None or split <= 0:
                warnings.append("SPLIT_METADATA_PARTIAL")
            else:
                factor *= split
        return {"vs_security_id": f"api:{name}", "ticker": name, "bars": list(reversed(result))[-253:]}

    series = {name: normalize(name, payload) for name, payload in responses.items()}
    candidate_series = series[ticker]
    if not candidate_series["bars"]:
        raise ApiResponseError(None, "context has no valid completed daily bars for the ticker")
    as_of_session = candidate_series["bars"][-1]["session"]
    # Keep the candidate's cutoff; a missing/stale benchmark must downgrade its own lane.
    for row in series.values():
        row["bars"] = [bar for bar in row["bars"] if bar["session"] <= as_of_session]
    identity = {"candidate_id": f"candidate:{ticker}", "vs_security_id": f"api:{ticker}", "ticker": ticker,
                "company_name": None, "industry_id": None, "industry_label": None}
    spec = {"schema_version": "screener_context_retrieval_spec.v2", "retrieval_release": RETRIEVAL_RELEASE,
            "decision_time": decision_time, "as_of_session": as_of_session,
            "screen": {"kind": "custom", "screen_id": f"toolkit-context:{ticker}", "screen_release": "toolkit-context-v1",
                       "definition_hash": canonical_hash({"ticker": ticker})}, "candidates": [identity], **deepcopy(POLICIES)}
    resolution = {"requested_industry_id": None, "requested_industry_label": None, "resolved_industry_id": None,
                  "resolved_industry_label": None, "resolved_taxonomy_level": None, "status": "unresolved"}
    headlines = []
    seen = set()
    for name, payload in news.items():
        for row in _rows(payload, "context headlines"):
            try:
                created = instant(_iso_datetime(row.get("created"), row.get("event_date")))
            except (ValueError, ApiResponseError):
                warnings.append("NEWS_TIMESTAMP_INVALID_OMITTED")
                continue
            if not cutoff - timedelta(days=14) <= created <= cutoff:
                continue
            title, url = str(row.get("title") or "").strip(), str(row.get("url") or "").strip()
            if not title or not url or any(ord(char) < 32 or ord(char) == 127 for char in title + url):
                warnings.append("NEWS_COVERAGE_PARTIAL")
                continue
            scope = "candidate" if name == ticker else "market"
            if sum(item["scope"] == scope for item in headlines) >= (8 if scope == "candidate" else 24):
                continue
            identifier = f"api-news:{scope}:" + str(row.get("id") or canonical_hash({"title": title, "created": row.get("created")}))
            if identifier in seen:
                continue
            seen.add(identifier)
            sentiment = _number(row.get("ticker_sentiment_score"))
            if sentiment is not None and not -1 <= sentiment <= 1:
                sentiment = None
                warnings.append("NEWS_SENTIMENT_INVALID_NOT_SUPPLIED")
            headlines.append({"headline_id": identifier, "scope": scope, "candidate_ids": [identity["candidate_id"]] if scope == "candidate" else [],
                              "industry_ids": [], "title": title[:1000], "teaser": None, "url": url[:2048], "topics": [],
                              "sentiment_score": sentiment,
                              "created_at": created.isoformat(timespec="milliseconds").replace("+00:00", "Z"), "availability_semantics": "created_at_proxy"})
    if headlines:
        warnings.append("HEADLINE_AVAILABILITY_CREATED_AT_PROXY")
    lanes = ("headlines", "market_breadth", "peer_aggregates", "peer_membership", "price_paths")
    packet = {"schema_version": "screener_context_evidence_packet.v2", "retrieval_release": RETRIEVAL_RELEASE,
              "retrieval_spec_hash": canonical_hash(spec), "decision_time": decision_time, "as_of_session": as_of_session,
              "source_cutoffs": {"prices": decision_time, "peer_membership": None, "market": decision_time,
                                 "headlines": decision_time if headlines else None},
              "source_query_hashes": {lane: canonical_hash({"lane": lane, "requests": requests}) for lane in lanes},
              "source_result_hashes": {lane: canonical_hash({"lane": lane, "prices": responses, "news": news}) for lane in lanes},
              "candidates": [{**identity, "industry_resolution": resolution, "series": candidate_series}],
              "peer_groups": [], "peer_aggregates": [], "market_series": [series[name] for name in ("SPY", "QQQ", "IWM", "RSP")],
              "market_breadth": {"positive_10d_pct": None, "positive_21d_pct": None, "above_sma50_pct": None,
                                 "eligible_count_10d": 0, "eligible_count_21d": 0, "eligible_count_sma50": 0},
              "vix": None, "headlines": headlines, "risk_codes": list(dict.fromkeys(warnings))}
    return spec, packet
