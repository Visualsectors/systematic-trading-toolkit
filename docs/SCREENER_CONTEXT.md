# Screener context computation and skill

The optional `vstoolkit context` command ports preset-skills 0.5.0 from
vs-intelligence commit `863489f2b111fe88ab7fd3827413cff46cda8f49`. It computes
Price, Peers and Market over a frozen screen, constructs the exact grounded
analyst request and validates/renders a supplied model answer. It never makes
a model call, buys calls or changes membership. The optional live adapter retrieves
authorized API data separately from the pure feature calculation.
The model interprets; code measures and owns displayed facts.

Python 3.10+ is enough for computed JSON and Markdown observation cards. Pure
Python functions preserve the released arithmetic and evidence ordering, checked
field for field against the golden fixture. **Only optional model-request/answer
validation needs Node.js 22+**. Its released engine/source are bundled; no npm
packages are required at runtime.

## Run the fictional parity example

From a source checkout, after the normal toolkit installation:

```powershell
vstoolkit context --offline --format markdown
vstoolkit context --offline --card context.local.md
vstoolkit context --retrieval-spec .\tests\fixtures\screener-context-0.5.0\retrieval-spec.json --data .\tests\fixtures\screener-context-0.5.0\evidence-packet.json
```

The fixture is synthetic: ALFA, its peer identities, bars and example.test
headlines are fictional. It is not licensed live data or a launch proof. JSON
output matches `computed-context.json` field for field, including ordered
evidence, risk codes, optional weighted/headline peers and narrative roles.

The CLI supports separate spec/packet files for parity and authorized replays.
Normal files use additive [dataset.v2](DATA_CONTRACT.md#v2-optional-context-fields).
The legacy context envelope below remains supported for authorized replays:

| Root field | Contract |
| --- | --- |
| `schema_version` | `visualsectors-toolkit.context-dataset.v1` |
| `dataset_id` | Non-empty dataset identity |
| `synthetic` | Boolean; do not relabel fixture values as real |
| `license`, `source` | Non-empty declared data rights and provenance |
| `decision_time` | Exact canonical decision instant shared by spec and packet |
| `retrieval_spec` | Released `screener_context_retrieval_spec.v2` with fixed policies |
| `evidence_packet` | Released `screener_context_evidence_packet.v2`, including true lineage |

Unknown root fields fail closed. Files accept UTF-8/BOM or BOM-marked UTF-16,
are capped at 16 MiB each, and reject duplicate object keys and non-finite
numbers. Total engine input is capped at 64 MiB and execution at 30 seconds.
The engine inherits no API credentials or `NODE_OPTIONS` injection flags.

The old `visualsectors-toolkit.dataset.v1` remains unchanged. Its snapshots do
not contain historical OHLCV, effective memberships, full-universe aggregates
or benchmark paths. It is deliberately rejected by `context`, not expanded
with invented data.

## Live Price and Market with explicit gaps

```powershell
vstoolkit login
vstoolkit context --ticker AAPL --format markdown
vstoolkit context --ticker KMI --card kmi-context.local.md
vstoolkit context --ticker JPM
```

This fetches candidate and SPY/QQQ/IWM/RSP daily bars plus candidate/SPY-linked
news. Each paginated response is metered; pace calls using current entitlements.
Live data is non-PIT; SPY-linked news is only a market proxy. Missing industry
membership, market caps, breadth and structured news linkages mean **not supplied**.
Peers abstain; no taxonomy or co-mentions are invented. Missing benchmark
entitlements downgrade the Market lane; authentication/quota failures remain errors.
The card's coverage section exposes proxy/split/lineage limitations. Client read
fingerprints are not warehouse lineage evidence. Full-lane historical work needs
licensed PIT datasets or a future server-side evidence endpoint; this CLI does
not pretend that endpoint exists.

The ordinary Markdown card is an evidence-linked observation summary, not a
validated A/B/C judgment. An agent adds tailwinds, headwinds and proposed review
conditions using cited facts; a machine-validated tier needs the frozen analyst
metadata and strict request/response path below.

## Feature coverage

- Price: 5/10/21/60-session returns, acceleration, drawdown/run-up, efficiency,
  one-year pace/volatility percentiles, gaps and follow-through, location,
  range/volume expansion and bounded patterns. At least 20 displayed sessions
  are needed; the full baseline requires 253 bars.
- Peers: effective SIC4/SIC2 membership, aligned full-universe median, breadth,
  dispersion, agreement, excess and representative leaders/laggards. Optional
  equal/cap-weight returns and concentration distinguish the group from giants.
  Headline peers compare supplied co-mentions by actual story/business-line
  theme, including names outside the static industry.
- Market: SPY and QQQ comparisons across all three windows, IWM/RSP, breadth,
  safe VIX when supplied, aligned correlation/beta and direction versus SPY.
  Leading and challenging narratives have coverage momentum, New York
  session-aligned SPY reactions and candidate theme linkage. These are timing
  and context, never causal estimates.

Absent optional fields remain `not_supplied`; valid empty headline peers are
`none_found`. Invalid optional fields are rejected. Source cutoffs, row/query
hashes, canonical timestamps, point-in-time bars and aggregate consistency are
validated before any feature is returned.

## Grounded model request and rendered card

Create `analysis.json` from the frozen screen, with exactly these metadata keys:
`schema_version` (`screener_context_analysis_input.v2`), `analysis_release`
(`screener-context-analyst-v2.6.0`), `retrieval_spec_hash`, `decision_time`,
`as_of_session`, `screen`, `performance_12m`, and `candidates`.
`screen` retains the exact identity, definition hash, name, thesis, side,
filter definition and primary holding period. `candidates` retains the frozen
order, matched metrics and gate/risk codes. Custom screens use a null prior.
Do not include model-derived tiers, precomputed context, eligibility lists or
numeric facts in this metadata: the engine builds them from validated evidence.

```powershell
vstoolkit context --data .\context-dataset.json --analysis-input .\analysis.json | Set-Content -Encoding utf8 .\request.local.json
```

The request contains the full system prompt, user JSON string, strict response
schema, evidence/numeric atom indices and exact input/request hashes. Use those
exact three request fields with your authorized model/service; no provider SDK
or automatic paid model call is included. Retain the actual raw response and
saved dispatched request. Do not sort/rewrite the bound request's object keys.

```powershell
vstoolkit context --data .\context-dataset.json --analysis-input .\analysis.json --model-output .\raw-response.local.json --request .\request.local.json
```

Only this final code-rendered output is a validated card. Request drift,
invalid interpretations and unjustified tier promotion fail. Model draft prose
and draft citations are non-authoritative; the released core normalizes them
and supplies its own rendered text/citations, so draft instructions or invented
citations cannot become displayed evidence. A/B/C describes contextual thesis
fit. Missing critical evidence is abstention, not a bearish tier. Historical
screen priors and proxy-news support cannot create Tier A.

For the released example, tests reconstruct a raw draft using the golden card's
closed choices and minimal citations. The renderer must reproduce every field
of `parsed-decision.json`; tests do not treat the already-rendered card as a raw
model response. `analyst-request-user.json` is also checked field for field.

## Source provenance maintenance and licensing

`src/visualsectors_toolkit/context_engine/source/` contains the six unchanged
released modules and a narrow export adapter. `manifest.json` records upstream
commit, releases and source/fixture SHA-256 hashes. `engine.mjs` is the generated
runtime; `run.mjs` is the bounded local adapter. The fixture files are whitespace
normalized only; all five JSON values match G13's supplied parity files.

Maintenance builds need esbuild, **not** runtime users. Use an existing esbuild
installation outside synced folders, or install a maintenance environment in a
non-synced workspace, then run:

```powershell
node scripts/build-context-engine.mjs --esbuild C:\verified\non-synced\node_modules\esbuild\lib\main.js
python -m unittest discover -s tests -v
```

The build rejects released-source hash drift. Updates require reviewed source,
release/hash changes and fresh parity fixtures; do not edit generated output
or replace golden values to hide a regression. Runtime tests require no network.
The engine, adapter and tests are MIT; this guide and the skill are CC BY 4.0,
with attribution to Visual Sectors' preset-skills 0.5.0. Connected datasets keep
their own rights and must not be committed or redistributed merely because the
code is public.

## Public release gate

This port does not change repository visibility or deploy the API. D428 still
requires the public `api.visualsectors.com` contract and a genuinely free key
to pass real-ticker `login`/`plan` QA. On 30 September 2026, the host still reports
`2.1.0-dev`; offline parity is not that proof. The repository must become public
after those gates and release review, **before the screener video is published**.
See [live QA](LIVE_QA.md). Do not describe the private repo as available to viewers.
