# API 2.2.0 contract and live launch QA

Offline tests are necessary, not launch evidence. Keep this repository private until the public host and a new **free** account pass the live steps below. Do not substitute an admin, Pro or pre-approved key.

## 1. Install from source

Follow the README clone, venv and `python -m pip install .` commands in a fresh directory. No PyPI package is currently published. Run:

```powershell
vstoolkit --version
vstoolkit --help
vstoolkit plan --help
vstoolkit size-stop --help
python -m unittest discover -s tests -v
python -m pip check
```

All subcommands' help paths are tested offline, including literal percent signs. The captured schema-only `tests/fixtures/visualsectors-openapi-2.2.0.json` checks every request used by login/plan against API 2.2.0 paths, parameter names and indicator IDs, plus the SEC `pe_ratio` field. It contains no licensed market values and does not make a network call during CI. Recorded response payloads are synthetic.

## 2. Confirm production is ready (no key needed)

```powershell
$apiContract = Invoke-RestMethod 'https://api.visualsectors.com/v1/openapi.json'
if ($apiContract.info.version -ne '2.2.0') { throw 'API 2.2.0 has not been promoted; do not launch.' }
Invoke-RestMethod 'https://api.visualsectors.com/v1/health'
curl.exe -sS 'https://api.visualsectors.com/v1/levels?ticker=AAPL'
```

Expected: health `ok=true`; unauthenticated levels has HTTP 401, `error=missing_api_key` and `get_key=https://api.visualsectors.com/signup`. The API repo additionally has a keyless release gate: `node scripts/check-toolkit-public-contract.mjs`. It fails closed on an old contract or missing signup guidance and does not deploy anything.

On 2026-09-30, the public host still reported `2.1.0-dev` and omitted the 401 signup link, even though API `main` already contained that link. That is a deployment gap, not a reason to restore withdrawn views. Re-run this check after promotion.

## 3. Use a genuinely free key in a chat-independent terminal

Get a new free key at the public signup URL. Never paste it into chat, a command argument, a screenshot, a test fixture or a Git file. Start in the freshly cloned project directory and unset only a stale API-host override, if present:

```powershell
Remove-Item Env:VISUALSECTORS_API_BASE_URL -ErrorAction SilentlyContinue
vstoolkit login
vstoolkit plan AAPL --capital 25000 --risk-fraction 0.005 --max-allocation 0.10
vstoolkit plan MSFT --capital 25000 --risk-fraction 0.005 --max-allocation 0.10
vstoolkit research --ticker AAPL --thesis "Price holds structural support while margins remain resilient"
vstoolkit risk --ticker AAPL --direction long
vstoolkit size-portfolio --tickers AAPL,MSFT --portfolio 100000 --intended-holdings 10
vstoolkit monitor --ticker AAPL --direction long --state .\monitoring\aapl-state.local.json
vstoolkit screen --preset near_support --limit 5
```

Pace commands against the response allowance. Login normally needs ten requests; a cold plan needs nine; a five-ticker screen can need 46 before pagination. A 429 must show a wait time, not a traceback. Wait before retrying. No tool here automatically purchases calls.

Inspect every result:

- AAPL/MSFT are real tickers, not fictional fixture symbols. The data is sourced from the public host, not an alternative host.
- Entry/stop/reassessment geometry is conditional. If inputs or a suitable zone are absent, explicit abstention is valid; a fabricated price is not.
- P/E is from SEC metrics `pe_ratio`. Earnings timing remains null with an explicit warning; it never falls back to a retired calendar.
- `data_warnings` remains visible in plan output. Missing news/fundamentals are gaps; authentication or quota failures are errors.
- Whole-share arithmetic agrees with `min(floor(capital × risk / abs(entry − stop)), floor(capital × max_allocation / entry))` when a plan is available. Gaps, fees and slippage are excluded.
- With a bogus/revoked key, the CLI exits 2, contains no key, and ends its authentication message with `run: vstoolkit login`.
- Failed login preserves the previous `.env` key. Successful login never prints the new one. Confirm `.env` is ignored before any commit.
- Multi-ticker sizing succeeds when source observation timestamps differ; no snapshot is placed after its manifest decision time.
- The monitor retains its saved invalidation and deduplicates unchanged events. Same-day cached reads are not proof of fresh intraday coverage.

The client-hardening regression tests now cover credential-separated caches, HTTPS-only hosts, refusal to forward credentials through redirects, common-cutoff news filtering and multi-ticker timestamp ordering. Recheck these boundaries in a fresh install; passing unit tests does not establish production entitlement behavior.

## 3a. Context and skills gate

```powershell
vstoolkit context --ticker AAPL --format markdown
vstoolkit context --ticker KMI --format markdown
vstoolkit context --ticker JPM --format markdown
vstoolkit screen --ask 'oversold above the 200' --tickers AAPL,KMI,JPM
vstoolkit screen --ask 'oversold with unusual volume' --interpret-only
vstoolkit measure --ticker AAPL --price 200 --kind strike
claude plugin validate .
```

Pace each live command; context normally has seven logical reads but daily-bar pagination can multiply them. Refused screen exits 2 before authentication/network. Verify every figure is present under its emitted evidence ID, every unavailable peer/cap/breadth/linkage lane says “not supplied,” and no real ticker is replaced with ALFA. News/market proxy and non-PIT caveats must survive card rendering. Named-price distances are signed; nulls stay null and the exact closing sentence is retained.

The top30 jargon cases each have a test. Validation of plugin JSON alone is not an installation test: after public release, install in a clean Claude Code project, verify four skills load and exercise their namespaced commands. Do not claim marketplace validation passed unless the actual CLI was available.

## 4. Record launch evidence

Record the toolkit commit, API deployment version/commit, date, Python/OS version, observed free-tier limits, commands and exit codes. Retain only redacted derived summaries and warnings in a private QA record, not raw licensed API rows. A contract fixture, green CI or dev-host test is not proof that the production/free-key gate passed.

Do not flip repository visibility, publish a package or claim live launch completion until the production checks above pass and Vlad authorizes release.
