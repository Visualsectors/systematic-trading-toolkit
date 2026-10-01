# Level fields

Every metric is backward-looking: it describes past tests of a level, never the next one. Every numeric field is nullable. Null means "not supplied", never zero and never a result. Percent fields use percentage points: `4.2` means 4.2%. Prices are in the instrument's quoted currency.

## Served level fields the toolkit reads

These come from the levels endpoint and appear on each `members` entry of a `plan` zone.

| Field | Unit | What it measures | How to say it |
| --- | --- | --- | --- |
| `level_date` | date | The trading session the level was computed for. Only the newest `level_date` on or before `as_of` is used. | "computed for the 2026-01-15 session" |
| `side` | Support or Resistance | Whether the level sat below the reference price (Support) or above it (Resistance) when computed. The toolkit keeps the served side; a resistance now below price is not relabelled support. | "a served Resistance level, now below the close" |
| `level_type` | label | Which construction method produced the level: the family it belongs to, such as `ma`, `gex`, `pivot` or `swing`. | Name it verbatim. |
| `approach` | label | The parameterisation of the construction method within its family. | Report it verbatim; the toolkit does not interpret it. |
| `price` | price | The level itself. | "support at $48.50" |
| `score` | unitless | A historical score computed upstream from the level's own measured record; higher means a stronger past record on the upstream scale. Not a percentage, not calibrated, not comparable across tickers. | "an upstream historical score of 0.81" |
| `p_hold_7d_pct` | percent | The share of past occasions on which a level of that kind held for seven days. It counts what already happened at comparable levels. | "held on 63% of past tests" |
| `exp_bounce_pct` | percent | The average move measured after those past tests. An average of past moves, not a figure this level will produce. | "the average move after past tests was 4.2%" |
| `hard_break_pct` | percentage points | How far the level sits from its stored hard-break threshold; a close beyond that price is a decisive break. A stored distance, not a count or a share of past tests; it says nothing about whether this level breaks. | "its hard-break threshold sits 18 percentage points from the level" |
| `reward_risk` | ratio | The ratio of the measured average past move to the measured distance to the decisive-break price, both from the same past tests. Not a trade plan; it describes no entry or exit. | "a measured ratio of 2.1 between the average past move and the distance to the decisive-break price". Do not lead with it. |
| `dist_atr` | ATR units | How far the level sits from the reference price on its own session, in average true range rather than dollars, so distances compare across tickers. It can differ from `measure`'s `distance_atr`, which uses the price you measure from. | Copy the value and sign as served. |
| `confluence_count` | count | How many separate level-construction methods put a level at approximately the same price. | "three construction methods put a level near this price" |

## Served by the API, not in the toolkit yet

The API schema lists these fields, but the toolkit's live mapping does not read them. Say they are not in the toolkit yet; never derive them from other fields.

| Field | Unit | What it measures |
| --- | --- | --- |
| `expected_bounce_usd` | price per share | The same average past move as `exp_bounce_pct`, in dollars per share. |
| `hard_break_price` | price | The level's stored hard-break threshold; a close beyond that price is a decisive break. |
| `num_tests_365d` | count | How many times price tested the level in the last 365 days. Without it, never write "of N tests". |

`only_best` is an API request filter, not a level field; the toolkit does not send it. No served field says whether a level is intact, broken or reclaimed.

## Fields the toolkit computes

`vstoolkit measure` (schema `toolkit.named-price.v1`):

| Field | Meaning |
| --- | --- |
| `named_price`, `kind` | The price you measured from and its label: `entry`, `cost` or `strike`. The label is not a recommendation. |
| `latest_close`, `atr14`, `as_of` | The snapshot's price, ATR14 and decision time. |
| `nearest_above`, `nearest_below` | The closest served level priced strictly above or below the named price, regardless of side. |
| `exactly_at` | Served levels priced exactly at the named price. |
| `evidence_id` | `level:<ticker>:<date>:<side>:<type>:<price>`. Cite it; never build one yourself. |
| `served_price`, `date`, `side`, `type` | The served `price`, `level_date`, `side` and `level_type`. |
| `distance_dollars` | Level price minus named price. Signed: above positive, below negative. |
| `distance_pct` | `distance_dollars` divided by the named price, in percent. |
| `distance_atr` | `distance_dollars` divided by `atr14`; null without ATR. |
| `hold_rate_pct`, `hold_rate_text` | `p_hold_7d_pct` when it lies from 0 to 100, and its sentence "held on N% of past tests"; otherwise null and "not supplied". |
| `strike_distance_from_close_atr` | For `--kind strike` only: strike minus latest close, divided by `atr14`. |
| `coverage_notes`, `closing` | Limitations to state, and the exact closing sentence. |

`vstoolkit plan` zones (`entry_zone`, `reassessment_zone`):

| Field | Meaning |
| --- | --- |
| `low`, `high`, `mid` | Band edges and midpoint: each level price plus and minus 0.25 × ATR14, rounded to cents, merged with overlapping same-side bands. |
| `width_atr` | (`high` − `low`) divided by ATR14. |
| `side`, `level_types` | The members' shared side and their sorted level types. |
| `member_count` | How many served levels the toolkit merged into this zone. Its own count, not served evidence. |
| `confluence_count_max`, `score_max` | The largest served `confluence_count` and `score` among the members. |
| `members` | The served level rows in the zone. |

`entry_historical_base_rates` and `reassessment_historical_base_rates` repeat each member's `p_hold_7d_pct`, `exp_bounce_pct` and `hard_break_pct` under the label `historical_base_rate`, for members with at least one of the three. `status` is `ready` or `insufficient_data`; `notes` and `data_warnings` say why.

`invalidation_price`, `risk_per_share`, `reward_to_reassessment_R`, `stop_distance_atr` and `stop_risk_size` are scenario-planning fields. This skill does not present them as level evidence.
