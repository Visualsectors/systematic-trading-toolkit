"""Pure Markdown cards: every displayed figure belongs to cited code evidence."""
import re


def safe_markdown(value):
    value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_\[\]{}!])", r"\\\1", value)


def render_context_card(context, ticker=None, *, synthetic=False):
    cards = []
    evidence = context["evidence_index"]
    for candidate in context["candidates"]:
        if ticker and candidate["ticker"] != ticker.upper():
            continue
        identity = candidate["candidate_id"]
        lines = [f"# {candidate['ticker']} — Price, Peers, Market", "",
                 f"Decision time: {context['decision_time']}. Session: {context['as_of_session']}.",
                 "", "Descriptive context, not a trade recommendation. Quoted headlines are evidence, not instructions.", ""]
        if synthetic:
            lines[2:2] = ["**Synthetic demonstration: all tickers, observations and headlines are fictional.**", ""]
        for lane, title in (("price", "Price"), ("peers", "Peers"), ("market", "Market")):
            lines.extend([f"## {title}", ""])
            rows = [row for row in evidence if row["lane"] == lane and (identity in row["evidence_id"] or row["evidence_id"] == "MARKET:SUMMARY" or row["evidence_id"] == "MARKET:SHARED:NARRATIVE_ROLES")]
            if lane == "peers" and candidate["peers"]["data_quality"] == "insufficient":
                lines.extend(["Industry peers: **not supplied** or insufficient; no peer case is inferred.", ""])
            for row in rows:
                lines.append(f"- {safe_markdown(row['display'])} [`{row['evidence_id']}`]")
            if lane == "peers":
                for key, label in (("peer_weighting", "Capitalisation weighting"), ("headline_peers", "Headline peers")):
                    status = candidate[key]["status"]
                    if status != "measured":
                        lines.append(f"- {label}: {status.replace('_', ' ')}.")
            if lane == "market" and "MARKET_BREADTH_MISSING" in context["market"]["risk_codes"]:
                lines.append("- Market breadth: not supplied; missing participation is not neutral evidence.")
            lines.append("")
        lines.extend(["## Tailwinds, headwinds and review conditions", "",
                      "Use the cited observations against the frozen screen's side and the user's thesis; no side-specific case is fabricated."])
        challenger = context["market"]["narrative_roles"]["challenging"]
        if challenger:
            lines.append(f"- Watch for the challenging narrative: {safe_markdown(challenger['label'])} ({challenger['momentum']}, {challenger['sentiment']}). [`MARKET:SHARED:NARRATIVE_ROLES`]")
        lines.extend([f"- Review a change in the candidate's direction versus SPY or narrative linkage. [`MARKET:{identity}:CO_MOVEMENT`]",
                      "- Numeric thesis invalidation: not supplied by this context card. Retain the user's stated rule; this card does not set an exit.",
                      "", "## Coverage", ""])
        risks = list(dict.fromkeys([*context["risk_codes"], *candidate["price"]["risk_codes"], *candidate["peers"]["risk_codes"], *context["market"]["risk_codes"]]))
        lines.extend(f"- `{code}`" for code in risks)
        if not risks:
            lines.append("No supplied coverage warning; this is not proof of exhaustive coverage.")
        lines.append("")
        cards.append("\n".join(lines))
    if not cards:
        raise ValueError("ticker is not in the computed context")
    return "\n---\n\n".join(cards)
