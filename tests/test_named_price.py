from dataclasses import replace
import unittest
from visualsectors_toolkit.models import Level
from visualsectors_toolkit.named_price import measure_named_price
from visualsectors_toolkit.providers import SyntheticFixtureProvider


class NamedPriceTests(unittest.TestCase):
    def setUp(self):
        self.row = replace(SyntheticFixtureProvider().get("ALFA"), price=110, atr14=2,
            levels=(Level("2026-01-15", "Support", "lower", 95, p_hold_7d_pct=60),
                    Level("2026-01-15", "Resistance", "upper", 105, p_hold_7d_pct=70)))

    def test_signed_measurements_and_exact_closing(self):
        result = measure_named_price(self.row, 100, kind="strike")
        self.assertEqual(result["nearest_above"]["distance_dollars"], 5)
        self.assertEqual(result["nearest_below"]["distance_pct"], -5)
        self.assertEqual(result["nearest_below"]["distance_atr"], -2.5)
        self.assertEqual(result["strike_distance_from_close_atr"], -5)
        self.assertEqual(result["nearest_above"]["hold_rate_text"], "held on 70% of past tests")
        self.assertEqual(result["closing"], "These are the served levels measured from $100; this isn't advice on what to do with a position.")

    def test_missing_atr_or_levels_remain_null(self):
        result = measure_named_price(replace(self.row, atr14=None, levels=()), 100, kind="strike")
        self.assertIsNone(result["nearest_above"])
        self.assertIsNone(result["strike_distance_from_close_atr"])

    def test_invalid_price_and_kind_refuse(self):
        for value in (0, -10, float("nan"), True):
            with self.assertRaises(ValueError): measure_named_price(self.row, value)
        with self.assertRaises(ValueError): measure_named_price(self.row, 100, kind="exit")

    def test_future_levels_and_exact_price_are_separate(self):
        row = replace(self.row, levels=(*self.row.levels, Level("2099-01-01", "Support", "future", 101)))
        result = measure_named_price(row, 105)
        self.assertIsNone(result["nearest_above"])
        self.assertEqual(len(result["exactly_at"]), 1)
