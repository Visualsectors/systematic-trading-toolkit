# Dataset contract

The toolkit accepts `visualsectors-toolkit.dataset.v1` and additive `visualsectors-toolkit.dataset.v2`, strict decision-time-bounded JSON documents. V1 remains unchanged. Unknown fields are rejected to catch spelling mistakes and silent schema drift.

## Manifest

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | `visualsectors-toolkit.dataset.v1` or `.v2` |
| `dataset_id` | non-empty string | Stable identifier for audit and replay |
| `generated_at` | timezone-aware ISO-8601 datetime | When this document was produced |
| `synthetic` | boolean | Whether every observation is fictional |
| `license` | non-empty string | Data-use or redistribution terms |
| `source` | non-empty string | Provider or fixture provenance |
| `decision_time` | timezone-aware ISO-8601 datetime | Information cutoff for the decision |
| `snapshots` | array | One unique row per ticker |

`generated_at` and `decision_time` are separate so delayed or replayed datasets remain auditable.

## Snapshot fields

All prices are in the instrument's quoted currency. Percentage fields use percentage points: `12.5` means 12.5%, not 0.125.

| Field | Required | Unit / rule |
| --- | --- | --- |
| `ticker` | yes | 1–12 uppercase-normalized letters, numbers, `.`, or `-` |
| `as_of` | yes | timezone-aware ISO-8601 observation time |
| `price` | yes | finite and greater than zero |
| `atr14` | yes, nullable | price units; positive when present |
| `average_dollar_volume_20d` | yes, nullable | quoted currency per session |
| `rsi14` | yes, nullable | indicator points |
| `sma20`, `sma50`, `sma200` | yes, nullable | price units |
| `momentum_20d_pct` | yes, nullable | percentage points |
| `volatility_20d_pct` | yes, nullable | provider-defined percentage points; document annualization upstream |
| `pe_ratio` | no, nullable | ratio |
| `earnings_growth_pct` | no, nullable | percentage points |
| `days_to_earnings` | no, nullable | integer calendar days; may be negative after an event |
| `levels` | no | dated support/resistance observations |
| `evidence` | no | source-attributed qualitative evidence |
| `warnings` | no | non-empty data-quality or coverage notices |

Missing values must be `null`; do not substitute zero, a universe mean, or a “neutral” score.

## Level fields

Required fields are `level_date` (`YYYY-MM-DD`), `side` (`Support` or `Resistance`), `level_type`, and positive `price`. Optional historical observations include `score`, `p_hold_7d_pct`, `exp_bounce_pct`, `hard_break_pct`, `reward_risk`, `dist_atr`, `confluence_count`, and `approach`.

The toolkit preserves the served side. A resistance below current price is not silently relabeled as support. `score` and historical rates are not assumed to be calibrated probabilities or comparable across instruments.

## Evidence fields

Evidence requires a stable `id`, `category`, `statement`, timezone-aware `as_of`, `source`, and `stance` (`support`, `opposition`, or `neutral`). `url` is optional.

Evidence statements should be concise factual observations. A source must describe where the fact came from; it must not be a model's unsupported assertion.

## Timing and leakage rules

- No observation timestamp may be later than `decision_time`.
- A provider must separately declare whether its historical values are truly point-in-time. The Stage 1 Visual Sectors API is non-PIT because later revisions can be visible in date-bounded reads.
- Restated fundamentals need an availability timestamp, not only a fiscal-period date.
- Corporate actions and price adjustment conventions must be documented by the provider.
- A backtest must select the dataset version available at each simulated decision time.
- News published after the cutoff cannot appear in the snapshot, even if it refers to an earlier event.

## Data rights

The manifest declares dataset terms but cannot grant rights the producer does not hold. Before sharing a dataset, confirm rights for raw values, derived values, caching, display, end-user analysis, model input, and redistribution. MIT applies to toolkit code and CC BY 4.0 to toolkit documentation—not automatically to connected data.

## V2 optional context fields

V2 has the same required manifest and snapshot fields. All six context extensions are optional; v1 rejects them. To compute context, `context_provenance` and a frozen retrieval spec are required. Do not relabel a snapshot as complete context. See the executable, fictional `src/visualsectors_toolkit/fixtures/context_demo.json` for a full-lane example, and `context_validation.py` for the closed nested contracts.

| Extension | Closed shape / rule |
| --- | --- |
| `bars[ticker]` | `{vs_security_id, ticker, bars}`; bars have exactly `session, open, high, low, close, volume`. Up to 253 ordered, unique completed NY-close sessions, split-normalized; valid positive OHLC, nonnegative or null volume. |
| `market` | Optional `series` (SPY/QQQ/IWM/RSP with the same series shape), `breadth`, `vix`. Breadth has positive-return percentages for 10/21 sessions and above-SMA50 percentage, each paired with its eligible count; count zero requires null. |
| `peers[ticker]` | Required `resolution`, optional `group`, `aggregate`, `capitalization`. Resolution carries requested/resolved industry id, label, taxonomy and status. Group carries effective membership release/time, full eligible count and up to 30 representative series. |
| `capitalization` | Inside a peer row: `{security_id: {market_cap, available_at}}`; positive values, IDs in supplied membership, canonical availability <= decision. Never current caps substituted into a historical replay. |
| `aggregate` | Released candidate/industry/taxonomy, eligible/observed counts, 5/10/21 median returns, breadth, dispersion, direction agreement and source/membership cutoffs/fingerprint; optional weighting. Upstream aggregates may cover more members than the representative paths. Returns here are fractions; computed `_pct` fields are percentage points. |
| `headlines[]` | Exactly `headline_id, scope, candidate_ids, industry_ids, title, teaser, url, topics, sentiment_score, created_at, availability_semantics`; optional `relevance_score`, `linked_tickers: [{ticker, relevance_score}]`. Candidate/industry/market scopes, 14-day window, canonical cutoff, bounded strings and relevance [0,1]. Candidate relevance, when supplied, must be >= 0.5. |
| `headline_peers[ticker]` | Released candidate row with 90-day lookback, source cutoff, candidate headline count and up to 8 peers. Each peer has identity, series, same-industry flag, >=2 co-mentions and <=4 topics with counts. |
| `context_provenance` | Exactly `retrieval_spec, source_cutoffs, source_query_hashes, source_result_hashes, risk_codes`. Canonical millisecond UTC timestamps and SHA-256 hashes; fixed policies, frozen candidate identities/order and shared decision/session. |

When no upstream aggregate is supplied, a peer group must include **all** declared eligible members (excluding the candidate); representative-only data is rejected for aggregate computation. The client computes aligned median, positive breadth, median absolute deviation and direction agreement. Optional supplied PIT caps produce equal/cap returns on the same capitalized eligible subset, largest/top-three shares and 1/HHI. Upstream aggregate metrics remain authoritative when supplied; do not mix definitions silently. Missing cap coverage is disclosed, never inflated into full-universe weights.

Headline-peer membership is provider-supplied: enforce 90 days, ticker relevance >= 0.5, >=2 shared headlines, <=8 peers and <=4 topics upstream. Exclude holdings-filing stories carrying a `$TICKER` cashtag before forming co-mentions. The toolkit validates the resulting bounded packet; aggregate counts alone cannot prove the provider performed that raw-story exclusion or relevance selection. Keep upstream policy/lineage evidence in the private QA record. Never infer peers by company name or unlinked headlines.

Every data availability/effective/source timestamp must be <= decision time. `generated_at` may be later because it describes document production, not information availability. A session's closing bar is unavailable before 16:00 America/New_York (DST handled). For live Stage 1 data the packet explicitly declares non-PIT/proxy limitations; date checks do not make revisions historically knowable.
