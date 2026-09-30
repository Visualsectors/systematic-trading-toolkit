---
name: build-research-thesis
description: Build or challenge an evidence-linked stock thesis with the Systematic Trading Toolkit. Use when a user asks to research a ticker, develop a thesis, examine technical/fundamental/news evidence, or identify contrary evidence and data gaps from a toolkit dataset.
---

# Build a research thesis

Use the toolkit's structured output as the factual boundary.

1. Obtain the ticker, falsifiable thesis and authorized data source. The live default uses the Visual Sectors API; use `--data <dataset.json>` for an authorized v1/v2 snapshot. Label bundled fixtures as fiction.
2. Run `vstoolkit research --ticker <ticker> --thesis "<thesis>"`, then `vstoolkit context --ticker <ticker>`. For files add `--data`; context requires dataset.v2 or a frozen evidence packet. Snapshot-only v1 cannot supply context history. Do not silently substitute demo context for a real ticker.
3. Check the dataset decision time, source, license, warnings, and whether it is synthetic before analyzing the result.
4. Present supplied facts, deterministic interpretations, contrary evidence, and coverage gaps as separate groups. Preserve each finding's evidence IDs.
5. Treat a missing section as a coverage gap. Do not infer that missing evidence supports the thesis.
6. State what new evidence would falsify or materially weaken the thesis. Tie it to cited observations or explicitly label it as a proposed research question.

7. Read [the context checklist](references/context-checklist.md). Fold leading and challenging narratives, SPY co-movement, weighted peers and headline-peer/business-line splits into contrary evidence and coverage gaps. A rising challenger adverse to the thesis is a named falsifier/review condition, not a causal claim. Missing live peers, caps, breadth or linkages are “not supplied,” never evidence of absence.
8. Follow [the shared wording list](references/wording.md). Every numerical claim must cite its emitted finding or context evidence ID. Separate proposed future checks from observed facts; never fabricate a future threshold.

Never invent news, fundamentals, levels, sources, or probabilities. Never describe a historical level metric as a forecast. Do not recommend a trade, claim suitability, or place an order.
