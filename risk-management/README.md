# Risk Management

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**Identify the stock-specific headwinds, tailwinds, and unknowns that matter to your scenario—and record what would require a fresh review.**

> **Recommended live provider: Visual Sectors.** Connect our API for the observations behind risk flags; combine served levels, technical readings, SEC metrics, and news without filling gaps with invented values. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## When to use it

Use this folder when you need a structured risk checklist for one stock, before or during a position review.

- Inspect technical, fundamental, and headline evidence as headwinds, tailwinds, or uncertainties.
- See severity, evidence IDs, and the condition behind each reassessment flag.
- Pass the register to [monitoring](../monitoring/) to detect changes later; missing coverage remains a risk to investigate, not an all-clear.

## AI skill

[review-risk](skills/review-risk/SKILL.md) guides an AI through the register in severity order: each flag's trigger and evidence IDs, whether each rule is Triggered, Clear or Unmeasured, the strongest contrary reading, conditional invalidation geometry, and the review conditions to hand to [monitoring](../monitoring/). It runs sizing arithmetic only on inputs you supply, names the method used, and never chooses a risk budget, an exit or a holding action. Missing or unavailable data stays an open question, never an all-clear.

## Quickstart

Follow the [one-time installation](../README.md#run-it-on-aapl) first. Run the commands below from the repository root. These scripts use the same installed, dependency-free package as `vstoolkit`.

### 1. Try it without a key

The offline tickers and observations are fictional; they require no network connection.

```powershell
python .\risk-management\run.py --offline --ticker ALFA --direction long
```

### 2. Connect the Visual Sectors API

Get your own free key through signup, then enter it with hidden input. Never paste it into a prompt or a command argument.

```powershell
vstoolkit login
python .\risk-management\run.py --ticker AAPL --direction long
```

Live use requires a supported production API. The toolkit targets API 2.2.0; [current release status and live QA](../docs/LIVE_QA.md) remain authoritative. API calls are metered; consult [the live catalogue](https://api.visualsectors.com/v1/docs.json) and respect `Retry-After`. No command here buys extra calls automatically.

## Inputs

| Input | Meaning |
| --- | --- |
| Ticker and direction | A US-listed ticker and a long/short scenario. |
| Snapshot | Price, available indicators, dated levels, evidence, and source warnings. |
| Plan context | Conditional invalidation geometry calculated from the same observations. |

## What you get

Flags with kind, severity, statement, trigger, reassessment action, and cited evidence IDs. Data limitations become uncertainty flags.

Output is JSON, suitable for inspection, saving locally, or feeding into your own builder workflow. For every available flag and its unit:

```powershell
python .\risk-management\run.py --help
```

Equivalent installed command: `vstoolkit risk`.

## How it works—and how to check it

- [Calculation source](../src/visualsectors_toolkit/risk.py)—the actual rules, not a duplicated folder-specific implementation.
- [Reference tests](../tests/test_research_risk_monitor.py)—arithmetic, edge cases, and deterministic behavior.
- [Launcher smoke tests](../tests/test_tool_folders.py)—every top-level entry point and its help path.
- [Limitations](../docs/LIMITATIONS.md)—what the output does not establish.

Import `build_risk_register(snapshot, level_plan=plan)` to feed the same register into your own monitoring or review process.

## Important boundaries

This is a review register, not an exhaustive risk model or an order engine. Missing earnings timing stays missing; it never clears event risk. A tailwind is evidence to examine, not a reason to ignore a headwind.

Code is [MIT licensed](../LICENSE); documentation is [CC BY 4.0](../LICENSE-DOCS). API data keeps separate rights: do not redistribute raw API values. You can use `--data` where supported or implement another provider; the API is the convenient built-in route, not a requirement to use the code.
