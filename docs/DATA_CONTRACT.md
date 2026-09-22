# Dataset contract

The toolkit accepts `visualsectors-toolkit.dataset.v1`, a strict point-in-time JSON document. Unknown fields are rejected to catch spelling mistakes and silent schema drift.

## Manifest

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Must equal `visualsectors-toolkit.dataset.v1` |
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

- Every field must have been available by `decision_time`.
- Restated fundamentals need an availability timestamp, not only a fiscal-period date.
- Corporate actions and price adjustment conventions must be documented by the provider.
- A backtest must select the dataset version available at each simulated decision time.
- News published after the cutoff cannot appear in the snapshot, even if it refers to an earlier event.

## Data rights

The manifest declares dataset terms but cannot grant rights the producer does not hold. Before sharing a dataset, confirm rights for raw values, derived values, caching, display, end-user analysis, model input, and redistribution. Apache-2.0 applies to toolkit code—not automatically to connected data.
