# Reading levels

## Which levels

Only levels from the newest `level_date` on or before the snapshot's `as_of` are read; older sessions are a different map. The live read covers every served level family at once. Both commands return the nearest levels only, never the full list; a complete level listing is not in the toolkit yet.

## Nearest levels and zones

`measure` picks the closest served level strictly above and strictly below a price by price alone, whatever its side. A Resistance level below the close is reported as `nearest_below` with side Resistance; keep that label and do not call it support.

`plan` groups levels into zones. Each level becomes a band 0.25 ATR14 either side of its price. Overlapping or touching bands of the same served side merge while the merged band stays within 1.0 ATR14. Side is decided by membership, not proximity: the nearest support zone must hold a Support level and lie below the close (or contain it); a resistance zone must hold a Resistance level and lie above it (or contain it). A zone is geometry around served prices, not evidence that a level holds. Where price sits relative to a zone is position, not a break.

When several levels share a zone, say they cluster within one band. `confluence_count_max` is the largest served confluence among the members; `member_count` is how many rows the toolkit merged. Reporting the second under the first's name inflates a served number.

## Comparing levels

Compare only the levels the commands emitted. Order by one served field you name: `p_hold_7d_pct` when the user cares how often a level held, `exp_bounce_pct` when they care how far price moved after past tests. Levels with a null value go after every measured one. Never blend fields into your own composite. A balanced ranking over both fields, and tie-breaking by number of past tests, are not in the toolkit yet. Ordering by a measured field is not a ranking of trade ideas.

## Historical record

- `p_hold_7d_pct`: "held on N% of past tests".
- `exp_bounce_pct`: "the average move after past tests was X%".
- `hard_break_pct`: the distance from the level to its stored hard-break threshold, where a close beyond that price counts as a decisive break. If the user asks where a level is invalidated, this is the served answer; the threshold price is not in the toolkit yet.
- The number of past tests is not in the toolkit yet. Never write "of N tests" or imply a sample size.

These describe their own sample, with upstream recomputation and hindsight limitations. Missing is "not supplied", never zero, never a result. Copy figures as emitted, rounded to at most two decimals; never compute your own distance, difference, percentage or average, and say relationships in words ("a little below the close").

## Dates and freshness

- `level_date`: the session the levels were computed for.
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
