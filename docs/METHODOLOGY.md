# Methodology

## Deterministic core

Every calculation is a pure function of explicit inputs. Core modules do not read a clock, network, environment variable, filesystem, or random generator. Provider I/O and CLI state persistence are separate modules.

## Screening

Screens apply disclosed hard filters, record every exclusion reason, and sort by a deterministic key with ticker as the final tie-breaker. The included presets are examples, not optimized strategies. No preset was chosen from the bundled fixture's returns; the fixture contains no future returns.

## Level geometry

Only observations from the newest `level_date` are eligible for a plan. Each level becomes a band with a default half-width of 0.25 ATR. Overlapping bands are clustered only with levels of the same served side. Entry, invalidation, and opposite-side reassessment zones are conditional geometry—not probability estimates.

A permanent data-quality gate excludes any row with `exp_bounce_pct > 100` before zone construction, score summaries or ATR estimation. Live responses disclose a warning naming the rejected level; file-backed snapshots and direct planning functions enforce the same rule. Other valid rows, including other approaches at the same price, remain usable. The newest session is selected before applying the gate, so a wholly invalid current session never silently falls back to older levels. This is a disclosed toolkit threshold, not a claim that all values below it are reliable.

Both historical base-rate lists group by exact `(side, level_type, level_price)` and list distinct source `approaches` in sorted order. Identical supplied statistics are kept once, missing statistics remain null, and conflicting non-null values become null with an explicit note. No mean, maximum or favorable-approach selection is used. Zone members still preserve the valid source observations; consolidation changes the descriptive base-rate display, not the identity of those source rows.

The schema name `historical_base_rate` is retained for compatibility. `p_hold_7d_pct` is a seven-day hold frequency; `exp_bounce_pct` and `hard_break_pct` are magnitudes in percentage points, not frequencies. The API documents the hold backtest as using levels recomputed in 2026 (hindsight). These are neither point-in-time strategy results nor current-setup probabilities. `approach` names the upstream scoring/selection method, not the level family's construction parameters; live plans request `only_best=true`, so they do not enumerate every served family.

## Stop-risk sizing

For portfolio capital `P`, risk fraction `r`, entry `E`, stop `S`, and maximum allocation fraction `a`:

```text
risk budget       = P × r
allocation cap    = P × a
risk shares       = floor(risk budget / |E − S|)
allocation shares = floor(allocation cap / E)
shares            = min(risk shares, allocation shares)
```

The planned loss excludes gaps through the stop, slippage, commissions, taxes, and borrow costs.

## Portfolio-slot sizing

For `N` intended holdings and `k` current picks:

```text
slot         = portfolio / N
batch budget = k × slot
```

When every priced pick has positive volatility, its allocation uses normalized inverse-volatility weight across the priced batch. If any priced pick lacks valid volatility, every priced pick receives an equal slot. Whole shares are floored. Missing prices remain unallocated. A one-share minimum is explicit; a second pass reduces other shares or omits the minimum so total deployment never exceeds the batch budget.

This is a disclosed toolkit example; it answers a different question from stop-risk sizing and is not combined with it.

## Research and risk

The brief cites supplied evidence or deterministic derived observations. It labels interpretations and missing coverage. The risk register converts available observations into explicit triggers and reassessment actions; it does not claim to enumerate every possible risk.

## Monitoring semantics

The monitor compares the newest risk map with the last valid map, including tailwinds. It reports new, changed, increased/decreased, and resolved flags plus evaluation failure/recovery. It also retains the original plan prices and reports entry-zone arrivals, reassessment-zone arrivals, and invalidation breaches against that saved plan. Identical failures and unchanged states are deduplicated; out-of-order observations are rejected. During failure, the previous active risks and plan remain active.

## Extending the toolkit

A new indicator or model must ship with:

- exact units and timing semantics;
- a missing-data rule;
- reference arithmetic tests;
- temporal tests preventing future-data leakage;
- disclosed ranking or threshold logic;
- provider/source and redistribution terms; and
- a plain-language limitation statement.
