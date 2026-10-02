# Stock Screener

[← All tools](../README.md#choose-a-tool) · [Methodology](../docs/METHODOLOGY.md) · [Data contract](../docs/DATA_CONTRACT.md)

**Find stocks that match your research criteria, see why each name qualified or was excluded, and add Price, Peers, and Market context to the shortlist.**

> **Recommended live provider: Visual Sectors.** Connect our API for live screener results, served S/R levels, and the readings needed to validate candidates locally. [Get a free API key](https://api.visualsectors.com/signup) · [Explore the API](https://api.visualsectors.com).

## When to use it

Use this folder to narrow research coverage before developing a thesis—not to generate a buy list.

- Run one of three disclosed presets: near support, oversold at support, or trend continuation.
- Translate supported trader jargon into explicit filters, or get a refusal explaining what the dataset cannot express. Custom live requests use a watchlist of 1–5 tickers, not a whole-market scan.
- Inspect ranked matches, exclusions, missing inputs, and truncation; then review the selected names in Price, Peers, and Market lanes without silently reranking them.

## AI skills

- [compose-screen](skills/compose-screen/SKILL.md): disclose every requested condition and default before running a supported screen; refuse unsupported combinations rather than weakening them.
- [analyze-screener-context](skills/analyze-screener-context/SKILL.md): interpret the frozen shortlist against code-owned observations, contrary evidence, and coverage gaps.

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
| Limit | 1–100 tickers; defaults to 5 to bound live calls. |

## What you get

Ranked candidates, observed inputs, exclusion reasons, and a count of candidates omitted by the requested limit.

Live presets fetch only one upstream candidate page, at most `--limit` tickers. The output discloses that scope even if no local candidate passes; no cursor is followed and exclusions are not backfilled. `coverage` counts hydrated snapshots, not the API's entire universe. `omitted_candidates` counts local matches beyond the output limit, not unseen upstream stocks. This is not an exhaustive whole-market ranking.

For `trend_continuation`, the API's coarse condition is positive SMA50, ordered by SMA50 descending. Local filters then require positive **20-session** momentum and rank by it. Positive 60-session returns are not required: the API cannot express the documented 20-session return rule, so upstream order is not a proxy for the local final rank.

Output is JSON, suitable for inspection, saving locally, or feeding into your own builder workflow. For every available flag and its unit:

```powershell
python .\screener\run.py --help
```

Equivalent installed command: `vstoolkit screen`.

## Add Price Peers and Market context

The optional [analyze-screener-context skill](skills/analyze-screener-context/SKILL.md) reads the already-selected candidates without changing membership or order. It covers the full price path, industry median/breadth/dispersion, equal- versus cap-weighted peers, headline peers by business-line theme, both SPY and QQQ, co-movement, and leading/challenging narratives.

`vstoolkit context` computes those features in pure Python from an authorized dataset.v2, or Price/Market live from the API with missing peer lanes explicitly marked **not supplied**. No model service or Node is needed for computed JSON/cards; optional machine-validated model cards need Node22+. The [context guide](../docs/SCREENER_CONTEXT.md) gives the complete fictional parity example and validation flow.

```powershell
vstoolkit context --offline --format markdown
vstoolkit context --ticker AAPL --card aapl-context.local.md
vstoolkit screen --ask "oversold above the 200" --offline
vstoolkit screen --ask 'golden cross state and price above $10' --tickers AAPL,KMI,JPM
vstoolkit screen --ask "oversold with unusual volume" --interpret-only
```

The last request deliberately refuses because its volume field is not wired in; no weakened screen executes. PowerShell expands dollar amounts in double quotes: use single quotes for requests containing `$`, e.g. `--ask 'price above $10'`. Custom live requests require 1–5 explicit tickers and are **not** whole-market scans. See the [compose-screen grammar](skills/compose-screen/references/grammar.md).

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
