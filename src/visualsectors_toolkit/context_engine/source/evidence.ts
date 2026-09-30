import { clamp, mean, median, medianAbsoluteDeviation, pct, percentileRank, round, standardDeviation } from './math.js';
import type {
  CandidateComputedContext,
  ComputedScreenerContext,
  ContextCandidateEvidence,
  ContextDailyBar,
  ContextEvidencePacket,
  ContextEvidenceRecord,
  ContextHeadlineEvidence,
  ContextHeadlinePeerEvidence,
  ContextHeadlineScope,
  ContextIndustryResolution,
  ContextPeerAggregateEvidence,
  ContextPeerGroupEvidence,
  ContextPeerWeightingEvidence,
  ContextRetrievalSpec,
  ContextSecuritySeries,
  HeadlinePeerFeatures,
  HeadlinePeerMove,
  HeadlinePeerTheme,
  MarketCoMovementFeatures,
  MarketDirection,
  MarketFeatures,
  MarketNarrativeRole,
  MarketNarrativeRoles,
  NarrativeCluster,
  PeerComparisonFeatures,
  PeerMemberMove,
  PeerWeightingFeatures,
  PriceActionFeatures,
  PriceGapObservation,
  PricePatternCandidate,
} from './types.js';
import { hashScreenerContextRetrievalSpec, validateScreenerContextRetrievalSpec } from './retrieval-spec.js';

/*
 * v2.4.0 (G13, 2026-09-30; Vlad "A A B", tail of _plan/03): the market lane names a CHALLENGING narrative
 * beside the leading one, each with a measured SPY reaction; the candidate's co-movement with SPY is
 * measured; peers gain equal- and cap-weighted returns with the largest member's share, and HEADLINE PEERS
 * (securities named in the same headlines, grouped by story theme). Every new packet field is optional, so
 * a connector that does not send it yet still produces the v2.3 context plus "not supplied" states.
 */
export const SCREENER_CONTEXT_FEATURE_RELEASE = 'screener-context-features-v2.4.0' as const;

/** What the connector follows when it sends `headline_peers`; validated against every packet that has them. */
export const SCREENER_CONTEXT_HEADLINE_PEER_POLICY = Object.freeze({
  lookback_calendar_days: 90,
  minimum_ticker_relevance: 0.5,
  minimum_co_mentions: 2,
  maximum_peers_per_candidate: 8,
  maximum_topics_per_peer: 4,
} as const);

/** Released thresholds for reading the weighted peer returns. */
export const SCREENER_CONTEXT_PEER_WEIGHTING_POLICY = Object.freeze({
  dominated_largest_member_weight: 0.4,
  concentrated_top3_weight: 0.6,
  weighting_split_pct_21d: 2,
  weighting_split_pct_10d: 1.5,
} as const);

/** Released thresholds for choosing and describing the market narratives. */
export const SCREENER_CONTEXT_NARRATIVE_POLICY = Object.freeze({
  recent_hours: 72,
  rising_recent_share: 0.5,
  minimum_role_articles: 2,
  market_direction_21d_pct: 1,
  market_direction_5d_pct: 0.5,
  co_movement_sessions: 60,
  minimum_co_movement_sessions: 20,
} as const);

export function buildComputedScreenerContext(
  spec: ContextRetrievalSpec,
  packet: ContextEvidencePacket,
): ComputedScreenerContext {
  validateScreenerContextEvidencePacket(spec, packet);
  const market = buildMarketFeatures(packet);
  const evidence: ContextEvidenceRecord[] = [marketEvidence(market)];
  for (const narrative of market.narratives) evidence.push(narrativeEvidence(narrative));
  const roles = narrativeRolesEvidence(market.narrative_roles);
  if (roles !== null) evidence.push(roles);

  const spy = packet.market_series.find(({ ticker }) => ticker === 'SPY');
  const qqq = packet.market_series.find(({ ticker }) => ticker === 'QQQ');
  const groups = new Map(packet.peer_groups.map((group) => [group.industry_id, group]));
  const peerAggregates = new Map(packet.peer_aggregates.map((aggregate) => [aggregate.candidate_id, aggregate]));
  const headlinePeerRows = packet.headline_peers === undefined ? null
    : new Map(packet.headline_peers.map((row) => [row.candidate_id, row]));
  const candidates: CandidateComputedContext[] = packet.candidates.map((candidate) => {
    const current = candidate.series.bars.at(-1)?.session === packet.as_of_session;
    const price = current
      ? buildPriceAction(candidate.series)
      : emptyPrice(Math.min(candidate.series.bars.length, 23), ['PRICE_SESSION_STALE']);
    const resolvedIndustryId = candidate.industry_resolution.resolved_industry_id;
    const group = groups.get(resolvedIndustryId ?? '');
    const aggregate = peerAggregates.get(candidate.candidate_id);
    const peers = current
      ? buildPeerComparison(candidate.candidate_id, candidate.series, candidate.industry_resolution, group, aggregate)
      : emptyPeers(candidate.industry_resolution, group?.industry_id ?? null,
        group?.industry_label ?? null, group?.taxonomy_level ?? null,
        ['PEER_CANDIDATE_SERIES_STALE']);
    const stockHeadlines = buildNarratives(
      packet.headlines.filter((headline) => headline.scope === 'candidate'
        && headline.candidate_ids.includes(candidate.candidate_id)),
      'candidate',
      packet.decision_time,
    );
    const industryHeadlines = resolvedIndustryId === null ? [] : buildNarratives(
      packet.headlines.filter((headline) => headline.scope === 'industry'
        && headline.industry_ids.includes(resolvedIndustryId)),
      'industry',
      packet.decision_time,
    );
    const candidateBars = eligibleBars(candidate.series);
    // Relative performance is meaningful only when both securities share the
    // exact comparison endpoints. Do not silently shift a benchmark to an
    // earlier trading session when a bar is absent or stale.
    const relative = (benchmark: ContextSecuritySeries | undefined, sessions: 5 | 10 | 21): number | null => {
      const candidateReturn = current ? periodReturn(candidateBars, sessions) : null;
      const benchmarkReturn = current && benchmark?.bars.at(-1)?.session === packet.as_of_session
        ? alignedPeriodReturn(benchmark, candidateBars, sessions)
        : null;
      return candidateReturn === null || benchmarkReturn === null ? null : pct(candidateReturn - benchmarkReturn);
    };
    const computed: CandidateComputedContext = {
      candidate_id: candidate.candidate_id,
      ticker: candidate.ticker,
      price,
      peers,
      stock_headlines: stockHeadlines,
      industry_headlines: industryHeadlines,
      relative_to_spy_5d_pct: relative(spy, 5),
      relative_to_spy_10d_pct: relative(spy, 10),
      relative_to_spy_21d_pct: relative(spy, 21),
      relative_to_qqq_5d_pct: relative(qqq, 5),
      relative_to_qqq_10d_pct: relative(qqq, 10),
      relative_to_qqq_21d_pct: relative(qqq, 21),
      peer_weighting: current && peers.data_quality !== 'insufficient'
        ? buildPeerWeighting(aggregate, candidateBars)
        : emptyPeerWeighting(aggregate?.weighting === undefined ? 'not_supplied' : 'insufficient'),
      headline_peers: headlinePeerRows === null ? emptyHeadlinePeers('not_supplied')
        : current ? buildHeadlinePeers(headlinePeerRows.get(candidate.candidate_id), candidateBars)
          : emptyHeadlinePeers('insufficient'),
      market_co_movement: buildMarketCoMovement(
        current ? candidateBars : [],
        spy?.bars.at(-1)?.session === packet.as_of_session ? spy : undefined,
        market.narrative_roles,
        [...stockHeadlines, ...industryHeadlines],
      ),
    };
    evidence.push(priceEvidence(computed));
    evidence.push(priceTapeEvidence(computed));
    for (const gap of price.material_gaps) evidence.push(gapEvidence(candidate.candidate_id, gap));
    for (const pattern of price.patterns) evidence.push(patternEvidence(candidate.candidate_id, pattern));
    evidence.push(peerEvidence(computed));
    const headlineScope = peerHeadlineScopeEvidence(computed);
    if (headlineScope !== null) evidence.push(headlineScope);
    if (computed.peer_weighting.status === 'measured') evidence.push(peerWeightingEvidence(computed));
    if (computed.headline_peers.status === 'measured') evidence.push(headlinePeerEvidence(computed));
    evidence.push(relativeMarketEvidence(computed));
    evidence.push(coMovementEvidence(computed));
    for (const narrative of [...stockHeadlines, ...industryHeadlines]) evidence.push(narrativeEvidence(narrative, candidate.candidate_id));
    return computed;
  });

  assertUniqueEvidence(evidence);
  return {
    schema_version: 'computed_screener_context.v2',
    feature_release: SCREENER_CONTEXT_FEATURE_RELEASE,
    screen: spec.screen,
    retrieval_spec_hash: packet.retrieval_spec_hash,
    decision_time: packet.decision_time,
    as_of_session: packet.as_of_session,
    candidates,
    market,
    evidence_index: evidence,
    risk_codes: [...new Set(packet.risk_codes)],
  };
}

export function buildPriceAction(series: ContextSecuritySeries): PriceActionFeatures {
  const bars = eligibleBars(series);
  const analysis = bars.slice(-23);
  const riskCodes: string[] = [];
  if (analysis.length < 20) riskCodes.push('PRICE_HISTORY_INSUFFICIENT');
  // A "complete" lane must have the complete released one-year baseline. A
  // shorter history remains usable for B/C, but may not support Tier A.
  if (bars.length < 253) riskCodes.push('PRICE_BASELINE_THIN');
  if (analysis.some(({ volume }) => volume === null)) riskCodes.push('PRICE_VOLUME_PARTIAL');
  if (analysis.length < 20) return emptyPrice(analysis.length, riskCodes);

  const dailyReturns = returns(bars);
  const analysisReturns = returns(analysis);
  const return5 = periodReturn(analysis, 5);
  const return10 = periodReturn(analysis, 10);
  const return21 = periodReturn(analysis, 21);
  const return60 = periodReturn(bars, 60);
  const rolling21 = rollingReturns(bars, 21);
  const currentVol = standardDeviation(analysisReturns.slice(-21));
  const rollingVol = rollingVolatility(dailyReturns, 21);
  const returnPercentile = return21 === null ? null : percentileRank(rolling21.slice(0, -1), return21);
  const volPercentile = currentVol === null ? null : percentileRank(rollingVol.slice(0, -1), currentVol);
  const acceleration = return5 === null || return21 === null ? null : return5 - return21 * (5 / 21);
  const closePath = analysis.map(({ close }) => close);
  const pathLength = analysisReturns.reduce((sum, value) => sum + Math.abs(Math.log1p(value)), 0);
  const trendEfficiency = return21 === null || pathLength === 0 ? null : Math.abs(Math.log1p(return21)) / pathLength;
  const analysisGapSessions = new Set(analysis.slice(1).map(({ session }) => session));
  const gaps = gapObservations(bars).filter(({ observation }) => analysisGapSessions.has(observation.observed_on));
  const allMaterialGaps = gaps.filter(({ raw_atr_multiple, raw_gap }) => Math.abs(raw_gap) >= 0.01
    || raw_atr_multiple >= 0.75);
  const materialGaps = [...allMaterialGaps]
    .sort((left, right) => Math.abs(right.raw_atr_multiple) - Math.abs(left.raw_atr_multiple)
      || Math.abs(right.raw_gap) - Math.abs(left.raw_gap)
      || left.observation.observed_on.localeCompare(right.observation.observed_on))
    .slice(0, 5);
  const followThrough = allMaterialGaps.length === 0 ? null
    : allMaterialGaps.filter(({ raw_gap, raw_same_day_return }) => Math.sign(raw_gap)
      === Math.sign(raw_same_day_return)).length
      / allMaterialGaps.length;
  const largestUp = gaps.length === 0 ? null : Math.max(0, ...gaps.map(({ raw_gap }) => raw_gap));
  const largestDown = gaps.length === 0 ? null : Math.min(0, ...gaps.map(({ raw_gap }) => raw_gap));
  const largestAtr = gaps.length === 0 ? null : Math.max(...gaps.map(({ raw_atr_multiple }) => raw_atr_multiple));
  const monthHigh = Math.max(...analysis.map(({ high }) => high));
  const monthLow = Math.min(...analysis.map(({ low }) => low));
  const latest = analysis.at(-1)!;
  const rangeLocation = monthHigh === monthLow ? 0.5 : (latest.close - monthLow) / (monthHigh - monthLow);
  const priorTenRanges = analysis.slice(-11, -1).map((bar) => bar.high - bar.low);
  const priorRange = mean(priorTenRanges);
  const latestRangeRatio = priorRange === null || priorRange === 0 ? null : (latest.high - latest.low) / priorRange;
  const volumes = analysis.slice(-21, -1).flatMap(({ volume }) => volume === null ? [] : [volume]);
  const averageVolume = mean(volumes);
  const latestVolumeRatio = latest.volume === null || averageVolume === null || averageVolume === 0
    ? null : latest.volume / averageVolume;
  const patterns = detectPatterns(analysis, return5, return21, acceleration, returnPercentile);

  if (returnPercentile !== null && (returnPercentile >= 0.95 || returnPercentile <= 0.05)) {
    riskCodes.push('PRICE_MONTHLY_PACE_UNUSUAL');
  }
  if (return21 !== null && Math.abs(return21) >= 0.5) riskCodes.push('PRICE_MONTHLY_MOVE_EXTREME');
  if (volPercentile !== null && volPercentile >= 0.90) riskCodes.push('PRICE_VOLATILITY_ELEVATED');
  if ((largestUp ?? 0) >= 0.05 || (largestDown ?? 0) <= -0.05 || (largestAtr ?? 0) >= 2) {
    riskCodes.push('PRICE_EVENT_SIZED_GAP');
  }
  if ((latestVolumeRatio ?? 0) >= 2) riskCodes.push('PRICE_VOLUME_SPIKE');

  return {
    data_quality: riskCodes.includes('PRICE_BASELINE_THIN') || riskCodes.includes('PRICE_VOLUME_PARTIAL') ? 'partial' : 'complete',
    session_count: analysis.length,
    return_5d_pct: pct(return5),
    return_10d_pct: pct(return10),
    return_21d_pct: pct(return21),
    return_60d_pct: pct(return60),
    maximum_drawdown_pct: pct(maximumDrawdown(closePath)),
    maximum_runup_pct: pct(maximumRunup(closePath)),
    trend_efficiency: round(trendEfficiency, 3),
    recent_acceleration_pct: pct(acceleration),
    return_21d_percentile_1y: pct(returnPercentile),
    realized_volatility_percentile_1y: pct(volPercentile),
    largest_gap_up_pct: pct(largestUp),
    largest_gap_down_pct: pct(largestDown),
    largest_gap_atr_multiple: round(largestAtr, 2),
    gap_follow_through_pct: pct(followThrough),
    latest_close_in_month_range_pct: pct(clamp(rangeLocation, 0, 1)),
    latest_range_vs_prior_10: round(latestRangeRatio, 2),
    latest_volume_vs_20d: round(latestVolumeRatio, 2),
    material_gaps: materialGaps.map(({ observation }) => observation),
    patterns,
    risk_codes: riskCodes,
  };
}

function buildPeerComparison(
  candidateId: string,
  candidate: ContextSecuritySeries,
  resolution: ContextIndustryResolution,
  group: ContextPeerGroupEvidence | undefined,
  aggregate: ContextPeerAggregateEvidence | undefined,
): PeerComparisonFeatures {
  if (group === undefined || resolution.resolved_industry_id === null) {
    return emptyPeers(resolution, null, null, null, ['PEER_MEMBERSHIP_MISSING']);
  }
  if (aggregate === undefined || aggregate.candidate_id !== candidateId
      || aggregate.industry_id !== group.industry_id) {
    return emptyPeers(resolution, group.industry_id, group.industry_label,
      group.taxonomy_level, ['PEER_AGGREGATE_MISSING']);
  }
  const candidateBars = eligibleBars(candidate);
  const candidateReturn5 = periodReturn(candidateBars, 5);
  const candidateReturn10 = periodReturn(candidateBars, 10);
  const candidateReturn21 = periodReturn(candidateBars, 21);
  const members = group.members
    .filter(({ vs_security_id }) => vs_security_id !== candidate.vs_security_id)
    .map((series) => ({
      series,
      return5: alignedPeriodReturn(series, candidateBars, 5),
      return10: alignedPeriodReturn(series, candidateBars, 10),
      return21: alignedPeriodReturn(series, candidateBars, 21),
    }))
    .filter((row): row is {
      series: ContextSecuritySeries;
      return5: number | null;
      return10: number;
      return21: number | null;
    } => row.return10 !== null);
  if (candidateReturn10 === null || aggregate.observed_peer_count_10d < 2
      || aggregate.peer_median_return_10d === null
      || aggregate.peer_positive_breadth_10d === null) {
    return emptyPeers(resolution, group.industry_id, group.industry_label,
      group.taxonomy_level, ['PEER_PRICE_HISTORY_INSUFFICIENT']);
  }
  const centre = aggregate.peer_median_return_10d;
  const breadth = aggregate.peer_positive_breadth_10d;
  const dispersion = aggregate.peer_dispersion_10d;
  const excess = candidateReturn10 - centre;
  const agreement = aggregate.direction_agreement_10d;
  const classifyWindow = (
    candidateReturn: number | null,
    peerMedian: number | null | undefined,
    peerBreadth: number | null | undefined,
    peerDispersion: number | null | undefined,
    directionAgreement: number | null | undefined,
  ): 'industry_wide' | 'candidate_specific' | 'mixed' | null => {
    if (candidateReturn === null || peerMedian === null || peerMedian === undefined
        || peerBreadth === null || peerBreadth === undefined) return null;
    const candidateDirection = Math.sign(candidateReturn);
    const broadDirection = peerBreadth >= 0.67 ? 1 : peerBreadth <= 0.33 ? -1 : 0;
    const windowExcess = candidateReturn - peerMedian;
    const specificityThreshold = Math.max(0.03, (peerDispersion ?? 0) * 2);
    const candidateSpecific = Math.abs(windowExcess) >= specificityThreshold
      && Math.abs(candidateReturn) >= Math.max(0.06, Math.abs(peerMedian) * 2);
    const broadlyConfirmed = !candidateSpecific && candidateDirection !== 0
      && candidateDirection === broadDirection && Math.sign(peerMedian) === candidateDirection
      && (directionAgreement === null || directionAgreement === undefined || directionAgreement >= 0.6);
    return broadlyConfirmed ? 'industry_wide' : candidateSpecific ? 'candidate_specific' : 'mixed';
  };
  const windowScopes = [
    classifyWindow(candidateReturn5, aggregate.peer_median_return_5d,
      aggregate.peer_positive_breadth_5d, aggregate.peer_dispersion_5d,
      aggregate.direction_agreement_5d),
    classifyWindow(candidateReturn10, centre, breadth, dispersion, agreement),
    classifyWindow(candidateReturn21, aggregate.peer_median_return_21d,
      aggregate.peer_positive_breadth_21d, aggregate.peer_dispersion_21d,
      aggregate.direction_agreement_21d),
  ].filter((value): value is 'industry_wide' | 'candidate_specific' | 'mixed' => value !== null);
  const moveScope = windowScopes.length === 3 && windowScopes.every((scope) => scope === 'industry_wide')
    ? 'industry_wide'
    : windowScopes.length === 3 && windowScopes.every((scope) => scope === 'candidate_specific')
      ? 'candidate_specific' : 'mixed';
  const ordered = [...members].sort((left, right) => right.return10 - left.return10);
  const representative = (row: typeof members[number]): PeerMemberMove => ({
    ticker: row.series.ticker,
    return_5d_pct: pct(row.return5),
    return_10d_pct: pct(row.return10)!,
    return_21d_pct: pct(row.return21),
  });
  const riskCodes: string[] = [];
  if (aggregate.observed_peer_count_10d < 5) riskCodes.push('PEER_AGGREGATE_SAMPLE_SMALL');
  if (aggregate.eligible_peer_count > 0
      && aggregate.observed_peer_count_10d / aggregate.eligible_peer_count < 0.8) {
    riskCodes.push('PEER_AGGREGATE_PRICE_COVERAGE_PARTIAL');
  }
  if (members.length < 2) riskCodes.push('PEER_REPRESENTATIVE_SERIES_THIN');
  if (group.taxonomy_level === 'sic2') riskCodes.push('PEER_TAXONOMY_WIDENED');
  if (windowScopes.length < 3) riskCodes.push('PEER_MULTI_WINDOW_COVERAGE_PARTIAL');
  return {
    data_quality: riskCodes.length === 0 ? 'complete' : 'partial',
    requested_industry_id: resolution.requested_industry_id,
    requested_industry_label: resolution.requested_industry_label,
    industry_id: group.industry_id,
    industry_label: group.industry_label,
    taxonomy_level: group.taxonomy_level,
    eligible_peer_count: aggregate.eligible_peer_count,
    observed_peer_count_5d: aggregate.observed_peer_count_5d ?? 0,
    observed_peer_count_10d: aggregate.observed_peer_count_10d,
    observed_peer_count_21d: aggregate.observed_peer_count_21d,
    representative_peer_count: members.length,
    peer_median_return_5d_pct: pct(aggregate.peer_median_return_5d ?? null),
    peer_median_return_10d_pct: pct(centre),
    peer_median_return_21d_pct: pct(aggregate.peer_median_return_21d),
    peer_positive_breadth_5d_pct: pct(aggregate.peer_positive_breadth_5d ?? null),
    peer_positive_breadth_10d_pct: pct(breadth),
    peer_positive_breadth_21d_pct: pct(aggregate.peer_positive_breadth_21d ?? null),
    peer_dispersion_5d_pct: pct(aggregate.peer_dispersion_5d ?? null),
    peer_dispersion_10d_pct: pct(dispersion),
    peer_dispersion_21d_pct: pct(aggregate.peer_dispersion_21d ?? null),
    candidate_excess_5d_pct: candidateReturn5 === null || aggregate.peer_median_return_5d === undefined
      || aggregate.peer_median_return_5d === null ? null : pct(candidateReturn5 - aggregate.peer_median_return_5d),
    candidate_excess_10d_pct: pct(excess),
    candidate_excess_21d_pct: candidateReturn21 === null || aggregate.peer_median_return_21d === null
      ? null : pct(candidateReturn21 - aggregate.peer_median_return_21d),
    direction_agreement_5d_pct: pct(aggregate.direction_agreement_5d ?? null),
    direction_agreement_10d_pct: pct(agreement),
    direction_agreement_21d_pct: pct(aggregate.direction_agreement_21d ?? null),
    move_scope: moveScope,
    representative_leaders: ordered.slice(0, 3).map(representative),
    representative_laggards: ordered.slice(-3).reverse().map(representative),
    risk_codes: riskCodes,
  };
}

function buildMarketFeatures(packet: ContextEvidencePacket): MarketFeatures {
  const actions = packet.market_series.map((series) => ({
    series,
    price: series.bars.at(-1)?.session === packet.as_of_session
      ? buildPriceAction(series)
      : emptyPrice(Math.min(series.bars.length, 23), ['MARKET_BENCHMARK_STALE']),
  }));
  const usableActions = actions.filter(({ series, price }) =>
    series.bars.at(-1)?.session === packet.as_of_session
      && price.return_5d_pct !== null
      && price.return_10d_pct !== null
      && price.return_21d_pct !== null);
  const staleBenchmark = actions.some(({ series }) => series.bars.length > 0
    && series.bars.at(-1)?.session !== packet.as_of_session);
  const missingBenchmark = actions.some(({ series, price }) => series.bars.length === 0
    || (series.bars.at(-1)?.session === packet.as_of_session && price.return_21d_pct === null));
  const coverageRisks: string[] = [];
  if (usableActions.length < packet.market_series.length) {
    coverageRisks.push('MARKET_BENCHMARK_COVERAGE_THIN');
  }
  if (staleBenchmark) coverageRisks.push('MARKET_BENCHMARK_STALE');
  if (missingBenchmark) coverageRisks.push('MARKET_BENCHMARK_MISSING');
  const benchmarkReturns: MarketFeatures['benchmark_returns'] = (['SPY', 'QQQ', 'IWM', 'RSP'] as const)
    .map((ticker) => {
      const price = actions.find(({ series }) => series.ticker === ticker)?.price;
      return {
        ticker,
        return_5d_pct: price?.return_5d_pct ?? null,
        return_10d_pct: price?.return_10d_pct ?? null,
        return_21d_pct: price?.return_21d_pct ?? null,
      };
    });
  const primary = actions.find(({ series }) => series.ticker === 'SPY');
  const marketHeadlines = packet.headlines.filter(({ scope }) => scope === 'market');
  const narratives = buildNarratives(marketHeadlines, 'market', packet.decision_time);
  const currentSpy = primary !== undefined && primary.series.bars.at(-1)?.session === packet.as_of_session
    ? primary : undefined;
  const narrativeRoles = buildNarrativeRoles(narratives, marketHeadlines, currentSpy?.series,
    currentSpy?.price.return_21d_pct ?? null, currentSpy?.price.return_5d_pct ?? null, packet.decision_time);
  if (primary === undefined || primary.price.return_21d_pct === null) {
    return {
      data_quality: 'insufficient', regime: 'insufficient', primary_benchmark: 'SPY',
      benchmark_return_5d_pct: null, benchmark_return_10d_pct: null,
      benchmark_return_21d_pct: null, benchmark_returns: benchmarkReturns,
      benchmark_dispersion_10d_pct: null,
      breadth: packet.market_breadth, vix: packet.vix,
      narratives, narrative_roles: narrativeRoles,
      risk_codes: [...new Set([...coverageRisks, 'MARKET_BENCHMARK_MISSING'])],
    };
  }
  const return10s = usableActions.map(({ price }) => price.return_10d_pct!);
  const breadth = packet.market_breadth.positive_10d_pct;
  const breadth21 = packet.market_breadth.positive_21d_pct;
  const aboveSma50 = packet.market_breadth.above_sma50_pct;
  const vix = packet.vix?.value ?? null;
  const r21 = primary.price.return_21d_pct;
  const r5 = primary.price.return_5d_pct ?? 0;
  const negativeBenchmarks10 = return10s.filter((value) => value < 0).length;
  // VIX is useful but the warehouse's current date-only VIX snapshot is not
  // safe for a point-in-time decision. Broad benchmark losses and weak
  // constituent participation independently identify a risk-off tape.
  const breadthRiskOff = (breadth !== null && breadth <= 35)
    || (breadth21 !== null && breadth21 <= 35)
    || (aboveSma50 !== null && aboveSma50 <= 35);
  const broadBenchmarkRiskOff = return10s.length >= 3 && negativeBenchmarks10 >= 3;
  const volatilityRiskOff = vix !== null && vix >= 25;
  const regime = r21 <= -5 && (volatilityRiskOff || breadthRiskOff || broadBenchmarkRiskOff) ? 'risk_off'
    : r21 < 0 && r5 >= 3 && (volatilityRiskOff || breadthRiskOff) ? 'volatile_rebound'
      : r21 >= 3 && (breadth ?? -1) >= 60 && (aboveSma50 ?? -1) >= 55 ? 'risk_on_broad'
        : r21 >= 3 ? 'risk_on_narrow'
          : Math.abs(r21) < 3 && (vix === null || vix < 22) && !breadthRiskOff ? 'range' : 'mixed';
  const risks: string[] = [...coverageRisks];
  if (breadth === null || breadth21 === null || aboveSma50 === null) risks.push('MARKET_BREADTH_MISSING');
  if (packet.vix === null) risks.push('MARKET_VIX_MISSING');
  if (regime === 'risk_off') risks.push('MARKET_RISK_OFF');
  if (regime === 'risk_on_narrow') risks.push('MARKET_PARTICIPATION_NARROW');
  return {
    // VIX is an optional overlay until a timestamp-safe source is available.
    // Missing benchmark or breadth evidence still downgrades the critical lane.
    data_quality: risks.some((code) => code === 'MARKET_BREADTH_MISSING'
      || code === 'MARKET_BENCHMARK_MISSING'
      || code === 'MARKET_BENCHMARK_STALE'
      || code === 'MARKET_BENCHMARK_COVERAGE_THIN') ? 'partial' : 'complete',
    regime,
    primary_benchmark: 'SPY',
    benchmark_return_5d_pct: primary.price.return_5d_pct,
    benchmark_return_10d_pct: primary.price.return_10d_pct,
    benchmark_return_21d_pct: r21,
    benchmark_returns: benchmarkReturns,
    benchmark_dispersion_10d_pct: round(medianAbsoluteDeviation(return10s), 2),
    breadth: packet.market_breadth,
    vix: packet.vix,
    narratives, narrative_roles: narrativeRoles,
    risk_codes: risks,
  };
}

export function buildNarratives(
  headlines: readonly ContextHeadlineEvidence[],
  scope: ContextHeadlineScope,
  decisionTime: string,
): NarrativeCluster[] {
  const decisionMillis = Date.parse(decisionTime);
  const groups = groupHeadlinesByTopic(headlines);
  return [...groups.entries()].map(([label, rows]) => {
    const uniqueRows = [...new Map(rows.map((row) => [row.headline_id, row])).values()]
      .sort((left, right) => right.created_at.localeCompare(left.created_at));
    const scores = uniqueRows.flatMap(({ sentiment_score }) => sentiment_score === null ? [] : [sentiment_score]);
    const positive = scores.some((score) => score >= 0.2);
    const negative = scores.some((score) => score <= -0.2);
    const latest = Math.max(...uniqueRows.map(({ created_at }) => Date.parse(created_at)));
    const sources = new Set(uniqueRows.flatMap(({ url }) => {
      const source = headlineSource(url);
      return source === null ? [] : [source];
    }));
    return {
      cluster_id: `${scope}:${label}`,
      label: label.replace(/_/gu, ' '),
      scope,
      article_count: uniqueRows.length,
      source_count: sources.size === 0 ? null : sources.size,
      freshness_hours: round(Math.max(0, decisionMillis - latest) / 3_600_000, 1)!,
      sentiment: positive && negative ? 'mixed' : positive ? 'positive' : negative ? 'negative'
        : scores.length === 0 ? 'unknown' : 'neutral',
      headline_ids: uniqueRows.map(({ headline_id }) => headline_id).slice(0, 8),
      representative_headlines: uniqueRows.slice(0, 3).map(({ headline_id, title, url, created_at }) => ({
        headline_id,
        title: title.slice(0, 240),
        url,
        created_at,
      })),
    } as const;
  }).sort((left, right) => right.article_count - left.article_count || left.freshness_hours - right.freshness_hours)
    .slice(0, 6);
}

/** Headlines grouped by canonical topic (up to four per headline), exactly as `buildNarratives` groups them. */
function groupHeadlinesByTopic(headlines: readonly ContextHeadlineEvidence[]): Map<string, ContextHeadlineEvidence[]> {
  const groups = new Map<string, ContextHeadlineEvidence[]>();
  for (const headline of headlines) {
    const codes = headline.topics.length === 0 ? keywordTopics(headline.title) : headline.topics;
    for (const code of codes.length === 0 ? ['other'] : codes.slice(0, 4)) {
      const canonical = canonicalTopic(code);
      const group = groups.get(canonical) ?? [];
      group.push(headline);
      groups.set(canonical, group);
    }
  }
  return groups;
}

function canonicalTopic(code: string): string {
  return code.trim().toLowerCase().replace(/[^a-z0-9]+/gu, '_').replace(/^_|_$/gu, '');
}

/*
 * THE LEADING AND THE CHALLENGING NARRATIVE (features v2.4.0).
 *
 * Until v2.3 the "leading" narrative was whichever market headline cluster had the most articles. A trader
 * reads two layers: the story the market is moving WITH, and the one pushing against it, often smaller and
 * still building, which takes over when the direction turns. So:
 *
 * - Leading: the largest cluster whose sentiment agrees with SPY's 21-session direction, if it carries at
 *   least half the top cluster's coverage; otherwise the top cluster, with its alignment stated.
 * - Challenging: a cluster whose sentiment runs against the leading one (or against the market when the
 *   leader has no direction), with at least two articles; rising coverage ranks first. When the five-session
 *   direction has already turned against the 21-session one, `direction_shift` says so.
 * - Reaction: SPY's mean session return on the sessions whose close first followed one of the narrative's
 *   headlines, against the window's other sessions. Measured coincidence, never a cause.
 */
export function buildNarrativeRoles(
  narratives: readonly NarrativeCluster[],
  headlines: readonly ContextHeadlineEvidence[],
  spy: ContextSecuritySeries | undefined,
  spyReturn21dPct: number | null,
  spyReturn5dPct: number | null,
  decisionTime: string,
): MarketNarrativeRoles {
  const policy = SCREENER_CONTEXT_NARRATIVE_POLICY;
  const direction21 = marketDirection(spyReturn21dPct, policy.market_direction_21d_pct);
  const direction5 = marketDirection(spyReturn5dPct, policy.market_direction_5d_pct);
  const directionShift = direction21 === 'up' && direction5 === 'down' || direction21 === 'down' && direction5 === 'up';
  const decisionMillis = Date.parse(decisionTime);
  const grouped = groupHeadlinesByTopic(headlines);
  const spyBars = spy === undefined ? [] : eligibleBars(spy);
  const windowStart = new Date(decisionMillis - 14 * 86_400_000).toISOString().slice(0, 10);
  const sessionReturns = spyBars.slice(1).map((bar, index) => ({
    session: bar.session,
    value: bar.close / spyBars[index]!.close - 1,
  })).filter(({ session }) => session >= windowStart);
  const roles = narratives
    .filter(({ cluster_id }) => cluster_id.split(':').slice(1).join(':') !== 'other')
    .map((narrative): MarketNarrativeRole => {
      const key = narrative.cluster_id.split(':').slice(1).join(':');
      const rows = [...new Map((grouped.get(key) ?? []).map((row) => [row.headline_id, row])).values()];
      const recent = rows.filter(({ created_at }) =>
        Date.parse(created_at) >= decisionMillis - policy.recent_hours * 3_600_000).length;
      const share = rows.length === 0 ? 0 : recent / rows.length;
      const reactionSessions = new Set(rows.flatMap(({ created_at }) => {
        const created = Date.parse(created_at);
        const bar = spyBars.find(({ session }) => newYorkCloseMillis(session) > created);
        return bar === undefined ? [] : [bar.session];
      }));
      const on = sessionReturns.filter(({ session }) => reactionSessions.has(session)).map(({ value }) => value);
      const other = sessionReturns.filter(({ session }) => !reactionSessions.has(session)).map(({ value }) => value);
      const onMean = pct(mean(on));
      const otherMean = pct(mean(other));
      const sentimentSign = sentimentDirection(narrative.sentiment);
      const marketSign = direction21 === 'up' ? 1 : direction21 === 'down' ? -1 : 0;
      return {
        cluster_id: narrative.cluster_id,
        label: narrative.label,
        sentiment: narrative.sentiment,
        alignment: sentimentSign === 0 || marketSign === 0 ? 'unaligned'
          : sentimentSign === marketSign ? 'with_market' : 'against_market',
        article_count: narrative.article_count,
        recent_article_share_pct: round(share * 100, 1)!,
        momentum: rows.length >= policy.minimum_role_articles && share >= policy.rising_recent_share ? 'rising'
          : rows.length >= 3 && recent === 0 ? 'fading' : 'steady',
        reaction_session_count: on.length,
        spy_mean_return_on_narrative_sessions_pct: onMean,
        spy_mean_return_other_sessions_pct: otherMean,
        reaction_gap_pct: onMean === null || otherMean === null ? null : round(onMean - otherMean, 2),
      };
    });
  const top = roles[0];
  const leading = top === undefined ? null
    : roles.find((role) => role.alignment === 'with_market'
      && role.article_count >= Math.max(policy.minimum_role_articles, Math.ceil(top.article_count / 2))) ?? top;
  const leadSign = leading === null ? 0 : sentimentDirection(leading.sentiment);
  const marketSign = direction21 === 'up' ? 1 : direction21 === 'down' ? -1 : 0;
  // Every candidate challenger shares one sign (against the leader, or against the market when the leader has
  // none), so a turned five-session direction never reorders them; it is reported as `direction_shift`.
  const against = leadSign !== 0 ? -leadSign : -marketSign;
  const challenging = against === 0 ? null : roles
    .filter((role) => role !== leading && role.article_count >= policy.minimum_role_articles
      && sentimentDirection(role.sentiment) === against)
    .sort((left, right) => Number(right.momentum === 'rising') - Number(left.momentum === 'rising')
      || right.recent_article_share_pct - left.recent_article_share_pct
      || right.article_count - left.article_count
      || left.cluster_id.localeCompare(right.cluster_id))[0] ?? null;
  return {
    market_direction_21d: direction21,
    market_direction_5d: direction5,
    direction_shift: directionShift,
    leading,
    challenging,
  };
}

function marketDirection(value: number | null, threshold: number): MarketDirection {
  if (value === null) return 'unavailable';
  return value > threshold ? 'up' : value < -threshold ? 'down' : 'flat';
}

function sentimentDirection(sentiment: NarrativeCluster['sentiment']): -1 | 0 | 1 {
  return sentiment === 'positive' ? 1 : sentiment === 'negative' ? -1 : 0;
}

/** The regular close, 16:00 New York, as a UTC instant: 20:00Z in daylight time, 21:00Z otherwise. */
function newYorkCloseMillis(session: string): number {
  const [year, month, day] = session.split('-').map(Number) as [number, number, number];
  return Date.UTC(year, month - 1, day, isUsEasternDaylightTime(year, month, day) ? 20 : 21);
}

/** US daylight time since 2007: from the second Sunday of March to the first Sunday of November. */
function isUsEasternDaylightTime(year: number, month: number, day: number): boolean {
  if (month < 3 || month > 11) return false;
  if (month > 3 && month < 11) return true;
  const firstSunday = 1 + (7 - new Date(Date.UTC(year, month - 1, 1)).getUTCDay()) % 7;
  return month === 3 ? day >= firstSunday + 7 : day < firstSunday;
}

/*
 * HOW THE CANDIDATE MOVES WITH THE MARKET. Correlation and beta of daily returns against SPY over the last
 * sixty aligned sessions (at least twenty), the sign of its 21-session move against SPY's, and which market
 * narrative its own candidate- or industry-linked headlines share by topic.
 */
function buildMarketCoMovement(
  candidateBars: readonly ContextDailyBar[],
  spy: ContextSecuritySeries | undefined,
  roles: MarketNarrativeRoles,
  candidateClusters: readonly NarrativeCluster[],
): MarketCoMovementFeatures {
  const policy = SCREENER_CONTEXT_NARRATIVE_POLICY;
  const topicKey = (clusterId: string): string => clusterId.split(':').slice(1).join(':');
  const keys = new Set(candidateClusters.map(({ cluster_id }) => topicKey(cluster_id)));
  const leadingLinked = roles.leading !== null && keys.has(topicKey(roles.leading.cluster_id));
  const challengingLinked = roles.challenging !== null && keys.has(topicKey(roles.challenging.cluster_id));
  const narrativeLink: MarketCoMovementFeatures['narrative_link'] =
    roles.leading === null && roles.challenging === null || candidateClusters.length === 0 ? 'unavailable'
      : leadingLinked && challengingLinked ? 'both' : leadingLinked ? 'leading'
        : challengingLinked ? 'challenging' : 'neither';
  if (spy === undefined || candidateBars.length < 2) {
    return {
      return_session_count: 0, correlation_60d: null, beta_60d: null, state: 'unavailable',
      direction_vs_market_21d: 'unavailable', narrative_link: narrativeLink,
    };
  }
  const spyCloses = new Map(eligibleBars(spy).map(({ session, close }) => [session, close]));
  const pairs: (readonly [number, number])[] = [];
  for (let index = candidateBars.length - 1; index >= 1 && pairs.length < policy.co_movement_sessions; index -= 1) {
    const current = candidateBars[index]!;
    const previous = candidateBars[index - 1]!;
    const spyCurrent = spyCloses.get(current.session);
    const spyPrevious = spyCloses.get(previous.session);
    if (spyCurrent === undefined || spyPrevious === undefined) continue;
    pairs.push([current.close / previous.close - 1, spyCurrent / spyPrevious - 1]);
  }
  let correlation: number | null = null;
  let beta: number | null = null;
  if (pairs.length >= policy.minimum_co_movement_sessions) {
    const candidateMean = mean(pairs.map(([value]) => value))!;
    const spyMean = mean(pairs.map(([, value]) => value))!;
    let covariance = 0;
    let candidateVariance = 0;
    let spyVariance = 0;
    for (const [candidateReturn, spyReturn] of pairs) {
      covariance += (candidateReturn - candidateMean) * (spyReturn - spyMean);
      candidateVariance += (candidateReturn - candidateMean) ** 2;
      spyVariance += (spyReturn - spyMean) ** 2;
    }
    if (candidateVariance > 0 && spyVariance > 0) {
      correlation = round(covariance / Math.sqrt(candidateVariance * spyVariance), 2);
      beta = round(covariance / spyVariance, 2);
    }
  }
  const candidate21 = periodReturn(candidateBars, 21);
  const spy21 = alignedPeriodReturn(spy, candidateBars, 21);
  const direction: MarketCoMovementFeatures['direction_vs_market_21d'] = candidate21 === null || spy21 === null
    ? 'unavailable'
    : Math.abs(candidate21) < 0.01 || Math.abs(spy21) < 0.01 ? 'flat'
      : Math.sign(candidate21) === Math.sign(spy21) ? 'same' : 'opposite';
  return {
    return_session_count: pairs.length,
    correlation_60d: correlation,
    beta_60d: beta,
    state: correlation === null ? 'unavailable' : correlation >= 0.5 ? 'tracks_market'
      : correlation >= 0.2 ? 'loosely_tracks' : 'independent',
    direction_vs_market_21d: direction,
    narrative_link: narrativeLink,
  };
}

/*
 * ONE GIANT IS NOT THE INDUSTRY. The median already reads the group equally; the connector adds the
 * equal- and capitalisation-weighted returns and the largest member's share. When one member holds 40% of
 * the group's capitalisation, or the top three hold 60%, the equal-weighted return describes the group and
 * the cap-weighted one describes its giants; the gap between them says which way the giants are pulling.
 */
function buildPeerWeighting(
  aggregate: ContextPeerAggregateEvidence | undefined,
  candidateBars: readonly ContextDailyBar[],
): PeerWeightingFeatures {
  const weighting = aggregate?.weighting;
  if (weighting === undefined) return emptyPeerWeighting('not_supplied');
  const policy = SCREENER_CONTEXT_PEER_WEIGHTING_POLICY;
  const window: 21 | 10 | null = weighting.cap_weight_return_21d !== null && weighting.equal_weight_return_21d !== null
    ? 21
    : weighting.cap_weight_return_10d !== null && weighting.equal_weight_return_10d !== null ? 10 : null;
  if (weighting.capitalized_peer_count < 2 || window === null) return emptyPeerWeighting('insufficient');
  const cap = window === 21 ? weighting.cap_weight_return_21d! : weighting.cap_weight_return_10d!;
  const equal = window === 21 ? weighting.equal_weight_return_21d! : weighting.equal_weight_return_10d!;
  const gap = pct(cap - equal)!;
  const threshold = window === 21 ? policy.weighting_split_pct_21d : policy.weighting_split_pct_10d;
  const concentration: PeerWeightingFeatures['concentration'] =
    weighting.largest_member_weight === null && weighting.top3_weight === null ? 'unavailable'
      : (weighting.largest_member_weight ?? 0) >= policy.dominated_largest_member_weight ? 'dominated'
        : (weighting.top3_weight ?? 0) >= policy.concentrated_top3_weight ? 'concentrated' : 'broad';
  const candidateReturn = periodReturn(candidateBars, window);
  return {
    status: 'measured',
    capitalized_peer_count: weighting.capitalized_peer_count,
    equal_weight_return_5d_pct: pct(weighting.equal_weight_return_5d),
    equal_weight_return_10d_pct: pct(weighting.equal_weight_return_10d),
    equal_weight_return_21d_pct: pct(weighting.equal_weight_return_21d),
    cap_weight_return_5d_pct: pct(weighting.cap_weight_return_5d),
    cap_weight_return_10d_pct: pct(weighting.cap_weight_return_10d),
    cap_weight_return_21d_pct: pct(weighting.cap_weight_return_21d),
    cap_minus_equal_pct: gap,
    comparison_sessions: window,
    candidate_excess_vs_equal_weight_pct: candidateReturn === null ? null : pct(candidateReturn - equal),
    candidate_excess_vs_cap_weight_pct: candidateReturn === null ? null : pct(candidateReturn - cap),
    largest_member_ticker: weighting.largest_member_ticker,
    largest_member_weight_pct: weighting.largest_member_weight === null ? null
      : round(weighting.largest_member_weight * 100, 1),
    top3_weight_pct: weighting.top3_weight === null ? null : round(weighting.top3_weight * 100, 1),
    effective_member_count: round(weighting.effective_member_count, 1),
    concentration,
    weighting_split: gap >= threshold ? 'largest_members_lead' : gap <= -threshold ? 'largest_members_lag' : 'agree',
    preferred_basis: concentration === 'dominated' || concentration === 'concentrated' ? 'equal_weight' : 'median',
  };
}

function emptyPeerWeighting(status: 'not_supplied' | 'insufficient'): PeerWeightingFeatures {
  return {
    status, capitalized_peer_count: null,
    equal_weight_return_5d_pct: null, equal_weight_return_10d_pct: null, equal_weight_return_21d_pct: null,
    cap_weight_return_5d_pct: null, cap_weight_return_10d_pct: null, cap_weight_return_21d_pct: null,
    cap_minus_equal_pct: null, comparison_sessions: null,
    candidate_excess_vs_equal_weight_pct: null, candidate_excess_vs_cap_weight_pct: null,
    largest_member_ticker: null, largest_member_weight_pct: null, top3_weight_pct: null,
    effective_member_count: null, concentration: 'unavailable', weighting_split: 'unavailable',
    preferred_basis: 'median',
  };
}

/*
 * HEADLINE PEERS. The stocks the news names alongside the candidate are its working peers, whatever the
 * SIC code says: AMD beside Micron and Intel, or Amazon beside Walmart in retail stories and beside Microsoft
 * in cloud ones. The connector counts co-mentions over 90 days; code measures their aligned moves, groups
 * them by the headlines' own topics, and marks separate business lines when two themes share no peer.
 */
function buildHeadlinePeers(
  row: ContextHeadlinePeerEvidence | undefined,
  candidateBars: readonly ContextDailyBar[],
): HeadlinePeerFeatures {
  if (row === undefined) return emptyHeadlinePeers('not_supplied');
  const base = {
    ...emptyHeadlinePeers(row.peers.length === 0 ? 'none_found' : 'insufficient'),
    lookback_calendar_days: row.lookback_calendar_days,
    candidate_headline_count: row.candidate_headline_count,
  };
  const measured = row.peers.map((peer) => ({
    peer,
    return5: alignedPeriodReturn(peer.series, candidateBars, 5),
    return10: alignedPeriodReturn(peer.series, candidateBars, 10),
    return21: alignedPeriodReturn(peer.series, candidateBars, 21),
  })).filter(({ return10 }) => return10 !== null);
  if (measured.length < 2) return base;
  const middle = (values: readonly (number | null)[]): number | null =>
    median(values.filter((value): value is number => value !== null));
  const median5 = middle(measured.map(({ return5 }) => return5));
  const median10 = middle(measured.map(({ return10 }) => return10))!;
  const median21 = middle(measured.map(({ return21 }) => return21));
  const candidate5 = periodReturn(candidateBars, 5);
  const candidate10 = periodReturn(candidateBars, 10);
  const candidate21 = periodReturn(candidateBars, 21);
  const excess5 = candidate5 === null || median5 === null ? null : candidate5 - median5;
  const excess21 = candidate21 === null || median21 === null ? null : candidate21 - median21;
  const primary = excess21 ?? (candidate10 === null ? null : candidate10 - median10);
  const relation: HeadlinePeerFeatures['relation'] =
    excess5 !== null && excess21 !== null && Math.abs(excess5) >= 0.02 && Math.abs(excess21) >= 0.02
      && Math.sign(excess5) !== Math.sign(excess21) ? 'mixed'
      : primary === null ? 'unavailable' : primary >= 0.02 ? 'leads' : primary <= -0.02 ? 'lags' : 'moves_with';
  const themeRows = new Map<string, { tickers: Set<string>; count: number; returns21: number[] }>();
  for (const { peer, return21 } of measured) {
    for (const topic of peer.topics) {
      const key = canonicalTopic(topic.topic);
      if (key === '') continue;
      const theme = themeRows.get(key) ?? { tickers: new Set<string>(), count: 0, returns21: [] };
      theme.tickers.add(peer.ticker);
      theme.count += topic.co_mention_count;
      if (return21 !== null) theme.returns21.push(return21);
      themeRows.set(key, theme);
    }
  }
  const themes: HeadlinePeerTheme[] = [...themeRows.entries()]
    .sort(([leftKey, left], [rightKey, right]) => right.count - left.count || leftKey.localeCompare(rightKey))
    .slice(0, 3)
    .map(([key, theme]) => ({
      topic: key,
      label: key.replace(/_/gu, ' '),
      tickers: [...theme.tickers].sort(),
      co_mention_count: theme.count,
      median_return_21d_pct: pct(median(theme.returns21)),
    }));
  const businessLinesSplit = themes.some((left, index) => themes.slice(index + 1)
    .some((right) => right.tickers.every((ticker) => !left.tickers.includes(ticker))));
  const peers: HeadlinePeerMove[] = [...measured]
    .sort((left, right) => right.peer.co_mention_count - left.peer.co_mention_count
      || left.peer.ticker.localeCompare(right.peer.ticker))
    .map(({ peer, return5, return10, return21 }) => ({
      ticker: peer.ticker,
      co_mention_count: peer.co_mention_count,
      same_industry: peer.same_industry,
      top_topic: [...peer.topics].sort((left, right) => right.co_mention_count - left.co_mention_count
        || left.topic.localeCompare(right.topic))[0]?.topic ?? null,
      return_5d_pct: pct(return5),
      return_10d_pct: pct(return10),
      return_21d_pct: pct(return21),
    }));
  return {
    ...base,
    status: 'measured',
    peer_count: measured.length,
    outside_industry_count: measured.filter(({ peer }) => !peer.same_industry).length,
    median_return_5d_pct: pct(median5),
    median_return_10d_pct: pct(median10),
    median_return_21d_pct: pct(median21),
    positive_breadth_10d_pct: round(measured.filter(({ return10 }) => return10! > 0).length / measured.length * 100, 1),
    candidate_excess_5d_pct: pct(excess5),
    candidate_excess_21d_pct: pct(excess21),
    relation,
    themes,
    business_lines_split: businessLinesSplit,
    peers,
  };
}

function emptyHeadlinePeers(status: HeadlinePeerFeatures['status']): HeadlinePeerFeatures {
  return {
    status, lookback_calendar_days: null, candidate_headline_count: null, peer_count: 0,
    outside_industry_count: 0, median_return_5d_pct: null, median_return_10d_pct: null,
    median_return_21d_pct: null, positive_breadth_10d_pct: null, candidate_excess_5d_pct: null,
    candidate_excess_21d_pct: null, relation: 'unavailable', themes: [], business_lines_split: false, peers: [],
  };
}

function headlineSource(url: string): string | null {
  const match = /^https?:\/\/([^/?#]+)(?:[/?#]|$)/iu.exec(url.trim());
  if (match === null) return null;
  let authority = match[1]!;
  const userInfo = authority.lastIndexOf('@');
  if (userInfo >= 0) authority = authority.slice(userInfo + 1);
  const colon = authority.lastIndexOf(':');
  if (colon >= 0) {
    if (authority.indexOf(':') !== colon) return null;
    const port = authority.slice(colon + 1);
    if (!/^\d{1,5}$/u.test(port) || Number(port) > 65_535) return null;
    authority = authority.slice(0, colon);
  }
  const hostname = authority.toLowerCase().replace(/^www\./u, '');
  if (hostname.length === 0 || hostname.length > 253 || !hostname.split('.').every((label) => (
    /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/u.test(label)
  ))) return null;
  return hostname;
}

function detectPatterns(
  bars: readonly ContextDailyBar[],
  return5: number | null,
  return21: number | null,
  acceleration: number | null,
  returnPercentile: number | null,
): PricePatternCandidate[] {
  const patterns: PricePatternCandidate[] = [];
  const latest = bars.at(-1)!;
  const prior = bars.at(-2)!;
  const range = latest.high - latest.low;
  const body = Math.abs(latest.close - latest.open);
  const upper = latest.high - Math.max(latest.open, latest.close);
  const lower = Math.min(latest.open, latest.close) - latest.low;
  const add = (code: string, direction: PricePatternCandidate['direction'], strength: PricePatternCandidate['strength'], description: string, invalidation: string | null): void => {
    patterns.push({ code, direction, strength, observed_on: latest.session, description, invalidation });
  };
  if (range > 0 && body / range <= 0.12) add('DOJI', 'neutral', 'weak', 'Latest session closed near its open, signalling indecision.', null);
  if (range > 0 && lower >= Math.max(body * 2, range * 0.45) && upper <= range * 0.2) {
    add('HAMMER', 'bullish', 'moderate', 'Long lower shadow shows intraday rejection of lower prices.', `Close below ${latest.low.toFixed(2)}`);
  }
  if (range > 0 && upper >= Math.max(body * 2, range * 0.45) && lower <= range * 0.2) {
    add('SHOOTING_STAR', 'bearish', 'moderate', 'Long upper shadow shows intraday rejection of higher prices.', `Close above ${latest.high.toFixed(2)}`);
  }
  if (latest.close > latest.open && prior.close < prior.open && latest.open <= prior.close && latest.close >= prior.open) {
    add('BULLISH_ENGULFING', 'bullish', 'strong', 'Latest real body engulfed the prior bearish body.', `Close below ${latest.low.toFixed(2)}`);
  }
  if (latest.close < latest.open && prior.close > prior.open && latest.open >= prior.close && latest.close <= prior.open) {
    add('BEARISH_ENGULFING', 'bearish', 'strong', 'Latest real body engulfed the prior bullish body.', `Close above ${latest.high.toFixed(2)}`);
  }
  if (latest.high < prior.high && latest.low > prior.low) add('INSIDE_BAR', 'neutral', 'weak', 'Latest range sits inside the prior session, indicating compression.', null);
  if (latest.high > prior.high && latest.low < prior.low) add('OUTSIDE_BAR', latest.close >= latest.open ? 'bullish' : 'bearish', 'moderate', 'Latest session expanded beyond both sides of the prior range.', null);
  const recent = bars.slice(-5);
  if (recent.length === 5 && recent.slice(1).every((bar, index) => bar.low > recent[index]!.low)) {
    add('HIGHER_LOW_SEQUENCE', 'bullish', 'moderate', 'Five-session sequence retained progressively higher lows.', `Close below ${Math.min(...recent.map(({ low }) => low)).toFixed(2)}`);
  }
  if (recent.length === 5 && recent.slice(1).every((bar, index) => bar.high < recent[index]!.high)) {
    add('LOWER_HIGH_SEQUENCE', 'bearish', 'moderate', 'Five-session sequence formed progressively lower highs.', `Close above ${Math.max(...recent.map(({ high }) => high)).toFixed(2)}`);
  }
  const priorTen = bars.slice(-15, -5);
  if (recent.length === 5 && priorTen.length >= 5) {
    const recentWidth = Math.max(...recent.map(({ high }) => high)) - Math.min(...recent.map(({ low }) => low));
    const priorWidth = Math.max(...priorTen.map(({ high }) => high)) - Math.min(...priorTen.map(({ low }) => low));
    if (priorWidth > 0 && recentWidth / priorWidth <= 0.5) add('CONSOLIDATION', 'neutral', 'moderate', 'Five-session range compressed versus the preceding ten sessions.', null);
  }
  const breakoutBase = bars.slice(-12, -2);
  if (breakoutBase.length >= 5 && prior.close > Math.max(...breakoutBase.map(({ high }) => high))
      && latest.close < Math.max(...breakoutBase.map(({ high }) => high))) {
    add('FAILED_BREAKOUT', 'bearish', 'strong', 'A close above the prior range was followed by a close back inside it.', `Close above ${prior.high.toFixed(2)}`);
  }
  if (return21 !== null && return21 > 0 && return5 !== null && return5 <= -0.02) {
    add('ROLLING_OVER', 'bearish', 'moderate', 'The positive monthly path weakened over the latest five sessions.', `Close above ${Math.max(...recent.map(({ high }) => high)).toFixed(2)}`);
  }
  if (return21 !== null && return21 > 0.03 && return5 !== null && return5 > 0.02 && (acceleration ?? 0) > 0) {
    add('TREND_REACCELERATION', 'bullish', 'moderate', 'The established monthly advance accelerated over the latest five sessions.', `Close below ${Math.min(...recent.map(({ low }) => low)).toFixed(2)}`);
  }
  if (return21 !== null && returnPercentile !== null && returnPercentile >= 0.95) {
    add('UNUSUAL_UPWARD_PACE', 'bearish', Math.abs(return21) >= 0.5 ? 'strong' : 'moderate', 'The 21-session advance ranks in the most extreme 5% of its one-year observations; extension risk is elevated.', null);
  }
  if (return21 !== null && returnPercentile !== null && returnPercentile <= 0.05) {
    add('UNUSUAL_DOWNWARD_PACE', 'bearish', Math.abs(return21) >= 0.5 ? 'strong' : 'moderate', 'The 21-session decline ranks in the most extreme 5% of its one-year observations.', null);
  }
  return patterns.slice(0, 10);
}

/** Validate the complete RPC packet before any feature computation or model call. */
export function validateScreenerContextEvidencePacket(
  spec: ContextRetrievalSpec,
  packet: ContextEvidencePacket,
): void {
  validateScreenerContextRetrievalSpec(spec);
  if (packet.schema_version !== 'screener_context_evidence_packet.v2'
      || packet.retrieval_release !== spec.retrieval_release
      || packet.decision_time !== spec.decision_time
      || packet.as_of_session !== spec.as_of_session
      || !HASH.test(packet.retrieval_spec_hash)
      || packet.retrieval_spec_hash !== hashScreenerContextRetrievalSpec(spec)) fail('packet_identity_invalid');
  const decisionMillis = canonicalInstantMillis(packet.decision_time);
  if (decisionMillis === null) fail('decision_time_invalid');
  // `headline_peers` is its own read, so it carries its own provenance exactly when the packet has it.
  const expectedSourceLanes = ['headlines', 'market_breadth', 'peer_aggregates', 'peer_membership', 'price_paths',
    ...packet.headline_peers === undefined ? [] : ['headline_peers']].sort();
  const sourceQueries = Object.entries(packet.source_query_hashes);
  const sourceResults = Object.entries(packet.source_result_hashes);
  if (JSON.stringify(Object.keys(packet.source_query_hashes).sort()) !== JSON.stringify(expectedSourceLanes)
      || JSON.stringify(Object.keys(packet.source_result_hashes).sort()) !== JSON.stringify(expectedSourceLanes)
      || [...sourceQueries, ...sourceResults].some(([key, value]) => key.length === 0 || key.length > 80
        || !HASH.test(value) || CONTROL.test(key))) {
    fail('source_provenance_invalid');
  }
  for (const cutoff of Object.values(packet.source_cutoffs)) {
    const cutoffMillis = cutoff === null ? null : canonicalInstantMillis(cutoff);
    if (cutoff !== null && (cutoffMillis === null || cutoffMillis > decisionMillis)) {
      fail('source_cutoff_after_decision');
    }
  }
  const populatedWithoutLineage =
    packet.candidates.some(({ series }) => series.bars.length > 0) && packet.source_cutoffs.prices === null
    || packet.peer_groups.length > 0 && packet.source_cutoffs.peer_membership === null
    || (packet.market_series.some(({ bars }) => bars.length > 0)
      || packet.market_breadth.eligible_count_10d > 0
      || packet.market_breadth.eligible_count_21d > 0
      || packet.market_breadth.eligible_count_sma50 > 0
      || packet.vix !== null) && packet.source_cutoffs.market === null
    || packet.headlines.length > 0 && packet.source_cutoffs.headlines === null;
  if (populatedWithoutLineage) fail('source_lineage_missing');
  if (packet.candidates.length !== spec.candidates.length) fail('candidate_population_mismatch');
  packet.candidates.forEach((candidate, index) => {
    const expected = spec.candidates[index];
    if (expected === undefined || candidate.candidate_id !== expected.candidate_id
        || candidate.vs_security_id !== expected.vs_security_id || candidate.ticker !== expected.ticker) {
      fail('candidate_identity_or_order_mismatch');
    }
    if (candidate.series.vs_security_id !== candidate.vs_security_id
        || candidate.series.ticker !== candidate.ticker) fail('candidate_series_identity_mismatch');
    const resolution = candidate.industry_resolution;
    if (candidate.industry_id !== expected.industry_id || candidate.industry_label !== expected.industry_label
        || resolution.requested_industry_id !== expected.industry_id
        || resolution.requested_industry_label !== expected.industry_label
        || (resolution.status === 'unresolved' && (resolution.resolved_industry_id !== null
          || resolution.resolved_industry_label !== null || resolution.resolved_taxonomy_level !== null))
        || (resolution.status === 'resolved_from_point_in_time_sic'
          && (resolution.resolved_industry_id === null || resolution.resolved_industry_label === null
            || resolution.resolved_taxonomy_level === null
            || !resolution.resolved_industry_id.startsWith(`${resolution.resolved_taxonomy_level}:`)))) {
      fail('candidate_industry_resolution_invalid');
    }
    validateSeries(candidate.series, packet.as_of_session, 253, false);
  });
  const resolvedCandidatesByIndustry = new Map<string, ContextCandidateEvidence[]>();
  for (const candidate of packet.candidates) {
    const industryId = candidate.industry_resolution.resolved_industry_id;
    if (industryId === null) continue;
    const candidates = resolvedCandidatesByIndustry.get(industryId) ?? [];
    candidates.push(candidate);
    resolvedCandidatesByIndustry.set(industryId, candidates);
  }
  const groupsById = new Map<string, ContextPeerGroupEvidence>();
  for (const group of packet.peer_groups) {
    const effectiveMillis = canonicalInstantMillis(group.effective_at);
    const resolvedCandidates = resolvedCandidatesByIndustry.get(group.industry_id) ?? [];
    if (groupsById.has(group.industry_id) || effectiveMillis === null || effectiveMillis > decisionMillis
        || !group.industry_id.startsWith(`${group.taxonomy_level}:`)
        || resolvedCandidates.length === 0
        || resolvedCandidates.some(({ industry_resolution: resolution }) =>
          resolution.resolved_taxonomy_level !== group.taxonomy_level
            || resolution.resolved_industry_label !== group.industry_label)
        || group.members.length > spec.peer_policy.maximum_members_per_industry
        || !Number.isInteger(group.eligible_member_count) || group.eligible_member_count < group.members.length
        || new Set(group.members.map(({ vs_security_id }) => vs_security_id)).size !== group.members.length) {
      fail('peer_group_invalid');
    }
    groupsById.set(group.industry_id, group);
    for (const member of group.members) validateSeries(member, packet.as_of_session, 253, false);
  }
  for (const candidate of packet.candidates) {
    const resolution = candidate.industry_resolution;
    if (resolution.resolved_industry_id !== null && !groupsById.has(resolution.resolved_industry_id)) {
      fail('candidate_industry_group_missing');
    }
  }
  const aggregateCandidates = new Set<string>();
  for (const aggregate of packet.peer_aggregates) {
    const candidate = packet.candidates.find(({ candidate_id }) => candidate_id === aggregate.candidate_id);
    const group = groupsById.get(aggregate.industry_id);
    const cutoff = aggregate.source_cutoff === null ? null : canonicalInstantMillis(aggregate.source_cutoff);
    const membershipCutoff = canonicalInstantMillis(aggregate.membership_source_cutoff);
    const metrics10 = [aggregate.peer_median_return_10d, aggregate.peer_positive_breadth_10d,
      aggregate.peer_dispersion_10d] as const;
    const metrics10WithAgreement = [...metrics10, aggregate.direction_agreement_10d] as const;
    const optional5 = [aggregate.observed_peer_count_5d, aggregate.peer_median_return_5d,
      aggregate.peer_positive_breadth_5d, aggregate.peer_dispersion_5d,
      aggregate.direction_agreement_5d] as const;
    const has5 = optional5.some((value) => value !== undefined);
    const observed5 = aggregate.observed_peer_count_5d;
    const metrics5 = [aggregate.peer_median_return_5d, aggregate.peer_positive_breadth_5d,
      aggregate.peer_dispersion_5d] as const;
    const metrics5WithAgreement = [...metrics5, aggregate.direction_agreement_5d] as const;
    const optional21 = [aggregate.peer_positive_breadth_21d, aggregate.peer_dispersion_21d,
      aggregate.direction_agreement_21d] as const;
    const has21Details = optional21.some((value) => value !== undefined);
    const optionalCandidateFacts = [aggregate.candidate_return_5d, aggregate.candidate_return_10d,
      aggregate.candidate_return_21d, aggregate.candidate_excess_return_5d,
      aggregate.candidate_excess_return_10d, aggregate.candidate_excess_return_21d] as const;
    const hasCandidateFacts = optionalCandidateFacts.some((value) => value !== undefined);
    const candidateBars = candidate === undefined ? [] : eligibleBars(candidate.series);
    const candidateReturns = [periodReturn(candidateBars, 5), periodReturn(candidateBars, 10),
      periodReturn(candidateBars, 21)] as const;
    const candidateExcess = [
      candidateReturns[0] === null || aggregate.peer_median_return_5d === undefined
        || aggregate.peer_median_return_5d === null ? null : candidateReturns[0] - aggregate.peer_median_return_5d,
      candidateReturns[1] === null || aggregate.peer_median_return_10d === null
        ? null : candidateReturns[1] - aggregate.peer_median_return_10d,
      candidateReturns[2] === null || aggregate.peer_median_return_21d === null
        ? null : candidateReturns[2] - aggregate.peer_median_return_21d,
    ] as const;
    // THE CHECKS ARE NAMED, AND THE FIRST ONE THAT FAILS IS IN THE CODE (G13, 2026-09-28). This was one condition
    // and one code, so a packet that failed it said nothing about which rule: AI-written custom screens on dev
    // failed every candidate here after 0.4.17 (jobs cdaea0a4, 25f00069) and the packet is not kept on the job.
    // Same rules, same order, the same short-circuits (each check runs only if every earlier one passed); only
    // the code gains `__<check>`, which consumers already read as a prefix match.
    const problem = firstFailing([
      ['identity', () => candidate === undefined || aggregateCandidates.has(aggregate.candidate_id)
        || candidate.industry_resolution.resolved_industry_id !== aggregate.industry_id
        || candidate.industry_resolution.resolved_taxonomy_level !== aggregate.taxonomy_level
        || group === undefined || group.taxonomy_level !== aggregate.taxonomy_level],
      ['eligible_count', () => group!.eligible_member_count !== aggregate.eligible_peer_count
        || !Number.isInteger(aggregate.eligible_peer_count) || aggregate.eligible_peer_count < 0],
      ['observed_counts', () => !Number.isInteger(aggregate.observed_peer_count_10d)
        || !Number.isInteger(aggregate.observed_peer_count_21d)
        || aggregate.observed_peer_count_10d < 0 || aggregate.observed_peer_count_21d < 0
        || aggregate.observed_peer_count_10d > aggregate.eligible_peer_count
        || aggregate.observed_peer_count_21d > aggregate.eligible_peer_count],
      // Each horizon's endpoint is covered on its own (data-connector screener-context/service.ts, #77): a
      // peer can miss the 10-session close yet have the 5- and 21-session ones, so the counts need not
      // shrink with the horizon. Requiring 5d >= 10d >= 21d failed AI-written custom screens whole on dev
      // (2026-09-28, jobs 247cc3c5 and 376a0985). Each count stays bounded by the eligible peers.
      ['horizon_5d', () => has5 && (optional5.some((value) => value === undefined)
        || !Number.isInteger(observed5) || observed5! < 0 || observed5! > aggregate.eligible_peer_count
        || metrics5WithAgreement.some((value) => value !== null && !Number.isFinite(value))
        || (observed5 === 0 && metrics5WithAgreement.some((value) => value !== null))
        || (observed5! > 0 && metrics5.some((value) => value === null))
        || aggregate.peer_median_return_5d! !== null && aggregate.peer_median_return_5d! <= -1
        || aggregate.peer_dispersion_5d! !== null && aggregate.peer_dispersion_5d! < 0
        || !unitIntervalOrNull(aggregate.peer_positive_breadth_5d!)
        || !unitIntervalOrNull(aggregate.direction_agreement_5d!))],
      ['horizon_21d_details', () => has21Details && (optional21.some((value) => value === undefined)
        || optional21.some((value) => value !== null && !Number.isFinite(value))
        || (aggregate.observed_peer_count_21d === 0 && optional21.some((value) => value !== null))
        || (aggregate.observed_peer_count_21d > 0
          && [aggregate.peer_positive_breadth_21d, aggregate.peer_dispersion_21d]
            .some((value) => value === null))
        || aggregate.peer_dispersion_21d! !== null && aggregate.peer_dispersion_21d! < 0
        || !unitIntervalOrNull(aggregate.peer_positive_breadth_21d!)
        || !unitIntervalOrNull(aggregate.direction_agreement_21d!))],
      ['candidate_facts_shape', () => hasCandidateFacts && (optionalCandidateFacts.some((value) => value === undefined)
        || optionalCandidateFacts.some((value) => value !== null && !Number.isFinite(value)))],
      ['candidate_returns', () => hasCandidateFacts && (
        !nearlyEqualNullable(aggregate.candidate_return_5d!, candidateReturns[0])
        || !nearlyEqualNullable(aggregate.candidate_return_10d!, candidateReturns[1])
        || !nearlyEqualNullable(aggregate.candidate_return_21d!, candidateReturns[2]))],
      ['candidate_excess', () => hasCandidateFacts && (
        !nearlyEqualNullable(aggregate.candidate_excess_return_5d!, candidateExcess[0])
        || !nearlyEqualNullable(aggregate.candidate_excess_return_10d!, candidateExcess[1])
        || !nearlyEqualNullable(aggregate.candidate_excess_return_21d!, candidateExcess[2]))],
      ['metrics_10d', () => metrics10WithAgreement.some((value) => value !== null && !Number.isFinite(value))
        || (aggregate.observed_peer_count_10d === 0 && metrics10WithAgreement.some((value) => value !== null))
        || (aggregate.observed_peer_count_10d > 0 && metrics10.some((value) => value === null))
        || aggregate.peer_median_return_10d !== null && aggregate.peer_median_return_10d <= -1
        || aggregate.peer_dispersion_10d !== null && aggregate.peer_dispersion_10d < 0
        || !unitIntervalOrNull(aggregate.peer_positive_breadth_10d)
        || !unitIntervalOrNull(aggregate.direction_agreement_10d)],
      ['median_21d', () => aggregate.peer_median_return_21d !== null && !Number.isFinite(aggregate.peer_median_return_21d)
        || (aggregate.observed_peer_count_21d === 0) !== (aggregate.peer_median_return_21d === null)
        || aggregate.peer_median_return_21d !== null && aggregate.peer_median_return_21d <= -1],
      ['source_cutoff', () => aggregate.source_cutoff !== null && cutoff === null
        || cutoff !== null && cutoff > decisionMillis
        || (aggregate.observed_peer_count_5d ?? 0) + aggregate.observed_peer_count_10d
          + aggregate.observed_peer_count_21d > 0 && cutoff === null],
      ['membership', () => membershipCutoff === null || membershipCutoff > decisionMillis
        || !/^[a-f0-9]{64}$/u.test(aggregate.membership_release_fingerprint)],
      ['weighting', () => aggregate.weighting !== undefined
        && weightingInvalid(aggregate.weighting, aggregate.eligible_peer_count, decisionMillis)],
    ]);
    if (problem !== null) fail(`peer_aggregate_invalid__${problem}`);
    aggregateCandidates.add(aggregate.candidate_id);
  }
  const marketTickers = packet.market_series.map(({ ticker }) => ticker);
  if (marketTickers.length !== spec.market_policy.benchmark_tickers.length
      || new Set(marketTickers).size !== marketTickers.length
      || marketTickers.some((ticker) => !spec.market_policy.benchmark_tickers.includes(ticker as never))) {
    fail('market_series_invalid');
  }
  // A failed market-data lane is represented by the complete requested panel
  // with empty/stale series. Keep that deterministic shape and let the feature
  // layer ground an insufficient-data decision instead of rejecting the packet.
  for (const series of packet.market_series) validateSeries(series, packet.as_of_session, 253, false);
  const headlineCaps: Record<ContextHeadlineScope, number> = {
    candidate: spec.news_policy.maximum_candidate_headlines * spec.candidates.length,
    industry: spec.news_policy.maximum_industry_headlines * Math.max(1, groupsById.size),
    market: spec.news_policy.maximum_market_headlines,
  };
  const candidateIds = new Set(spec.candidates.map(({ candidate_id }) => candidate_id));
  const headlineIds = new Set<string>();
  for (const scope of ['candidate', 'industry', 'market'] as const) {
    if (packet.headlines.filter((headline) => headline.scope === scope).length > headlineCaps[scope]) fail('headline_cap_exceeded');
  }
  for (const headline of packet.headlines) {
    const created = canonicalInstantMillis(headline.created_at);
    const oldestAllowed = decisionMillis - spec.news_policy.lookback_calendar_days * 86_400_000;
    if (created === null || created > decisionMillis || created < oldestAllowed
        || headline.availability_semantics !== 'created_at_proxy'
        || headline.headline_id.length === 0 || headline.headline_id.length > 180
        || headlineIds.has(headline.headline_id) || headline.title.length === 0
        || headline.title.length > 1_000 || headline.url.length === 0 || headline.url.length > 2_048
        || CONTROL.test(headline.headline_id) || CONTROL.test(headline.title) || CONTROL.test(headline.url)
        || (headline.teaser !== null && (headline.teaser.length > 2_000 || CONTROL.test(headline.teaser)))
        || headline.topics.length > 8 || headline.topics.some((topic) => topic.length === 0
          || topic.length > 80 || CONTROL.test(topic))
        || headline.sentiment_score !== null && (!Number.isFinite(headline.sentiment_score)
          || headline.sentiment_score < -1 || headline.sentiment_score > 1)
        || new Set(headline.candidate_ids).size !== headline.candidate_ids.length
        || new Set(headline.industry_ids).size !== headline.industry_ids.length
        || headline.linked_tickers !== undefined
          && (new Set(headline.linked_tickers).size !== headline.linked_tickers.length
            || headline.linked_tickers.some((ticker) => ticker.length === 0 || ticker.length > 32
              || CONTROL.test(ticker)))
        || headline.relevance_score !== undefined && headline.relevance_score !== null
          && (!Number.isFinite(headline.relevance_score) || headline.relevance_score < 0
            || headline.relevance_score > 1
            || headline.scope === 'candidate'
              && headline.relevance_score < spec.news_policy.minimum_ticker_relevance)
        || (headline.scope === 'candidate' && (headline.candidate_ids.length === 0
          || headline.candidate_ids.some((id) => !candidateIds.has(id))))
        || (headline.scope === 'industry' && (headline.industry_ids.length === 0
          || headline.industry_ids.some((id) => !groupsById.has(id))))
        || (headline.scope === 'market' && (headline.candidate_ids.length > 0
          || headline.industry_ids.length > 0))) {
      fail('headline_cutoff_invalid');
    }
    headlineIds.add(headline.headline_id);
  }
  if (packet.headline_peers !== undefined) {
    const problem = headlinePeersProblem(spec, packet, decisionMillis);
    if (problem !== null) fail(`headline_peers_invalid__${problem}`);
  }
  if (packet.headlines.length > 0
      && !packet.risk_codes.includes('HEADLINE_AVAILABILITY_CREATED_AT_PROXY')) {
    fail('headline_availability_risk_missing');
  }
  if (packet.vix !== null) {
    const available = canonicalInstantMillis(packet.vix.available_at);
    if (available === null || available > decisionMillis || !Number.isFinite(packet.vix.value)
        || packet.vix.value < 0) fail('market_vix_invalid');
  }
  const breadthPairs = [
    [packet.market_breadth.positive_10d_pct, packet.market_breadth.eligible_count_10d],
    [packet.market_breadth.positive_21d_pct, packet.market_breadth.eligible_count_21d],
    [packet.market_breadth.above_sma50_pct, packet.market_breadth.eligible_count_sma50],
  ] as const;
  for (const [value, eligible] of breadthPairs) {
    if (!Number.isInteger(eligible) || eligible < 0
        || value !== null && (!Number.isFinite(value) || value < 0 || value > 100)
        || (eligible === 0) !== (value === null)) fail('market_breadth_invalid');
  }
}

function weightingInvalid(
  weighting: ContextPeerWeightingEvidence,
  eligiblePeerCount: number,
  decisionMillis: number,
): boolean {
  const cutoff = canonicalInstantMillis(weighting.market_cap_source_cutoff);
  const returns = [weighting.equal_weight_return_5d, weighting.equal_weight_return_10d,
    weighting.equal_weight_return_21d, weighting.cap_weight_return_5d, weighting.cap_weight_return_10d,
    weighting.cap_weight_return_21d];
  const count = weighting.capitalized_peer_count;
  const largest = weighting.largest_member_weight;
  const top3 = weighting.top3_weight;
  const effective = weighting.effective_member_count;
  return cutoff === null || cutoff > decisionMillis
    || !Number.isInteger(count) || count < 0 || count > eligiblePeerCount
    || returns.some((value) => value !== null && (!Number.isFinite(value) || value <= -1))
    || count === 0 && (returns.some((value) => value !== null) || largest !== null || top3 !== null
      || effective !== null || weighting.largest_member_ticker !== null)
    || (largest === null) !== (weighting.largest_member_ticker === null)
    || weighting.largest_member_ticker !== null && (weighting.largest_member_ticker.length === 0
      || weighting.largest_member_ticker.length > 32 || CONTROL.test(weighting.largest_member_ticker))
    || !unitIntervalOrNull(largest) || !unitIntervalOrNull(top3)
    || largest !== null && top3 !== null && top3 + 1e-9 < largest
    || effective !== null && (!Number.isFinite(effective) || effective < 1 - 1e-9 || effective > count + 1e-9);
}

/** The name of the first failing check on the packet's headline peers, or null. */
function headlinePeersProblem(
  spec: ContextRetrievalSpec,
  packet: ContextEvidencePacket,
  decisionMillis: number,
): string | null {
  const policy = SCREENER_CONTEXT_HEADLINE_PEER_POLICY;
  const rows = packet.headline_peers ?? [];
  const candidates = new Map(packet.candidates.map((candidate) => [candidate.candidate_id, candidate]));
  return firstFailing([
    ['population', () => rows.length !== packet.candidates.length
      || new Set(rows.map(({ candidate_id }) => candidate_id)).size !== rows.length
      || rows.some(({ candidate_id }) => !candidates.has(candidate_id))],
    ['policy', () => rows.some((row) => row.lookback_calendar_days !== policy.lookback_calendar_days
      || row.peers.length > policy.maximum_peers_per_candidate)],
    ['source_cutoff', () => rows.some((row) => {
      const cutoff = row.source_cutoff === null ? null : canonicalInstantMillis(row.source_cutoff);
      return row.source_cutoff !== null && cutoff === null || cutoff !== null && cutoff > decisionMillis
        || row.peers.length > 0 && cutoff === null;
    })],
    ['counts', () => rows.some((row) => !Number.isInteger(row.candidate_headline_count)
      || row.candidate_headline_count < 0
      || row.peers.some(({ co_mention_count: count }) => !Number.isInteger(count)
        || count < policy.minimum_co_mentions || count > row.candidate_headline_count))],
    ['identity', () => rows.some((row) => {
      const candidate = candidates.get(row.candidate_id)!;
      const ids = row.peers.map(({ vs_security_id }) => vs_security_id);
      return new Set(ids).size !== ids.length || ids.includes(candidate.vs_security_id)
        || row.peers.some((peer) => peer.series.vs_security_id !== peer.vs_security_id
          || peer.series.ticker !== peer.ticker || peer.ticker.length === 0 || peer.ticker.length > 32
          || CONTROL.test(peer.ticker) || typeof peer.same_industry !== 'boolean');
    })],
    ['topics', () => rows.some((row) => row.peers.some((peer) => peer.topics.length > policy.maximum_topics_per_peer
      || new Set(peer.topics.map(({ topic }) => canonicalTopic(topic))).size !== peer.topics.length
      || peer.topics.some(({ topic, co_mention_count: count }) => topic.length === 0 || topic.length > 80
        || CONTROL.test(topic) || canonicalTopic(topic) === '' || !Number.isInteger(count) || count < 1
        || count > peer.co_mention_count)))],
    ['series', () => {
      for (const row of rows) {
        for (const peer of row.peers) {
          try {
            validateSeries(peer.series, spec.as_of_session, 253, false);
          } catch {
            return true;
          }
        }
      }
      return false;
    }],
  ]);
}

function validateSeries(
  series: ContextSecuritySeries,
  asOfSession: string,
  maximum: number,
  requireCurrent: boolean,
): void {
  if (series.vs_security_id.length === 0 || series.ticker.length === 0 || series.bars.length > maximum) fail('series_invalid');
  let previous = '';
  for (const bar of series.bars) {
    if (!isCanonicalDate(bar.session) || bar.session > asOfSession || bar.session <= previous
        || !finitePositive(bar.open) || !finitePositive(bar.high) || !finitePositive(bar.low)
        || !finitePositive(bar.close) || bar.high < Math.max(bar.open, bar.close)
        || bar.low > Math.min(bar.open, bar.close)
        || (bar.volume !== null && (!Number.isFinite(bar.volume) || bar.volume < 0))) fail('bar_invalid');
    previous = bar.session;
  }
  if (requireCurrent && series.bars.at(-1)?.session !== asOfSession) fail('series_stale');
}

function eligibleBars(series: ContextSecuritySeries): ContextDailyBar[] {
  return [...series.bars].sort((left, right) => left.session.localeCompare(right.session)).slice(-253);
}

function returns(bars: readonly ContextDailyBar[]): number[] {
  return bars.slice(1).map((bar, index) => bar.close / bars[index]!.close - 1);
}

function periodReturn(bars: readonly ContextDailyBar[], sessions: number): number | null {
  if (bars.length <= sessions) return null;
  return bars.at(-1)!.close / bars[bars.length - sessions - 1]!.close - 1;
}

function alignedPeriodReturn(
  series: ContextSecuritySeries,
  referenceBars: readonly ContextDailyBar[],
  sessions: number,
): number | null {
  if (referenceBars.length <= sessions) return null;
  const startSession = referenceBars[referenceBars.length - sessions - 1]!.session;
  const endSession = referenceBars.at(-1)!.session;
  const closes = new Map(eligibleBars(series).map(({ session, close }) => [session, close]));
  const start = closes.get(startSession);
  const end = closes.get(endSession);
  return start === undefined || end === undefined ? null : end / start - 1;
}

function rollingReturns(bars: readonly ContextDailyBar[], sessions: number): number[] {
  return bars.slice(sessions).map((bar, index) => bar.close / bars[index]!.close - 1);
}

function rollingVolatility(values: readonly number[], sessions: number): number[] {
  return values.slice(sessions - 1).flatMap((_, index) => {
    const value = standardDeviation(values.slice(index, index + sessions));
    return value === null ? [] : [value];
  });
}

function maximumDrawdown(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  let peak = values[0]!;
  let result = 0;
  for (const value of values) {
    peak = Math.max(peak, value);
    result = Math.min(result, value / peak - 1);
  }
  return result;
}

function maximumRunup(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  let trough = values[0]!;
  let result = 0;
  for (const value of values) {
    trough = Math.min(trough, value);
    result = Math.max(result, value / trough - 1);
  }
  return result;
}

interface CalculatedGap {
  readonly observation: PriceGapObservation;
  readonly raw_gap: number;
  readonly raw_atr_multiple: number;
  readonly raw_same_day_return: number;
}

function gapObservations(bars: readonly ContextDailyBar[]): CalculatedGap[] {
  const trueRanges = bars.map((bar, index) => index === 0 ? bar.high - bar.low : Math.max(
    bar.high - bar.low,
    Math.abs(bar.high - bars[index - 1]!.close),
    Math.abs(bar.low - bars[index - 1]!.close),
  ));
  return bars.slice(1).map((bar, priorIndex) => {
    const barIndex = priorIndex + 1;
    const priorClose = bars[priorIndex]!.close;
    const gap = bar.open / priorClose - 1;
    const sameDayReturn = bar.close / bar.open - 1;
    const atr = mean(trueRanges.slice(Math.max(0, barIndex - 20), barIndex)) ?? 0;
    const atrMultiple = atr === 0 ? 0 : Math.abs(bar.open - priorClose) / atr;
    const direction = gap > 0 ? 'up' : 'down';
    const fills = (candidate: ContextDailyBar): boolean => direction === 'up'
      ? candidate.low <= priorClose
      : candidate.high >= priorClose;
    let fillIndex: number | null = null;
    for (let index = barIndex; index <= Math.min(barIndex + 5, bars.length - 1); index += 1) {
      if (fills(bars[index]!)) {
        fillIndex = index;
        break;
      }
    }
    const complete = barIndex + 5 < bars.length;
    const sessionsToFill = fillIndex === null ? null : fillIndex - barIndex;
    return {
      raw_gap: gap,
      raw_atr_multiple: atrMultiple,
      raw_same_day_return: sameDayReturn,
      observation: {
        observed_on: bar.session,
        direction,
        gap_pct: pct(gap)!,
        atr_multiple: round(atrMultiple, 2)!,
        same_day_return_pct: pct(sameDayReturn)!,
        fill_status: sessionsToFill === 0 ? 'filled_same_session'
          : sessionsToFill !== null ? 'filled_within_5_sessions'
            : complete ? 'open_after_5_sessions' : 'observation_incomplete',
        sessions_to_fill: sessionsToFill,
        five_session_follow_through_pct: complete ? pct(bars[barIndex + 5]!.close / priorClose - 1) : null,
      },
    };
  });
}

function emptyPrice(sessionCount: number, riskCodes: readonly string[]): PriceActionFeatures {
  return {
    data_quality: 'insufficient', session_count: sessionCount, return_5d_pct: null,
    return_10d_pct: null, return_21d_pct: null, return_60d_pct: null,
    maximum_drawdown_pct: null, maximum_runup_pct: null, trend_efficiency: null,
    recent_acceleration_pct: null, return_21d_percentile_1y: null,
    realized_volatility_percentile_1y: null, largest_gap_up_pct: null,
    largest_gap_down_pct: null, largest_gap_atr_multiple: null, gap_follow_through_pct: null,
    latest_close_in_month_range_pct: null, latest_range_vs_prior_10: null,
    latest_volume_vs_20d: null, material_gaps: [], patterns: [], risk_codes: riskCodes,
  };
}

function emptyPeers(
  resolution: ContextIndustryResolution,
  industryId: string | null,
  industryLabel: string | null,
  taxonomyLevel: 'sic4' | 'sic2' | null,
  risks: readonly string[],
): PeerComparisonFeatures {
  return {
    data_quality: 'insufficient',
    requested_industry_id: resolution.requested_industry_id,
    requested_industry_label: resolution.requested_industry_label,
    industry_id: industryId, industry_label: industryLabel,
    taxonomy_level: taxonomyLevel, eligible_peer_count: 0,
    observed_peer_count_5d: 0,
    observed_peer_count_10d: 0, observed_peer_count_21d: 0,
    representative_peer_count: 0, peer_median_return_5d_pct: null,
    peer_median_return_10d_pct: null,
    peer_median_return_21d_pct: null, peer_positive_breadth_10d_pct: null,
    peer_positive_breadth_5d_pct: null, peer_positive_breadth_21d_pct: null,
    peer_dispersion_5d_pct: null, peer_dispersion_10d_pct: null, peer_dispersion_21d_pct: null,
    candidate_excess_5d_pct: null, candidate_excess_10d_pct: null, candidate_excess_21d_pct: null,
    direction_agreement_5d_pct: null, direction_agreement_10d_pct: null,
    direction_agreement_21d_pct: null, move_scope: 'insufficient',
    representative_leaders: [], representative_laggards: [], risk_codes: risks,
  };
}

function keywordTopics(title: string): string[] {
  const text = title.toLowerCase();
  const rules: readonly [string, RegExp][] = [
    ['monetary_policy', /\bfed(?:eral reserve)?\b|interest rate|central bank/u],
    ['inflation', /inflation|\bcpi\b|consumer price|\bppi\b/u],
    ['growth_recession', /recession|economic growth|\bgdp\b|soft landing|hard landing/u],
    ['labor_market', /employment|jobs report|nonfarm payroll|unemployment|jobless claims/u],
    ['rates_credit', /treasury yield|bond yield|credit spread|credit market/u],
    ['equity_risk', /stock market|\bstocks\b|s&p 500|nasdaq|dow jones|risk[- ]off|volatility|\bvix\b/u],
    ['fiscal_policy', /fiscal|government shutdown|debt ceiling|budget deficit/u],
    ['currency', /us dollar|\bdollar\b|\bdxy\b|foreign exchange/u],
    ['consumer', /consumer spending|retail sales|consumer confidence/u],
    ['earnings', /earnings|revenue|profit|guidance|quarterly result/u],
    ['ai_capex', /artificial intelligence|\bai\b|data cent(?:er|re)|semiconductor/u],
    ['regulation', /regulat|antitrust|justice department|\bsec\b/u],
    ['geopolitics', /tariff|sanction|\bwar\b|geopolit|trade conflict/u],
    ['energy', /crude oil|natural gas|\bopec\b|oil price/u],
  ];
  return rules.filter(([, pattern]) => pattern.test(text)).map(([code]) => code);
}

function priceEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord {
  const price = candidate.price;
  return {
    evidence_id: `PRICE:${candidate.candidate_id}:SUMMARY`,
    lane: 'price',
    display: `${candidate.ticker}: 5d ${displayPct(price.return_5d_pct)}, 10d ${displayPct(price.return_10d_pct)}, 21d ${displayPct(price.return_21d_pct)}, 60d ${displayPct(price.return_60d_pct)}, 21d one-year percentile ${displayPct(price.return_21d_percentile_1y)}, max drawdown ${displayPct(price.maximum_drawdown_pct)}, max run-up ${displayPct(price.maximum_runup_pct)}, largest gaps ${displayPct(price.largest_gap_up_pct)}/${displayPct(price.largest_gap_down_pct)}, month-range close ${displayPct(price.latest_close_in_month_range_pct)}.`,
    value: price,
  };
}

function priceTapeEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord {
  const price = candidate.price;
  return {
    evidence_id: `PRICE:${candidate.candidate_id}:TAPE`,
    lane: 'price',
    display: `${candidate.ticker} tape: acceleration ${displayPct(price.recent_acceleration_pct)}; trend efficiency ${displayNumber(price.trend_efficiency)}; volatility percentile ${displayPct(price.realized_volatility_percentile_1y)}; latest range/prior 10 ${displayMultiple(price.latest_range_vs_prior_10)}; latest volume/20d ${displayMultiple(price.latest_volume_vs_20d)}.`,
    value: {
      recent_acceleration_pct: price.recent_acceleration_pct,
      trend_efficiency: price.trend_efficiency,
      realized_volatility_percentile_1y: price.realized_volatility_percentile_1y,
      latest_range_vs_prior_10: price.latest_range_vs_prior_10,
      latest_volume_vs_20d: price.latest_volume_vs_20d,
    },
  };
}

function gapEvidence(candidateId: string, gap: PriceGapObservation): ContextEvidenceRecord {
  return {
    evidence_id: `PRICE:${candidateId}:GAP:${gap.observed_on}`,
    lane: 'price',
    display: `${gap.observed_on} gap ${gap.direction} ${displayPct(gap.gap_pct)} (${gap.atr_multiple.toFixed(2)} ATR); same-session return ${displayPct(gap.same_day_return_pct)}; fill ${gap.fill_status}; sessions to fill ${gap.sessions_to_fill ?? 'unavailable'}; five-session follow-through ${displayPct(gap.five_session_follow_through_pct)}.`,
    value: gap,
  };
}

function patternEvidence(candidateId: string, pattern: PricePatternCandidate): ContextEvidenceRecord {
  return {
    evidence_id: `PRICE:${candidateId}:PATTERN:${pattern.code}:${pattern.observed_on}`,
    lane: 'price',
    display: `${pattern.code} (${pattern.direction}, ${pattern.strength}) on ${pattern.observed_on}: ${pattern.description} Invalidation: ${pattern.invalidation ?? 'not defined'}.`,
    value: pattern,
  };
}

function peerEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord {
  const peers = candidate.peers;
  const leaders = peers.representative_leaders.map(peerMoveDisplay).join(', ') || 'unavailable';
  const laggards = peers.representative_laggards.map(peerMoveDisplay).join(', ') || 'unavailable';
  return {
    evidence_id: `PEERS:${candidate.candidate_id}:SUMMARY`, lane: 'peers',
    display: `${peers.industry_label ?? 'Unknown industry'} (${peers.industry_id ?? 'unresolved'}, requested ${peers.requested_industry_id ?? 'none'}): full PIT universe ${peers.eligible_peer_count} peers; observed 5d/10d/21d ${peers.observed_peer_count_5d}/${peers.observed_peer_count_10d}/${peers.observed_peer_count_21d}; median 5d ${displayPct(peers.peer_median_return_5d_pct)}, 10d ${displayPct(peers.peer_median_return_10d_pct)}, 21d ${displayPct(peers.peer_median_return_21d_pct)}; positive breadth 5d/10d/21d ${displayPct(peers.peer_positive_breadth_5d_pct)}/${displayPct(peers.peer_positive_breadth_10d_pct)}/${displayPct(peers.peer_positive_breadth_21d_pct)}; direction agreement 5d/10d/21d ${displayPct(peers.direction_agreement_5d_pct)}/${displayPct(peers.direction_agreement_10d_pct)}/${displayPct(peers.direction_agreement_21d_pct)}; ${candidate.ticker} excess 5d/10d/21d ${displayPct(peers.candidate_excess_5d_pct)}/${displayPct(peers.candidate_excess_10d_pct)}/${displayPct(peers.candidate_excess_21d_pct)}; scope ${peers.move_scope}; bounded sample leaders ${leaders}; bounded sample laggards ${laggards}.`,
    value: peers,
  };
}

/**
 * A single peers-lane row that makes stock-linked versus industry-linked news
 * directly comparable without relaxing the cross-lane citation boundary.
 */
function peerHeadlineScopeEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord | null {
  if (candidate.stock_headlines.length === 0 && candidate.industry_headlines.length === 0) return null;
  const describe = (rows: readonly NarrativeCluster[]): string => rows.length === 0
    ? 'none in the supplied window'
    : rows.map((row) => {
      const titles = row.representative_headlines.map(({ title }) => `“${title}”`).join('; ');
      return `${row.label} (${row.article_count} articles, ${row.source_count ?? 'unknown'} sources, ${row.freshness_hours.toFixed(1)} hours old; ${titles || 'no representative title'})`;
    }).join(' | ');
  return {
    evidence_id: `PEERS:${candidate.candidate_id}:HEADLINE_SCOPE`,
    lane: 'peers',
    display: `Candidate-linked headline clusters: ${describe(candidate.stock_headlines)}. Industry-linked headline clusters: ${describe(candidate.industry_headlines)}. The two scopes are linkage context, not causal attribution.`,
    value: {
      candidate_linked: candidate.stock_headlines,
      industry_linked: candidate.industry_headlines,
    },
  };
}

function marketEvidence(market: MarketFeatures): ContextEvidenceRecord {
  const benchmarks = market.benchmark_returns.map(({ ticker, return_5d_pct, return_10d_pct, return_21d_pct }) =>
    `${ticker} 5d ${displayPct(return_5d_pct)}, 10d ${displayPct(return_10d_pct)}, 21d ${displayPct(return_21d_pct)}`)
    .join('; ');
  return {
    evidence_id: 'MARKET:SUMMARY', lane: 'market',
    display: `Market regime ${market.regime}; benchmarks ${benchmarks}; positive breadth 10d ${displayPct(market.breadth.positive_10d_pct)} across ${market.breadth.eligible_count_10d} eligible names, 21d ${displayPct(market.breadth.positive_21d_pct)} across ${market.breadth.eligible_count_21d} eligible names; above SMA50 ${displayPct(market.breadth.above_sma50_pct)} across ${market.breadth.eligible_count_sma50} eligible names; VIX ${market.vix?.value.toFixed(1) ?? 'unavailable'}.`,
    value: market,
  };
}

function relativeMarketEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord {
  return {
    evidence_id: `MARKET:${candidate.candidate_id}:RELATIVE`,
    lane: 'market',
    display: `${candidate.ticker} excess versus SPY: 5d ${displayPct(candidate.relative_to_spy_5d_pct)}, 10d ${displayPct(candidate.relative_to_spy_10d_pct)}, 21d ${displayPct(candidate.relative_to_spy_21d_pct)}; versus QQQ (Nasdaq-100 ETF proxy, not Nasdaq Composite): 5d ${displayPct(candidate.relative_to_qqq_5d_pct)}, 10d ${displayPct(candidate.relative_to_qqq_10d_pct)}, 21d ${displayPct(candidate.relative_to_qqq_21d_pct)}.`,
    value: {
      relative_to_spy_5d_pct: candidate.relative_to_spy_5d_pct,
      relative_to_spy_10d_pct: candidate.relative_to_spy_10d_pct,
      relative_to_spy_21d_pct: candidate.relative_to_spy_21d_pct,
      relative_to_qqq_5d_pct: candidate.relative_to_qqq_5d_pct,
      relative_to_qqq_10d_pct: candidate.relative_to_qqq_10d_pct,
      relative_to_qqq_21d_pct: candidate.relative_to_qqq_21d_pct,
    },
  };
}

function narrativeRolesEvidence(roles: MarketNarrativeRoles): ContextEvidenceRecord | null {
  if (roles.leading === null && roles.challenging === null) return null;
  const describe = (name: string, role: MarketNarrativeRole | null): string => role === null
    ? `${name}: none supplied`
    : `${name}: “${role.label}” (${role.sentiment}, ${role.alignment.replaceAll('_', ' ')}; ${role.article_count} articles, ${role.recent_article_share_pct.toFixed(1)}% in the last 72 hours, ${role.momentum}; SPY mean session return ${displayPct2(role.spy_mean_return_on_narrative_sessions_pct)} on its ${role.reaction_session_count} reaction sessions versus ${displayPct2(role.spy_mean_return_other_sessions_pct)} on the window's other sessions)`;
  return {
    evidence_id: 'MARKET:SHARED:NARRATIVE_ROLES',
    lane: 'market',
    display: `SPY direction 21 sessions ${roles.market_direction_21d}, 5 sessions ${roles.market_direction_5d}${roles.direction_shift ? ' (the short-term direction has turned)' : ''}. ${describe('Leading narrative', roles.leading)}. ${describe('Challenging narrative', roles.challenging)}. Reaction figures are coincident timing, not causation.`,
    value: roles,
  };
}

function coMovementEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord {
  const movement = candidate.market_co_movement;
  return {
    evidence_id: `MARKET:${candidate.candidate_id}:CO_MOVEMENT`,
    lane: 'market',
    display: `${candidate.ticker} against SPY over ${movement.return_session_count} aligned daily returns: correlation ${movement.correlation_60d?.toFixed(2) ?? 'unavailable'}, beta ${movement.beta_60d?.toFixed(2) ?? 'unavailable'} (${movement.state.replaceAll('_', ' ')}); 21-session direction versus SPY ${movement.direction_vs_market_21d}; ${NARRATIVE_LINK_TEXT[movement.narrative_link]}.`,
    value: movement,
  };
}

function peerWeightingEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord {
  const weighting = candidate.peer_weighting;
  const window = weighting.comparison_sessions ?? 21;
  return {
    evidence_id: `PEERS:${candidate.candidate_id}:WEIGHTING`,
    lane: 'peers',
    display: `${candidate.peers.industry_label ?? 'Industry'}, ${weighting.capitalized_peer_count} peers with a point-in-time market capitalisation: equal-weighted ${window}-session ${displayPct(window === 21 ? weighting.equal_weight_return_21d_pct : weighting.equal_weight_return_10d_pct)}, cap-weighted ${displayPct(window === 21 ? weighting.cap_weight_return_21d_pct : weighting.cap_weight_return_10d_pct)} (cap minus equal ${displayPct(weighting.cap_minus_equal_pct)}, ${weighting.weighting_split.replaceAll('_', ' ')}); largest member ${weighting.largest_member_ticker ?? 'unavailable'} at ${displayPct(weighting.largest_member_weight_pct)}, top three ${displayPct(weighting.top3_weight_pct)}, behaves like ${weighting.effective_member_count?.toFixed(1) ?? 'unavailable'} equal members (${weighting.concentration}); ${candidate.ticker} versus equal-weighted ${displayPct(weighting.candidate_excess_vs_equal_weight_pct)}, versus cap-weighted ${displayPct(weighting.candidate_excess_vs_cap_weight_pct)}; the group is read from the ${weighting.preferred_basis === 'equal_weight' ? 'equal-weighted return' : 'median'}.`,
    value: weighting,
  };
}

function headlinePeerEvidence(candidate: CandidateComputedContext): ContextEvidenceRecord {
  const headline = candidate.headline_peers;
  const peers = headline.peers.map((peer) =>
    `${peer.ticker} ${peer.co_mention_count}x${peer.same_industry ? '' : ' (other industry)'} 21d ${displayPct(peer.return_21d_pct)}`).join(', ');
  const themes = headline.themes.map((theme) =>
    `“${theme.label}”: ${theme.tickers.join('/')} (median 21d ${displayPct(theme.median_return_21d_pct)})`).join('; ');
  return {
    evidence_id: `PEERS:${candidate.candidate_id}:HEADLINE_PEERS`,
    lane: 'peers',
    display: `Named alongside ${candidate.ticker} in ${headline.candidate_headline_count} headlines over ${headline.lookback_calendar_days} days: ${peers}. ${headline.peer_count} headline peers, ${headline.outside_industry_count} outside its industry; median 5d ${displayPct(headline.median_return_5d_pct)}, 21d ${displayPct(headline.median_return_21d_pct)}, positive 10d breadth ${displayPct(headline.positive_breadth_10d_pct)}; ${candidate.ticker} excess 5d ${displayPct(headline.candidate_excess_5d_pct)}, 21d ${displayPct(headline.candidate_excess_21d_pct)} (${headline.relation.replaceAll('_', ' ')}). Themes: ${themes || 'none'}${headline.business_lines_split ? '; separate business lines have separate peers' : ''}. Co-mention is linkage, not causation.`.slice(0, 2_000),
    value: headline,
  };
}

function narrativeEvidence(narrative: NarrativeCluster, candidateId?: string): ContextEvidenceRecord {
  const prefix = narrative.scope === 'market' ? 'MARKET' : narrative.scope === 'industry' ? 'PEERS' : 'NEWS';
  const examples = narrative.representative_headlines
    .map(({ title }) => `“${title}”`)
    .join('; ');
  const sourceDiversity = narrative.source_count === null
    ? 'source diversity unavailable'
    : `${narrative.source_count} distinct source${narrative.source_count === 1 ? '' : 's'}`;
  return {
    evidence_id: `${prefix}:${candidateId ?? 'SHARED'}:NARRATIVE:${narrative.cluster_id}`,
    lane: narrative.scope === 'market' ? 'market' : narrative.scope === 'industry' ? 'peers' : 'news',
    display: `${narrative.scope} narrative “${narrative.label}”: ${narrative.article_count} linked headlines from ${sourceDiversity}, ${narrative.freshness_hours.toFixed(1)} hours fresh, sentiment ${narrative.sentiment}; representative headlines: ${examples || 'unavailable'}.`,
    value: narrative,
  };
}

const NARRATIVE_LINK_TEXT: Readonly<Record<MarketCoMovementFeatures['narrative_link'], string>> = {
  leading: 'its own headlines share the topic of the leading narrative',
  challenging: 'its own headlines share the topic of the challenging narrative',
  both: 'its own headlines share the topics of both narratives',
  neither: 'its own headlines share the topic of neither narrative',
  unavailable: 'no own headlines or market narratives to match',
};

/** Two decimals, for daily mean returns that one decimal would round to zero. */
function displayPct2(value: number | null): string {
  return value === null ? 'unavailable' : `${value.toFixed(2)}%`;
}

function displayPct(value: number | null): string {
  return value === null ? 'unavailable' : `${value.toFixed(1)}%`;
}

function displayNumber(value: number | null): string {
  return value === null ? 'unavailable' : value.toFixed(3);
}

function displayMultiple(value: number | null): string {
  return value === null ? 'unavailable' : `${value.toFixed(2)}x`;
}

function peerMoveDisplay(move: PeerMemberMove): string {
  return `${move.ticker} (5d ${displayPct(move.return_5d_pct)}, 10d ${displayPct(move.return_10d_pct)}, 21d ${displayPct(move.return_21d_pct)})`;
}

function assertUniqueEvidence(rows: readonly ContextEvidenceRecord[]): void {
  const ids = rows.map(({ evidence_id }) => evidence_id);
  if (new Set(ids).size !== ids.length) fail('evidence_id_duplicate');
}

function finitePositive(value: number): boolean {
  return Number.isFinite(value) && value > 0;
}

function unitIntervalOrNull(value: number | null): boolean {
  return value === null || Number.isFinite(value) && value >= 0 && value <= 1;
}

function nearlyEqualNullable(actual: number | null, expected: number | null): boolean {
  return actual === null || expected === null
    ? actual === expected
    : Math.abs(actual - expected) <= 1e-8;
}

function fail(code: string): never {
  throw new TypeError(`screener_context_${code}`);
}

/** The name of the first check that fails, running each only when every earlier one passed; null when all pass. */
function firstFailing(checks: readonly (readonly [string, () => boolean])[]): string | null {
  for (const [name, fails] of checks) if (fails()) return name;
  return null;
}

const DATE = /^\d{4}-\d{2}-\d{2}$/u;
const HASH = /^[a-f0-9]{64}$/u;
const CONTROL = /[\u0000-\u001f\u007f]/u;

function isCanonicalDate(value: string): boolean {
  if (!DATE.test(value)) return false;
  const millis = Date.parse(`${value}T00:00:00.000Z`);
  return Number.isFinite(millis) && new Date(millis).toISOString().slice(0, 10) === value;
}

function canonicalInstantMillis(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u.test(value)) return null;
  const millis = Date.parse(value);
  return Number.isFinite(millis) && new Date(millis).toISOString() === value ? millis : null;
}
