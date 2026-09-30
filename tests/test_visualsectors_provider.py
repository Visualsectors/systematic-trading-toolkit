import copy
from datetime import date, timedelta
from email.message import Message
from io import BytesIO
import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from visualsectors_toolkit.providers import ApiResponseError, MissingApiKeyError, RateLimitError, VisualSectorsProvider
from visualsectors_toolkit.providers.visualsectors import PLAN_INDICATORS


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
        self.cache_flags = []
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
            ("GET", "/v1/timeseries/history", "daily"): envelope(bars),
            ("GET", "/v1/fundamentals", "metrics"): envelope([{"pe_ratio": 29.5}]),
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
        for indicator, value in {"atr14": 2.5, "rsi14": 33, "sma20": 115, "sma50": 110, "sma200": 90}.items():
            self.recorded[("GET", f"/v1/technicals/{indicator}", None)] = envelope([
                {"date": "2026-09-23", "indicator": indicator, "value": value}
            ])

    def _request_json(self, method, path, *, query=None, body=None, cache=True):
        self.calls.append((method, path, copy.deepcopy(query), copy.deepcopy(body)))
        self.cache_flags.append(cache)
        view = query.get("view") if query else None
        payload = self.recorded[(method, path, view)]
        if isinstance(payload, Exception):
            raise payload
        return copy.deepcopy(payload)


class VisualSectorsProviderTests(unittest.TestCase):
    def test_recorded_payload_maps_to_live_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            row = provider.get("aapl")
            self.assertEqual(row.price, 120)
            self.assertEqual(row.rsi14, 33)
            self.assertEqual(row.pe_ratio, 29.5)
            self.assertIsNone(row.days_to_earnings)
            self.assertIn("earnings calendar data is not served", " ".join(row.warnings))
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

    def test_verify_exercises_every_plan_endpoint_without_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.get("AAPL")  # A warm in-memory/disk cache must not validate a different key.
            provider.calls.clear()
            provider.cache_flags.clear()
            warnings = provider.verify()
            self.assertEqual(
                [(method, path) for method, path, _query, _body in provider.calls],
                [("GET", "/v1/health"), ("GET", "/v1/levels")]
                + [("GET", f"/v1/technicals/{indicator}") for indicator in PLAN_INDICATORS]
                + [("GET", "/v1/timeseries/history"), ("GET", "/v1/fundamentals"), ("GET", "/v1/news")],
            )
            self.assertTrue(all(flag is False for flag in provider.cache_flags))
            self.assertIn("Days to earnings", " ".join(warnings))

    def test_optional_endpoint_failures_degrade_with_explicit_gaps(self):
        for path, view in (("/v1/fundamentals", "metrics"), ("/v1/news", "headlines")):
            for failure in (ApiResponseError(403, "unavailable"), ApiResponseError(503, "outage"), {"rows": "bad"}):
                with self.subTest(path=path, failure=failure), tempfile.TemporaryDirectory() as directory:
                    provider = RecordedProvider(directory)
                    provider.recorded[("GET", path, view)] = failure
                    row = provider.get("AAPL")
                    self.assertEqual(row.price, 120)
                    self.assertIn(path, " ".join(row.warnings))
                    if path == "/v1/fundamentals":
                        self.assertIsNone(row.pe_ratio)
                    else:
                        self.assertEqual(row.evidence, ())

    def test_optional_endpoints_never_hide_authentication_or_rate_limits(self):
        for path, view in (("/v1/fundamentals", "metrics"), ("/v1/news", "headlines")):
            for failure in (ApiResponseError(401, "invalid key"), RateLimitError("42")):
                with self.subTest(path=path, failure=failure), tempfile.TemporaryDirectory() as directory:
                    provider = RecordedProvider(directory)
                    provider.recorded[("GET", path, view)] = failure
                    with self.assertRaises(type(failure)):
                        provider.verify()

    def test_core_endpoint_failure_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.recorded[("GET", "/v1/technicals/atr14", None)] = ApiResponseError(503, "outage")
            with self.assertRaises(ApiResponseError):
                provider.verify()

    def test_malformed_optional_news_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.recorded[("GET", "/v1/news", "headlines")] = envelope([{"id": "bad", "title": "Unknown date"}])
            row = provider.get("AAPL")
            self.assertEqual(row.evidence, ())
            self.assertIn("malformed news", " ".join(row.warnings))

    def test_plan_requests_match_captured_220_openapi(self):
        contract = json.loads((Path(__file__).parent / "fixtures/visualsectors-openapi-2.2.0.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["info"]["version"], "2.2.0")
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.verify()
            for method, path, query, _body in provider.calls:
                template = "/v1/technicals/{indicator}" if path.startswith("/v1/technicals/") else path
                operation = contract["paths"][template][method.lower()]
                parameters = operation["parameters"]
                allowed = {parameter["name"] for parameter in parameters if parameter["in"] == "query"}
                self.assertFalse(set(query or {}) - allowed, path)
                if template != path:
                    indicator = next(parameter for parameter in parameters if parameter["name"] == "indicator")
                    self.assertIn(path.rsplit("/", 1)[-1], indicator["schema"]["enum"])
                if path == "/v1/fundamentals":
                    view = next(parameter for parameter in parameters if parameter["name"] == "view")
                    self.assertEqual(query["view"], view["schema"]["example"])
                    self.assertNotIn("earnings_calendar", view["description"])
            schemas = contract["components"]["schemas"]
            self.assertEqual(schemas["FundamentalsMetricsRow"]["properties"]["pe_ratio"], {"type": "number", "nullable": True})
            self.assertEqual(schemas["TechnicalRow"]["required"], ["date", "indicator", "value"])

    def test_401_ends_with_login_guidance_and_never_echoes_response(self):
        error = HTTPError("https://api.visualsectors.com/v1/levels", 401, "unauthorized", Message(),
                          BytesIO(b'{"message":"do-not-echo-this-secret"}'))
        with tempfile.TemporaryDirectory() as directory:
            provider = VisualSectorsProvider(api_key="recorded-test-key", cache_dir=directory)
            with patch("visualsectors_toolkit.providers.visualsectors.urlopen", side_effect=error):
                with self.assertRaises(ApiResponseError) as caught:
                    provider._request_json("GET", "/v1/levels", cache=False)
            self.assertTrue(str(caught.exception).endswith("run: vstoolkit login"))
            self.assertIn("https://api.visualsectors.com/signup", str(caught.exception))
            self.assertNotIn("do-not-echo", str(caught.exception))

    def test_key_file_is_rejected_without_echoing_its_contents(self):
        with self.assertRaisesRegex(ValueError, "single token"):
            VisualSectorsProvider(api_key="-----BEGIN OPENSSH PRIVATE KEY-----\nnot-a-secret")

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
