import unittest

from visualsectors_toolkit.levels import build_level_plan
from visualsectors_toolkit.models import MarketSnapshot
from visualsectors_toolkit.monitoring import evaluate_monitor
from visualsectors_toolkit.providers import SyntheticFixtureProvider
from visualsectors_toolkit.research import build_research_brief
from visualsectors_toolkit.risk import RiskFlag, RiskRegister, build_risk_register


class ResearchRiskMonitorTests(unittest.TestCase):
    def setUp(self):
        provider = SyntheticFixtureProvider()
        self.row = provider.get("ALFA")
        self.plan = build_level_plan(
            ticker=self.row.ticker, as_of=self.row.as_of, direction="long",
            current_price=self.row.price, atr=self.row.atr14, levels=self.row.levels,
        )

    def test_brief_labels_contrary_evidence_and_gaps(self):
        brief = build_research_brief(self.row, thesis="Test thesis", level_plan=self.plan)
        contrary = next(block for block in brief.blocks if block.title == "Contrary evidence")
        self.assertEqual(contrary.findings[0].kind, "contrary_evidence")
        self.assertEqual(contrary.findings[0].evidence_ids, ("alfa-input-costs",))
        cited = {item.id for item in brief.evidence}
        for block in brief.blocks:
            for finding in block.findings:
                self.assertTrue(set(finding.evidence_ids) <= cited)

    def test_unchanged_state_does_not_repeat_events(self):
        register = build_risk_register(self.row, level_plan=self.plan)
        first = evaluate_monitor(None, observed_at="2026-01-15T22:00:00Z", register=register)
        second = evaluate_monitor(first.state, observed_at="2026-01-16T22:00:00Z", register=register)
        self.assertTrue(first.events)
        self.assertEqual(second.events, ())

    def test_severity_increase_emits_change(self):
        low = RiskRegister("ALFA", self.row.as_of, (RiskFlag("x", "uncertainty", "low", "x", "t", "a"),), ())
        high = RiskRegister("ALFA", self.row.as_of, (RiskFlag("x", "uncertainty", "high", "x", "t", "a"),), ())
        initial = evaluate_monitor(None, observed_at="2026-01-15T22:00:00Z", register=low)
        changed = evaluate_monitor(initial.state, observed_at="2026-01-16T22:00:00Z", register=high)
        self.assertEqual([event.type for event in changed.events], ["severity_increased"])

    def test_tailwind_severity_drop_and_statement_change_are_visible(self):
        first_register = RiskRegister(
            "ALFA", self.row.as_of,
            (RiskFlag("x", "tailwind", "high", "old", "t", "a"),), (),
        )
        second_register = RiskRegister(
            "ALFA", self.row.as_of,
            (RiskFlag("x", "tailwind", "low", "new", "t", "a"),), (),
        )
        initial = evaluate_monitor(None, observed_at="2026-01-15T22:00:00Z", register=first_register)
        changed = evaluate_monitor(initial.state, observed_at="2026-01-16T22:00:00Z", register=second_register)
        self.assertEqual(
            [event.type for event in changed.events],
            ["severity_decreased", "flag_changed"],
        )

    def test_warning_ids_do_not_depend_on_warning_order(self):
        values = {field: getattr(self.row, field) for field in self.row.__dataclass_fields__}
        values["warnings"] = ("warning A", "warning B")
        first = build_risk_register(MarketSnapshot(**values))
        values["warnings"] = tuple(reversed(values["warnings"]))
        second = build_risk_register(MarketSnapshot(**values))
        first_ids = {flag.id for flag in first.flags if flag.id.startswith("data-warning-")}
        second_ids = {flag.id for flag in second.flags if flag.id.startswith("data-warning-")}
        self.assertEqual(first_ids, second_ids)

    def test_failure_retains_risks_and_recovery_is_explicit(self):
        register = build_risk_register(self.row, level_plan=self.plan)
        initial = evaluate_monitor(None, observed_at="2026-01-15T22:00:00Z", register=register)
        failed = evaluate_monitor(initial.state, observed_at="2026-01-16T22:00:00Z", failure="provider timeout")
        self.assertEqual(failed.state.active, initial.state.active)
        self.assertEqual(failed.events[0].type, "evaluation_failed")
        duplicate = evaluate_monitor(failed.state, observed_at="2026-01-17T22:00:00Z", failure="provider timeout")
        self.assertEqual(duplicate.events, ())
        recovered = evaluate_monitor(failed.state, observed_at="2026-01-18T22:00:00Z", register=register)
        self.assertEqual([event.type for event in recovered.events], ["evaluation_recovered"])

    def test_saved_plan_emits_price_zone_events(self):
        register = build_risk_register(self.row, level_plan=self.plan)
        initial = evaluate_monitor(
            None, observed_at="2026-01-15T22:00:00Z", register=register,
            current_price=self.row.price, level_plan=self.plan,
        )
        breached = evaluate_monitor(
            initial.state, observed_at="2026-01-16T22:00:00Z", register=register,
            current_price=self.plan.invalidation_price - 0.01,
        )
        self.assertIn("invalidation_breached", [event.type for event in breached.events])
        self.assertEqual(breached.state.plan.invalidation_price, self.plan.invalidation_price)

    def test_breach_is_not_reported_as_resolved_when_new_plan_disappears(self):
        initial_register = build_risk_register(self.row, level_plan=self.plan)
        initial = evaluate_monitor(
            None, observed_at="2026-01-15T22:00:00Z", register=initial_register,
            current_price=self.row.price, level_plan=self.plan,
        )
        rebuilt_without_plan = build_risk_register(self.row)
        changed = evaluate_monitor(
            initial.state, observed_at="2026-01-16T22:00:00Z", register=rebuilt_without_plan,
            current_price=self.plan.invalidation_price - 0.01,
        )
        event_types = [event.type for event in changed.events]
        self.assertIn("invalidation_breached", event_types)
        self.assertNotIn("resolved", event_types)

    def test_out_of_order_monitor_updates_are_rejected(self):
        register = build_risk_register(self.row, level_plan=self.plan)
        initial = evaluate_monitor(None, observed_at="2026-01-15T22:00:00Z", register=register)
        with self.assertRaisesRegex(ValueError, "later than"):
            evaluate_monitor(initial.state, observed_at="2026-01-15T22:00:00Z", register=register)

    def test_first_failure_uses_supplied_ticker(self):
        result = evaluate_monitor(
            None, observed_at="2026-01-15T22:00:00Z", failure="offline", ticker="ALFA"
        )
        self.assertEqual(result.state.ticker, "ALFA")

    def test_past_earnings_does_not_raise_event_flag(self):
        values = {field: getattr(self.row, field) for field in self.row.__dataclass_fields__}
        values["days_to_earnings"] = -2
        register = build_risk_register(MarketSnapshot(**values), level_plan=self.plan)
        self.assertNotIn("earnings-window", {flag.id for flag in register.flags})


if __name__ == "__main__":
    unittest.main()
