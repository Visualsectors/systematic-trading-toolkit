import { sha256 } from './sha256.js';
import type { ContextCandidateIdentity, ContextRetrievalSpec, ScreenerOrigin } from './types.js';

export const SCREENER_CONTEXT_RETRIEVAL_RELEASE = 'screener-context-retrieval-v2.2.0' as const;

export interface BuildContextRetrievalSpecInput {
  readonly decision_time: string;
  readonly as_of_session: string;
  readonly screen: {
    readonly kind: ScreenerOrigin;
    readonly screen_id: string;
    readonly screen_release: string;
    readonly definition_hash: string;
  };
  readonly candidates: readonly ContextCandidateIdentity[];
}

/**
 * Produces the only retrieval request an intelligence consumer may send. It is
 * intentionally semantic and closed: table names, SQL, column names, ordering,
 * and arbitrary limits are not part of the contract.
 */
export function buildScreenerContextRetrievalSpec(
  input: BuildContextRetrievalSpecInput,
): ContextRetrievalSpec {
  const spec: ContextRetrievalSpec = {
    schema_version: 'screener_context_retrieval_spec.v2',
    retrieval_release: SCREENER_CONTEXT_RETRIEVAL_RELEASE,
    decision_time: input.decision_time,
    as_of_session: input.as_of_session,
    screen: input.screen,
    candidates: input.candidates,
    price_policy: {
      basis: 'raw_ohlcv_pit_split_normalized',
      analysis_window_sessions: 23,
      minimum_analysis_sessions: 20,
      baseline_sessions: 252,
      fields: ['session', 'open', 'high', 'low', 'close', 'volume'],
    },
    peer_policy: {
      taxonomy: 'sic4_then_sic2',
      universe: 'paper_common_stock_pit',
      comparison_sessions: [5, 10, 21],
      minimum_eligible_members: 5,
      maximum_members_per_industry: 30,
      exclude_candidate: true,
    },
    market_policy: {
      benchmark_tickers: ['SPY', 'QQQ', 'IWM', 'RSP'],
      primary_benchmark: 'SPY',
      breadth_universe: 'paper_common_stock_pit',
      include_vix: true,
    },
    news_policy: {
      lookback_calendar_days: 14,
      maximum_candidate_headlines: 8,
      maximum_industry_headlines: 12,
      maximum_market_headlines: 24,
      minimum_ticker_relevance: 0.5,
      require_cutoff: true,
    },
  };
  validateScreenerContextRetrievalSpec(spec);
  return spec;
}

/** Stable identity used to bind a connector response to the exact closed request. */
export function hashScreenerContextRetrievalSpec(spec: ContextRetrievalSpec): string {
  validateScreenerContextRetrievalSpec(spec);
  return sha256(canonicalJson(spec));
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value as Readonly<Record<string, unknown>>)
      .filter(([, item]) => item !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => [key, canonicalize(item)]));
  }
  return value;
}

export function validateScreenerContextRetrievalSpec(spec: ContextRetrievalSpec): void {
  if (spec.schema_version !== 'screener_context_retrieval_spec.v2'
      || spec.retrieval_release !== SCREENER_CONTEXT_RETRIEVAL_RELEASE) fail('identity_invalid');
  const decisionMillis = canonicalInstantMillis(spec.decision_time);
  if (decisionMillis === null) fail('decision_time_invalid');
  if (!isCanonicalDate(spec.as_of_session)) fail('as_of_session_invalid');
  const sessionStart = Date.parse(`${spec.as_of_session}T00:00:00.000Z`);
  if (sessionStart > decisionMillis) fail('as_of_after_decision_time');
  if (spec.screen.screen_id.length === 0 || spec.screen.screen_release.length === 0
      || !HASH.test(spec.screen.definition_hash)) fail('screen_identity_invalid');
  if (spec.candidates.length === 0 || spec.candidates.length > 100) fail('candidate_cap_exceeded');
  const candidateIds = new Set<string>();
  const securityIds = new Set<string>();
  for (const candidate of spec.candidates) {
    if (candidate.candidate_id.length === 0 || candidate.vs_security_id.length === 0
        || candidate.ticker.length === 0 || candidateIds.has(candidate.candidate_id)
        || securityIds.has(candidate.vs_security_id)) fail('candidate_identity_invalid');
    candidateIds.add(candidate.candidate_id);
    securityIds.add(candidate.vs_security_id);
  }
  if (JSON.stringify(spec.price_policy) !== JSON.stringify(FIXED_PRICE_POLICY)
      || JSON.stringify(spec.peer_policy) !== JSON.stringify(FIXED_PEER_POLICY)
      || JSON.stringify(spec.market_policy) !== JSON.stringify(FIXED_MARKET_POLICY)
      || JSON.stringify(spec.news_policy) !== JSON.stringify(FIXED_NEWS_POLICY)) {
    fail('policy_not_allowlisted');
  }
}

const FIXED_PRICE_POLICY: ContextRetrievalSpec['price_policy'] = {
  basis: 'raw_ohlcv_pit_split_normalized', analysis_window_sessions: 23, minimum_analysis_sessions: 20,
  baseline_sessions: 252, fields: ['session', 'open', 'high', 'low', 'close', 'volume'],
};
const FIXED_PEER_POLICY: ContextRetrievalSpec['peer_policy'] = {
  taxonomy: 'sic4_then_sic2', universe: 'paper_common_stock_pit',
  comparison_sessions: [5, 10, 21], minimum_eligible_members: 5,
  maximum_members_per_industry: 30, exclude_candidate: true,
};
const FIXED_MARKET_POLICY: ContextRetrievalSpec['market_policy'] = {
  benchmark_tickers: ['SPY', 'QQQ', 'IWM', 'RSP'], primary_benchmark: 'SPY',
  breadth_universe: 'paper_common_stock_pit', include_vix: true,
};
const FIXED_NEWS_POLICY: ContextRetrievalSpec['news_policy'] = {
  lookback_calendar_days: 14, maximum_candidate_headlines: 8,
  maximum_industry_headlines: 12, maximum_market_headlines: 24,
  minimum_ticker_relevance: 0.5, require_cutoff: true,
};

function fail(code: string): never {
  throw new TypeError(`screener_context_retrieval_${code}`);
}

const DATE = /^\d{4}-\d{2}-\d{2}$/u;
const HASH = /^[a-f0-9]{64}$/u;

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
