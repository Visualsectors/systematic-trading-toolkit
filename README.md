# Systematic Trading Toolkit

An open, inspectable Python toolkit for turning point-in-time US-equity data into six practical research outputs:

1. filtered, ready-to-research watchlists;
2. reproducible position sizes;
3. evidence-first research briefs;
4. explicit tailwind, headwind, and uncertainty registers;
5. change-based monitoring events; and
6. conditional entry, invalidation, and reassessment zones.

The core is deterministic and dependency-free. It runs offline with a bundled synthetic dataset, contains no broker integration, and never treats missing data as neutral evidence.

> **Project status:** pre-release public-repository candidate. The code is usable locally, but no Visual Sectors API adapter or live-data entitlement is included in v0.1.0.

## Why this exists

Most trading examples hide critical assumptions in a notebook, mix data access with financial logic, or report only the attractive result. This toolkit keeps the decision path visible:

- every screen publishes its filters, rank method, and exclusions;
- each sizing result names its method and binding constraint;
- research findings distinguish facts, interpretations, contrary evidence, and gaps;
- monitoring reports state changes instead of repeating unchanged alerts;
- level metrics are historical observations, not cross-instrument probabilities; and
- calculation modules have no network, clock, environment, filesystem, or random dependency.

It is designed for Python and agent-tool builders who want code they can inspect, fork, test, and connect to their own licensed data.

## Quickstart

Requirements: Python 3.12 or newer.

```bash
git clone https://github.com/Visualsectors/systematic-trading-toolkit.git
cd systematic-trading-toolkit
python -m pip install -e .
vstoolkit demo --output toolkit-report.md
```

The demo is entirely offline and uses fictional symbols and observations. It creates one Markdown report containing all six outcomes.

Run an individual screen:

```bash
vstoolkit screen --preset oversold_at_support --limit 10
```

Run auditable stop-risk arithmetic:

```bash
vstoolkit size-stop \
  --capital 100000 \
  --risk-fraction 0.005 \
  --entry 100 \
  --stop 95 \
  --max-allocation 0.10
```

The result is 100 shares, $10,000 notional, and $500 planned loss at the stop before gaps, slippage, commissions, taxes, or borrow costs.

## The six outcomes

### 1. Screening

Three disclosed presets ship in v0.1.0:

| Preset | Purpose | Rank method |
| --- | --- | --- |
| `near_support` | Liquid shares within 1.5 ATR of served support | nearest support-band edge in ATR units |
| `oversold_at_support` | Near support with RSI(14) at or below 35 | lowest RSI, then support distance |
| `trend_continuation` | Ordered long-term averages, near SMA(20), positive momentum | highest 20-session momentum |

Every non-candidate has machine-readable exclusion reasons. Historical level `score` fields are not used as comparable return probabilities.

### 2. Position sizing

The methods are deliberately separate:

- `stop_risk/v1`: whole shares constrained by both a planned-loss budget and a maximum allocation;
- `portfolio_slots/v1`: the established Visual Sectors slot method, with inverse-volatility weights when every priced pick has valid volatility and equal slots otherwise.

They are never silently blended. Missing price leaves a slot unallocated. A one-share minimum and an unaffordable share are reported explicitly.

### 3. Research briefs

`build_research_brief` creates a structured brief over supplied fields and evidence. Every factual or interpreted claim carries evidence IDs. Contrary evidence has its own section. Missing news, fundamentals, event dates, levels, or thesis inputs remain visible as coverage gaps.

The public implementation is deterministic; it does not need an LLM. An AI client can summarize the resulting JSON, but it should not replace or invent the cited facts.

### 4. Risk registers

`build_risk_register` turns the available evidence into review conditions. A flag states:

- type: headwind, tailwind, or uncertainty;
- severity;
- the observed condition;
- the trigger for reassessment; and
- the action to take when the trigger changes.

Absence of a flag means absence of supplied evidence, not absence of risk.

### 5. Monitoring

`evaluate_monitor` compares the newest risk register with the last valid state. It emits events for new flags, severity increases, resolutions, evaluation failures, and recovery. An evaluation failure retains existing risks and cannot generate a false all-clear.

```bash
vstoolkit monitor --ticker ALFA --state monitor-state.json
```

The command writes state atomically. Running the unchanged fixture again produces no duplicate risk events.

### 6. Entry and exit planning

Levels from the most recent served level date are expanded into ATR-width zones and clustered without changing their original support/resistance side. For a long scenario, the toolkit can identify:

- a support-based entry zone;
- an invalidation boundary below that zone; and
- the nearest served resistance zone as a reassessment area.

These are conditional planning scenarios—not fill promises, price targets, forecasts, or orders.

## Bring your own data

Use the strict JSON contract documented in [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md):

```bash
vstoolkit screen --data /path/to/your-dataset.json --preset near_support
vstoolkit research --data /path/to/your-dataset.json --ticker AAPL --thesis "Your falsifiable thesis"
```

Unknown fields fail closed. Every dataset must declare its source, license, whether it is synthetic, its decision time, and generation time. Raw data rights remain separate from the Apache-2.0 code license.

Provider I/O implements `MarketDataProvider`; calculations consume immutable `MarketSnapshot` values. This keeps live API credentials and transport logic outside the research core.

## Python API

```python
from visualsectors_toolkit import SyntheticFixtureProvider, run_screen
from visualsectors_toolkit.levels import build_level_plan

provider = SyntheticFixtureProvider()
screen = run_screen(provider.universe(), "oversold_at_support")
row = provider.get(screen.candidates[0].ticker)
plan = build_level_plan(
    ticker=row.ticker,
    as_of=row.as_of,
    direction="long",
    current_price=row.price,
    atr=row.atr14,
    levels=row.levels,
)
```

## Architecture and trust boundary

```text
licensed API or local JSON
          │
          ▼
  provider boundary (I/O)
          │ immutable, point-in-time snapshots
          ▼
 deterministic calculation core
  ├─ screening
  ├─ level geometry
  ├─ two named sizing methods
  ├─ research assembly
  ├─ risk register
  └─ monitor comparison
          │
          ▼
 JSON / Markdown / optional AI presentation layer
```

The public repository contains orchestration and interpretation logic. Proprietary Visual Sectors indicator-generation methods, credentials, licensed raw market data, entitlements, and broker execution stay outside this boundary.

## What is not included

- trade execution or broker connectivity;
- personal suitability or portfolio advice;
- live data or a guarantee of data quality;
- proprietary options-derived, market-regime, or earnings indicators;
- a backtesting engine (that belongs in the separate Edge Clinic effort); or
- a claim that a historical level held, bounced, or broke with any future probability.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) and [docs/LIMITATIONS.md](docs/LIMITATIONS.md) before adapting the output to a production decision process.

## Development and QA

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m visualsectors_toolkit demo --output toolkit-report.md
```

The reference suite covers arithmetic, missing-data behavior, temporal level selection, deterministic rankings, evidence traceability, alert deduplication, failure recovery, strict schemas, and purity of calculation modules.

Contributions are welcome under [CONTRIBUTING.md](CONTRIBUTING.md). Security reports should follow [SECURITY.md](SECURITY.md).

## License and data rights

Code and documentation are licensed under Apache-2.0. Dataset and API rights are separate. The bundled dataset is fictional and distributable under the terms stated in its manifest. Connecting another dataset does not grant permission to redistribute it.

This software is for research and education. It does not provide investment, legal, tax, or accounting advice.
