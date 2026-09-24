import unittest

from visualsectors_toolkit.levels import build_level_plan, cluster_levels, latest_levels, nearest_zones
from visualsectors_toolkit.models import Level


def level(date, side, price, kind="test"):
    return Level(date, side, kind, price)


class LevelTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
