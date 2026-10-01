from dataclasses import replace
import unittest

from visualsectors_toolkit.models import Level
from visualsectors_toolkit.providers import SyntheticFixtureProvider
from visualsectors_toolkit.screening import run_screen


class ScreeningTests(unittest.TestCase):
    def setUp(self):
        self.rows = SyntheticFixtureProvider().universe()

    def test_oversold_screen_returns_expected_watchlist_and_exclusions(self):
        result = run_screen(self.rows, "oversold_at_support")
        self.assertEqual([row.ticker for row in result.candidates], ["ALFA", "DLTA"])
        excluded = {row.ticker: row.reasons for row in result.exclusions}
        self.assertIn("rsi14_above_35", excluded["BRVO"])
        self.assertIn("price_below_5", excluded["CRWN"])
        self.assertIn("levels_missing", excluded["ECHO"])

    def test_order_of_input_does_not_change_output(self):
        forward = run_screen(self.rows, "near_support")
        reverse = run_screen(tuple(reversed(self.rows)), "near_support")
        self.assertEqual(forward, reverse)

    def test_historical_score_is_not_used_for_ranking(self):
        result = run_screen(self.rows, "near_support")
        self.assertIn("ATR units", result.ranking_method)
        self.assertNotIn("score", result.ranking_method.lower())

    def test_limit_reports_omitted_candidates(self):
        result = run_screen(self.rows, "oversold_at_support", limit=1)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.omitted_candidates, 1)

    def test_implausible_support_cannot_influence_screen_rank_or_coverage(self):
        row = self.rows[0]
        bad = Level(row.as_of[:10], "Support", "pivot", row.price,
                    exp_bounce_pct=33196824404, reward_risk=1e12, score=1e12, approach="risk_reward")
        corrupt = replace(row, levels=(bad,))
        result = run_screen((corrupt,), "near_support")
        self.assertEqual(result.candidates, ())
        self.assertIn("levels_missing", result.exclusions[0].reasons)
        self.assertIn(f"{row.ticker} Support pivot at", " ".join(result.warnings))
        mixed = replace(row, levels=(*row.levels, bad))
        expected = run_screen((row,), "near_support")
        actual = run_screen((mixed,), "near_support")
        self.assertEqual(actual.candidates, expected.candidates)
        self.assertEqual(actual.exclusions, expected.exclusions)


if __name__ == "__main__":
    unittest.main()
