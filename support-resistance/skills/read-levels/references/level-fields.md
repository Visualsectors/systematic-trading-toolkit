# Level fields

Every metric is backward-looking: it describes past tests of a level, never the next one. Definitions follow the API 2.2.0 data dictionary (`/v1/docs.json`, checked 2 October 2026). Where it does not settle a detail, this file says so rather than guessing. A field in the schema is not proof that a value is populated. Every numeric field is nullable. Null means "not supplied", never zero and never a result. Percent fields use percentage points: `4.2` means 4.2%. Prices are in the instrument's quoted currency.

## Served level fields the toolkit reads

These come from the levels endpoint and appear on each `members` entry of a `plan` zone.

| Field | Unit | Dictionary meaning | How to say it |
| --- | --- | --- | --- |
| `level_date` | date | The source event session; not an availability timestamp. Only the newest `level_date` on or before `as_of` is used. | "from the 2026-01-15 session" |
| `side` | Support or Resistance | The served side. The dictionary gives no rule for how it is assigned, so do not explain one. The toolkit keeps it: a resistance now below price is not relabelled support. | "a served Resistance level, now below the close" |
| `level_type` | label | The level's construction family, such as `ma`, `gex`, `pivot` or `swing`. | Name it verbatim. |
| `approach` | label | The scoring/selection approach the row was scored under: `hold_rate` or `daily_strength` (from 16 October 2012), and `quality`, `magnetic` or `risk_reward` as well from 9 July 2026. The level and its price are the same under every approach; `score`, `p_hold_7d_pct` and the selection flag differ. It is not a different level or construction method. | Report it verbatim with that row's figures. Never present rows under different approaches as independent confirmation, and never silently keep the stronger figure. |
| `price` | price | The level price. | "support at $48.50" |
| `score` | unitless | A stored blended level score, specific to the row's approach. The dictionary gives no scale or calibration. | "a stored blended score of 0.81 under the `quality` approach". Never as a percentage or probability, and never compared across tickers or approaches. |
| `p_hold_7d_pct` | percentage points | A seven-day hold frequency from a backtest over levels recomputed in 2026, so it carries hindsight. Specific to the row's approach. | "held on 63% of past tests, measured with hindsight over levels recomputed in 2026". Compare only within one approach. |
| `exp_bounce_pct` | percentage points | A measured historical bounce magnitude. The dictionary does not say which statistic (average, median or other). Rows above 100 are rejected by the toolkit; see below. | "a measured bounce of 4.2% after past tests". Never "average" or "typical". |
| `hard_break_pct` | percentage points | A stored hard-break magnitude. Not a frequency of past breaks, not a current break signal, and not a price. The dictionary does not settle its sign or what close it is measured from, so do not add those. | "a stored hard-break magnitude of 1.6 percentage points" |
| `reward_risk` | ratio | A ratio derived from the measured bounce and hard-break magnitudes. The exact formula is not published. Not a trade plan; it describes no entry or exit. | "a stored ratio of 2.6 derived from the measured bounce and hard-break magnitudes". Do not lead with it. |
| `dist_atr` | ATR units | Distance from the reference price in average true range units. Whether live rows are signed, and which reference price they use, is not established; copy the value as served and do not infer a direction from its sign. It can differ from `measure`'s `distance_atr`, which uses the price you measure from. | Copy the value as served. |
| `confluence_count` | count | A stored count of contributing level signals. | "a stored confluence count of 3" |

## Served by the API, not in the toolkit yet

The API schema lists these fields, but the toolkit's live mapping does not read them. Say they are not in the toolkit yet; never derive them from other fields. Whether live rows populate them is not verified.

| Field | Unit | Dictionary meaning |
| --- | --- | --- |
| `expected_bounce_usd` | US dollars | The measured historical bounce magnitude expressed in US dollars. |
| `hard_break_price` | price | The stored hard-break threshold price; "not a current break-state claim". Never reconstruct it from `hard_break_pct`. |
| `num_tests_365d` | count | A stored count of level tests in the trailing 365-day measurement window. Without it, never write "of N tests". |

## What the live read selects

`only_best` is an API request filter, not a level field. The dictionary: it returns "only rows marked as the selected level: one per side for each approach", so up to two rows per approach for one session. The live provider sends `only_best=true` with a date ceiling of the current UTC date and a row limit, in one read without following a cursor; a `data_warnings` entry says when a cursor was returned. Live coverage is therefore the selected subset: one Support and one Resistance per approach, possibly the same level repeated across approaches. It is never every physical level or family. A `--data` file holds whatever its author included. No served field says whether a level is intact, broken or reclaimed.

## The toolkit's quality gate

The toolkit treats `exp_bounce_pct` above 100 as a data gap, whatever the source. It drops the whole row before `measure`, zone building, base rates and ATR estimation. It names the row in a warning: `Data gap: <TICKER> <side> <level_type> at <price> (date=…, approach=…) has exp_bounce_pct=… above 100; the row was excluded from scoring and zones.` The warning appears in `plan`'s `data_warnings` and in `measure`'s `coverage_notes`; a plan built from a `--data` file repeats it in `notes`.

- Exactly 100 is accepted.
- Null is not zero. A null may be the source's own gap or a value the API served as null; either way it is missing, and no warning is expected. Null is never proof that the source was corrected.
- Other approaches' rows at the same price are kept if they pass.
- The newest session is chosen before the gate runs. If every row in it fails, `plan` reports `insufficient_data` and no older session is used. The live provider then also warns "No current selected levels were returned; level evidence is unavailable." Rows were returned and then rejected; the `Data gap:` warning says which.

## Fields the toolkit computes

`vstoolkit measure` (schema `toolkit.named-price.v1`):

| Field | Meaning |
| --- | --- |
| `named_price`, `kind` | The price you measured from and its label: `entry`, `cost` or `strike`. The label is not a recommendation. |
| `latest_close`, `atr14`, `as_of` | The snapshot's price, ATR14 and decision time. |
| `nearest_above`, `nearest_below` | The closest kept level priced strictly above or below the named price, regardless of side. One row each. It carries no `approach`, so when the same price exists under several approaches, the row shown does not say which approach its rate belongs to. |
| `exactly_at` | Kept levels priced exactly at the named price. |
| `evidence_id` | `level:<ticker>:<date>:<side>:<type>:<price>`. It has no approach part, so rows that differ only by approach share one ID. Cite it; never build one yourself. |
| `served_price`, `date`, `side`, `type` | The served `price`, `level_date`, `side` and `level_type`. |
| `distance_dollars` | Level price minus named price. Signed: above positive, below negative. |
| `distance_pct` | `distance_dollars` divided by the named price, in percent. |
| `distance_atr` | `distance_dollars` divided by `atr14`; null without ATR. |
| `hold_rate_pct`, `hold_rate_text` | `p_hold_7d_pct` when it lies from 0 to 100, and its sentence "held on N% of past tests"; otherwise null and "not supplied". |
| `strike_distance_from_close_atr` | For `--kind strike` only: strike minus latest close, divided by `atr14`. |
| `coverage_notes`, `closing` | Limitations to state (including any `Data gap:` warning), and the exact closing sentence. |

`vstoolkit plan` zones (`entry_zone`, `reassessment_zone`):

The [plan output definitions](../../../../docs/PLAN_OUTPUT_FIELDS.md) document their count and presentation semantics.

| Field | Meaning |
| --- | --- |
| `low`, `high`, `mid` | Band edges and midpoint: each level price plus and minus 0.25 × ATR14, rounded to cents, merged with overlapping same-side bands. |
| `width_atr` | (`high` − `low`) divided by ATR14, rounded to two decimal places in JSON output only. Internal calculations retain their original precision. |
| `side`, `level_types` | The members' shared side and their sorted level types. |
| `member_count` | Distinct exact price levels, not approach rows. Two approaches or two families at the same exact price count once. Unrounded distinct prices remain distinct. All observations are retained in `members`; `len(members)` gives the source-observation count. Its own count, not served evidence and not a count of independent confirmations or construction methods. |
| `confluence_count_max`, `score_max` | The largest served `confluence_count` and `score` among the members. |
| `members` | The kept served rows in the zone, one per approach, each with its own `approach` (when supplied) and figures. |

`entry_historical_base_rates` and `reassessment_historical_base_rates` hold one row per physical level in the zone, keyed by exact `side`, `level_type` and `level_price`. Each row lists the sorted `approaches` it came from and carries `p_hold_7d_pct`, `exp_bounce_pct` and `hard_break_pct`, labelled `historical_base_rate`. That schema label does not make every field a rate: only `p_hold_7d_pct` is a frequency.

- Identical figures across approaches are kept once.
- A figure that differs across approaches is null, and `notes` says `Data gap: conflicting historical base rates for … remain null. Approach statistics were not averaged or ranked.`
- A level with none of the three figures has no row.

So there are three views of history: `members` (one source row per approach), base-rate rows (one per physical level, null where approaches disagree), and `measure` (one unattributed nearest row). Keep them apart. `status` is `ready` or `insufficient_data`; `notes` and `data_warnings` say why.

The two zones are conditional scenario geometry for one direction, not a full two-sided map. The toolkit drops an opposite-side zone that is not beyond the entry zone (for example when support and resistance both contain the price), and its `notes` say so. A null `reassessment_zone` therefore never means resistance is absent; the raw levels from `measure` still stand. Missing ATR can prevent zones while raw levels remain measurable.

`invalidation_price`, `risk_per_share`, `reward_to_reassessment_R`, `stop_distance_atr` and `stop_risk_size` are scenario-planning fields. This skill does not present them as level evidence.
