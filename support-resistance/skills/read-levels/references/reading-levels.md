# Reading levels

## Which levels

Only levels from the newest `level_date` on or before the snapshot's `as_of` are read; older sessions are a different map. The live read is one bounded request for the rows marked as selected (`only_best=true`) up to the current date, with a row limit and no cursor-following. The API selects one Support and one Resistance per scoring approach, so the read is a selected subset, often the same level repeated across approaches, never every level or family. A `--data` file holds what its author included. Both commands return the nearest levels only, never the full list; a complete level map is not in the toolkit yet.

Rows with `exp_bounce_pct` above 100 are dropped by the toolkit before anything is measured, and a `Data gap:` warning names each one. Report the warning and leave the row out; never quote its figures. If the whole newest session was dropped, there is no level evidence for it, and older sessions are not a substitute.

## Nearest levels and zones

`measure` picks the closest kept level strictly above and strictly below a price by price alone, whatever its side. A Resistance level below the close is reported as `nearest_below` with side Resistance; keep that label and do not call it support.

`plan` groups levels into zones for one scenario direction; it is conditional geometry, not the level map. When support and resistance both contain the price, or the opposite-side zone is not beyond the entry zone, `plan` leaves `reassessment_zone` null and says why in `notes`. That is not a missing resistance: report the raw resistance `measure` emitted, keep its served side, and never invent the zone's edges.

Each level becomes a band 0.25 ATR14 either side of its price. Overlapping or touching bands of the same served side merge while the merged band stays within 1.0 ATR14. Side is decided by membership, not proximity: the nearest support zone must hold a Support level and lie below the close (or contain it); a resistance zone must hold a Resistance level and lie above it (or contain it). A zone is geometry around served prices, not evidence that a level holds. Where price sits relative to a zone is position, not a break.

When several rows share a zone, say they fall in one band. The same level and price can appear once per scoring approach, each with its own `score` and `p_hold_7d_pct`: that is one level scored several ways, not several confirmations. The base-rate rows already group them by physical level and list their `approaches`. Where the approaches disagree, the toolkit leaves the figure null with a note. Say they disagree, give each member's figure under its own approach name if useful, and never average them or quietly keep the stronger one. `confluence_count_max` is the largest served confluence among the members; `member_count` counts distinct exact price levels, not approach rows. Two approaches or two families at the same exact price count once; `len(members)` gives the source-observation count. Reporting the second under the first's name conflates a computed count with served evidence.

## Comparing levels

Compare only the levels the commands emitted, and only within one approach: the dictionary says scores and hold rates differ by approach. Order by one served field you name: `p_hold_7d_pct` when the user cares how often a level held, `exp_bounce_pct` when they care how large the measured bounce after past tests was. Levels with a null value go after every measured one. Never blend fields into your own composite. A balanced ranking over both fields, and tie-breaking by number of past tests, are not in the toolkit yet. Ordering by a measured field is not a ranking of trade ideas.

## Historical record

- `p_hold_7d_pct`: "held on N% of past tests", a seven-day hold frequency. It comes from a backtest over levels recomputed in 2026, so it carries hindsight; say so beside the rate, not only in a closing note.
- `exp_bounce_pct`: "a measured bounce of X% after past tests". The dictionary does not say whether it is an average, so never call it one.
- `hard_break_pct`: a stored hard-break magnitude in percentage points. It is not a frequency of breaks, not a current break signal and not a price; the threshold price is not in the toolkit yet. Do not turn it into a distance from today's price or a place to put an invalidation.
- The number of past tests is not in the toolkit yet. Never write "of N tests" or imply a sample size.

These describe their own sample, with upstream recomputation and hindsight limitations. Missing is "not supplied", never zero, never a result. Copy figures as emitted, rounded to at most two decimals; never compute your own distance, difference, percentage or average, and say relationships in words ("a little below the close").

## Dates and freshness

- `level_date`: the source event session. It is not when the level became available.
- `as_of`: the snapshot's decision time. Live, it is the earliest `as_of` across the API responses combined; with `--data`, the dataset snapshot's own `as_of`.
- The time of the read is not printed. Same-day live reads may come from the local cache, so they do not prove fresh intraday coverage.
- `data_warnings` carry source limits, such as unadjusted prices and non-point-in-time data. State them before conclusions.

## Asking

Ask only when the answer truly changes, and never more than one question in a reply. If the side is unclear, answer for both sides and add one question, for example: "Are you looking at this from the long side or the short side, and over roughly what timeframe?" Never ask again for something already given. A missing ticker is the one case to ask before running anything.

## Not in the toolkit yet

Some hosts supply richer level evidence than the toolkit reads. If a user brings it, or asks about it, read it this way and say the toolkit does not produce it.

- **Past-level history.** Earlier levels with their valid-from and valid-to dates. History lists are truncated; never present them as exhaustive.
- **Outcome counts.** Counts of `win`, `loss` and `unclassified` cover unique level IDs in that one response, not lifetime performance. Unclassified includes source records with no classification and is neither result. A level with no outcome has no result.
- **Metric status.** Metrics dated for a different day than their level are not current metrics; say so rather than reading their values.
- **Exposure profile.** A profile carries its kind, unit, date and methodology. Signs and units follow that methodology. Its largest-magnitude points are a truncated list.
- **Flip price.** A supplied profile value with its own label. Report it only as supplied; never infer one from a different kind of exposure.
- **Data status.** End-of-day, delayed and realtime are different; keep them apart.
- **Read time.** A field such as `known_at` is the time the data was read, not a data date.
