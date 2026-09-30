# Data and feature contract

The local context dataset is documented in `docs/SCREENER_CONTEXT.md`. It wraps
the fixed retrieval spec and evidence packet with dataset provenance. No live
connector or raw SQL is part of the toolkit port; G13 owns connector retrieval.
Do not manufacture a rich packet from one snapshot or silently call a different
host/provider. Separate spec/packet files are accepted for parity and authorized
replay, with `--retrieval-spec` and `--data`.

The engine is the unchanged preset-skills 0.5.0 core, compiled for Node 22+ and
shipped with source and hashes. It validates screen identity, candidate order,
retrieval hash, fixed policies, canonical times, source cutoffs/result lineage,
bars, effective peer membership, full-universe aggregates and optional fields.
Bars use raw OHLCV normalized only with split metadata available at the decision,
not a promise of vendor-adjusted closes. Stale or thin series remain disclosed.

Price uses up to 23 displayed sessions, at least 20 for an evaluable lane, and
253 bars for the full 252-session baseline. SPY and QQQ comparisons require the
same endpoints as the candidate; absent sessions are not shifted silently.

Industry comparisons exclude only the current candidate, not every other screen
candidate. SIC4 widens to SIC2 only under the released membership policy. Group
aggregates cover the complete eligible universe; bounded member examples do not
stand in for its breadth. Weighting needs point-in-time market-cap provenance.
The 40% largest-member and 60% top-three thresholds are product choices, not
scientific proof that a group will move a certain way.

Headline peers are supplied by retrieval: at least two distinct co-mentions in
90 days, relevance at least 0.5, at most eight peers and four actual topics per
peer, with bounded aligned price series. The model never supplies this universe.
Missing optional fields remain `not_supplied`; an empty valid peer list becomes
`none_found`. Invalid fields fail closed rather than silently becoming missing.

Leading/challenging narratives are code-selected from supplied clusters, using
SPY's direction, coverage and recent momentum. New York session-close alignment
measures coincident SPY returns, including daylight-saving time. It establishes
neither causation nor a prediction. Headline availability marked
`created_at_proxy` retains its risk code and cannot create Tier A support.
