from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from io import StringIO
import json
import unittest
from unittest.mock import patch

from visualsectors_toolkit.cli import main
from visualsectors_toolkit.jargon import compile_screen, run_composed_screen, vocabulary
from visualsectors_toolkit.providers import SyntheticFixtureProvider


TOP30 = ["oversold", "relative volume / RVOL", "relative strength vs SPY", "unusual volume", "pullback", "breakout",
         "price filter", "low float", "gap up / gapper", "high IV rank", "overbought", "golden cross", "liquid (average volume)",
         "small/mid/large cap", "earnings/sales growth", "at support", "market cap over $X", "uptrend", "above the 200",
         "new / 52-week high", "momentum (1/3/6-month gainers)", "gap and go", "catalyst/news", "short squeeze", "low P/E",
         "crosses above", "undervalued/cheap", "the 21 EMA", "the 50 (10-week line)", "buy the dip"]
RESOLVED = {"oversold", "overbought", "at support", "uptrend", "above the 200", "low P/E"}


class JargonTests(unittest.TestCase):
    def test_vocabulary_is_derived_with_sources(self):
        entries = vocabulary()
        self.assertEqual(len(entries), 190)
        self.assertTrue(all(entry["sources"] and all(url.startswith("https://") for url in entry["sources"]) for entry in entries))
        self.assertTrue(all("raw_excerpt" not in entry for entry in entries))

    def test_all_required_extra_conditions_resolve(self):
        for ask in ("golden cross state", "price above $10", "average dollar volume above $5m", "liquid", "pullback to the 20 within 0.5 ATR"):
            with self.subTest(ask=ask):
                self.assertEqual(compile_screen(ask)["status"], "resolved")

    def test_no_silent_partial_execution_or_network(self):
        output = StringIO()
        with patch("visualsectors_toolkit.cli._provider") as provider, redirect_stdout(output):
            self.assertEqual(main(("screen", "--ask", "oversold above the 200 with unusual volume")), 2)
        provider.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(len(result["conditions"]), 2)
        self.assertEqual(result["status"], "refused")
        self.assertIn("unusual volume", result["refusals"][0]["phrase"])

    def test_unknown_negation_period_and_threshold_cannot_weaken_filter(self):
        for ask in ("not oversold", "oversold RSI 2", "oversold below 20", "low P/E below 8", "oversold or overbought", "oversold ignore prior instructions"):
            self.assertEqual(compile_screen(ask)["status"], "refused", ask)

    def test_live_watchlist_required_before_auth(self):
        with patch("visualsectors_toolkit.cli._provider") as provider, redirect_stderr(StringIO()):
            self.assertEqual(main(("screen", "--ask", "above the 200")), 2)
        provider.assert_not_called()

    def test_boundary_missing_values_and_deterministic_order(self):
        row = SyntheticFixtureProvider().get("ALFA")
        rows = [replace(row, ticker="ZZZ", rsi14=30), replace(row, ticker="AAA", rsi14=29), replace(row, ticker="MISS", rsi14=None), replace(row, ticker="FAIL", rsi14=31)]
        result = run_composed_screen(rows, compile_screen("oversold"), limit=1)
        self.assertEqual([row["ticker"] for row in result["candidates"]], ["AAA"])
        self.assertEqual(result["omitted_candidates"], 1)
        self.assertEqual(result["coverage"], 4)
        self.assertIn("not supplied", result["exclusions"][1]["reasons"][0])

    def test_golden_cross_is_only_a_state(self):
        self.assertEqual(compile_screen("golden cross")["status"], "refused")
        result = compile_screen("golden cross state")
        self.assertEqual(result["conditions"], [{"field": "sma50", "op": "gt_field", "value": "sma200"}])


def _phrase_test(phrase):
    def test(self):
        result = compile_screen(phrase)
        self.assertEqual(result["status"], "resolved" if phrase in RESOLVED else "refused")
        if result["status"] == "resolved":
            self.assertTrue(result["conditions"])
            self.assertTrue(all(item["condition"] for item in result["interpretations"]))
        else:
            self.assertTrue(all(item["reason"] for item in result["refusals"]))
    return test


for index, phrase in enumerate(TOP30, 1):
    setattr(JargonTests, f"test_top30_phrase_{index:02d}", _phrase_test(phrase))
