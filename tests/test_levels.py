from dataclasses import replace
import unittest

from visualsectors_toolkit.levels import build_level_plan, cluster_levels, derive_atr, latest_levels, nearest_zones, zone_for
from visualsectors_toolkit.models import Level, to_dict


def level(date, side, price, kind="test"):
    return Level(date, side, kind, price)


class LevelTests(unittest.TestCase):
    def plan_for(self, levels, *, direction="long"):
        return build_level_plan(
            ticker="TEST", as_of="2026-01-15T21:00:00Z", direction=direction,
            current_price=100, atr=4, levels=levels,
        )

    def test_only_latest_level_date_is_used_by_plan(self):
        levels = (
            level("2026-01-14", "Support", 90),
            level("2026-01-15", "Support", 98),
            level("2026-01-15", "Resistance", 105),
        )
        plan = build_level_plan(
            ticker="TEST", as_of="2026-01-15T21:00:00Z", direction="long",
            current_price=100, atr=4, levels=levels,
        )
        self.assertEqual({item.level_date for item in plan.entry_zone.members}, {"2026-01-15"})
        self.assertAlmostEqual(plan.entry_zone.low, 97)
        self.assertAlmostEqual(plan.invalidation_price, 96)

    def test_level_side_is_not_reclassified_from_price(self):
        levels = (level("2026-01-15", "Resistance", 95),)
        nearest = nearest_zones(100, levels, 2)
        self.assertIsNone(nearest.support)
        self.assertIsNone(nearest.resistance)

    def test_long_plan_does_not_use_containing_resistance_as_entry(self):
        levels = (level("2026-01-15", "Resistance", 100),)
        plan = build_level_plan(
            ticker="TEST", as_of="2026-01-15T21:00:00Z", direction="long",
            current_price=100, atr=2, levels=levels,
        )
        self.assertIsNone(plan.entry_zone)
        self.assertEqual(plan.reassessment_zone.side, "Resistance")

    def test_overlapping_support_and_resistance_remain_separate(self):
        levels = (
            level("2026-01-15", "Support", 100),
            level("2026-01-15", "Resistance", 100.2),
        )
        nearest = nearest_zones(100.1, levels, 2)
        self.assertEqual(len(nearest.inside), 2)
        self.assertEqual({item.zone.side for item in nearest.inside}, {"Support", "Resistance"})

    def test_missing_inputs_do_not_create_levels(self):
        plan = build_level_plan(
            ticker="TEST", as_of="2026-01-15T21:00:00Z", direction="long",
            current_price=100, atr=None, levels=(),
        )
        self.assertEqual(plan.status, "insufficient_data")
        self.assertIsNone(plan.entry_zone)

    def test_latest_levels_is_deterministic(self):
        values = (level("2026-01-15", "Support", 2), level("2026-01-14", "Support", 1))
        self.assertEqual(latest_levels(values), (values[0],))

    def test_latest_levels_respects_decision_cutoff(self):
        values = (level("2026-01-16", "Support", 3), level("2026-01-15", "Support", 2))
        self.assertEqual(latest_levels(values, not_after="2026-01-15T21:00:00Z"), (values[1],))

    def test_plan_rounds_prices_and_exposes_historical_base_rates(self):
        values = (
            Level("2026-01-15", "Support", "s", 98.003, p_hold_7d_pct=60),
            Level("2026-01-15", "Resistance", "r", 105.007, exp_bounce_pct=3),
        )
        plan = build_level_plan(
            ticker="TEST", as_of="2026-01-15T21:00:00Z", direction="long",
            current_price=100, atr=4, levels=values,
        )
        self.assertEqual(plan.entry_zone.low, 97.0)
        self.assertEqual(plan.invalidation_price, 96.0)
        self.assertGreater(plan.reward_to_reassessment_R, 0)
        self.assertEqual(plan.entry_historical_base_rates[0].label, "historical_base_rate")

    def test_overlapping_opposite_zone_is_not_called_reassessment(self):
        values = (
            level("2026-01-15", "Support", 100),
            level("2026-01-15", "Resistance", 100.2),
        )
        plan = build_level_plan(
            ticker="TEST", as_of="2026-01-15T21:00:00Z", direction="long",
            current_price=100.1, atr=2, levels=values,
        )
        self.assertIsNone(plan.reassessment_zone)
        self.assertTrue(any("not beyond" in note for note in plan.notes))

    def test_zero_atr_is_insufficient_instead_of_raising(self):
        plan = build_level_plan(
            ticker="TEST", as_of="2026-01-15T21:00:00Z", direction="long",
            current_price=100, atr=0, levels=(level("2026-01-15", "Support", 98),),
        )
        self.assertEqual(plan.status, "insufficient_data")

    def test_chained_levels_cannot_create_unbounded_zone(self):
        values = tuple(level("2026-01-15", "Support", price) for price in (100, 100.8, 101.6))
        zones = cluster_levels(values, atr=2, half_width_atr=0.25, max_zone_width_atr=1)
        self.assertGreater(len(zones), 1)
        self.assertTrue(all(zone.width_atr <= 1 for zone in zones))

    def test_both_base_rate_lists_merge_duplicate_levels_and_list_unique_approaches(self):
        support = Level("2026-01-15", "Support", "dex", 98, p_hold_7d_pct=60,
                        exp_bounce_pct=3, hard_break_pct=1)
        resistance = replace(support, side="Resistance", price=105)
        rows = tuple(replace(row, approach=approach) for row in (support, resistance)
                     for approach in ("risk_reward", "quality", "distance", "quality"))
        plan = self.plan_for(rows)
        for rates, side, price in ((plan.entry_historical_base_rates, "Support", 98),
                                   (plan.reassessment_historical_base_rates, "Resistance", 105)):
            self.assertEqual(len(rates), 1)
            rate = rates[0]
            self.assertEqual((rate.side, rate.level_type, rate.level_price), (side, "dex", price))
            self.assertEqual(rate.approaches, ("distance", "quality", "risk_reward"))
            self.assertEqual((rate.p_hold_7d_pct, rate.exp_bounce_pct, rate.hard_break_pct), (60, 3, 1))
            self.assertEqual(to_dict(rate)["approaches"], ["distance", "quality", "risk_reward"])
        reversed_plan = self.plan_for(tuple(reversed(rows)))
        self.assertEqual(plan.entry_historical_base_rates, reversed_plan.entry_historical_base_rates)
        self.assertEqual(plan.reassessment_historical_base_rates, reversed_plan.reassessment_historical_base_rates)

    def test_base_rate_identity_uses_exact_side_type_and_price_without_rounding(self):
        base = Level("2026-01-15", "Support", "dex", 98.0001, exp_bounce_pct=3, approach="quality")
        rows = (base, replace(base, price=98.0002), replace(base, level_type="pivot"),
                replace(base, side="Resistance", price=105))
        plan = self.plan_for(rows)
        self.assertEqual(len(plan.entry_historical_base_rates), 3)
        self.assertEqual(len(plan.reassessment_historical_base_rates), 1)
        self.assertEqual(len({(rate.side, rate.level_type, rate.level_price)
                              for rate in plan.entry_historical_base_rates}), 3)
        short = self.plan_for(rows, direction="short")
        self.assertEqual(short.entry_historical_base_rates, plan.reassessment_historical_base_rates)
        self.assertEqual(short.reassessment_historical_base_rates, plan.entry_historical_base_rates)

    def test_conflicting_approach_statistics_are_null_with_a_disclosed_gap(self):
        base = Level("2026-01-15", "Support", "dex", 98, p_hold_7d_pct=60,
                     exp_bounce_pct=3, hard_break_pct=1, approach="quality")
        other = replace(base, p_hold_7d_pct=90, exp_bounce_pct=4, approach="risk_reward")
        plan = self.plan_for((base, other))
        rate = plan.entry_historical_base_rates[0]
        self.assertEqual(rate.approaches, ("quality", "risk_reward"))
        self.assertIsNone(rate.p_hold_7d_pct)
        self.assertIsNone(rate.exp_bounce_pct)
        self.assertEqual(rate.hard_break_pct, 1)
        self.assertIn("Support dex at 98", " ".join(plan.notes))
        self.assertIn("p_hold_7d_pct, exp_bounce_pct remain null", " ".join(plan.notes))
        self.assertEqual(plan.notes, self.plan_for((other, base)).notes)

    def test_missing_statistics_and_approaches_are_not_invented(self):
        base = Level("2026-01-15", "Support", "dex", 98, exp_bounce_pct=0)
        plan = self.plan_for((base, replace(base, exp_bounce_pct=None, approach="quality")))
        rate = plan.entry_historical_base_rates[0]
        self.assertEqual(rate.exp_bounce_pct, 0)
        self.assertIsNone(rate.p_hold_7d_pct)
        self.assertEqual(rate.approaches, ("quality",))
        self.assertEqual(self.plan_for((base,)).entry_historical_base_rates[0].approaches, ())
        self.assertEqual(self.plan_for((replace(base, exp_bounce_pct=None),)).entry_historical_base_rates, ())

    def test_bounce_above_100_is_excluded_before_geometry_or_zone_score(self):
        valid = Level("2026-01-15", "Support", "dex", 98, score=0.5, exp_bounce_pct=3, approach="quality")
        resistance = replace(valid, side="Resistance", price=105)
        for bounce in (100.000001, 4420, 33196824404):
            for side in ("Support", "Resistance"):
                with self.subTest(bounce=bounce, side=side):
                    invalid = replace(valid, side=side, level_type="donchian", price=100,
                                      exp_bounce_pct=bounce, score=1e12, reward_risk=1e12,
                                      approach="risk_reward")
                    plan = self.plan_for((valid, resistance, invalid))
                    expected = self.plan_for((valid, resistance))
                    self.assertEqual(plan.entry_zone, expected.entry_zone)
                    self.assertEqual(plan.reassessment_zone, expected.reassessment_zone)
                    self.assertEqual(plan.reward_to_reassessment_R, expected.reward_to_reassessment_R)
                    self.assertEqual(plan.entry_zone.score_max, 0.5)
                    self.assertEqual(plan.reassessment_zone.score_max, 0.5)
                    warning = " ".join(plan.notes)
                    self.assertIn(f"TEST {side} donchian at 100", warning)
                    self.assertIn("exp_bounce_pct=", warning)
                    self.assertIn("excluded from scoring and zones", warning)
                    self.assertNotIn(invalid, [row for zone in cluster_levels((valid, invalid), 4)
                                               for row in zone.members])
                    with self.assertRaisesRegex(ValueError, "excluded from scoring and zones"):
                        zone_for(invalid, 4)

    def test_guard_accepts_100_zero_and_missing_bounce(self):
        for bounce in (100, 0, None):
            with self.subTest(bounce=bounce):
                row = Level("2026-01-15", "Support", "dex", 98, exp_bounce_pct=bounce)
                plan = self.plan_for((row,))
                self.assertEqual(plan.status, "ready")
                self.assertEqual(plan.entry_zone.members, (row,))
                self.assertNotIn("excluded", " ".join(plan.notes))

    def test_invalid_latest_session_never_resurrects_older_levels(self):
        invalid = Level("2026-01-15", "Support", "pivot", 98, exp_bounce_pct=4420)
        older = replace(invalid, level_date="2026-01-14", exp_bounce_pct=3)
        self.assertEqual(latest_levels((older, invalid)), ())
        plan = self.plan_for((older, invalid))
        self.assertEqual(plan.status, "insufficient_data")
        self.assertIsNone(plan.entry_zone)
        self.assertEqual(plan.entry_historical_base_rates, ())
        self.assertIn("Support pivot at 98", " ".join(plan.notes))
        self.assertEqual(cluster_levels((invalid,), 4), ())

    def test_bad_level_cannot_supply_an_atr_estimate(self):
        valid = Level("2026-01-15", "Support", "dex", 98, dist_atr=-1, exp_bounce_pct=3)
        invalid = replace(valid, price=90, dist_atr=-0.000001, exp_bounce_pct=4420)
        self.assertEqual(derive_atr((valid, invalid), 100), 2)
        self.assertIsNone(derive_atr((invalid,), 100))


if __name__ == "__main__":
    unittest.main()
