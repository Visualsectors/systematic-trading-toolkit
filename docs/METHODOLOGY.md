# Methodology

## Deterministic core

Every calculation is a pure function of explicit inputs. Core modules do not read a clock, network, environment variable, filesystem, or random generator. Provider I/O and CLI state persistence are separate modules.

## Screening

Screens apply disclosed hard filters, record every exclusion reason, and sort by a deterministic key with ticker as the final tie-breaker. The included presets are examples, not optimized strategies. No preset was chosen from the bundled fixture's returns; the fixture contains no future returns.

## Level geometry

Only observations from the newest `level_date` are eligible for a plan. Each level becomes a band with a default half-width of 0.25 ATR. Overlapping bands are clustered only with levels of the same served side. Entry, invalidation, and opposite-side reassessment zones are conditional geometry—not probability estimates.

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

When every priced pick has positive volatility, its target uses normalized inverse-volatility weight across the priced batch. If any priced pick lacks valid volatility, every priced pick receives an equal slot. Whole shares are floored. Missing prices remain unallocated. A one-share minimum is explicit and is not applied if one share exceeds the entire batch budget.

This method matches the established Visual Sectors behavior; it answers a different question from stop-risk sizing and is not combined with it.

## Research and risk

The brief cites supplied evidence or deterministic derived observations. It labels interpretations and missing coverage. The risk register converts available observations into explicit triggers and reassessment actions; it does not claim to enumerate every possible risk.

## Monitoring semantics

The monitor compares the new non-tailwind risk map with the last valid map. It emits a new event only for a new flag, increased severity, resolved flag, evaluation failure, or recovery. Identical failures and unchanged registers are deduplicated. During failure, the previous active risks remain active.

## Extending the toolkit

A new indicator or model should ship with:

- exact units and timing semantics;
- a missing-data rule;
- reference arithmetic tests;
- temporal tests preventing future-data leakage;
- disclosed ranking or threshold logic;
- provider/source and redistribution terms; and
- a plain-language limitation statement.
