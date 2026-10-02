# Support & Resistance

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**Understand the served support/resistance levels around a stock, how those levels behaved historically, and which price boundaries define your research scenario.**

> **Recommended live provider: Visual Sectors.** Connect our API for served S/R levels, historical hold frequency, bounce magnitude and hard-break readings. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## When to use it

Use this folder when you want to turn a stock's dated levels into an inspectable price map—not a buy/sell instruction.

- See conditional entry and reassessment bands, the scenario's invalidation boundary, and distances in ATR units.
- Inspect the historical hold frequency, bounce magnitude and hard-break magnitude supplied for each selected level, with their limitations.
- Measure the nearest served levels above and below a price you name, such as an entry, cost basis, or strike.

## AI skill

A dedicated toolkit-compatible support/resistance skill is not bundled yet. The calculation commands work independently; a skill will be added separately. No placeholder skill or automatic advice is included.

## Quickstart

Follow the [one-time installation](../README.md#run-it-on-aapl) first. Run the commands below from the repository root. These scripts use the same installed, dependency-free package as `vstoolkit`.

### 1. Try it without a key

The offline tickers and observations are fictional; they require no network connection.

```powershell
python .\support-resistance\run.py ALFA --offline --direction long --capital 25000 --risk-fraction 0.005 --max-allocation 0.10
```

### 2. Connect the Visual Sectors API

Get your own free key through signup, then enter it with hidden input. Never paste it into a prompt or a command argument.

```powershell
vstoolkit login
python .\support-resistance\run.py AAPL --direction long --capital 25000 --risk-fraction 0.005 --max-allocation 0.10
```

Live use requires a supported production API. The toolkit targets API 2.2.0; [current release status and live QA](../docs/LIVE_QA.md) remain authoritative. API calls are metered; consult [the live catalogue](https://api.visualsectors.com/v1/docs.json) and respect `Retry-After`. No command here buys extra calls automatically.

## Inputs

| Input | Meaning |
| --- | --- |
| Ticker and direction | One US-listed ticker, long or short. |
| Geometry | Newest eligible dated levels, current price, and ATR14. |
| Sizing assumptions | Capital, decimal risk fraction, and decimal allocation cap. Defaults: 100,000 / 0.005 / 0.10. |

## What you get

Entry and reassessment bands, invalidation price, ATR stop distance, reward-to-reassessment R, whole-share sizing, and `data_warnings`. Historical measurements use the schema label `historical_base_rate`: only `p_hold_7d_pct` is a frequency; `exp_bounce_pct` and `hard_break_pct` are magnitudes in percentage points. The API documents the hold backtest as using levels recomputed in 2026 (hindsight), not a point-in-time strategy test.

Live plans request the latest eligible session with `only_best=true`. They read the upstream selected support/resistance pair per approach, not every level family. A returned cursor is a disclosed evidence gap, never followed to fetch the remaining families.

Historical base-rate rows are consolidated by `(side, level_type, level_price)`, with a sorted `approaches` list on each row. Conflicting statistics remain null with a note; they are not averaged or selected for the most favorable value. Exact source prices define identity, not rounded display prices.

The toolkit permanently treats `exp_bounce_pct > 100` as a data gap. The entire offending row is excluded from scoring, ATR estimation and zones, and a warning names its ticker, side, type, price and approach. Exactly 100 is accepted; missing values stay missing. If all current levels fail the guard, the plan reports insufficient data rather than reviving older levels. This client guard remains in place after upstream corrections.

Output is JSON, suitable for inspection, saving locally, or feeding into your own builder workflow. For every available flag and its unit:

```powershell
python .\support-resistance\run.py --help
```

Equivalent installed command: `vstoolkit plan`.

To measure levels from a user-named price instead of calculating scenario zones:

```powershell
vstoolkit measure --ticker ALFA --price 100 --kind cost --offline
vstoolkit measure --ticker AAPL --price 200 --kind strike
```

This returns signed dollar, percent, and ATR distances; a strike also gets its distance from the latest close in ATR. It uses served level prices, not generated targets. Unavailable levels, ATR, or historical rates remain null.

## How it works—and how to check it

- [Calculation source](../src/visualsectors_toolkit/levels.py)—the actual rules, not a duplicated folder-specific implementation.
- [Reference tests](../tests/test_levels.py)—arithmetic, edge cases, and deterministic behavior.
- [Launcher smoke tests](../tests/test_tool_folders.py)—every top-level entry point and its help path.
- [Limitations](../docs/LIMITATIONS.md)—what the output does not establish.

Import `build_level_plan` to inspect the same deterministic geometry in Python. Follow it with the [position sizer](../position-sizer/) or [monitor](../monitoring/) without silently moving the saved invalidation.

## Important boundaries

An exit here means a scenario invalidation/reassessment boundary, not a broker order or a fill guarantee. Historical level measurements are not probabilities for today's trade. If valid inputs or a suitable zone are absent, the tool abstains rather than fabricating a price.

Code is [MIT licensed](../LICENSE); documentation is [CC BY 4.0](../LICENSE-DOCS). API data keeps separate rights: do not redistribute raw API values. You can use `--data` where supported or implement another provider; the API is the convenient built-in route, not a requirement to use the code.
