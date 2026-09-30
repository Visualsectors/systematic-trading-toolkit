export type ScreenerOrigin = 'preset' | 'custom';
export type ContextTier = 'A' | 'B' | 'C' | 'INSUFFICIENT_DATA';
export type ContextAssessment = 'tailwind' | 'neutral' | 'headwind' | 'mixed' | 'insufficient';
export type ContextConfidence = 'high' | 'medium' | 'low';
export type DataQuality = 'complete' | 'partial' | 'insufficient';

export interface ContextCandidateIdentity {
  readonly candidate_id: string;
  readonly vs_security_id: string;
  readonly ticker: string;
  readonly company_name: string | null;
  readonly industry_id: string | null;
  readonly industry_label: string | null;
}

export interface ContextRetrievalSpec {
  readonly schema_version: 'screener_context_retrieval_spec.v2';
  readonly retrieval_release: string;
  readonly decision_time: string;
  readonly as_of_session: string;
  readonly screen: {
    readonly kind: ScreenerOrigin;
    readonly screen_id: string;
    readonly screen_release: string;
    readonly definition_hash: string;
  };
  readonly candidates: readonly ContextCandidateIdentity[];
  readonly price_policy: {
    /** Raw PIT OHLCV, normalized only with action metadata visible at decision time. */
    readonly basis: 'raw_ohlcv_pit_split_normalized';
    readonly analysis_window_sessions: 23;
    readonly minimum_analysis_sessions: 20;
    readonly baseline_sessions: 252;
    readonly fields: readonly ['session', 'open', 'high', 'low', 'close', 'volume'];
  };
  readonly peer_policy: {
    readonly taxonomy: 'sic4_then_sic2';
    readonly universe: 'paper_common_stock_pit';
    readonly comparison_sessions: readonly [5, 10, 21];
    readonly minimum_eligible_members: 5;
    readonly maximum_members_per_industry: 30;
    readonly exclude_candidate: true;
  };
  readonly market_policy: {
    readonly benchmark_tickers: readonly ['SPY', 'QQQ', 'IWM', 'RSP'];
    readonly primary_benchmark: 'SPY';
    readonly breadth_universe: 'paper_common_stock_pit';
    readonly include_vix: true;
  };
  readonly news_policy: {
    readonly lookback_calendar_days: 14;
    readonly maximum_candidate_headlines: 8;
    readonly maximum_industry_headlines: 12;
    readonly maximum_market_headlines: 24;
    readonly minimum_ticker_relevance: 0.5;
    readonly require_cutoff: true;
  };
}

export interface ContextDailyBar {
  readonly session: string;
  readonly open: number;
  readonly high: number;
  readonly low: number;
  readonly close: number;
  readonly volume: number | null;
}

export interface ContextSecuritySeries {
  readonly vs_security_id: string;
  readonly ticker: string;
  readonly bars: readonly ContextDailyBar[];
}

export interface ContextIndustryResolution {
  readonly requested_industry_id: string | null;
  readonly requested_industry_label: string | null;
  readonly resolved_industry_id: string | null;
  readonly resolved_industry_label: string | null;
  readonly resolved_taxonomy_level: 'sic4' | 'sic2' | null;
  readonly status: 'resolved_from_point_in_time_sic' | 'unresolved';
}

export interface ContextCandidateEvidence extends ContextCandidateIdentity {
  readonly industry_resolution: ContextIndustryResolution;
  readonly series: ContextSecuritySeries;
}

export interface ContextPeerGroupEvidence {
  readonly industry_id: string;
  readonly industry_label: string;
  readonly taxonomy_level: 'sic4' | 'sic2';
  readonly membership_release: string;
  readonly effective_at: string;
  readonly eligible_member_count: number;
  /** Bounded deterministic examples; aggregate metrics never use this sample. */
  readonly members: readonly ContextSecuritySeries[];
}

export interface ContextPeerAggregateEvidence {
  readonly candidate_id: string;
  readonly industry_id: string;
  readonly taxonomy_level: 'sic4' | 'sic2';
  readonly eligible_peer_count: number;
  /** Optional connector-calculated facts; packet validation binds them back to the supplied PIT bars. */
  readonly candidate_return_5d?: number | null | undefined;
  readonly candidate_return_10d?: number | null | undefined;
  readonly candidate_return_21d?: number | null | undefined;
  readonly candidate_excess_return_5d?: number | null | undefined;
  readonly candidate_excess_return_10d?: number | null | undefined;
  readonly candidate_excess_return_21d?: number | null | undefined;
  /** Optional during the additive connector rollout; null metrics require a zero observed count. */
  readonly observed_peer_count_5d?: number | undefined;
  readonly observed_peer_count_10d: number;
  readonly observed_peer_count_21d: number;
  readonly peer_median_return_5d?: number | null | undefined;
  readonly peer_median_return_10d: number | null;
  readonly peer_median_return_21d: number | null;
  readonly peer_positive_breadth_5d?: number | null | undefined;
  readonly peer_positive_breadth_10d: number | null;
  readonly peer_positive_breadth_21d?: number | null | undefined;
  readonly peer_dispersion_5d?: number | null | undefined;
  readonly peer_dispersion_10d: number | null;
  readonly peer_dispersion_21d?: number | null | undefined;
  readonly direction_agreement_5d?: number | null | undefined;
  readonly direction_agreement_10d: number | null;
  readonly direction_agreement_21d?: number | null | undefined;
  readonly source_cutoff: string | null;
  /** Full-universe PIT membership lineage, distinct from representative member rows. */
  readonly membership_source_cutoff: string;
  readonly membership_release_fingerprint: string;
  /**
   * Optional during the additive connector rollout (features v2.4.0). The same full eligible population
   * weighted two ways, so a group dominated by one giant is not read from that giant's move alone.
   */
  readonly weighting?: ContextPeerWeightingEvidence | undefined;
}

/**
 * Equal- and capitalisation-weighted peer returns over the aggregate's own eligible population, with the
 * concentration that decides which one describes the group. Weights come from point-in-time market
 * capitalisation visible at the decision; the candidate is excluded as in every other aggregate.
 */
export interface ContextPeerWeightingEvidence {
  readonly market_cap_source_cutoff: string;
  /** Eligible peers with a point-in-time market capitalisation; never above the eligible count. */
  readonly capitalized_peer_count: number;
  readonly equal_weight_return_5d: number | null;
  readonly equal_weight_return_10d: number | null;
  readonly equal_weight_return_21d: number | null;
  readonly cap_weight_return_5d: number | null;
  readonly cap_weight_return_10d: number | null;
  readonly cap_weight_return_21d: number | null;
  readonly largest_member_ticker: string | null;
  /** Share of the capitalised peers' total market capitalisation, 0..1. */
  readonly largest_member_weight: number | null;
  readonly top3_weight: number | null;
  /** 1 / Herfindahl index of the weights: how many equal-sized members the group behaves like. */
  readonly effective_member_count: number | null;
}

/**
 * Headline peers: securities named in the same point-in-time headlines as the candidate. The connector
 * counts co-mentions; no model chooses them. Topics are the headlines' own warehouse topics, so a company
 * with several businesses gets one peer set per story theme rather than one blended industry.
 */
export interface ContextHeadlinePeerEvidence {
  readonly candidate_id: string;
  readonly lookback_calendar_days: number;
  readonly source_cutoff: string | null;
  /** Candidate-scope headlines in the lookback at or above the ticker-relevance floor. */
  readonly candidate_headline_count: number;
  readonly peers: readonly ContextHeadlinePeer[];
}

export interface ContextHeadlinePeer {
  readonly vs_security_id: string;
  readonly ticker: string;
  /** Candidate headlines that also link this security. */
  readonly co_mention_count: number;
  readonly topics: readonly { readonly topic: string; readonly co_mention_count: number }[];
  /** True when the security is a member of the candidate's resolved point-in-time industry. */
  readonly same_industry: boolean;
  readonly series: ContextSecuritySeries;
}

export interface ContextMarketBreadth {
  readonly positive_10d_pct: number | null;
  readonly positive_21d_pct: number | null;
  readonly above_sma50_pct: number | null;
  /** Denominators are kept per measurement because history requirements differ. */
  readonly eligible_count_10d: number;
  readonly eligible_count_21d: number;
  readonly eligible_count_sma50: number;
}

export interface ContextVixSnapshot {
  readonly value: number;
  readonly sma50: number | null;
  readonly sma200: number | null;
  readonly term_structure: 'contango' | 'backwardation' | 'flat' | 'unknown';
  readonly available_at: string;
}

export type ContextHeadlineScope = 'candidate' | 'industry' | 'market';

export interface ContextHeadlineEvidence {
  readonly headline_id: string;
  readonly scope: ContextHeadlineScope;
  readonly candidate_ids: readonly string[];
  readonly industry_ids: readonly string[];
  /** True warehouse linkages, when that source exposes them. Never inferred by the analyst. */
  readonly linked_tickers?: readonly string[] | undefined;
  readonly relevance_score?: number | null | undefined;
  readonly title: string;
  readonly teaser: string | null;
  readonly url: string;
  readonly topics: readonly string[];
  readonly sentiment_score: number | null;
  readonly created_at: string;
  /** The current warehouse exposes created_at, not a separately proven publish/ingest pair. */
  readonly availability_semantics: 'created_at_proxy';
}

export interface ContextSourceCutoffs {
  readonly prices: string | null;
  readonly peer_membership: string | null;
  readonly market: string | null;
  readonly headlines: string | null;
}

export interface ContextEvidencePacket {
  readonly schema_version: 'screener_context_evidence_packet.v2';
  readonly retrieval_release: string;
  readonly retrieval_spec_hash: string;
  readonly decision_time: string;
  readonly as_of_session: string;
  readonly source_cutoffs: ContextSourceCutoffs;
  /** Fingerprints of compiled SQL and bound parameters. */
  readonly source_query_hashes: Readonly<Record<string, string>>;
  /** Fingerprints of canonical returned rows, distinct from query identity. */
  readonly source_result_hashes: Readonly<Record<string, string>>;
  readonly candidates: readonly ContextCandidateEvidence[];
  readonly peer_groups: readonly ContextPeerGroupEvidence[];
  readonly peer_aggregates: readonly ContextPeerAggregateEvidence[];
  readonly market_series: readonly ContextSecuritySeries[];
  readonly market_breadth: ContextMarketBreadth;
  readonly vix: ContextVixSnapshot | null;
  readonly headlines: readonly ContextHeadlineEvidence[];
  /** Optional during the additive connector rollout (features v2.4.0); one row per candidate when present. */
  readonly headline_peers?: readonly ContextHeadlinePeerEvidence[] | undefined;
  readonly risk_codes: readonly string[];
}

export interface PricePatternCandidate {
  readonly code: string;
  readonly direction: 'bullish' | 'bearish' | 'neutral';
  readonly strength: 'strong' | 'moderate' | 'weak';
  readonly observed_on: string;
  readonly description: string;
  readonly invalidation: string | null;
}

export interface PriceGapObservation {
  readonly observed_on: string;
  readonly direction: 'up' | 'down';
  readonly gap_pct: number;
  readonly atr_multiple: number;
  readonly same_day_return_pct: number;
  readonly fill_status: 'filled_same_session' | 'filled_within_5_sessions' | 'open_after_5_sessions' | 'observation_incomplete';
  readonly sessions_to_fill: number | null;
  readonly five_session_follow_through_pct: number | null;
}

export interface PriceActionFeatures {
  readonly data_quality: DataQuality;
  readonly session_count: number;
  readonly return_5d_pct: number | null;
  readonly return_10d_pct: number | null;
  readonly return_21d_pct: number | null;
  readonly return_60d_pct: number | null;
  readonly maximum_drawdown_pct: number | null;
  readonly maximum_runup_pct: number | null;
  readonly trend_efficiency: number | null;
  readonly recent_acceleration_pct: number | null;
  readonly return_21d_percentile_1y: number | null;
  readonly realized_volatility_percentile_1y: number | null;
  readonly largest_gap_up_pct: number | null;
  readonly largest_gap_down_pct: number | null;
  readonly largest_gap_atr_multiple: number | null;
  readonly gap_follow_through_pct: number | null;
  readonly latest_close_in_month_range_pct: number | null;
  readonly latest_range_vs_prior_10: number | null;
  readonly latest_volume_vs_20d: number | null;
  readonly material_gaps: readonly PriceGapObservation[];
  readonly patterns: readonly PricePatternCandidate[];
  readonly risk_codes: readonly string[];
}

export interface PeerMemberMove {
  readonly ticker: string;
  readonly return_5d_pct: number | null;
  readonly return_10d_pct: number;
  readonly return_21d_pct: number | null;
}

export interface PeerComparisonFeatures {
  readonly data_quality: DataQuality;
  readonly requested_industry_id: string | null;
  readonly requested_industry_label: string | null;
  readonly industry_id: string | null;
  readonly industry_label: string | null;
  readonly taxonomy_level: 'sic4' | 'sic2' | null;
  readonly eligible_peer_count: number;
  readonly observed_peer_count_5d: number;
  readonly observed_peer_count_10d: number;
  readonly observed_peer_count_21d: number;
  readonly representative_peer_count: number;
  readonly peer_median_return_5d_pct: number | null;
  readonly peer_median_return_10d_pct: number | null;
  readonly peer_median_return_21d_pct: number | null;
  readonly peer_positive_breadth_5d_pct: number | null;
  readonly peer_positive_breadth_10d_pct: number | null;
  readonly peer_positive_breadth_21d_pct: number | null;
  readonly peer_dispersion_5d_pct: number | null;
  readonly peer_dispersion_10d_pct: number | null;
  readonly peer_dispersion_21d_pct: number | null;
  readonly candidate_excess_5d_pct: number | null;
  readonly candidate_excess_10d_pct: number | null;
  readonly candidate_excess_21d_pct: number | null;
  readonly direction_agreement_5d_pct: number | null;
  readonly direction_agreement_10d_pct: number | null;
  readonly direction_agreement_21d_pct: number | null;
  readonly move_scope: 'industry_wide' | 'candidate_specific' | 'mixed' | 'insufficient';
  readonly representative_leaders: readonly PeerMemberMove[];
  readonly representative_laggards: readonly PeerMemberMove[];
  readonly risk_codes: readonly string[];
}

export interface NarrativeCluster {
  readonly cluster_id: string;
  readonly label: string;
  readonly scope: ContextHeadlineScope;
  readonly article_count: number;
  readonly source_count: number | null;
  readonly freshness_hours: number;
  readonly sentiment: 'positive' | 'negative' | 'mixed' | 'neutral' | 'unknown';
  readonly headline_ids: readonly string[];
  readonly representative_headlines: readonly {
    readonly headline_id: string;
    readonly title: string;
    readonly url: string;
    readonly created_at: string;
  }[];
}

export interface MarketFeatures {
  readonly data_quality: DataQuality;
  readonly regime: 'risk_on_broad' | 'risk_on_narrow' | 'range' | 'risk_off' | 'volatile_rebound' | 'mixed' | 'insufficient';
  readonly primary_benchmark: 'SPY';
  readonly benchmark_return_5d_pct: number | null;
  readonly benchmark_return_10d_pct: number | null;
  readonly benchmark_return_21d_pct: number | null;
  readonly benchmark_returns: readonly {
    readonly ticker: 'SPY' | 'QQQ' | 'IWM' | 'RSP';
    readonly return_5d_pct: number | null;
    readonly return_10d_pct: number | null;
    readonly return_21d_pct: number | null;
  }[];
  readonly benchmark_dispersion_10d_pct: number | null;
  readonly breadth: ContextMarketBreadth;
  readonly vix: ContextVixSnapshot | null;
  readonly narratives: readonly NarrativeCluster[];
  /** The leading and the challenging market narrative, chosen by code from `narratives` and the SPY path. */
  readonly narrative_roles: MarketNarrativeRoles;
  readonly risk_codes: readonly string[];
}

export type MarketDirection = 'up' | 'down' | 'flat' | 'unavailable';

/**
 * One market narrative in its role. The reaction is measured, not asserted: SPY's mean session return on the
 * sessions whose close first followed one of the narrative's headlines, against its mean on the window's other
 * sessions. Coincident timing, never proof that the story moved the market.
 */
export interface MarketNarrativeRole {
  readonly cluster_id: string;
  readonly label: string;
  readonly sentiment: NarrativeCluster['sentiment'];
  /** Sentiment direction against SPY's 21-session direction. */
  readonly alignment: 'with_market' | 'against_market' | 'unaligned';
  readonly article_count: number;
  /** Share of the narrative's articles created in the 72 hours before the decision. */
  readonly recent_article_share_pct: number;
  readonly momentum: 'rising' | 'steady' | 'fading';
  readonly reaction_session_count: number;
  readonly spy_mean_return_on_narrative_sessions_pct: number | null;
  readonly spy_mean_return_other_sessions_pct: number | null;
  readonly reaction_gap_pct: number | null;
}

export interface MarketNarrativeRoles {
  readonly market_direction_21d: MarketDirection;
  readonly market_direction_5d: MarketDirection;
  /** The five-session direction has turned against the 21-session one: the layer where a challenger surfaces. */
  readonly direction_shift: boolean;
  readonly leading: MarketNarrativeRole | null;
  readonly challenging: MarketNarrativeRole | null;
}

export interface PeerWeightingFeatures {
  readonly status: 'measured' | 'not_supplied' | 'insufficient';
  readonly capitalized_peer_count: number | null;
  readonly equal_weight_return_5d_pct: number | null;
  readonly equal_weight_return_10d_pct: number | null;
  readonly equal_weight_return_21d_pct: number | null;
  readonly cap_weight_return_5d_pct: number | null;
  readonly cap_weight_return_10d_pct: number | null;
  readonly cap_weight_return_21d_pct: number | null;
  /** Capitalisation-weighted minus equal-weighted return over the longest measured window. */
  readonly cap_minus_equal_pct: number | null;
  readonly comparison_sessions: 21 | 10 | null;
  readonly candidate_excess_vs_equal_weight_pct: number | null;
  readonly candidate_excess_vs_cap_weight_pct: number | null;
  readonly largest_member_ticker: string | null;
  readonly largest_member_weight_pct: number | null;
  readonly top3_weight_pct: number | null;
  readonly effective_member_count: number | null;
  readonly concentration: 'dominated' | 'concentrated' | 'broad' | 'unavailable';
  readonly weighting_split: 'agree' | 'largest_members_lead' | 'largest_members_lag' | 'unavailable';
  /** Which group return describes the industry: the median unless a few giants carry the weight. */
  readonly preferred_basis: 'median' | 'equal_weight';
}

export interface HeadlinePeerMove {
  readonly ticker: string;
  readonly co_mention_count: number;
  readonly same_industry: boolean;
  readonly top_topic: string | null;
  readonly return_5d_pct: number | null;
  readonly return_10d_pct: number | null;
  readonly return_21d_pct: number | null;
}

export interface HeadlinePeerTheme {
  readonly topic: string;
  readonly label: string;
  readonly tickers: readonly string[];
  readonly co_mention_count: number;
  readonly median_return_21d_pct: number | null;
}

export interface HeadlinePeerFeatures {
  readonly status: 'measured' | 'not_supplied' | 'none_found' | 'insufficient';
  readonly lookback_calendar_days: number | null;
  readonly candidate_headline_count: number | null;
  /** Headline peers with an aligned ten-session return. */
  readonly peer_count: number;
  readonly outside_industry_count: number;
  readonly median_return_5d_pct: number | null;
  readonly median_return_10d_pct: number | null;
  readonly median_return_21d_pct: number | null;
  readonly positive_breadth_10d_pct: number | null;
  readonly candidate_excess_5d_pct: number | null;
  readonly candidate_excess_21d_pct: number | null;
  readonly relation: 'leads' | 'lags' | 'moves_with' | 'mixed' | 'unavailable';
  /** At most three story themes, each with its own peers; two or more disjoint themes mark separate business lines. */
  readonly themes: readonly HeadlinePeerTheme[];
  readonly business_lines_split: boolean;
  readonly peers: readonly HeadlinePeerMove[];
}

/** How the candidate moves with the market, and which market narrative its own headlines share. */
export interface MarketCoMovementFeatures {
  readonly return_session_count: number;
  readonly correlation_60d: number | null;
  readonly beta_60d: number | null;
  readonly state: 'tracks_market' | 'loosely_tracks' | 'independent' | 'unavailable';
  readonly direction_vs_market_21d: 'same' | 'opposite' | 'flat' | 'unavailable';
  readonly narrative_link: 'leading' | 'challenging' | 'both' | 'neither' | 'unavailable';
}

export interface CandidateComputedContext {
  readonly candidate_id: string;
  readonly ticker: string;
  readonly price: PriceActionFeatures;
  readonly peers: PeerComparisonFeatures;
  readonly stock_headlines: readonly NarrativeCluster[];
  readonly industry_headlines: readonly NarrativeCluster[];
  readonly relative_to_spy_5d_pct: number | null;
  readonly relative_to_spy_10d_pct: number | null;
  readonly relative_to_spy_21d_pct: number | null;
  /** QQQ is the Nasdaq-100 ETF proxy, not the Nasdaq Composite index. */
  readonly relative_to_qqq_5d_pct: number | null;
  readonly relative_to_qqq_10d_pct: number | null;
  readonly relative_to_qqq_21d_pct: number | null;
  readonly peer_weighting: PeerWeightingFeatures;
  readonly headline_peers: HeadlinePeerFeatures;
  readonly market_co_movement: MarketCoMovementFeatures;
}

export interface ComputedScreenerContext {
  readonly schema_version: 'computed_screener_context.v2';
  readonly feature_release: string;
  readonly screen: {
    readonly kind: ScreenerOrigin;
    readonly screen_id: string;
    readonly screen_release: string;
    readonly definition_hash: string;
  };
  readonly retrieval_spec_hash: string;
  readonly decision_time: string;
  readonly as_of_session: string;
  readonly candidates: readonly CandidateComputedContext[];
  readonly market: MarketFeatures;
  readonly evidence_index: readonly ContextEvidenceRecord[];
  readonly risk_codes: readonly string[];
}

export type ContextEvidenceLane = 'filter' | 'performance' | 'price' | 'peers' | 'market' | 'news';

export interface ContextEvidenceRecord {
  readonly evidence_id: string;
  readonly lane: ContextEvidenceLane;
  readonly display: string;
  readonly value: unknown;
}

export interface ScreenPerformancePrior {
  readonly horizon: '1w' | '1m' | '1q';
  readonly holding_period: 'calendar_week' | 'calendar_month' | 'calendar_quarter';
  readonly matured_count: number;
  readonly win_rate_pct: number | null;
  readonly date_balanced_mean_return_pct: number | null;
  readonly median_return_pct: number | null;
  readonly lower_quartile_return_pct: number | null;
  readonly mean_excess_return_pct: number | null;
  readonly confidence: 'insufficient' | 'thin' | 'adequate';
}

export interface ScreenPerformanceHistory {
  readonly schema_version: 'screener_performance_prior_response.v2';
  readonly methodology_release: 'screener-all-signals-performance-v1.2.0';
  readonly preset_id: 'trend_continuation' | 'oversold_at_support' | 'undervalued_momentum_shift';
  readonly preset_release: string;
  readonly serving_decision_time: string;
  readonly requested_window_session_count: 252;
  readonly entry_rule: 'first_regular_session_open_after_decision_time';
  readonly exit_rule: 'first_regular_session_close_on_or_after_calendar_target';
  readonly measured_window_session_count: number;
  readonly window_start_session: string | null;
  readonly window_end_session: string | null;
  readonly candidate_signal_count: number;
  readonly priors: readonly ScreenPerformancePrior[];
  readonly warning_codes: readonly string[];
  readonly source_hash: string;
}

export interface CandidateFilterEvidence {
  readonly candidate_id: string;
  readonly ticker: string;
  readonly matched_metrics: readonly {
    readonly id: string;
    readonly label: string;
    readonly display_value: string;
    readonly raw_value: number | string | boolean | null;
  }[];
  readonly gate_codes: readonly string[];
  readonly risk_codes: readonly string[];
}

export interface ScreenerContextAnalysisInput {
  readonly schema_version: 'screener_context_analysis_input.v2';
  readonly analysis_release: string;
  /** Exact retrieval identity; duplicated deliberately so stale context cannot be paired with a new screen. */
  readonly retrieval_spec_hash: string;
  readonly decision_time: string;
  readonly as_of_session: string;
  readonly screen: {
    readonly kind: ScreenerOrigin;
    readonly screen_id: string;
    readonly screen_release: string;
    readonly definition_hash: string;
    readonly name: string;
    readonly thesis: string;
    readonly side: 'long' | 'short';
    readonly filter_definition: Readonly<Record<string, unknown>>;
    readonly primary_holding_period: '1w' | '1m' | '1q' | null;
  };
  /** Null for custom screens until they have an independently released historical methodology. */
  readonly performance_12m: ScreenPerformanceHistory | null;
  readonly candidates: readonly CandidateFilterEvidence[];
  readonly context: ComputedScreenerContext;
}
