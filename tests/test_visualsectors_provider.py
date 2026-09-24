import copy
from datetime import date, timedelta
from email.message import Message
from io import BytesIO
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from visualsectors_toolkit.providers import MissingApiKeyError, RateLimitError, VisualSectorsProvider


AS_OF = "2026-09-23T23:59:59Z"


def envelope(rows):
    return {
        "category": "recorded",
        "source": "recorded-test-payload",
        "configured": True,
        "ticker": "AAPL",
        "range": "latest",
        "as_of": AS_OF,
        "count": len(rows),
        "rows": rows,
        "next_cursor": None,
        "row_cap": 1000,
    }


class RecordedProvider(VisualSectorsProvider):
    def __init__(self, cache_dir):
        super().__init__(api_key="recorded-test-key", cache_dir=cache_dir)
        first = date(2026, 9, 3)
        bars = [
            {
                "ticker": "AAPL",
                "date": (first + timedelta(days=index)).isoformat(),
                "close": 100 + index,
                "volume": 1_000_000,
            }
            for index in range(21)
        ]
        self.calls = []
        self.recorded = {
            ("GET", "/v1/health", None): {"ok": True, "service": "recorded"},
            ("GET", "/v1/levels", None): envelope([
                {
                    "level_date": "2026-09-23", "side": "Support", "level_type": "ma",
                    "price": 118, "score": 0.8, "p_hold_7d_pct": 62,
                    "exp_bounce_pct": 3.2, "hard_break_pct": 1.5, "reward_risk": 2.1,
                    "dist_atr": -0.5, "confluence_count": 2, "approach": "quality",
                    "example": False, "expected_bounce_usd": 3.77, "hard_break_price": 116.23,
                    "num_tests_365d": 9,
                }
            ]),
            ("GET", "/v1/technicals", None): envelope([
                {"date": "2026-09-23", "indicators": {
                    "atr14": 2.5, "rsi14": 33, "sma20": 115,
                    "sma50": 110, "sma200": 90,
                }}
            ]),
            ("GET", "/v1/timeseries/history", "daily"): envelope(bars),
            ("GET", "/v1/fundamentals", "overview"): envelope([{"PERatio": 29.5}]),
            ("GET", "/v1/fundamentals", "earnings_calendar"): envelope([
                {"report_date": "2026-09-30", "estimate": 1.2, "currency": "USD"}
            ]),
            ("GET", "/v1/news", "headlines"): envelope([
                {
                    "id": "story-1", "title": "Recorded product announcement", "author": "Publisher",
                    "created": "2026-09-23T13:00:00Z", "event_date": "2026-09-23",
                    "ticker_sentiment_score": 0.2, "url": "https://example.com/story",
                }
            ]),
            ("POST", "/v1/screen", None): {
                "version": 1, "results": [{"ticker": "AAPL"}], "next_cursor": None, "row_cap": 100,
            },
        }

    def _request_json(self, method, path, *, query=None, body=None, cache=True):
        self.calls.append((method, path, copy.deepcopy(query), copy.deepcopy(body)))
        view = query.get("view") if query else None
        return copy.deepcopy(self.recorded[(method, path, view)])


class VisualSectorsProviderTests(unittest.TestCase):
    def test_recorded_payload_maps_to_live_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            row = provider.get("aapl")
            self.assertEqual(row.price, 120)
            self.assertEqual(row.rsi14, 33)
            self.assertEqual(row.pe_ratio, 29.5)
            self.assertEqual(row.days_to_earnings, 7)
            self.assertGreater(row.momentum_20d_pct, 0)
            self.assertGreater(row.volatility_20d_pct, 0)
            self.assertEqual(row.average_dollar_volume_20d, 110_500_000)
            self.assertEqual(row.evidence[0].stance, "support")
            self.assertFalse(provider.manifest.synthetic)
            self.assertIn("non-point-in-time", " ".join(row.warnings))
            self.assertFalse(hasattr(row.levels[0], "expected_bounce_usd"))

    def test_live_universe_is_seeded_by_post_screen(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            rows = provider.screen_universe("oversold_at_support", limit=10)
            self.assertEqual([row.ticker for row in rows], ["AAPL"])
            method, path, _query, body = provider.calls[0]
            self.assertEqual((method, path), ("POST", "/v1/screen"))
            self.assertEqual(body["limit"], 10)

    def test_verify_makes_exactly_health_and_one_levels_request(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.verify()
            self.assertEqual(
                [(method, path) for method, path, _query, _body in provider.calls],
                [("GET", "/v1/health"), ("GET", "/v1/levels")],
            )

    def test_missing_key_has_signup_guidance(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"VISUALSECTORS_API_KEY": ""}, clear=False
        ):
            with self.assertRaisesRegex(MissingApiKeyError, "api.visualsectors.com/signup"):
                VisualSectorsProvider(env_file=f"{directory}/missing.env", cache_dir=directory)

    def test_rate_limit_surfaces_retry_after(self):
        headers = Message()
        headers["Retry-After"] = "42"
        error = HTTPError("https://api.visualsectors.com/v1/levels", 429, "limited", headers, BytesIO(b"{}"))
        with tempfile.TemporaryDirectory() as directory:
            provider = VisualSectorsProvider(api_key="recorded-test-key", cache_dir=directory)
            with patch(
                "visualsectors_toolkit.providers.visualsectors.urlopen", side_effect=error
            ):
                with self.assertRaisesRegex(RateLimitError, "42 seconds"):
                    provider._request_json("GET", "/v1/levels", query={"ticker": "AAPL"})


if __name__ == "__main__":
    unittest.main()
