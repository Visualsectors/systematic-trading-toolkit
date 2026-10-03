"""Offline regressions for Rustam's main f740e0d plan-output review."""

from dataclasses import replace
from contextlib import redirect_stdout
from io import StringIO
import json
import unittest
from unittest.mock import patch

from visualsectors_toolkit.cli import main
from visualsectors_toolkit.levels import build_level_plan, cluster_levels
from visualsectors_toolkit.models import Level, to_dict
from visualsectors_toolkit.providers import SyntheticFixtureProvider


class PlanOutputReviewTests(unittest.TestCase):
    def plan(self, direction="long", resistance=102.73, support=98, atr=4):
        return build_level_plan(
            ticker="MSFT", as_of="2026-01-15T21:00:00Z", direction=direction,
            current_price=100, atr=atr,
            levels=(Level("2026-01-15", "Support", "fixture", support),
                    Level("2026-01-15", "Resistance", "fixture", resistance)),
        )

    def test_091R_is_explicitly_flagged_in_long_and_short_plans(self):
        for direction in ("long", "short"):
            with self.subTest(direction=direction):
                plan = self.plan(direction)
                self.assertEqual(plan.reward_to_reassessment_R, 0.91)
                self.assertEqual(plan.reward_risk_warning, "reward_below_risk")
                self.assertIn("reward is smaller than risk", " ".join(plan.notes))
                self.assertEqual(to_dict(plan)["reward_risk_warning"], "reward_below_risk")

    def test_warning_boundary_uses_unrounded_ratio(self):
        # Entry/reassessment geometry gives reward=3 and risk=3 exactly at 1R.
        at_one = self.plan(resistance=103)
        self.assertEqual(at_one.reward_to_reassessment_R, 1)
        self.assertIsNone(at_one.reward_risk_warning)
        above = self.plan(resistance=105)
        self.assertGreater(above.reward_to_reassessment_R, 1)
        self.assertIsNone(above.reward_risk_warning)
        missing = build_level_plan(ticker="MSFT", as_of="2026-01-15T21:00:00Z",
                                   direction="long", current_price=100, atr=None, levels=())
        self.assertIsNone(missing.reward_risk_warning)
        self.assertEqual(missing.status, "insufficient_data")
        just_below = build_level_plan(ticker="MSFT", as_of="2026-01-15T21:00:00Z",
                                     direction="long", current_price=50000, atr=4000,
                                     levels=(Level("2026-01-15", "Support", "fixture", 48000),
                                             Level("2026-01-15", "Resistance", "fixture", 52999.99)))
        self.assertEqual(just_below.reward_to_reassessment_R, 1.0)
        self.assertEqual(just_below.reward_risk_warning, "reward_below_risk")

    def test_five_approach_rows_at_three_exact_prices_count_as_three_levels(self):
        base = Level("2026-01-15", "Support", "fixture", 98, approach="quality")
        rows = (base, replace(base, approach="distance"), replace(base, price=98.01),
                replace(base, price=98.01, approach="risk_reward"), replace(base, price=98.02))
        zones = cluster_levels(rows, atr=4)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].member_count, 3)
        self.assertEqual(len(zones[0].members), 5)
        self.assertEqual(zones[0].member_count, cluster_levels(tuple(reversed(rows)), 4)[0].member_count)

    def test_same_price_across_families_is_one_price_level_but_keeps_all_evidence(self):
        base = Level("2026-01-15", "Support", "fixture", 98)
        zone = cluster_levels((base, replace(base, level_type="pivot")), atr=4)[0]
        self.assertEqual(zone.member_count, 1)
        self.assertEqual(len(zone.members), 2)
        self.assertEqual(zone.level_types, ("fixture", "pivot"))

    def test_distinct_unrounded_prices_count_separately_even_when_display_rounding_matches(self):
        base = Level("2026-01-15", "Support", "fixture", 98.0001)
        other = replace(base, price=98.0002)
        self.assertEqual(round(base.price, 2), round(other.price, 2))
        zone = cluster_levels((base, other), atr=4)[0]
        self.assertEqual(zone.member_count, 2)
        self.assertEqual(tuple(member.price for member in zone.members), (98.0001, 98.0002))

    def test_atr_output_rounds_only_for_presentation_in_nested_json(self):
        plan = replace(self.plan(), stop_distance_atr=0.4992254099786105,
                       entry_zone=replace(self.plan().entry_zone, width_atr=0.4992254099786105))
        output = to_dict({"plan": plan})["plan"]
        self.assertEqual(output["stop_distance_atr"], 0.5)
        self.assertEqual(output["entry_zone"]["width_atr"], 0.5)
        self.assertEqual(plan.stop_distance_atr, 0.4992254099786105)
        self.assertEqual(plan.entry_zone.width_atr, 0.4992254099786105)
        self.assertEqual(output["risk_per_share"], plan.risk_per_share)
        self.assertIsNone(to_dict({"stop_distance_atr": None})["stop_distance_atr"])

    def test_plan_command_emits_warning_distinct_count_and_rounded_atr(self):
        base = Level("2026-01-15", "Support", "fixture", 98, approach="quality")
        rows = (base, replace(base, approach="distance"), replace(base, price=98.01),
                replace(base, price=98.01, approach="risk_reward"), replace(base, price=98.02),
                replace(base, side="Resistance", price=102.73))
        snapshot = replace(SyntheticFixtureProvider().get("ALFA"), ticker="MSFT",
                           as_of="2026-01-15T21:00:00Z", price=100, atr14=4.0062, levels=rows)
        output = StringIO()
        with patch("visualsectors_toolkit.cli._provider") as provider, redirect_stdout(output):
            provider.return_value.get.return_value = snapshot
            self.assertEqual(main(("plan", "MSFT")), 0)
        plan = json.loads(output.getvalue())["plan"]
        self.assertEqual(plan["reward_risk_warning"], "reward_below_risk")
        self.assertEqual(plan["entry_zone"]["member_count"], 3)
        self.assertEqual(len(plan["entry_zone"]["members"]), 5)
        for value in (plan["stop_distance_atr"], plan["entry_zone"]["width_atr"],
                      plan["reassessment_zone"]["width_atr"]):
            self.assertEqual(value, round(value, 2))


if __name__ == "__main__":
    unittest.main()
