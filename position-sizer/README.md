# Position Sizer

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**Convert explicit capital and risk assumptions into a whole-share position size, with the limiting constraint and unallocated capital visible.**

> **Recommended live provider: Visual Sectors.** Connect our API for live prices, volatility inputs, and level-based plan geometry. Manual entry/stop arithmetic also works without an API key. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## Quickstart

Follow the [one-time installation](../README.md#run-it-on-aapl) first. Run the commands below from the repository root. These scripts use the same installed, dependency-free package as `vstoolkit`.

### 1. Try it without a key

The offline tickers and observations are fictional; they require no network connection.

```powershell
python .\position-sizer\run.py --capital 100000 --risk-fraction 0.005 --entry 100 --stop 95 --max-allocation 0.10
python .\position-sizer\portfolio_slots.py --offline --tickers ALFA,BRVO --portfolio 100000 --intended-holdings 10
```

### 2. Connect the Visual Sectors API

Get your own free key through signup, then enter it with hidden input. Never paste it into a prompt or a command argument.

```powershell
vstoolkit login
python .\position-sizer\portfolio_slots.py --tickers AAPL,MSFT --portfolio 100000 --intended-holdings 10
```

Live use requires a supported production API. The toolkit targets API 2.2.0; [current release status and live QA](../docs/LIVE_QA.md) remain authoritative. API calls are metered; consult [the live catalogue](https://api.visualsectors.com/v1/docs.json) and respect `Retry-After`. No command here buys extra calls automatically.

## Inputs

| Input | Meaning |
| --- | --- |
| Stop-risk method | Capital, risk fraction, entry, stop, allocation cap, and long/short side. |
| Portfolio-slot method | Portfolio capital, intended holding count, ticker batch, and available volatility. |
| Units | Fractions are decimal: `0.005 = 0.5%`; `0.10 = 10%`. |

## What you get

Versioned method name, whole shares, capital allocation, planned stop loss or batch allocation, binding constraints, and missing-input warnings.

Output is JSON, suitable for inspection, saving locally, or feeding into your own builder workflow. For every available flag and its unit:

```powershell
python .\position-sizer\run.py --help
```

The second launcher, `portfolio_slots.py`, is equivalent to `vstoolkit size-portfolio`; `run.py` is equivalent to `vstoolkit size-stop`.

## How it works—and how to check it

- [Calculation source](../src/visualsectors_toolkit/sizing.py)—the actual rules, not a duplicated folder-specific implementation.
- [Reference tests](../tests/test_sizing.py)—arithmetic, edge cases, and deterministic behavior.
- [Launcher smoke tests](../tests/test_tool_folders.py)—every top-level entry point and its help path.
- [Limitations](../docs/LIMITATIONS.md)—what the output does not establish.

Import `size_by_stop_risk` or `size_by_portfolio_slots` to use the same deterministic arithmetic in your own strategy. Reference tests cover budget bounds and minimum-share behavior.

## Important boundaries

These are two separate sizing methods, not a blended recommendation. Stop-risk shares are the smaller of the loss-budget and allocation-cap share counts. Portfolio slots use inverse volatility only when every priced name has valid volatility; otherwise they use equal slots. Neither method models gaps, slippage, fees, taxes, or borrow costs.

Code is [MIT licensed](../LICENSE); documentation is [CC BY 4.0](../LICENSE-DOCS). API data keeps separate rights: do not redistribute raw API values. You can use `--data` where supported or implement another provider; the API is the convenient built-in route, not a requirement to use the code.
