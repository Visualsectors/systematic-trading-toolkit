import copy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
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
from visualsectors_toolkit.providers.visualsectors import (
    CURRENT_LEVELS_LIMIT, CURRENT_METRIC_LIMIT, NEWS_HEADLINES_LIMIT, PLAN_INDICATORS,
)
from visualsectors_toolkit.screening import run_screen


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

    def test_live_trend_does_not_reject_positive_20_negative_60_session_momentum(self):
        closes = [150.0] + [100.0] * 39 + [100.0 + 0.5 * index for index in range(21)]
        self.assertLess((closes[-1] / closes[0] - 1) * 100, 0)
        bars = [{"date": (date(2026, 7, 24) + timedelta(days=index)).isoformat(),
                 "close": close, "volume": 1_000_000} for index, close in enumerate(closes)]
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            momentum, _volatility, adv = provider._derived_bar_fields(bars)
            row = replace(provider.get("AAPL"), price=110, atr14=5, sma20=105.25,
                          sma50=102.10, sma200=86.875, momentum_20d_pct=momentum,
                          average_dollar_volume_20d=adv)
            provider.calls.clear()
            with patch.object(provider, "get", return_value=row):
                snapshots = provider.screen_universe("trend_continuation", limit=5)
            body = provider.calls[0][3]
            self.assertEqual(body["criteria"], [{"id": "trend", "dataset": "technicals",
                                               "field": "sma50", "op": "gt", "value": 0}])
            self.assertEqual(body["sort"], {"field": "sma50", "direction": "desc"})
            self.assertEqual([candidate.ticker for candidate in run_screen(snapshots, "trend_continuation").candidates], ["AAPL"])
            self.assertIn("not the whole market", " ".join(provider.screen_warnings))

    def test_live_universe_defaults_to_five_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.universe()
            self.assertEqual(provider.calls[0][3]["limit"], 5)

    def test_screen_empty_or_cursor_pages_are_bounded_and_disclosed(self):
        for results in ([], [{"ticker": "AAPL"}]):
            with self.subTest(results=results), tempfile.TemporaryDirectory() as directory:
                provider = RecordedProvider(directory)
                provider.recorded[("POST", "/v1/screen", None)]["results"] = results
                provider.recorded[("POST", "/v1/screen", None)]["next_cursor"] = "more-candidates"
                provider.screen_universe("trend_continuation", limit=5)
                self.assertEqual(sum(path == "/v1/screen" for _, path, _, _ in provider.calls), 1)
                self.assertIn("Further candidates remain unexamined", " ".join(provider.screen_warnings))
                self.assertIn("at most 5", " ".join(provider.screen_warnings))

    def test_screen_over_limit_or_malformed_response_fails_before_hydration(self):
        for results in ([{"ticker": "AAPL"}] * 6, ["AAPL"]):
            with self.subTest(results=results), tempfile.TemporaryDirectory() as directory:
                provider = RecordedProvider(directory)
                provider.recorded[("POST", "/v1/screen", None)]["results"] = results
                with self.assertRaises(ApiResponseError), patch.object(provider, "get") as hydrate:
                    provider.screen_universe("near_support", limit=5)
                hydrate.assert_not_called()

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

    def test_current_levels_request_is_date_bounded_and_selected_on_weekends(self):
        # A Sunday ceiling must not invent a session date or require a row on Sunday.
        sunday = datetime(2026, 9, 27, 0, 30, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            with patch("visualsectors_toolkit.providers.visualsectors.datetime") as clock:
                clock.now.return_value = sunday
                clock.fromisoformat.side_effect = datetime.fromisoformat
                row = provider.get("AAPL")
            query = next(query for _method, path, query, _body in provider.calls if path == "/v1/levels")
            self.assertEqual(query, {"ticker": "AAPL", "date": "2026-09-27",
                                     "only_best": "true", "limit": str(CURRENT_LEVELS_LIMIT)})
            self.assertEqual([level.level_date for level in row.levels], ["2026-09-23"])

    def test_login_and_plans_never_follow_a_levels_cursor_even_on_short_or_empty_pages(self):
        for operation in ("verify", "get"):
            for count in (0, 1, 10, CURRENT_LEVELS_LIMIT):
                with self.subTest(operation=operation, count=count), tempfile.TemporaryDirectory() as directory:
                    provider = RecordedProvider(directory)
                    response = provider.recorded[("GET", "/v1/levels", None)]
                    response["rows"] = response["rows"] * count
                    response["next_cursor"] = "older-history-page"
                    if operation == "verify":
                        warnings = provider.verify()
                        self.assertTrue(all(flag is False for flag in provider.cache_flags))
                    else:
                        warnings = provider.get("AAPL").warnings
                    level_calls = [query for _method, path, query, _body in provider.calls if path == "/v1/levels"]
                    self.assertEqual(len(level_calls), 1)
                    self.assertNotIn("cursor", level_calls[0])
                    self.assertIn("only the first bounded page", " ".join(warnings))
                    self.assertEqual(len(provider.calls), 10 if operation == "verify" else 9)

    def test_current_levels_reject_an_over_limit_response(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            response = provider.recorded[("GET", "/v1/levels", None)]
            response["rows"] *= CURRENT_LEVELS_LIMIT + 1
            with self.assertRaisesRegex(ApiResponseError, "current-snapshot row limit"):
                provider.verify()

    def test_current_technicals_and_metrics_request_one_date_bounded_row_on_weekends(self):
        sunday = datetime(2026, 9, 27, 0, 30, tzinfo=timezone.utc)
        for operation in ("verify", "get"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                provider = RecordedProvider(directory)
                with patch("visualsectors_toolkit.providers.visualsectors.datetime") as clock:
                    clock.now.return_value = sunday
                    clock.fromisoformat.side_effect = datetime.fromisoformat
                    if operation == "verify":
                        provider.verify()
                    else:
                        provider.get("AAPL")
                    clock.now.assert_called_once_with(timezone.utc)
                for indicator in PLAN_INDICATORS:
                    path = f"/v1/technicals/{indicator}"
                    queries = [query for _method, route, query, _body in provider.calls if route == path]
                    self.assertEqual(queries, [{"ticker": "AAPL", "date": "2026-09-27",
                                                "limit": str(CURRENT_METRIC_LIMIT)}])
                metrics = [query for _method, route, query, _body in provider.calls if route == "/v1/fundamentals"]
                self.assertEqual(metrics, [{"ticker": "AAPL", "view": "metrics", "date": "2026-09-27",
                                             "limit": str(CURRENT_METRIC_LIMIT)}])
                news = [query for _method, route, query, _body in provider.calls if route == "/v1/news"]
                self.assertEqual(news, [{"ticker": "AAPL", "view": "headlines", "limit": str(NEWS_HEADLINES_LIMIT)}])
                self.assertEqual(provider._snapshots["AAPL"].rsi14, 33)
                self.assertEqual(provider._snapshots["AAPL"].pe_ratio, 29.5)

    def test_login_and_plans_never_follow_0_1_10_100_pages_of_current_evidence(self):
        routes = [(f"/v1/technicals/{indicator}", None) for indicator in PLAN_INDICATORS]
        routes += [("/v1/fundamentals", "metrics"), ("/v1/news", "headlines")]
        for operation in ("verify", "get"):
            for path, view in routes:
                for page_count in (0, 1, 10, 100):
                    for empty_first_page in (False, True):
                        with self.subTest(operation=operation, path=path, pages=page_count,
                                          empty=empty_first_page), tempfile.TemporaryDirectory() as directory:
                            provider = RecordedProvider(directory)
                            original_request = provider._request_json
                            requests = []

                            def page(method, route, *, query=None, body=None, cache=True):
                                response = original_request(method, route, query=query, body=body, cache=cache)
                                if route != path:
                                    return response
                                requests.append(query)
                                self.assertNotIn("cursor", query, "Current evidence must not request a continuation")
                                response["next_cursor"] = f"history:2-of-{page_count}" if page_count > 1 else None
                                if page_count == 0 or empty_first_page:
                                    response["rows"] = []
                                    response["count"] = 0
                                return response

                            with patch.object(provider, "_request_json", side_effect=page):
                                if operation == "verify":
                                    warnings = provider.verify()
                                else:
                                    warnings = provider.get("AAPL").warnings
                            self.assertEqual(len(requests), 1)
                            self.assertEqual(len(provider.calls), 10 if operation == "verify" else 9)
                            self.assertTrue(all(flag == (operation == "get") for flag in provider.cache_flags))
                            cursor_warnings = [warning for warning in warnings
                                               if path in warning and "only the first bounded page" in warning]
                            self.assertEqual(len(cursor_warnings), int(page_count > 1))
                            row = provider._snapshots["AAPL"]
                            empty = page_count == 0 or empty_first_page
                            if path.startswith("/v1/technicals/"):
                                self.assertEqual(getattr(row, path.rsplit("/", 1)[-1]) is None, empty)
                            elif view == "metrics":
                                self.assertEqual(row.pe_ratio is None, empty)
                            else:
                                self.assertEqual(len(row.evidence), 0 if empty else 1)

    def test_current_evidence_rejects_over_limit_rows_without_following_a_cursor(self):
        routes = [(f"/v1/technicals/{indicator}", None, CURRENT_METRIC_LIMIT) for indicator in PLAN_INDICATORS]
        routes += [("/v1/fundamentals", "metrics", CURRENT_METRIC_LIMIT),
                   ("/v1/news", "headlines", NEWS_HEADLINES_LIMIT)]
        for operation in ("verify", "get"):
            for path, view, limit in routes:
                with self.subTest(operation=operation, path=path), tempfile.TemporaryDirectory() as directory:
                    provider = RecordedProvider(directory)
                    response = provider.recorded[("GET", path, view)]
                    response["rows"] *= limit + 1
                    response["next_cursor"] = "history:2"
                    if view is None:
                        with self.assertRaisesRegex(ApiResponseError, "current-snapshot row limit"):
                            provider.verify() if operation == "verify" else provider.get("AAPL")
                    else:
                        warnings = provider.verify() if operation == "verify" else provider.get("AAPL").warnings
                        self.assertIn(f"{path} view={view} is unavailable", " ".join(warnings))
                        row = provider._snapshots["AAPL"]
                        if view == "metrics":
                            self.assertIsNone(row.pe_ratio)
                        else:
                            self.assertEqual(row.evidence, ())
                    queries = [query for _method, route, query, _body in provider.calls if route == path]
                    self.assertEqual(len(queries), 1)
                    self.assertNotIn("cursor", queries[0])

    def test_empty_or_after_cutoff_technicals_remain_missing_without_history_fallback(self):
        for indicator in PLAN_INDICATORS:
            for rows in ([], [{"date": "2026-09-24", "indicator": indicator, "value": 999}]):
                with self.subTest(indicator=indicator, rows=rows), tempfile.TemporaryDirectory() as directory:
                    provider = RecordedProvider(directory)
                    response = envelope(rows)
                    response["next_cursor"] = "older-session"
                    provider.recorded[("GET", f"/v1/technicals/{indicator}", None)] = response
                    row = provider.get("AAPL")
                    self.assertIsNone(getattr(row, indicator))
                    self.assertIn(f"{indicator} is unavailable", " ".join(row.warnings))

    def test_current_technicals_never_hide_authentication_or_rate_limits(self):
        for indicator in PLAN_INDICATORS:
            for failure in (ApiResponseError(401, "invalid key"), RateLimitError("42")):
                with self.subTest(indicator=indicator, failure=failure), tempfile.TemporaryDirectory() as directory:
                    provider = RecordedProvider(directory)
                    provider.recorded[("GET", f"/v1/technicals/{indicator}", None)] = failure
                    with self.assertRaises(type(failure)):
                        provider.verify()

    def test_news_retains_up_to_25_items_from_the_first_page_only(self):
        for count in (0, 1, 10, NEWS_HEADLINES_LIMIT):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                provider = RecordedProvider(directory)
                news = provider.recorded[("GET", "/v1/news", "headlines")]
                item = news["rows"][0]
                news["rows"] = [{**item, "id": f"story-{index}"} for index in range(count)]
                news["next_cursor"] = "older-headlines"
                row = provider.get("AAPL")
                self.assertEqual(len(row.evidence), count)
                self.assertIn("/v1/news view=headlines returned a cursor", " ".join(row.warnings))

    def test_plan_pagination_is_reserved_for_timeseries_with_its_60_row_bound(self):
        for operation in ("verify", "get"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                provider = RecordedProvider(directory)
                with patch.object(provider, "_get_pages", wraps=provider._get_pages) as pages:
                    provider.verify() if operation == "verify" else provider.get("AAPL")
                pages.assert_called_once()
                self.assertEqual(pages.call_args.args[0], "/v1/timeseries/history")
                self.assertEqual(pages.call_args.kwargs["max_rows"], 60)
                self.assertEqual(pages.call_args.kwargs["cache"], operation == "get")

    def test_current_levels_omit_history_and_observations_after_common_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            response = provider.recorded[("GET", "/v1/levels", None)]
            current = response["rows"][0]
            response["rows"] = [
                {**current, "level_date": "2026-09-22", "price": 117},
                {**current, "level_date": "2026-09-24", "price": 119},
                current,
            ]
            row = provider.get("AAPL")
            self.assertEqual([level.level_date for level in row.levels], ["2026-09-23"])
            self.assertIn("latest levels endpoint returned multiple dates", " ".join(row.warnings))

    def test_current_levels_never_hide_authentication_or_rate_limits(self):
        for failure in (ApiResponseError(401, "invalid key"), RateLimitError("42")):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                provider = RecordedProvider(directory)
                provider.recorded[("GET", "/v1/levels", None)] = failure
                with self.assertRaises(type(failure)):
                    provider.verify()

    def test_empty_current_levels_are_an_explicit_data_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.recorded[("GET", "/v1/levels", None)] = envelope([])
            row = provider.get("AAPL")
            self.assertEqual(row.levels, ())
            self.assertIn("No current selected levels", " ".join(row.warnings))

    def test_reported_aapl_and_msft_bounce_outliers_are_removed_with_named_gaps(self):
        for ticker, kind, price, bounce in (("AAPL", "donchian", 328.7, 4420),
                                           ("MSFT", "pivot", 497.09, 33196824404)):
            for all_bad in (False, True):
                with self.subTest(ticker=ticker, all_bad=all_bad), tempfile.TemporaryDirectory() as directory:
                    provider = RecordedProvider(directory)
                    response = provider.recorded[("GET", "/v1/levels", None)]
                    good = response["rows"][0]
                    bad = {**good, "level_type": kind, "price": price, "exp_bounce_pct": bounce,
                           "score": 1e12, "reward_risk": 1e12, "approach": "risk_reward"}
                    response["rows"] = [bad] if all_bad else [good, bad]
                    row = provider.get(ticker)
                    self.assertEqual(len(row.levels), 0 if all_bad else 1)
                    self.assertNotIn(kind, [level.level_type for level in row.levels])
                    warning = " ".join(row.warnings)
                    self.assertIn(f"{ticker} Support {kind} at {price:g}", warning)
                    self.assertIn(f"exp_bounce_pct={bounce}", warning)
                    self.assertIn("excluded from scoring and zones", warning)
                    if all_bad:
                        self.assertIn("No current selected levels", warning)

    def test_login_reports_the_level_guard_without_following_any_extra_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            response = provider.recorded[("GET", "/v1/levels", None)]
            response["rows"][0]["exp_bounce_pct"] = "4420"
            warnings = provider.verify()
            self.assertIn("AAPL Support ma at 118", " ".join(warnings))
            self.assertIn("exp_bounce_pct=4420", " ".join(warnings))
            self.assertEqual(provider._snapshots["AAPL"].levels, ())
            self.assertEqual(len(provider.calls), 10)
            self.assertTrue(all(flag is False for flag in provider.cache_flags))

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

    def test_history_uses_server_entitlement_floor_not_a_guessed_window(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.get("AAPL")
            history = next(query for method, path, query, body in provider.calls if path == "/v1/timeseries/history")
            self.assertNotIn("from", history)
            self.assertEqual(history["limit"], "60")

    def test_recent_row_bound_stops_pagination_and_preserves_earliest_cutoff(self):
        first, second = envelope([{"id": 4}, {"id": 3}]), envelope([{"id": 2}, {"id": 1}])
        first["next_cursor"], second["next_cursor"] = "second", "third"
        second["as_of"] = "2026-09-22T20:00:00Z"
        with tempfile.TemporaryDirectory() as directory:
            provider = VisualSectorsProvider(api_key="test-only", cache_dir=directory)
            with patch.object(provider, "_request_json", side_effect=[first, second]) as request:
                result = provider._get_pages("/v1/timeseries/history", {"ticker": "AAPL"}, max_rows=3)
        self.assertEqual(request.call_count, 2)
        self.assertEqual([row["id"] for row in result["rows"]], [4, 3, 2])
        self.assertEqual(result["as_of"], second["as_of"])
        self.assertEqual(result["client_row_bound"], 3)

    def test_runaway_pagination_is_bounded(self):
        counter = 0
        def page(*args, **kwargs):
            nonlocal counter
            counter += 1
            return {**envelope([]), "next_cursor": f"cursor:{counter}"}
        with tempfile.TemporaryDirectory() as directory:
            provider = VisualSectorsProvider(api_key="test-only", cache_dir=directory)
            with patch.object(provider, "_request_json", side_effect=page), self.assertRaisesRegex(ApiResponseError, "bounded pagination"):
                provider._get_pages("/v1/levels", {"ticker": "AAPL"})
        self.assertEqual(counter, 100)

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

    def test_api_hosts_reject_insecure_or_credential_bearing_urls_before_io(self):
        for host in ("http://api.example.com", "ftp://api.example.com", "https://user:password@example.com",
                     "https://example.com?secret=yes", "https://example.com#fragment", "https://example.com\n"):
            with self.subTest(host=host), patch("visualsectors_toolkit.providers.visualsectors.urlopen") as http:
                with self.assertRaisesRegex(ValueError, "HTTPS"):
                    VisualSectorsProvider(api_key="test-only", base_url=host)
                http.assert_not_called()

    def test_authenticated_redirects_are_refused_without_forwarding_a_key(self):
        from visualsectors_toolkit.providers.visualsectors import _NoCredentialRedirect
        from urllib.request import Request
        request = Request("https://api.visualsectors.com/v1/levels", headers={"Authorization": "Bearer test-only"})
        for target in ("http://api.visualsectors.com/v1/levels", "https://untrusted.example/v1/levels"):
            with self.subTest(target=target), self.assertRaisesRegex(ApiResponseError, "redirects are refused"):
                _NoCredentialRedirect().redirect_request(request, None, 302, "redirect", {}, target)

    def test_cache_is_separate_for_each_key_and_does_not_use_legacy_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            first = VisualSectorsProvider(api_key="first-test-key", cache_dir=directory)
            second = VisualSectorsProvider(api_key="second-test-key", cache_dir=directory)
            with patch("visualsectors_toolkit.providers.visualsectors.urlopen",
                       side_effect=[BytesIO(b'{"account":"first"}'), BytesIO(b'{"account":"second"}')]) as http:
                self.assertEqual(first._request_json("GET", "/v1/levels"), {"account": "first"})
                self.assertEqual(second._request_json("GET", "/v1/levels"), {"account": "second"})
                self.assertEqual(first._request_json("GET", "/v1/levels"), {"account": "first"})
                self.assertEqual(http.call_count, 2)
            self.assertNotEqual(first._cache_namespace, second._cache_namespace)
            paths = [str(path) for path in Path(directory).rglob("*.json")]
            self.assertEqual(len(paths), 2)
            self.assertTrue(all("test-key" not in path for path in paths))

    def test_multi_ticker_manifest_uses_latest_valid_snapshot_time(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.get("AAPL")
            for payload in provider.recorded.values():
                if isinstance(payload, dict) and "as_of" in payload:
                    payload["as_of"] = "2026-09-24T23:59:59Z"
            provider.get("MSFT")
            self.assertEqual(provider.manifest.decision_time, "2026-09-24T23:59:59Z")
            self.assertEqual(len(provider.manifest.snapshots), 2)

    def test_news_and_observations_after_common_cutoff_are_not_used(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = RecordedProvider(directory)
            provider.recorded[("GET", "/v1/levels", None)]["as_of"] = "2026-09-23T12:00:00Z"
            row = provider.get("AAPL")
            self.assertEqual(row.evidence, ())
            self.assertIn("after the common source cutoff", " ".join(row.warnings))

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
