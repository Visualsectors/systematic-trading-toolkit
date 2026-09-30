# Research Intelligence

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**Build an evidence-linked research brief that separates observations, interpretations, contrary evidence, and missing coverage.**

> **Recommended live provider: Visual Sectors.** Connect our API to bring current SEC metrics, technical readings, served levels, and headlines into an evidence-linked research brief. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## Quickstart

Follow the [one-time installation](../README.md#run-it-on-aapl) first. Run the commands below from the repository root. These scripts use the same installed, dependency-free package as `vstoolkit`.

### 1. Try it without a key

The offline tickers and observations are fictional; they require no network connection.

```powershell
python .\research\run.py --offline --ticker ALFA --direction long --thesis "Price holds structural support while margins remain resilient"
```

### 2. Connect the Visual Sectors API

Get your own free key through signup, then enter it with hidden input. Never paste it into a prompt or a command argument.

```powershell
vstoolkit login
python .\research\run.py --ticker AAPL --direction long --thesis "Price holds structural support while margins remain resilient"
```

Live use requires a supported production API. The toolkit targets API 2.2.0; [current release status and live QA](../docs/LIVE_QA.md) remain authoritative. API calls are metered; consult [the live catalogue](https://api.visualsectors.com/v1/docs.json) and respect `Retry-After`. No command here buys extra calls automatically.

## Inputs

| Input | Meaning |
| --- | --- |
| Ticker and direction | A US-listed ticker and a long/short scenario. |
| Thesis | A falsifiable claim to examine; omission produces an explicit gap. |
| Evidence | Live API observations, the fictional fixture, or a validated local dataset. |

## What you get

A structured brief with evidence IDs, derived observations, opposing evidence, technical/fundamental context, and explicit data gaps.

Output is JSON, suitable for inspection, saving locally, or feeding into your own builder workflow. For every available flag and its unit:

```powershell
python .\research\run.py --help
```

Equivalent installed command: `vstoolkit research`.

## How it works—and how to check it

- [Calculation source](../src/visualsectors_toolkit/research.py)—the actual rules, not a duplicated folder-specific implementation.
- [Reference tests](../tests/test_research_risk_monitor.py)—arithmetic, edge cases, and deterministic behavior.
- [Launcher smoke tests](../tests/test_tool_folders.py)—every top-level entry point and its help path.
- [Limitations](../docs/LIMITATIONS.md)—what the output does not establish.

Import `build_research_brief` to consume a `MarketSnapshot`. Preserve evidence IDs and the distinction between facts and interpretations in any downstream AI presentation.

## Important boundaries

The brief is bounded by supplied evidence; it does not independently browse the web or run an LLM. The optional [build-research-thesis skill](../skills/build-research-thesis/SKILL.md) helps an AI present this audit record without inventing missing facts. An absent earnings calendar or unavailable news feed is not a neutral signal.

Code is [MIT licensed](../LICENSE); documentation is [CC BY 4.0](../LICENSE-DOCS). API data keeps separate rights: do not redistribute raw API values. You can use `--data` where supported or implement another provider; the API is the convenient built-in route, not a requirement to use the code.
