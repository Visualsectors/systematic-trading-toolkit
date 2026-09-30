# Stock Screener

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**Turn a broad US-equity universe into a filtered, ranked watchlist—with every inclusion rule and exclusion reason inspectable.**

> **Recommended live provider: Visual Sectors.** Connect our API for live screener results, served S/R levels, and the readings needed to validate candidates locally. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## Quickstart

Follow the [one-time installation](../README.md#run-it-on-aapl) first. Run the commands below from the repository root. These scripts use the same installed, dependency-free package as `vstoolkit`.

### 1. Try it without a key

The offline tickers and observations are fictional; they require no network connection.

```powershell
python .\screener\run.py --offline --preset oversold_at_support --limit 5
```

### 2. Connect the Visual Sectors API

Get your own free key through signup, then enter it with hidden input. Never paste it into a prompt or a command argument.

```powershell
vstoolkit login
python .\screener\run.py --preset near_support --limit 5
```

Live use requires a supported production API. The toolkit targets API 2.2.0; [current release status and live QA](../docs/LIVE_QA.md) remain authoritative. API calls are metered; consult [the live catalogue](https://api.visualsectors.com/v1/docs.json) and respect `Retry-After`. No command here buys extra calls automatically.

## Inputs

| Input | Meaning |
| --- | --- |
| Preset | `near_support`, `oversold_at_support`, or `trend_continuation`. |
| Universe | Live API, fictional offline fixture, or your own `--data` JSON. |
| Limit | 1–100 tickers; start at 5 with a free key. |

## What you get

Ranked candidates, observed inputs, exclusion reasons, and a count of candidates omitted by the requested limit.

Output is JSON, suitable for inspection, saving locally, or feeding into your own builder workflow. For every available flag and its unit:

```powershell
python .\screener\run.py --help
```

Equivalent installed command: `vstoolkit screen`.

## Add Price Peers and Market context

The optional [analyze-screener-context skill](../skills/analyze-screener-context/SKILL.md) reads the already-selected candidates without changing membership or order. It covers the full price path, industry median/breadth/dispersion, equal- versus cap-weighted peers, headline peers by business-line theme, both SPY and QQQ, co-movement, and leading/challenging narratives.

`vstoolkit context` computes those features from an authorized context dataset. It requires **Node.js 22+**, but no npm packages or model service. The [context guide](../docs/SCREENER_CONTEXT.md) gives an immediately runnable fictional parity example and the analyst request/validation flow. An ordinary snapshot dataset or `screen` result alone cannot supply the needed historical paths, memberships and source cutoffs; missing context is not fabricated.

The code measures and renders; a model only chooses admitted contextual interpretations. Tier A/B/C describes thesis fit, not expected return or a trade recommendation. Missing critical evidence yields `INSUFFICIENT_DATA`.

## How it works—and how to check it

- [Calculation source](../src/visualsectors_toolkit/screening.py)—the actual rules, not a duplicated folder-specific implementation.
- [Reference tests](../tests/test_screening.py)—arithmetic, edge cases, and deterministic behavior.
- [Launcher smoke tests](../tests/test_tool_folders.py)—every top-level entry point and its help path.
- [Limitations](../docs/LIMITATIONS.md)—what the output does not establish.

`run_screen(provider.universe(), preset, limit=5)` is available through the Python API. Keep new filters explicit and add exclusion/tie-break tests.

## Important boundaries

A screen narrows research coverage; it is not a forecast, a buy list, or evidence of positive expected return. A cold live screen can use about `1 + 9 × returned tickers` calls before pagination. A 429 stops the command with a wait time—no hidden retries or purchases.

Code is [MIT licensed](../LICENSE); documentation is [CC BY 4.0](../LICENSE-DOCS). API data keeps separate rights: do not redistribute raw API values. You can use `--data` where supported or implement another provider; the API is the convenient built-in route, not a requirement to use the code.
