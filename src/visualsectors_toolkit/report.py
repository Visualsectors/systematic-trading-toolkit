"""Markdown rendering for the reference workflow."""

from __future__ import annotations

from .monitoring import MonitorResult
from .workflow import ToolkitRun


def _fmt(value: float | None, places: int = 2) -> str:
    return "unavailable" if value is None else f"{value:.{places}f}"


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(run: ToolkitRun, monitor: MonitorResult) -> str:
    """Render every public outcome with provenance and limitations visible."""
    manifest = run.manifest
    plan = run.level_plan
    entry_zone = (
        f"{_fmt(plan.entry_zone.low)}–{_fmt(plan.entry_zone.high)}" if plan.entry_zone else "unavailable"
    )
    reassessment_zone = (
        f"{_fmt(plan.reassessment_zone.low)}–{_fmt(plan.reassessment_zone.high)}"
        if plan.reassessment_zone
        else "unavailable"
    )
    lines = [
        "# Systematic Trading Toolkit — reproducible example",
        "",
        (
            "> **Synthetic data only.** This report uses fictional observations, does not contain live market data, "
            "and is not investment advice."
            if manifest.synthetic
            else "> **Live API data.** Stage 1 observations are date-bounded but non-point-in-time and are not "
            "investment advice."
        ),
        "",
        "## Provenance",
        "",
        f"- Dataset: `{manifest.dataset_id}`",
        f"- Decision time: `{manifest.decision_time}`",
        f"- Generated at: `{manifest.generated_at}`",
        f"- Source: {manifest.source}",
        f"- Dataset terms: {manifest.license}",
        "",
        "## 1. Screener — ready-to-research watchlist",
        "",
        f"Preset: `{run.screen.preset}` — {run.screen.description}",
        "",
        "| Rank | Ticker | Price | Support distance (ATR) | Matched criteria |",
        "| ---: | --- | ---: | ---: | --- |",
    ]
    for rank, candidate in enumerate(run.screen.candidates, start=1):
        lines.append(
            f"| {rank} | {candidate.ticker} | {candidate.price:.2f} | "
            f"{_fmt(candidate.support_distance_atr)} | {_cell(', '.join(candidate.matched_criteria))} |"
        )
    lines.extend([
        "",
        f"Ranking: {run.screen.ranking_method}",
        "",
        "Explicit exclusions:",
        "",
    ])
    lines.extend(f"- `{item.ticker}`: {', '.join(item.reasons)}" for item in run.screen.exclusions)
    lines.extend([
        "",
        "## 2. Position sizing — two methods, never silently blended",
        "",
        "### Stop-risk method (`stop_risk/v1`)",
        "",
        f"- Selected ticker: `{run.selected.ticker}`",
        f"- Shares: **{run.stop_risk_size.shares}**",
        f"- Entry assumption: {run.stop_risk_size.entry:.2f}",
        f"- Stop assumption: {run.stop_risk_size.stop:.2f}",
        f"- Notional: {run.stop_risk_size.notional:,.2f}",
        f"- Planned loss at stop: {run.stop_risk_size.planned_loss_at_stop:,.2f}",
        f"- Binding constraint: `{run.stop_risk_size.binding_constraint}`",
        "",
        "### Portfolio-slot method (`portfolio_slots/v1`)",
        "",
        f"- Slot: {run.portfolio_slot_size.slot:,.2f}",
        f"- Batch budget: {run.portfolio_slot_size.batch_budget:,.2f}",
        f"- Deployed: {run.portfolio_slot_size.deployed:,.2f}",
        f"- Unallocated: {run.portfolio_slot_size.unallocated:,.2f}",
        "",
        "| Ticker | Side | Shares | Price | Notional | Portfolio share | Allocation note |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ])
    for position in run.portfolio_slot_size.positions:
        lines.append(
            f"| {position.ticker} | {position.side} | {position.shares} | {_fmt(position.close)} | "
            f"{position.notional:,.2f} | {position.portfolio_share:.2%} | {_cell(position.note or position.tilt)} |"
        )
    lines.extend([
        "",
        "## 3. Research agent — evidence-first brief",
        "",
    ])
    for block in run.research.blocks:
        lines.extend([f"### {block.title}", ""])
        for finding in block.findings:
            citations = f" (`{', '.join(finding.evidence_ids)}`)" if finding.evidence_ids else ""
            lines.append(f"- **{finding.kind.replace('_', ' ').title()}:** {finding.statement}{citations}")
        lines.append("")
    lines.extend([
        "## 4. Risk management — conditions that matter",
        "",
        "| Severity | Type | Flag | Trigger | Reassessment action |",
        "| --- | --- | --- | --- | --- |",
    ])
    for flag in run.risk.flags:
        lines.append(
            f"| {flag.severity} | {flag.kind} | {_cell(flag.statement)} | {_cell(flag.trigger)} | "
            f"{_cell(flag.reassessment_action)} |"
        )
    lines.extend([
        "",
        "## 5. Monitoring — change-based review events",
        "",
    ])
    if monitor.events:
        lines.extend(f"- `{event.type}`: {event.message}" for event in monitor.events)
    else:
        lines.append("- No new or worsening review condition was detected.")
    lines.extend([
        "",
        "The monitor stores the last valid risk state. A provider failure is an evaluation failure, not an all-clear.",
        "",
        "## 6. Entry and exit planning — conditional level geometry",
        "",
        f"- Direction: `{plan.direction}`",
        f"- Status: `{plan.status}`",
        f"- Entry zone: {entry_zone}",
        f"- Invalidation: {_fmt(plan.invalidation_price)}",
        f"- Opposite-side reassessment zone: {reassessment_zone}",
        f"- Reward to reassessment: {_fmt(plan.reward_to_reassessment_R)}R",
        f"- Stop distance: {_fmt(plan.stop_distance_atr)} ATR",
        "",
        "Served historical base rates (descriptive, not a setup forecast):",
        "",
        "| Zone | Level family | Hold 7d | Bounce | Hard break | Label |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ])
    for zone_name, base_rates in (
        ("entry", plan.entry_historical_base_rates),
        ("reassessment", plan.reassessment_historical_base_rates),
    ):
        for rate in base_rates:
            lines.append(
                f"| {zone_name} | {_cell(rate.level_type)} | {_fmt(rate.p_hold_7d_pct)}% | "
                f"{_fmt(rate.exp_bounce_pct)}% | {_fmt(rate.hard_break_pct)}% | {rate.label} |"
            )
    if not plan.entry_historical_base_rates and not plan.reassessment_historical_base_rates:
        lines.append("| unavailable | unavailable | unavailable | unavailable | unavailable | historical_base_rate |")
    lines.extend([
        "",
        "These are conditional scenarios derived from served levels and ATR geometry. "
        "They are not fills, projected prices, forecasts, or broker orders.",
        "",
        "## Limitations",
        "",
    ])
    lines.extend(f"- {warning}" for warning in (*run.screen.warnings, *run.stop_risk_size.warnings, *run.risk.warnings))
    return "\n".join(lines) + "\n"
