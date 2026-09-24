---
name: reassess-position
description: Reassess a monitored stock scenario when evidence, risk, or levels change. Use when a user asks whether an existing position thesis needs review, wants to compare a new toolkit snapshot with prior monitor state, or needs explicit invalidation and follow-up questions without broker execution.
---

# Reassess a position scenario

Require the existing thesis or plan, ticker, authorized current dataset, and prior monitor-state file. If any is missing, identify the gap before drawing a conclusion.

1. Run `vstoolkit monitor --ticker <ticker> --direction <long-or-short> --state <state.json>` (or add `--data <dataset.json>` for an authorized file).
2. Read only emitted changes: new, changed, increased/decreased, or resolved flags; entry/reassessment-zone arrivals; invalidation breaches; evaluation failures; and recovery.
3. If the evaluation failed, retain the prior active risks and say that current status is unknown. Never call a failure an all-clear.
4. Run `vstoolkit research --data <dataset.json> --ticker <ticker> --thesis "<existing thesis>"` when evidence changed.
5. Treat the prices saved in monitor state as the controlling plan. Never replace a breached invalidation with a newly calculated plan before reporting the breach. Compare contrary evidence, event risk, volatility, and data warnings with the original assumptions.
6. Report one of: no new review condition, reassessment required, thesis invalidated under its stated rule, or unable to evaluate. Cite the exact event and evidence IDs.
7. If size is recalculated, name either `stop_risk/v1` or `portfolio_slots/v1` and show all inputs. Never blend the methods silently.

This workflow supports human review. It does not provide suitability analysis, connect to a broker, or execute a change.
