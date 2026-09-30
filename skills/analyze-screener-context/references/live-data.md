# Live coverage and consent

The public origin and signup host are https://api.visualsectors.com. Keep API keys in environment/ignored .env, never prompts or command arguments.

Computed context is dependency-free Python. Only the optional frozen model-request and model-answer validation paths need Node 22+. History uses the server's entitlement floor and at most 254 recent rows per series; a free account's shorter window leaves one-year baseline fields unavailable rather than requesting forbidden history.

Until a server-side evidence endpoint exists, context fetches daily bars for the ticker and SPY/QQQ/IWM/RSP plus ticker/SPY news. Pagination increases request count. Stage 1 responses are date-bounded, **not point in time**; do not use them to simulate historical availability. A free key may cap history, requests or endpoints; response entitlements are authoritative. Missing history downgrades coverage.

Industry membership, capitalization weights, market breadth, structured topics, relevance and headline-peer linkages are not supplied. Peers must abstain. SPY-linked news is explicitly a proxy, not comprehensive market coverage. Keyword topics are a deterministic text classifier, not provider linkage. Client request/result fingerprints are not upstream lineage proof.

Use a licensed frozen dataset.v2 for full-lane context. The bundled ALFA example is fictional, never a real-ticker comparison. A machine-validated tier also requires frozen analyst metadata and the unchanged dispatched model request; the simple Markdown card contains observations, not a validated tier.
