# Risk lenses, statuses and change detection

How the Visual Sectors in-product analyst reads risk, mapped onto what the toolkit emits today. Where the toolkit has no equivalent, the entry says **not in the toolkit yet**. Do not fill that gap by hand or from memory.

## Shared rules

- The review is assembled from served rows before any prose is written. A lens that cannot read its inputs degrades alone and says why; the rest of the review continues.
- A lens ends in one of four states: measured; **not measured** (rows arrived but the fields it needs are null, and "nobody counted" is the opposite of "counted none"); **locked** (the category is not on the caller's plan, stated with the provider's own notice); **unavailable** (the read failed or the category has not shipped, stated with its reason).
- Severity is an ordering rule, never a measurement, a score or a displayed number. Proximity ranks first. Anything unmeasured ranks last, never at a default.
- Each number keeps its source and `as_of`. A figure the review computes, such as a band edge or a distance to a band, is labeled computed, not served.
- Readings say where a measurement sits today. A position relative to a band is stated as a position ("sits below the band"), never as an event nothing recorded ("has broken").

## Statuses

| Status | Meaning | Reading it from the toolkit |
| --- | --- | --- |
| Triggered | Today's reading meets the risk's trigger. It says the condition is met, not what price does next. | The rule's flag is emitted. Exception: `level-invalidation` is emitted whenever a plan has a boundary; it is Triggered only when `monitor` emits `invalidation_breached`. |
| Near | Today's reading is inside the risk's near band: close to the trigger, not meeting it. | Not in the toolkit yet. No rule in the toolkit's risk.py has a near band. |
| Clear | Today's reading is outside both the trigger and the near band. It judges today's reading only. | `vstoolkit research` emits the rule's input with its `derived:` evidence ID, and the flag did not fire. |
| Unmeasured | The data behind the risk was not supplied, so nothing is judged. It is never counted as clear and never suggested for monitoring. | `research` lists the input as unavailable, or `plan` reports `status: insufficient_data`. |

`evidence-*` and `data-warning-*` flags are observations and gaps, not rules. Report them as emitted, without a status.

## The toolkit's rules

From the toolkit's risk.py. Flags sort by severity (high, medium, low), then id. The register's own warning applies: absence of a flag means absence of supplied evidence, not absence of risk.

| Flag | Kind | Severity | Emitted when | Input shown by `research` |
| --- | --- | --- | --- | --- |
| `level-invalidation` | headwind | high | the plan has an invalidation price; the trigger is a close below it (long) or above it (short) | `derived:<TICKER>:invalidation` |
| `earnings-window` | uncertainty | high at 0–7 days, medium at 8–21 days | days to earnings is 0–21 | `derived:<TICKER>:earnings-window` |
| `below-sma200` | headwind | medium | price is below SMA(200) | `derived:<TICKER>:sma200`, `derived:<TICKER>:price` |
| `elevated-volatility` | uncertainty | high at 45% or more, medium at 30% or more | 20-session volatility is 30% or more | `derived:<TICKER>:volatility20d` |
| `evidence-<id>` | tailwind for supporting, headwind for opposing evidence | low for a tailwind, medium for a headwind | supplied evidence is not neutral | the evidence ID itself |
| `data-warning-<hash>` | uncertainty | medium | the dataset carries a warning | none; cite the flag ID |

In live data, the toolkit's Visual Sectors provider sets a headline's stance from its ticker sentiment score: supporting at +0.15 or above, opposing at −0.15 or below, otherwise neutral, and neutral items raise no flag. Stance does not depend on scenario direction. The same provider computes 20-session volatility as the annualized standard deviation of the latest 20 daily close-to-close returns, in percentage points; file datasets define it upstream. The live mapping has no earnings calendar, so `earnings-window` is Unmeasured there.

## The seven lenses

### 1. Distance to invalidation

- **Measures:** how far the last price sits from the nearest level band below and above, in ATR. Price inside a band is named as inside, not as a zero distance.
- **Inputs:** last price, the latest-dated served levels, and ATR. A served ATR is preferred; one derived from the served `dist_atr` is a fallback and is labeled derived.
- **Trigger and near band:** in-product, being inside a band, or within a short ATR distance of one, draws attention; further away reads as comfortable. Toolkit: not in the toolkit yet.
- **Severity:** proximity dominates. Break history only orders bands at a similar distance; no amount of history lifts a far band above a near one.
- **Unmeasured when:** there is no price, no level dated on or before the decision time, or no usable ATR.
- **Toolkit:** `plan` emits the entry band and `invalidation_price`, set 0.25 ATR beyond the entry band's far edge (the toolkit's levels.py). Its `risk_per_share` and `stop_distance_atr` run from the entry band's near edge to the invalidation, in dollars and ATR; neither is the distance from today's price. Each band member carries its served `dist_atr`. `measure` emits signed ATR distances from a user-named price to the nearest served levels. `risk` emits `level-invalidation`; `monitor` emits `invalidation_breached` against the saved plan.

### 2. Level quality

- **Measures:** how much measured history stands behind the nearest band: its strongest member's served `score`, `confluence_count`, seven-day hold share (`p_hold_7d_pct`) and `reward_risk`.
- **Inputs:** the same bands as lens 1.
- **Trigger and near band:** in-product, a band with a weak measured hold record draws attention. Toolkit: not in the toolkit yet; no flag reads level history.
- **Severity:** none of its own; it qualifies lens 1.
- **Unmeasured when:** there are no levels, or the nearest band carries no served history. Null means nobody counted, not that the level never held.
- **Toolkit:** `plan` emits `entry_historical_base_rates`, `reassessment_historical_base_rates`, `score_max` and `confluence_count_max`; `measure` emits `hold_rate_text`. Say rates as "held on N% of past tests". `score` is an upstream, unitless historical score: never turn it into a percentage. Quote `exp_bounce_pct` and `hard_break_pct` under their field names; neither is a statement about this level's next test. The number of past tests behind a rate is not served; never state or imply one.

### 3. Event proximity

- **Measures:** the next scheduled company report inside the horizon, as a date. Dates and names only, never what the event means for price. Past events are dropped.
- **Inputs:** an earnings calendar.
- **Trigger and near band:** a report within the week draws attention in-product. Toolkit: `earnings-window`, high at 0–7 days and medium at 8–21 days.
- **Severity:** nearer events rank higher.
- **Unmeasured when:** no calendar was supplied. The live API mapping has none: `days_to_earnings` stays null and event risk is Unmeasured, never clear.
- **Toolkit:** the `earnings-window` flag; `research` shows the input or "Days to the next earnings event is unavailable."

### 4. Volatility context

- **Measures:** in-product, the latest ATR against the median of the same ticker's own trailing sessions, never against another ticker or the market.
- **Inputs:** a trailing ATR series. With too few sessions, the lens reports the single served ATR and says it cannot call it typical or unusual.
- **Trigger and near band:** a reading much wider than the ticker's usual range draws attention.
- **Severity:** wider than usual ranks higher.
- **Unmeasured when:** there are too few sessions and no served ATR.
- **Toolkit:** the own-history comparison is not in the toolkit yet. `elevated-volatility` reads an absolute level of 20-session volatility, not a comparison with the stock's usual range; say which one you are reporting.

### 5. Concentration (whole list)

- **Measures:** the share of a list in its largest sector and its largest industry.
- **Inputs:** each name's sector and industry, and optional quantities. Quantity weighting applies only when every name has a quantity and a price; otherwise each name counts equally, and the review says which.
- **Trigger and near band:** a list mostly in one sector ranks first.
- **Severity:** larger shares rank higher.
- **Unmeasured when:** fewer than two names carry sector data.
- **Toolkit:** not in the toolkit yet; snapshots carry no sector field. Shares are of the list, never a currency total: a currency total is a statement about the person. The `portfolio_share` from `size-portfolio` is sizing arithmetic, not concentration.

### 6. Macro calendar (whole list)

- **Measures:** scheduled market-wide releases inside the horizon, stated once for the list as names and dates.
- **Unmeasured when:** no release calendar was supplied.
- **Toolkit:** not in the toolkit yet.

### 7. Options-derived risk (whole list)

- **Measures:** options-derived positioning readings, which may be locked on a given plan.
- **Unmeasured when:** the category is locked (state it as locked, with the provider's notice) or the read failed (state it as unavailable, with the reason). A failed read is never presented as locked.
- **Toolkit:** not in the toolkit yet.

## Contrary reading

In-product, the review always names the single strongest measured reading cutting against a calm view, ordered by severity, then lens, then ticker. Only measured readings qualify: a gap is not contrary evidence. When nothing qualifies, it says so, and says this describes what was measured, not a conclusion that risk is low. The toolkit selection is step 4 of the skill. The `research` brief's "Contrary evidence" block lists opposing evidence; its "No contrary evidence was supplied" entry is a coverage gap.

## Sixteen-risk watch list

In-product, each stock also gets sixteen named risks in four families. Each has a one-line risk, the metric watched, a trigger, a near band and an update cadence, and each is framed for a holder of the stock; in a short scenario, several reverse direction. A risk whose data was not supplied is Unmeasured, and an Unmeasured or stale risk is never suggested for monitoring. The toolkit's `monitor` tracks every emitted flag instead and has no suggestion step.

| Risk id | Family | The risk | Toolkit |
| --- | --- | --- | --- |
| `fund.fcf` | fundamental | Cash generation weakens: free cash flow turns negative or falls sharply against a year earlier. A filer with no cash-flow statement, such as a bank, is read on net profit instead. | Not in the toolkit yet |
| `fund.margin` | fundamental | Profitability slips: the operating margin falls against a year earlier. A bank is read on price to book. | Not in the toolkit yet |
| `fund.leverage` | fundamental | The balance sheet tightens: debt climbs against earnings or interest cover thins. A bank is read on debt to equity. | Not in the toolkit yet |
| `fund.insider` | fundamental | Insiders sell into strength. | Not in the toolkit yet |
| `news.tone` | headline | Headline tone turns negative on the stock, on its own or against its longer-window average. | Partial: each headline past the provider's sentiment cut raises its own `evidence-<id>` flag; no window average |
| `news.attention` | headline | Attention spikes: a burst of coverage against the usual weekly count. | Not in the toolkit yet |
| `news.negative` | headline | A highly relevant, strongly negative headline lands in the last few days. | Partial: opposing headlines raise `evidence-<id>` headwinds; no relevance filter or window |
| `news.divergence` | headline | Tone and price disagree: good news is being sold, or bad news bought. | Not in the toolkit yet |
| `tech.close_below_support` | technical | A daily close below the nearest support band breaks the base the price is holding. | Closest: `monitor` `invalidation_breached` for a long scenario, against the saved invalidation, which sits beyond the band rather than at its edge |
| `tech.near_support` | technical | The price reaches support, where the next test decides the base. | Closest: `monitor` `entered_entry_zone` for a long scenario; arrival inside the band, with no ATR near band |
| `tech.stall_resistance` | technical | The rally stalls at resistance: tested, then turned back. | Partial: `monitor` `reached_reassessment_zone` for a long scenario reports arrival only |
| `tech.trend` | technical | The trend breaks: the price closes below its 50-day average. | Not in the toolkit yet; `below-sma200` uses the 200-session average, and `research` reports SMA(50) as a fact only |
| `opt.flip`, `opt.adjusted`, `opt.top_record`, `opt.agreement` | options | The net options reading turns bearish; the record-adjusted net reading turns bearish; the indicator with the best past record on the stock points down; fewer option groups agree with the net reading. | Not in the toolkit yet |

## Change detection

In-product, a re-review compares two evidence packs field by field, never by rereading prose. It reports names added or removed, a lens appearing or lost, a status change (a locked reading becoming available leads), a measured value moving beyond rounding noise, a value that is no longer measured, and the contrary reading moving. It always opens with a lead line: nothing measured has changed since the earlier date, or how many changes there are since then. A value that stopped being measured is always reported: the evidence thinned; it did not improve.

The toolkit's `monitor` reports `new_flag`, `severity_increased`, `severity_decreased`, `flag_changed`, `resolved`, `evaluation_failed`, `evaluation_recovered`, `invalidation_breached`, `entered_entry_zone` and `reached_reassessment_zone`, and deduplicates unchanged states and identical failures. A failed evaluation keeps the prior active risks and saved plan. `flag_changed` fires on any change in a flag's statement, including a small numeric move; it has no noise floor. Before calling a `resolved` flag an improvement, check with `research` that its input is still supplied: a flag that resolved because its input went missing is a new gap. Lead with what changed since the state file's `evaluated_at`.

## Freshness

In-product, every number keeps a freshness stamp per source and per ticker, and a missing `as_of` is reported as unknown, never invented. In the toolkit, the register's `as_of` is the decision time (for live reads, the earliest `as_of` across the sources read), levels carry `level_date`, and `research` lists each evidence item's `as_of` and source. Live reads are not point-in-time: later revisions can be visible in date-bounded reads.
