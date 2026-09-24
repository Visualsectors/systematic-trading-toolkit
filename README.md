# Systematic Trading Toolkit

**S/R levels with measured hold, bounce and break rates**—plus screening, position sizing, evidence-linked research, risk registers, and change-based monitoring for US-listed equities.

This is an inspectable, dependency-free Python toolkit for builders using Claude Code, Codex, Cursor, or their own automation. It connects to the Visual Sectors Data API with a free key, keeps credentials outside prompts and shell history, and contains no broker connection or order execution.

## Run it on AAPL

Requirements: Python 3.10 or newer. In PowerShell:

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install visualsectors-toolkit
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

`login` opens signup, reads the key through hidden input, saves it to the ignored `.env` file, and verifies the service plus one AAPL levels request. A successful plan includes:

- entry and reassessment zones built from the newest eligible served levels;
- a scenario invalidation and stop distance in ATR units;
- reward to reassessment in R;
- served hold, bounce, and hard-break measurements labelled `historical_base_rate`; and
- whole-share `stop_risk/v1` arithmetic with every input visible.

Until the package is published, install the repository checkout instead:

```powershell
python -m pip install .
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
vstoolkit screen --preset near_support --limit 10
vstoolkit screen --preset oversold_at_support --limit 10
vstoolkit screen --preset trend_continuation --limit 10
```

The live provider starts with `POST /v1/screen`, then loads the fields needed to validate the returned names locally. The three presets disclose their filters in [the methodology](docs/METHODOLOGY.md). Distance is measured to the computed support-zone edge.

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

The default host and signup surface are both `https://api.visualsectors.com`.

- Anonymous free access: 500 requests/minute, 10,000/day, 100,000/month, and a 6-month history allowance.
- LinkedIn-approved free access: the same request allowance and a 3-year history allowance.
- Capacity access: 1,000 requests/minute, 25,000/day, 500,000/month, and a 15-year history allowance.

Returned rows remain limited by retained source history. The August 2026 audit found daily bars beginning on 2025-08-11, technicals beginning on 2021-01-04, and shorter coverage for some fundamentals and news views. The live adapter therefore derives 20-session momentum, annualized 20-session volatility, and 20-session average dollar volume from available raw, unadjusted bars and carries that limitation in every snapshot.

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

Provider I/O is isolated from deterministic calculation modules. The live adapter uses the standard library, Bearer authentication, cursor paging, `Retry-After`, and a per-day local cache. One fully hydrated ticker normally uses about six API requests before cache hits.

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

## License

Code is MIT licensed. README, `docs/`, and `skills/` are CC BY 4.0. Dataset and API rights remain separate; see [LICENSE](LICENSE), [LICENSE-DOCS](LICENSE-DOCS), and [NOTICE](NOTICE).

This software supports research and education. It does not provide investment, legal, tax, or accounting advice.
