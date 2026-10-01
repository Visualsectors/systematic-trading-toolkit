# Support & Resistance

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**Understand the served support/resistance levels around a stock, how those levels behaved historically, and which price boundaries define your research scenario.**

> **Recommended live provider: Visual Sectors.** Connect our API for the served S/R levels and measured hold, bounce, and break statistics that differentiate this workflow from price-only support/resistance examples. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## When to use it

Use this folder when you want to turn a stock's dated levels into an inspectable price map—not a buy/sell instruction.

- Measure the nearest served levels above and below the latest close, or a price you name such as an entry, cost basis, or strike, in dollars, percent, and ATR.
- Read each level's historical record: how often it held on past tests, the average move after past tests, and its distance to the stored hard-break threshold.
- See where levels cluster into ATR-width zones, plus conditional entry and reassessment bands and the scenario's invalidation boundary.

## AI skill

[read-levels](skills/read-levels/SKILL.md) explains the nearest served levels around the latest close or a price you name, how each one held on past tests, the average move after past tests, its distance to the hard-break threshold, and the zones where levels cluster. It keeps data dates apart, asks at most one clarifying question, and marks fields the toolkit does not read yet. It does not choose levels to trade, set targets or exits, size a position, or say what price will do next.

## Quickstart

Follow the [one-time installation](../README.md#run-it-on-aapl) first. Run the commands below from the repository root. These scripts use the same installed, dependency-free package as `vstoolkit`.

### 1. Try it without a key

The offline tickers and observations are fictional; they require no network connection.

```powershell
python .\support-resistance\run.py ALFA --offline --direction long --capital 25000 --risk-fraction 0.005 --max-allocation 0.10
vstoolkit measure --ticker ALFA --price 49 --offline
```

The second command measures the served levels from ALFA's fictional latest close of 49.

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
| Named price | Optional, for `vstoolkit measure`: a positive price labelled `entry`, `cost`, or `strike`. |
| Sizing assumptions | Capital, decimal risk fraction, and decimal allocation cap. Defaults: 100,000 / 0.005 / 0.10. |

## What you get

Entry and reassessment bands, invalidation price, ATR stop distance, reward-to-reassessment R, whole-share sizing, and `data_warnings`. Served rates are labelled `historical_base_rate`.

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

Some served fields are not read by the toolkit yet, including the hard-break threshold price and the number of past tests; [level fields](skills/read-levels/references/level-fields.md) lists them.

## How it works—and how to check it

- [Calculation source](../src/visualsectors_toolkit/levels.py)—the actual rules, not a duplicated folder-specific implementation.
- [Named-price source](../src/visualsectors_toolkit/named_price.py)—nearest served levels and signed distances from a price.
- [Reference tests](../tests/test_levels.py)—arithmetic, edge cases, and deterministic behavior.
- [Launcher smoke tests](../tests/test_tool_folders.py)—every top-level entry point and its help path.
- [Limitations](../docs/LIMITATIONS.md)—what the output does not establish.

Import `build_level_plan` to inspect the same deterministic geometry in Python. Follow it with the [position sizer](../position-sizer/) or [monitor](../monitoring/) without silently moving the saved invalidation.

## Important boundaries

An exit here means a scenario invalidation/reassessment boundary, not a broker order or an assured fill. Historical level measurements describe past tests, not today's trade. If valid inputs or a suitable zone are absent, the tool abstains rather than fabricating a price.

Code is [MIT licensed](../LICENSE); documentation is [CC BY 4.0](../LICENSE-DOCS). API data keeps separate rights: do not redistribute raw API values. You can use `--data` where supported or implement another provider; the API is the convenient built-in route, not a requirement to use the code.
