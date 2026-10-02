# API 2.2.0 contract and live launch QA

Offline tests are necessary, not production evidence. The full ordinary-Free test below uses a new **free** account: an admin, Pro, demo or pre-approved key does not prove that tier.

Release scope (2026-10-02): the release owner accepted the existing production `login` and AAPL/MSFT plan checks without a newly registered Free-account retest. The tester's account is recorded as approved with a custom history grant, and those checks preceded the final level-display guard. Keep that scope explicit: the latest client guard is covered by synthetic regressions; final ordinary-Free entitlement behavior and full chat-plugin installation remain unverified. This exception does not turn the remaining checklist into completed evidence.

Beta hardening (2026-10-02): the independently built and installed wheel passes 196 tests. New regressions cover a positive-20/negative-60-session trend candidate, bounded/empty live screen pages, five-candidate defaults, explicit sizing assumptions and stale offline monitoring with unchanged saved state. All six skills pass static validation; their supplied files are unchanged. Local wheel tests are not a new authenticated production-key or logged-in Claude test. CI results on the exact merged commit remain a separate release gate.

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

Checked 2026-10-02: the public host returns health `ok=true`, contract `2.2.0`, and the expected 401 signup guidance. The API connector's level-bounce guard was promoted on 2026-10-01 and api-mcp refreshed afterwards. These keyless and deployment checks do not establish the limits or data access of a particular key. Re-run the commands rather than treating this dated observation as a permanent guarantee.

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

Pace commands against the response allowance. Login normally needs ten requests; a cold plan needs nine; a five-ticker screen can need 46 before daily-bar pagination. Current levels, technicals, fundamentals metrics and news never follow cursors. A 429 must show a wait time, not a traceback. Wait before retrying. No tool here automatically purchases calls.

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

The top30 jargon cases each have a test. Validation of plugin JSON alone is not an installation test: after public release, install in a clean Claude Code project, verify six skills load and exercise their namespaced commands. Do not claim marketplace validation passed unless the actual CLI was available.

## 3b. Rehearsal login: bounded current levels

Login and cold plans request `/v1/levels?ticker=AAPL&date=<today-UTC>&only_best=true&limit=100` exactly once. `date` is a ceiling, not an exact session date: weekends and holidays still return the latest eligible session. `only_best=true` selects the published support/resistance pair for each approach (currently up to ten rows on a session). A levels cursor is never followed, including on a short or empty first page; an unexpected cursor is reported as incomplete evidence. Only the newest level date on or before the common source cutoff is retained. Authentication and rate-limit failures still fail login, without replacing the existing key.

Reinstall the reviewed toolkit source into the existing virtual environment before retesting; an already installed wheel will not pick up the fix merely because the source checkout changed. In a separate terminal, set `VISUALSECTORS_API_BASE_URL` to `https://api.rehearsal.visualsectors.com`, then run `vstoolkit login` and an AAPL plan with a rehearsal key entered only at the hidden prompt. Repeat with Pro and a genuine free key. Inspect rehearsal logs: one levels request with the date, `only_best` and `limit`, and no levels cursor requests. Return the host override to its previous value afterwards. This is rehearsal evidence only, not the production/free-key launch gate.

**C0 API check:** rehearsal's 2.2.0 OpenAPI says an undated `/v1/levels` request is the latest eligible snapshot. The report of roughly 100 cursor pages does not alone establish whether those rows span dates. With an existing rehearsal key, compare the distinct `level_date` values in the first two pages of the undated request and the bounded selected-levels request above. Retain only dates/counts and the API/connector deployment commits, never the key or raw market values. If the undated route crosses dates, report an API/deployment defect to C0 separately; the toolkit bound is not a server-side fix. No full-history pagination is needed for this check.

## 3c. Production login and plans: bounded current evidence

This extends the levels-only fix in PR #4. With the reviewed fix installed, login and plans read:

| Source | Query bound | Cursor handling |
| --- | --- | --- |
| Selected levels | `date=<today-UTC>&only_best=true&limit=100` | First page only |
| Each of ATR14, RSI14, SMA20/50/200 | `date=<today-UTC>&limit=1` | First page only; latest row only |
| Fundamentals metrics | `view=metrics&date=<today-UTC>&limit=1` | First page only |
| News headlines | `view=headlines&limit=25` | First page only |
| Daily timeseries | `view=daily&to=<today-UTC>&limit=60` | Existing `max_rows=60` retained |

Every query also supplies the ticker. An unexpected current-evidence cursor is a visible incomplete-evidence warning, never an instruction to fetch history. Empty technicals stay null; empty optional evidence is a disclosed gap. A response exceeding its requested row limit is rejected: core technicals fail closed; optional metrics/news become explicit gaps. HTTP 401 and 429 still stop the command. No missing latest row is replaced by historical cursor data.

To retest the reviewed branch, record its exact commit and reinstall into your existing virtual environment from that checkout:

```powershell
python -m pip install --no-cache-dir --force-reinstall .
Remove-Item Env:VISUALSECTORS_API_BASE_URL -ErrorAction SilentlyContinue
vstoolkit login --no-open
vstoolkit plan AAPL
vstoolkit plan MSFT
```

Enter the **production free key** only at the hidden login prompt. Allow for quota limits between commands; do not loop on 429. The `bounded pagination allowance` error must not recur for technicals, metrics or news. In API request logs, check one request per current-evidence endpoint, the query bounds above, and no continuation requests for those endpoints. Login bypasses caches; plans may reuse same-day cached responses. Retain only toolkit/API commits, host, date, request counts, query names, exit codes and warning summaries, not keys or raw licensed rows.

The provider regressions cover 0/1/10/100 advertised pages for **each** indicator, metrics and news, both login verification and plans, including empty first pages with cursors. Separate tests enforce UTC/weekend ceilings, first-page row limits, null/data-gap behavior, authentication/quota propagation, and the unchanged timeseries row cap.

**G14.1 API investigation:** determine independently whether an undated individual indicator route, such as `/v1/technicals/atr14?ticker=AAPL&limit=1`, serves one latest observation or historical pagination. Compare with the explicitly dated request above; the `/v1/technicals` catalogue itself is not the value endpoint. Report dates/counts, cursors and deployment commit only. The client fix neither proves nor repairs the API's undated behavior. Route that finding to G14.1 and the merge desk separately; do not require a full-history fetch to diagnose it.

## 3d. Production plan output and implausible level inputs

After installing the reviewed fix, rerun AAPL/MSFT plans on production. In each of `entry_historical_base_rates` and `reassessment_historical_base_rates`, verify every `(side, level_type, level_price)` occurs once and its `approaches` array lists the contributing approaches. Different sides/types/exact source prices must remain separate. Conflicting historical values must be null with a plan note, not averaged.

Before the source correction, any supplied `exp_bounce_pct > 100` must produce a level-naming `data_warnings` entry and must not appear in either zone's members or affect its score. Tests reproduce the reported AAPL donchian 328.7 / 4,420 and MSFT pivot 497.09 / 33,196,824,404 cases. If the connector has already masked those fields to null, do not expect the raw-outlier client warning: the permanent toolkit guard is exercised by the synthetic tests, while the production response now contains a missing statistic. Do not infer that missing bounce/reward data has been repaired at source.

Exactly 100, zero and missing bounce values remain permitted by this gate. If all current levels are rejected, insufficient-data output is valid; using older rejected-session substitutes is not. The latest-route fix is now promoted, so do not dismiss recurring per-indicator cursor warnings as normal: the client remains bounded and warns, but report them with the host and deployment version for API investigation. Return the toolkit/API commits, exit codes and redacted warning summaries; never include credentials or raw licensed tables.

## 4. Record launch evidence

Record the toolkit commit, API deployment version/commit, date, Python/OS version, observed free-tier limits, commands and exit codes. Retain only redacted derived summaries and warnings in a private QA record, not raw licensed API rows. A contract fixture, green CI or dev-host test is not proof that the production/free-key gate passed.

Repository publication follows the release owner's authorization and its explicitly accepted QA scope. Do not claim the full checklist passed when a check was waived or not run. This release does not publish a PyPI package or the screener video.
