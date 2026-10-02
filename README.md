# Systematic Trading Toolkit

[![CI](https://github.com/Visualsectors/systematic-trading-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/Visualsectors/systematic-trading-toolkit/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](pyproject.toml)
[![Code license: MIT](https://img.shields.io/badge/Code-MIT-15803D)](LICENSE)
[![Docs license: CC BY 4.0](https://img.shields.io/badge/Docs-CC_BY_4.0-64748B)](LICENSE-DOCS)

**S/R levels with measured hold frequency, bounce magnitude and hard-break readings**—plus screening, position sizing, evidence-linked research, risk registers, and change-based monitoring for US-listed equities.

This is an inspectable, dependency-free Python toolkit for builders using Claude Code, Codex, Cursor, or their own automation. It connects to the Visual Sectors Data API with a free key, keeps credentials outside prompts and shell history, and contains no broker connection or order execution.

**[Get a free Visual Sectors API key](https://api.visualsectors.com/signup)** · [API documentation](https://api.visualsectors.com) · [Try the offline demo](#offline-demo) · [Review the methodology](docs/METHODOLOGY.md)

## Choose a tool

All six tools have their own top-level folder. Open one for its quickstart, runnable scripts, calculation source, and reference tests:

| Tool folder | Outcome | Installed command |
| --- | --- | --- |
| [screener/](screener/) | Find stocks that match disclosed filters; inspect ranked matches, exclusions, and Price/Peers/Market context | `vstoolkit screen` / `vstoolkit context` |
| [position-sizer/](position-sizer/) | Calculate whole shares within your chosen risk budget and capital cap, or allocate a portfolio batch | `vstoolkit size-stop` / `size-portfolio` |
| [research/](research/) | Examine a stock thesis against technical, SEC, and news evidence—with contradictions and gaps visible | `vstoolkit research` |
| [risk-management/](risk-management/) | Identify stock-specific headwinds, tailwinds, and unknowns; record what would require reassessment | `vstoolkit risk` |
| [monitoring/](monitoring/) | Compare observations with saved state and emit changes in risks or original price boundaries | `vstoolkit monitor` |
| [support-resistance/](support-resistance/) | Inspect served S/R levels, historical measurements, and conditional scenario zones; measure levels from your own price | `vstoolkit plan` / `vstoolkit measure` |

The folder scripts call the same tested package as `vstoolkit`; calculations are not duplicated. Shared implementation lives in [`src/visualsectors_toolkit/`](src/visualsectors_toolkit/) and documentation in [`docs/`](docs/). Existing AI skills live inside their topical folders, alongside the tool they explain; see [skill coverage](#agent-skills). There is no separate top-level skills folder.

`support-resistance/` replaces the former `entry-exit/` folder. The installed `vstoolkit plan` command is unchanged.

## Use the Visual Sectors API for live data

The Visual Sectors API is the built-in live provider: one key connects screening, S/R levels, daily prices, technical readings, SEC metrics, and news. Start with the fictional offline examples, then connect your own free key through `vstoolkit login`.

- **Get started:** [free-key signup](https://api.visualsectors.com/signup), followed by hidden-input login. Never paste the key into a prompt.
- **Know the limits:** live calls are metered; [published entitlements](https://api.visualsectors.com/v1/docs.json) and response headers are authoritative. Begin with a small watchlist.
- **Keep control:** the code is MIT licensed. Use your own dataset with `--data` or implement another provider; connecting to our API is not mandatory.

API **2.2.0 is live** on the public host (checked 2026-10-02). This toolkit is experimental: missing evidence stays visible, and live API calls consume your allowance. The offline examples work without signup or a network connection. See [live QA](docs/LIVE_QA.md) for checks you can reproduce and the limits of the release evidence.

## Run it on AAPL

Requirements: Python 3.10 or newer and Git; a Visual Sectors API key for live commands. In PowerShell, start in a project directory outside synced folders such as OneDrive:

```powershell
git clone https://github.com/Visualsectors/systematic-trading-toolkit.git
Set-Location systematic-trading-toolkit
py -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install .
vstoolkit plan AAPL
```

The first live command exits with this instruction when no key exists:

```text
AAPL needs live data. Get a free key (no card) at https://api.visualsectors.com/signup, then run: vstoolkit login
```

Continue without putting the key on a command line:

```powershell
vstoolkit login
vstoolkit plan AAPL
```

Install from source as shown above. There is no PyPI release yet: do not use `pip install visualsectors-toolkit`.

`login` opens signup, reads the key through hidden input, and checks health plus every endpoint used by `plan AAPL`, bypassing the local cache. Only then does it save the key to the ignored `.env` file; a failed check preserves any previous key. Optional fundamentals/news failures are printed as data gaps, not reported as complete coverage. A successful plan includes:

- entry and reassessment zones built from the newest eligible served levels;
- a scenario invalidation and stop distance in ATR units;
- reward to reassessment in R;
- served hold, bounce, and hard-break measurements labelled `historical_base_rate`; and
- whole-share `stop_risk/v1` arithmetic with every input visible.

`plan` includes `sizing_inputs`, each omitted/defaulted input, and an `example_only` flag. Without all three sizing flags, the 100,000 capital / 0.005 risk fraction / 0.10 allocation-cap defaults are **example assumptions**, not your position size. To use your own arithmetic scenario:

```powershell
vstoolkit plan AAPL --capital 25000 --risk-fraction 0.005 --max-allocation 0.10
```

To install without a checkout (Git still required):

```powershell
python -m pip install git+https://github.com/Visualsectors/systematic-trading-toolkit.git
```

## Offline demo

The bundled fixture is fictional and needs no key or network:

```powershell
vstoolkit demo --offline --output toolkit-report.md
vstoolkit screen --offline --preset oversold_at_support --limit 10
vstoolkit plan ALFA --offline
```

The report contains all six outcomes in one Markdown file.

## What it produces

1. Ready-to-research watchlists from disclosed filters and deterministic rank rules.
2. Position sizes from either stop risk or portfolio slots, never a silent blend.
3. Research briefs that separate facts, interpretations, contrary evidence, and gaps.
4. Tailwind, headwind, and uncertainty flags with explicit reassessment conditions.
5. State-based events for risk changes, zone arrivals, invalidation breaches, provider failures, and recovery.
6. Conditional entry, invalidation, and reassessment geometry from served S/R levels.

### Screening

Live preset screens default to five upstream candidates to bound API use. Local rules and ranks apply only to that fetched set: this is not an exhaustive whole-market ranking, and local exclusions are not backfilled. For `trend_continuation`, the API selects positive-SMA50 candidates ordered by SMA50; the toolkit then checks and ranks by **20-session** momentum. It does not require positive 60-session returns. Coverage and any unfollowed cursor are disclosed in the output, including when no candidates pass.

```powershell
vstoolkit screen --preset near_support --limit 5
vstoolkit screen --preset oversold_at_support --limit 5
vstoolkit screen --preset trend_continuation --limit 5
```

The live provider starts with `POST /v1/screen`, then loads the fields needed to validate the returned names locally. The default limit is 5. A cold screen takes roughly `1 + 9 × returned tickers` requests, before extra pagination: 5 tickers need about 46 calls, but an explicit limit of 25 can need 226. Five is a safer starting point, not a guarantee against quota errors after other requests. A 429 stops the command and displays `Retry-After`; it does not silently retry or buy more calls. Wait before retrying; completed reads may be reused from the same-day cache.

The three presets disclose their filters in [the methodology](docs/METHODOLOGY.md). Distance is measured to the computed support-zone edge.

### Screener context and AI skill

After membership is frozen, `vstoolkit context` measures Price, Peers and Market in **pure Python**, with exact preset-skills0.5.0 fixture parity. A full fictional card is one command: `vstoolkit context --offline --format markdown`. Live: `vstoolkit context --ticker AAPL --card aapl-context.local.md`.

Live context retrieves Price/Market data and explicitly marks missing industry peers, weights, breadth and structured news linkages **not supplied**. Full-lane replay uses an authorized [dataset.v2](docs/DATA_CONTRACT.md#v2-optional-context-fields). It never calls a model, guesses peers or changes membership. Only optional machine-validated model cards require Node22+. See [context and grounding](docs/SCREENER_CONTEXT.md).

Plain-English filters are disclosed and bounded:

```powershell
vstoolkit screen --ask 'oversold above the 200' --offline
vstoolkit screen --ask 'golden cross state and price above $10' --tickers AAPL,KMI,JPM
vstoolkit screen --ask 'oversold with unusual volume' --interpret-only
```

The last request refuses before any network call: volume criteria are not wired in. Nothing is quietly dropped. Live custom screens require an explicit watchlist of at most five tickers; they do not imply whole-market coverage. See [supported grammar and defaults](screener/skills/compose-screen/references/grammar.md).

### Position sizing

The two methods answer different questions:

- `stop_risk/v1` caps whole shares by planned loss and maximum allocation.
- `portfolio_slots/v1` divides a batch into slots and uses inverse volatility only when every priced name has valid volatility.

```powershell
vstoolkit size-stop --capital 100000 --risk-fraction 0.005 --entry 100 --stop 95 --max-allocation 0.10
vstoolkit size-portfolio --tickers AAPL,MSFT --portfolio 100000 --intended-holdings 10
```

`0.005` means 0.5% of capital and `0.10` means 10%. Fractions above 5% risk or 50% allocation require interactive confirmation or `--yes`. Calculated loss excludes gaps, slippage, commissions, taxes, and borrow costs.

### Research and monitoring

```powershell
vstoolkit research --ticker AAPL --direction long --thesis "Margins improve while price holds structural support"
vstoolkit risk --ticker AAPL --direction long
vstoolkit monitor --ticker AAPL --direction long --state monitor-state.json
```

The monitor writes state atomically. It retains the original plan prices, so crossing the saved invalidation emits `invalidation_breached` even when new levels have moved. A provider failure becomes `evaluation_failed`; prior risks and plan prices remain active.

### Files and reports

```powershell
vstoolkit screen --data .\my-dataset.json --preset near_support
vstoolkit report --data .\my-dataset.json --output .\research-report.md
```

The strict file format is documented in [the dataset contract](docs/DATA_CONTRACT.md). Unknown fields, future-dated observations, duplicate evidence IDs, and missing evidence stance fail closed. UTF-8, UTF-8 with BOM, and BOM-marked UTF-16 files are accepted for Windows PowerShell interoperability.

## How to read the output

`p_hold_7d_pct` is a historical seven-day hold frequency; `exp_bounce_pct` and `hard_break_pct` are measured magnitudes in percentage points, not frequencies. The output retains the schema label `historical_base_rate`, but that label does not turn every member field into a rate. The API documents hold measurements from levels recomputed in 2026 (hindsight); they are not point-in-time strategy results or probabilities for the current setup.

Zones are conditional geometry, not fills or forecasts. A screen narrows research coverage; it does not establish expected return or suitability. Missing values remain missing, and Stage 1 API observations are non-point-in-time. Treat cited structured output as the audit record when an AI presents it.

## Live data scope and rights

The default host and signup surface are both `https://api.visualsectors.com`. Toolkit live workflows need your own API key; the API's separately documented limited demo key is not a substitute for account login or free-tier QA. The offline fixture remains key-free.

Production's **2.2.0** catalogue, checked 2026-10-02, publishes these allowances:

| Access | History window | Requests/minute | Requests/day | Requests/month |
| --- | --- | ---: | ---: | ---: |
| Free | 6 months | 60 | 1,000 | 5,000 |
| LinkedIn-approved Free | 3 years | 500 | 10,000 | 100,000 |
| Data API Pro | Up to 15 years | 1,000 | 25,000 | 500,000 |

The published row cap is 1,000 per response. Account-specific grants can differ; the [live catalogue](https://api.visualsectors.com/v1/docs.json), your account and response rate-limit headers remain authoritative. Ordinary Free is not eligible for call-pack top-ups in this catalogue; approved Free and Pro are. Do not work around a 404/410 by using withdrawn datasets. A successful run on an account with a custom grant does not prove ordinary Free entitlements.

Returned rows remain limited by retained source history and key entitlements. The adapter derives 20-session momentum, annualized 20-session volatility, and 20-session average dollar volume from available raw, unadjusted bars. If fewer than 21 valid sessions are returned, those derived fields remain null.

P/E comes from `/v1/fundamentals?view=metrics` (`pe_ratio`). Earnings-calendar data is withdrawn: `days_to_earnings` is always null, with a warning. Optional fundamentals/news outages produce explicit gaps. Unknown earnings timing or missing headlines must never be read as clearance of event risk. The `plan` JSON includes `data_warnings`; research and risk output retain the same limitations.

The API may be used to research, advise, or build decision tools under the applicable terms. Do not redistribute raw API values. Code and data rights are separate; connecting a dataset does not relicense it.

## Agent skills

Skills belong to their topical tools, not a separate root folder. Six existing skills include portable metadata and references:

| Tool | Bundled AI skill | Purpose or status |
| --- | --- | --- |
| Screener | [compose-screen](screener/skills/compose-screen/SKILL.md) | Disclose supported filters and defaults; refuse unexpressible conditions without weakening the request |
| Screener | [analyze-screener-context](screener/skills/analyze-screener-context/SKILL.md) | Interpret frozen candidates through Price, Peers, and Market evidence, including contrary narratives and gaps |
| Research | [build-research-thesis](research/skills/build-research-thesis/SKILL.md) | Develop or challenge a thesis without inventing facts or hiding contradictory evidence |
| Monitoring | [reassess-position](monitoring/skills/reassess-position/SKILL.md) | Explain changes against the original plan, preserving saved boundaries and unknown current status |
| Risk management | [review-risk](risk-management/skills/review-risk/SKILL.md) | Order flags by severity, mark unmeasured rules, and record review conditions without choosing inputs or actions |
| Support/resistance | [read-levels](support-resistance/skills/read-levels/SKILL.md) | Explain the nearest served levels, their measured history and clustering zones, without targets or exits |
| Position sizing | None by design | Deterministic arithmetic from user-chosen inputs, without an allocation agent |

Every topical tool except position sizing has a bundled skill; screener has two.

Install the Claude Code plugin from an authorized checkout with one PowerShell command (Claude Code must already be installed):

```powershell
& .\scripts\install-claude-plugin.ps1
```

It registers `visualsectors` and installs `systematic-trading-toolkit@visualsectors` in project scope; restart Claude Code and try `/systematic-trading-toolkit:compose-screen`. The manifest explicitly scans the skills inside `screener/`, `research/`, `risk-management/`, `monitoring/`, and `support-resistance/` ([custom skill-path reference](https://code.claude.com/docs/en/plugins-reference#fields)). Python installation is separate. This is a repository-hosted catalogue, not a claim of approval by Anthropic's official directory. See [plugin documentation](https://code.claude.com/docs/en/plugin-marketplaces).

For local plugin QA: `claude plugin validate .`, then start `claude --plugin-dir <absolute-checkout-path>` in a separate test project. Verify that all six existing skills appear once. Static manifest tests do not replace that installation check.

For Codex, copy the chosen complete skill directory into your project's `.agents/skills/`—for example, `screener/skills/compose-screen/` becomes `.agents/skills/compose-screen/`. Keep its `references/` and `agents/` together. The topical `skills/` locations are source bundles, not automatic Codex discovery locations ([official skills guidance](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)). For Cursor or another agent, attach the relevant `SKILL.md` as project instructions. Never paste an API key into an AI prompt.

The upgraded position-review skill also measures a named entry, cost basis or strike without selecting an action:

```powershell
vstoolkit measure --ticker AAPL --price 200 --kind strike
vstoolkit measure --ticker ALFA --price 100 --kind cost --offline
```

Distances to served levels are signed dollars/percent/ATR. Missing values stay null; historical rates read “held on N% of past tests.”

### Published prompt snapshot

[`prompts/`](prompts/README.md) publishes the system prompts that Visual Sectors' Alfred used on 1 October 2026 for the Support/Resistance explainer, the News + Sentiment explainer, the daily narrative cluster and the Options run explainer. This is a one-time snapshot: the files are not updated when Alfred's prompts change. They take closed, host-supplied evidence only: no SQL, browser, URL, warehouse, or HTTP client is embedded in a skill. Prompt text is CC BY 4.0 and its normalized SHA-256 is pinned by tests.

## Python API

```python
from visualsectors_toolkit import VisualSectorsProvider, build_level_plan

provider = VisualSectorsProvider()
row = provider.get("AAPL")
plan = build_level_plan(
    ticker=row.ticker,
    as_of=row.as_of,
    direction="long",
    current_price=row.price,
    atr=row.atr14,
    levels=row.levels,
)
```

Provider I/O is isolated from deterministic calculation modules. The live adapter uses the standard library, Bearer authentication, explicit `Retry-After` errors, and a per-day local cache. A cold ticker normally uses nine requests: levels, five individual technical indicators (ATR14, RSI14, SMA20/50/200), daily bar history, SEC metrics, and news. Login adds a health check and bypasses cached responses, so normally uses ten requests. Only daily bar history follows cursors, up to 60 rows; short history pages can add requests. Current levels are selected with `date=<today-UTC>&only_best=true&limit=100`. Each technical indicator and SEC metrics use `date=<today-UTC>&limit=1`; news uses `limit=25`. These current-evidence reads never follow a cursor, even on an empty first page; unexpected cursors produce visible incomplete-evidence warnings. `/v1/technicals` is an indicator catalogue in 2.2.0, not a bundled value feed. See [production retest steps](docs/LIVE_QA.md#3c-production-login-and-plans-bounded-current-evidence).

## Trust boundary

```text
Visual Sectors API or strict local JSON
                 |
                 v
          provider boundary
                 |
                 v
     deterministic calculation core
       | screen | levels | sizing |
       | research | risk | monitor |
                 |
                 v
       JSON / Markdown / AI display
```

Proprietary options-derived indicator implementations, production warehouse/regime methods, credentials, raw licensed datasets, entitlements, and broker execution stay outside this repository. The released screener context's basic regime and narrative classifiers are inspectable in the bundled source; they do not reproduce proprietary server-side data generation.

## Development and QA

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m pip check
python -m pip wheel --no-cache-dir --no-deps . --wheel-dir dist
python -m visualsectors_toolkit demo --offline --output toolkit-report.md
```

CI covers Windows, macOS, and Linux on Python 3.10–3.13. See [methodology](docs/METHODOLOGY.md), [limitations](docs/LIMITATIONS.md), [contribution guidance](CONTRIBUTING.md), and [security policy](SECURITY.md).

Live launch QA is separate from fixture tests: see [the API contract and real-key checklist](docs/LIVE_QA.md). Passing offline tests does not prove that production is deployed or that a free account can access the data.

## License

Code is MIT licensed. All README files, `docs/`, and the skills and references inside topical folders are CC BY 4.0. Dataset and API rights remain separate; see [LICENSE](LICENSE), [LICENSE-DOCS](LICENSE-DOCS), and [NOTICE](NOTICE).

This software supports research and education. It does not provide investment, legal, tax, or accounting advice.
