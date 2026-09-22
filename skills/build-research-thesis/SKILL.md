---
name: build-research-thesis
description: Build or challenge an evidence-linked stock thesis with the Systematic Trading Toolkit. Use when a user asks to research a ticker, develop a thesis, examine technical/fundamental/news evidence, or identify contrary evidence and data gaps from a toolkit dataset.
---

# Build a research thesis

Use the toolkit's structured output as the factual boundary.

1. Obtain the ticker, falsifiable thesis, and an authorized `visualsectors-toolkit.dataset.v1` file. Use the bundled fixture only for a clearly labeled demonstration.
2. Run `vstoolkit research --data <dataset.json> --ticker <ticker> --thesis "<thesis>"`.
3. Check the dataset decision time, source, license, warnings, and whether it is synthetic before analyzing the result.
4. Present supplied facts, deterministic interpretations, contrary evidence, and coverage gaps as separate groups. Preserve each finding's evidence IDs.
5. Treat a missing section as a coverage gap. Do not infer that missing evidence supports the thesis.
6. State what new evidence would falsify or materially weaken the thesis. Tie it to cited observations or explicitly label it as a proposed research question.

Never invent news, fundamentals, levels, sources, or probabilities. Never describe a historical level metric as a forecast. Do not recommend a trade, claim suitability, or place an order.
