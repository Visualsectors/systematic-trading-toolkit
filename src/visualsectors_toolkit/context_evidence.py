"""Code-owned evidence displays; figures are attached to stable lane IDs."""
from decimal import Decimal, ROUND_HALF_UP


def fixed(value, digits=1):
    if value is None:
        return "unavailable"
    quantum = Decimal(1).scaleb(-digits)
    number = Decimal.from_float(float(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    if number == 0:
        number = abs(number)
    return f"{number:.{digits}f}"


def percent(value, digits=1):
    return "unavailable" if value is None else fixed(value, digits) + "%"


def record(identity, lane, display, value):
    return {"evidence_id": identity, "lane": lane, "display": display, "value": value}


def narrative_evidence(narrative, candidate_id="SHARED"):
    scope = narrative["scope"]
    prefix, lane = ("MARKET", "market") if scope == "market" else ("PEERS", "peers") if scope == "industry" else ("NEWS", "news")
    examples = "; ".join(f"“{row['title']}”" for row in narrative["representative_headlines"]) or "unavailable"
    count = narrative["source_count"]
    diversity = "source diversity unavailable" if count is None else f"{count} distinct source{'s' if count != 1 else ''}"
    display = f"{scope} narrative “{narrative['label']}”: {narrative['article_count']} linked headlines from {diversity}, {fixed(narrative['freshness_hours'])} hours fresh, sentiment {narrative['sentiment']}; representative headlines: {examples}."
    return record(f"{prefix}:{candidate_id}:NARRATIVE:{narrative['cluster_id']}", lane, display, narrative)


def market_evidence(market):
    benchmarks = "; ".join(f"{row['ticker']} 5d {percent(row['return_5d_pct'])}, 10d {percent(row['return_10d_pct'])}, 21d {percent(row['return_21d_pct'])}" for row in market["benchmark_returns"])
    breadth = market["breadth"]
    display = f"Market regime {market['regime']}; benchmarks {benchmarks}; positive breadth 10d {percent(breadth['positive_10d_pct'])} across {breadth['eligible_count_10d']} eligible names, 21d {percent(breadth['positive_21d_pct'])} across {breadth['eligible_count_21d']} eligible names; above SMA50 {percent(breadth['above_sma50_pct'])} across {breadth['eligible_count_sma50']} eligible names; VIX {fixed(market['vix']['value']) if market['vix'] else 'unavailable'}."
    result = [record("MARKET:SUMMARY", "market", display, market)]
    result.extend(narrative_evidence(row) for row in market["narratives"])
    roles = market["narrative_roles"]
    if roles["leading"] is not None or roles["challenging"] is not None:
        def describe(name, role):
            if role is None:
                return f"{name}: none supplied"
            return f"{name}: “{role['label']}” ({role['sentiment']}, {role['alignment'].replace('_', ' ')}; {role['article_count']} articles, {fixed(role['recent_article_share_pct'])}% in the last 72 hours, {role['momentum']}; SPY mean session return {percent(role['spy_mean_return_on_narrative_sessions_pct'], 2)} on its {role['reaction_session_count']} reaction sessions versus {percent(role['spy_mean_return_other_sessions_pct'], 2)} on the window's other sessions)"
        shift = " (the short-term direction has turned)" if roles["direction_shift"] else ""
        display = f"SPY direction 21 sessions {roles['market_direction_21d']}, 5 sessions {roles['market_direction_5d']}{shift}. {describe('Leading narrative', roles['leading'])}. {describe('Challenging narrative', roles['challenging'])}. Reaction figures are coincident timing, not causation."
        result.append(record("MARKET:SHARED:NARRATIVE_ROLES", "market", display, roles))
    return result


def candidate_evidence(candidate):
    identity, ticker, price, peers = candidate["candidate_id"], candidate["ticker"], candidate["price"], candidate["peers"]
    display = f"{ticker}: 5d {percent(price['return_5d_pct'])}, 10d {percent(price['return_10d_pct'])}, 21d {percent(price['return_21d_pct'])}, 60d {percent(price['return_60d_pct'])}, 21d one-year percentile {percent(price['return_21d_percentile_1y'])}, max drawdown {percent(price['maximum_drawdown_pct'])}, max run-up {percent(price['maximum_runup_pct'])}, largest gaps {percent(price['largest_gap_up_pct'])}/{percent(price['largest_gap_down_pct'])}, month-range close {percent(price['latest_close_in_month_range_pct'])}."
    result = [record(f"PRICE:{identity}:SUMMARY", "price", display, price)]
    tape = {key: price[key] for key in ("recent_acceleration_pct", "trend_efficiency", "realized_volatility_percentile_1y", "latest_range_vs_prior_10", "latest_volume_vs_20d")}
    multiple = lambda value: "unavailable" if value is None else fixed(value, 2) + "x"
    display = f"{ticker} tape: acceleration {percent(price['recent_acceleration_pct'])}; trend efficiency {fixed(price['trend_efficiency'], 3)}; volatility percentile {percent(price['realized_volatility_percentile_1y'])}; latest range/prior 10 {multiple(price['latest_range_vs_prior_10'])}; latest volume/20d {multiple(price['latest_volume_vs_20d'])}."
    result.append(record(f"PRICE:{identity}:TAPE", "price", display, tape))
    for gap in price["material_gaps"]:
        fill = gap["sessions_to_fill"] if gap["sessions_to_fill"] is not None else "unavailable"
        display = f"{gap['observed_on']} gap {gap['direction']} {percent(gap['gap_pct'])} ({fixed(gap['atr_multiple'], 2)} ATR); same-session return {percent(gap['same_day_return_pct'])}; fill {gap['fill_status']}; sessions to fill {fill}; five-session follow-through {percent(gap['five_session_follow_through_pct'])}."
        result.append(record(f"PRICE:{identity}:GAP:{gap['observed_on']}", "price", display, gap))
    for pattern in price["patterns"]:
        display = f"{pattern['code']} ({pattern['direction']}, {pattern['strength']}) on {pattern['observed_on']}: {pattern['description']} Invalidation: {pattern['invalidation'] if pattern['invalidation'] is not None else 'not defined'}."
        result.append(record(f"PRICE:{identity}:PATTERN:{pattern['code']}:{pattern['observed_on']}", "price", display, pattern))
    peer_move = lambda row: f"{row['ticker']} (5d {percent(row['return_5d_pct'])}, 10d {percent(row['return_10d_pct'])}, 21d {percent(row['return_21d_pct'])})"
    leaders = ", ".join(peer_move(row) for row in peers["representative_leaders"]) or "unavailable"
    laggards = ", ".join(peer_move(row) for row in peers["representative_laggards"]) or "unavailable"
    display = f"{peers['industry_label'] if peers['industry_label'] is not None else 'Unknown industry'} ({peers['industry_id'] if peers['industry_id'] is not None else 'unresolved'}, requested {peers['requested_industry_id'] if peers['requested_industry_id'] is not None else 'none'}): full PIT universe {peers['eligible_peer_count']} peers; observed 5d/10d/21d {peers['observed_peer_count_5d']}/{peers['observed_peer_count_10d']}/{peers['observed_peer_count_21d']}; median 5d {percent(peers['peer_median_return_5d_pct'])}, 10d {percent(peers['peer_median_return_10d_pct'])}, 21d {percent(peers['peer_median_return_21d_pct'])}; positive breadth 5d/10d/21d {percent(peers['peer_positive_breadth_5d_pct'])}/{percent(peers['peer_positive_breadth_10d_pct'])}/{percent(peers['peer_positive_breadth_21d_pct'])}; direction agreement 5d/10d/21d {percent(peers['direction_agreement_5d_pct'])}/{percent(peers['direction_agreement_10d_pct'])}/{percent(peers['direction_agreement_21d_pct'])}; {ticker} excess 5d/10d/21d {percent(peers['candidate_excess_5d_pct'])}/{percent(peers['candidate_excess_10d_pct'])}/{percent(peers['candidate_excess_21d_pct'])}; scope {peers['move_scope']}; bounded sample leaders {leaders}; bounded sample laggards {laggards}."
    result.append(record(f"PEERS:{identity}:SUMMARY", "peers", display, peers))
    if candidate["stock_headlines"] or candidate["industry_headlines"]:
        def describe(rows):
            displays = []
            for row in rows:
                titles = "; ".join(f"“{item['title']}”" for item in row["representative_headlines"]) or "no representative title"
                count = row["source_count"] if row["source_count"] is not None else "unknown"
                displays.append(f"{row['label']} ({row['article_count']} articles, {count} sources, {fixed(row['freshness_hours'])} hours old; {titles})")
            return " | ".join(displays) or "none in the supplied window"
        value = {"candidate_linked": candidate["stock_headlines"], "industry_linked": candidate["industry_headlines"]}
        display = f"Candidate-linked headline clusters: {describe(candidate['stock_headlines'])}. Industry-linked headline clusters: {describe(candidate['industry_headlines'])}. The two scopes are linkage context, not causal attribution."
        result.append(record(f"PEERS:{identity}:HEADLINE_SCOPE", "peers", display, value))
    weighting = candidate["peer_weighting"]
    if weighting["status"] == "measured":
        window = weighting["comparison_sessions"] or 21
        display = f"{peers['industry_label'] if peers['industry_label'] is not None else 'Industry'}, {weighting['capitalized_peer_count']} peers with a point-in-time market capitalisation: equal-weighted {window}-session {percent(weighting[f'equal_weight_return_{window}d_pct'])}, cap-weighted {percent(weighting[f'cap_weight_return_{window}d_pct'])} (cap minus equal {percent(weighting['cap_minus_equal_pct'])}, {weighting['weighting_split'].replace('_', ' ')}); largest member {weighting['largest_member_ticker'] if weighting['largest_member_ticker'] is not None else 'unavailable'} at {percent(weighting['largest_member_weight_pct'])}, top three {percent(weighting['top3_weight_pct'])}, behaves like {fixed(weighting['effective_member_count'])} equal members ({weighting['concentration']}); {ticker} versus equal-weighted {percent(weighting['candidate_excess_vs_equal_weight_pct'])}, versus cap-weighted {percent(weighting['candidate_excess_vs_cap_weight_pct'])}; the group is read from the {'equal-weighted return' if weighting['preferred_basis'] == 'equal_weight' else 'median'}."
        result.append(record(f"PEERS:{identity}:WEIGHTING", "peers", display, weighting))
    headline = candidate["headline_peers"]
    if headline["status"] == "measured":
        moves = ", ".join(f"{row['ticker']} {row['co_mention_count']}x{'' if row['same_industry'] else ' (other industry)'} 21d {percent(row['return_21d_pct'])}" for row in headline["peers"])
        themes = "; ".join(f"“{row['label']}”: {'/'.join(row['tickers'])} (median 21d {percent(row['median_return_21d_pct'])})" for row in headline["themes"])
        display = f"Named alongside {ticker} in {headline['candidate_headline_count']} headlines over {headline['lookback_calendar_days']} days: {moves}. {headline['peer_count']} headline peers, {headline['outside_industry_count']} outside its industry; median 5d {percent(headline['median_return_5d_pct'])}, 21d {percent(headline['median_return_21d_pct'])}, positive 10d breadth {percent(headline['positive_breadth_10d_pct'])}; {ticker} excess 5d {percent(headline['candidate_excess_5d_pct'])}, 21d {percent(headline['candidate_excess_21d_pct'])} ({headline['relation'].replace('_', ' ')}). Themes: {themes or 'none'}{'; separate business lines have separate peers' if headline['business_lines_split'] else ''}. Co-mention is linkage, not causation."
        result.append(record(f"PEERS:{identity}:HEADLINE_PEERS", "peers", display[:2000], headline))
    relative = {key: candidate[key] for key in (f"relative_to_{benchmark}_{window}d_pct" for benchmark in ("spy", "qqq") for window in (5, 10, 21))}
    display = f"{ticker} excess versus SPY: 5d {percent(relative['relative_to_spy_5d_pct'])}, 10d {percent(relative['relative_to_spy_10d_pct'])}, 21d {percent(relative['relative_to_spy_21d_pct'])}; versus QQQ (Nasdaq-100 ETF proxy, not Nasdaq Composite): 5d {percent(relative['relative_to_qqq_5d_pct'])}, 10d {percent(relative['relative_to_qqq_10d_pct'])}, 21d {percent(relative['relative_to_qqq_21d_pct'])}."
    result.append(record(f"MARKET:{identity}:RELATIVE", "market", display, relative))
    movement = candidate["market_co_movement"]
    links = {"leading": "its own headlines share the topic of the leading narrative", "challenging": "its own headlines share the topic of the challenging narrative",
             "both": "its own headlines share the topics of both narratives", "neither": "its own headlines share the topic of neither narrative", "unavailable": "no own headlines or market narratives to match"}
    display = f"{ticker} against SPY over {movement['return_session_count']} aligned daily returns: correlation {fixed(movement['correlation_60d'], 2)}, beta {fixed(movement['beta_60d'], 2)} ({movement['state'].replace('_', ' ')}); 21-session direction versus SPY {movement['direction_vs_market_21d']}; {links[movement['narrative_link']]}."
    result.append(record(f"MARKET:{identity}:CO_MOVEMENT", "market", display, movement))
    result.extend(narrative_evidence(row, identity) for row in [*candidate["stock_headlines"], *candidate["industry_headlines"]])
    return result
