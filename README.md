# Systematic Trading Toolkit

[![CI](https://github.com/Visualsectors/systematic-trading-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/Visualsectors/systematic-trading-toolkit/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](pyproject.toml)
[![Code license: MIT](https://img.shields.io/badge/Code-MIT-15803D)](LICENSE)
[![Docs license: CC BY 4.0](https://img.shields.io/badge/Docs-CC_BY_4.0-64748B)](LICENSE-DOCS)

**S/R levels with measured hold, bounce and break rates**—plus screening, position sizing, evidence-linked research, risk registers, and change-based monitoring for US-listed equities.

This is an inspectable, dependency-free Python toolkit for builders using Claude Code, Codex, Cursor, or their own automation. It connects to the Visual Sectors Data API with a free key, keeps credentials outside prompts and shell history, and contains no broker connection or order execution.

**[Get a free Visual Sectors API key](https://api.visualsectors.com/signup)** · [API documentation](https://api.visualsectors.com) · [Try the offline demo](#offline-demo) · [Review the methodology](docs/METHODOLOGY.md)

## Choose a tool

All six tools have their own top-level folder. Open one for its quickstart, runnable scripts, calculation source, and reference tests:

| Tool folder | Outcome | Installed command |
| --- | --- | --- |
| [screener/](screener/) | Filtered, ranked watchlists with exclusion reasons | `vstoolkit screen` |
| [position-sizer/](position-sizer/) | Whole-share stop-risk sizes or portfolio-slot allocations | `vstoolkit size-stop` / `size-portfolio` |
| [research/](research/) | Evidence-linked briefs, contrary evidence, and data gaps | `vstoolkit research` |
| [risk-management/](risk-management/) | Tailwinds, headwinds, uncertainty, and reassessment triggers | `vstoolkit risk` |
| [monitoring/](monitoring/) | Changes in risks and saved plan boundaries | `vstoolkit monitor` |
| [entry-exit/](entry-exit/) | Conditional entry, invalidation, and reassessment zones | `vstoolkit plan` |

The folder scripts call the same tested package as `vstoolkit`; calculations are not duplicated. Shared implementation lives in [`src/visualsectors_toolkit/`](src/visualsectors_toolkit/), documentation in [`docs/`](docs/), and optional AI instructions in [`skills/`](skills/).

## Use the Visual Sectors API for live data

The Visual Sectors API is the built-in live provider: one key connects screening, S/R levels, daily prices, technical readings, SEC metrics, and news. Start with the fictional offline examples, then connect your own free key through `vstoolkit login`.

- **Get started:** [free-key signup](https://api.visualsectors.com/signup), followed by hidden-input login. Never paste the key into a prompt.
- **Know the limits:** live calls are metered; [published entitlements](https://api.visualsectors.com/v1/docs.json) and response headers are authoritative. Begin with a small watchlist.
- **Keep control:** the code is MIT licensed. Use your own dataset with `--data` or implement another provider; connecting to our API is not mandatory.

Live launch is pending while the public host serves the older contract. The code targets API 2.2.0; [live QA](docs/LIVE_QA.md) must pass before public release. The offline examples work without signup or a network connection.

## Run it on AAPL

Requirements: Python 3.10 or newer and Git. **Live launch is pending:** this client needs API 2.2.0 on the public host; production still serves the older contract as of 2026-09-30. The offline demo works now. In PowerShell, start in a project directory outside synced folders such as OneDrive:

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

The repository is currently private, so cloning requires authorized GitHub access. There is no PyPI release yet: do not use `pip install visualsectors-toolkit`. After the repository becomes public, this same source install works without GitHub authentication.

`login` opens signup, reads the key through hidden input, and checks health plus every endpoint used by `plan AAPL`, bypassing the local cache. Only then does it save the key to the ignored `.env` file; a failed check preserves any previous key. Optional fundamentals/news failures are printed as data gaps, not reported as complete coverage. A successful plan includes:

- entry and reassessment zones built from the newest eligible served levels;
- a scenario invalidation and stop distance in ATR units;
- reward to reassessment in R;
- served hold, bounce, and hard-break measurements labelled `historical_base_rate`; and
- whole-share `stop_risk/v1` arithmetic with every input visible.

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

```powershell
vstoolkit screen --preset near_support --limit 5
vstoolkit screen --preset oversold_at_support --limit 5
vstoolkit screen --preset trend_continuation --limit 5
```

The live provider starts with `POST /v1/screen`, then loads the fields needed to validate the returned names locally. Start with `--limit 5` on a free key. A cold screen takes roughly `1 + 9 × returned tickers` requests, before extra pagination: 5 tickers need about 46 calls, but 25 can need 226. The default limit is 25, not a guarantee that a free key can hydrate it in one burst. A 429 stops the command and displays `Retry-After`; it does not silently retry or buy more calls. Wait before retrying; completed reads may be reused from the same-day cache.

The three presets disclose their filters in [the methodology](docs/METHODOLOGY.md). Distance is measured to the computed support-zone edge.

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

Historical hold, bounce, and break rates describe the served level family; they are not probabilities for the current setup. Zones are conditional geometry, not fills or forecasts. A screen narrows research coverage; it does not establish expected return or suitability. Missing values remain missing, and Stage 1 API observations are non-point-in-time. Treat cited structured output as the audit record when an AI presents it.

## Live data scope and rights

The default host and signup surface are both `https://api.visualsectors.com`. Every live request needs an API key; there is no anonymous live tier or public demo-data endpoint. The offline fixture remains key-free.

Production's published contract, checked 2026-09-30, is still `2.1.0-dev`: a free key has **60 requests/minute, 1,000/day, 5,000/month and a 30-day levels-history window**. Its LinkedIn tier is documented as 1,000/minute, 10,000/day, 100,000/month and five years of levels history. These are the served figures, not a promise of unreleased tiers. Consult [the live catalogue](https://api.visualsectors.com/v1/docs.json) and response rate-limit headers for the current offer and your key's limits.

This client targets the **2.2.0 contract**. That release documents six months of free history at the same 60/1,000/5,000 request limits; LinkedIn-approved free access has 500/10,000/100,000 calls and three years; Data API Pro has 1,000/25,000/500,000 calls and up to 15 years. These newer figures are not yet production entitlements. The repo stays private until 2.2.0 is promoted to the public host and `login` plus real-ticker plans work with a genuinely free key. Do not work around a 404/410 by using withdrawn datasets.

Returned rows remain limited by retained source history and key entitlements. The adapter derives 20-session momentum, annualized 20-session volatility, and 20-session average dollar volume from available raw, unadjusted bars. If fewer than 21 valid sessions are returned, those derived fields remain null.

P/E comes from `/v1/fundamentals?view=metrics` (`pe_ratio`). Earnings-calendar data is withdrawn: `days_to_earnings` is always null, with a warning. Optional fundamentals/news outages produce explicit gaps. Unknown earnings timing or missing headlines must never be read as clearance of event risk. The `plan` JSON includes `data_warnings`; research and risk output retain the same limitations.

The API may be used to research, advise, or build decision tools under the applicable terms. Do not redistribute raw API values. Code and data rights are separate; connecting a dataset does not relicense it.

## Agent skills

Two optional skills are included:

- `build-research-thesis` keeps an AI inside cited evidence and makes contrary evidence visible.
- `reassess-position` interprets monitor events without replacing the saved invalidation.

Install them for Claude Code in PowerShell:

```powershell
$profileRoot = [Environment]::GetFolderPath('UserProfile')
New-Item -ItemType Directory -Force (Join-Path $profileRoot '.claude\skills') | Out-Null
Copy-Item -Recurse -Force .\skills\build-research-thesis (Join-Path $profileRoot '.claude\skills\build-research-thesis')
Copy-Item -Recurse -Force .\skills\reassess-position (Join-Path $profileRoot '.claude\skills\reassess-position')
```

For Codex, use the same commands with `.codex\skills` as the destination. In Cursor or another agent, attach the relevant `SKILL.md` as project instructions. Never paste an API key into an AI prompt.

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

Provider I/O is isolated from deterministic calculation modules. The live adapter uses the standard library, Bearer authentication, cursor paging, explicit `Retry-After` errors, and a per-day local cache. A cold ticker normally uses nine requests: levels, five individual technical indicators (ATR14, RSI14, SMA20/50/200), daily bar history, SEC metrics, and news. Login adds a health check and bypasses cached responses, so normally uses ten requests. Pagination can add more. `/v1/technicals` is an indicator catalogue in 2.2.0, not a bundled value feed.

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

Proprietary options-derived indicators, market-regime methods, credentials, raw licensed datasets, entitlements, and broker execution stay outside this repository.

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

Code is MIT licensed. All README files, `docs/`, and `skills/` are CC BY 4.0. Dataset and API rights remain separate; see [LICENSE](LICENSE), [LICENSE-DOCS](LICENSE-DOCS), and [NOTICE](NOTICE).

This software supports research and education. It does not provide investment, legal, tax, or accounting advice.
