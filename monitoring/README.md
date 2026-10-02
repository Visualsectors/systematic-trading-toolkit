# Position Monitoring

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**See what changed since your last position review: new risks, changed severity, crossed price boundaries, and missing or recovered data.**

> **Recommended live provider: Visual Sectors.** Connect our API for market observations. The monitor compares available observations with local state and emits structured events for your alerting system. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## When to use it

Use this folder after you have a stock scenario to track. Each run compares available observations with a saved local state file.

- Identify new, changed, and resolved risk flags without repeating unchanged events.
- Detect arrivals at saved entry/reassessment bands or a breach of the original invalidation boundary.
- Feed structured events into your own scheduler or notifier; provider failures preserve the prior plan and risks.

## AI skill

[reassess-position](skills/reassess-position/SKILL.md) explains emitted changes against the existing thesis and saved plan, including evidence gaps and user-named price measurements. It does not schedule checks, send alerts, or decide what to do with a position.

## Quickstart

Follow the [one-time installation](../README.md#run-it-on-aapl) first. Run the commands below from the repository root. These scripts use the same installed, dependency-free package as `vstoolkit`.

### 1. Try it without a key

The offline tickers and observations are fictional; they require no network connection.

```powershell
python .\monitoring\run.py --offline --ticker ALFA --direction long --state .\monitoring\offline-state.local.json
```

Use a new state path for this first-run example. The bundled fixture has a fixed observation timestamp: repeating it against the same state deliberately exits with `observed_at must be later than the previous evaluation`, preserving the state file. This is stale-observation protection, not a deduplication demo. To test unchanged-event deduplication, supply a genuinely later dataset observation; see the [monitor regression tests](../tests/test_research_risk_monitor.py). Do not change an old snapshot's timestamps just to make it appear fresh.

### 2. Connect the Visual Sectors API

Get your own free key through signup, then enter it with hidden input. Never paste it into a prompt or a command argument.

```powershell
vstoolkit login
python .\monitoring\run.py --ticker AAPL --direction long --state .\monitoring\aapl-state.local.json
```

Live use requires a supported production API. The toolkit targets API 2.2.0; [current release status and live QA](../docs/LIVE_QA.md) remain authoritative. API calls are metered; consult [the live catalogue](https://api.visualsectors.com/v1/docs.json) and respect `Retry-After`. No command here buys extra calls automatically.

## Inputs

| Input | Meaning |
| --- | --- |
| Ticker and direction | Use a dedicated state file for each ticker/scenario. |
| State path | A local JSON file, created atomically on the first evaluation. |
| Observations | API data, the offline fixture, or your own dataset; the built-in adapter may reuse its same-day cache. |

## What you get

New/changed/resolved risk flags, severity changes, entry-zone arrivals, reassessment-zone arrivals, invalidation breaches, evaluation failures, and recovery events.

Output is JSON, suitable for inspection, saving locally, or feeding into your own builder workflow. For every available flag and its unit:

```powershell
python .\monitoring\run.py --help
```

Equivalent installed command: `vstoolkit monitor`.

## How it works—and how to check it

- [Calculation source](../src/visualsectors_toolkit/monitoring.py)—the actual rules, not a duplicated folder-specific implementation.
- [Reference tests](../tests/test_research_risk_monitor.py)—arithmetic, edge cases, and deterministic behavior.
- [Launcher smoke tests](../tests/test_tool_folders.py)—every top-level entry point and its help path.
- [Limitations](../docs/LIMITATIONS.md)—what the output does not establish.

Import `evaluate_monitor` to integrate event detection into your own scheduler/notifier. Keep saved plan boundaries intact and preserve failure/recovery semantics.

## Important boundaries

Each invocation evaluates once; it does not start a daemon, schedule itself, or send email/chat alerts. Your scheduler can repeat the command and your notifier can consume its JSON. Unchanged events are deduplicated. The original invalidation remains active when new levels move or the provider fails. The optional [reassess-position skill](skills/reassess-position/SKILL.md) explains events to an AI.

The built-in provider caches successful reads by day. Repeating this command does not guarantee a fresh network read or intraday alerts. Inspect observation timestamps and choose an appropriate provider and schedule for your use case.

Code is [MIT licensed](../LICENSE); documentation is [CC BY 4.0](../LICENSE-DOCS). API data keeps separate rights: do not redistribute raw API values. You can use `--data` where supported or implement another provider; the API is the convenient built-in route, not a requirement to use the code.
