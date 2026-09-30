from contextlib import redirect_stdout
from copy import deepcopy
from importlib.resources import files
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from visualsectors_toolkit.cli import main
from visualsectors_toolkit.context_dataset import dataset_context
from visualsectors_toolkit.context_features import compute_context
from visualsectors_toolkit.context_live import live_context
from visualsectors_toolkit.context_market import new_york_close
from visualsectors_toolkit.models import parse_manifest, to_dict
from visualsectors_toolkit.providers import ApiResponseError


class ContextLiveV2Tests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(files("visualsectors_toolkit").joinpath("fixtures/context_demo.json").read_text(encoding="utf-8"))

    def test_dataset_v2_is_lossless_and_full_parity(self):
        validated = parse_manifest(deepcopy(self.raw))
        spec, packet = dataset_context(to_dict(validated))
        expected = json.loads((Path(__file__).parent / "fixtures/screener-context-0.5.0/computed-context.json").read_text(encoding="utf-8"))
        self.assertEqual(compute_context(spec, packet), expected)

    def test_v2_unknown_nested_and_future_fields_refuse(self):
        for kind in ("root", "market", "bar", "future_cap", "future_headline", "linked"):
            row = deepcopy(self.raw)
            if kind == "root": row["unexpected"] = True
            if kind == "market": row["market"]["unexpected"] = True
            if kind == "bar": row["bars"]["ALFA"]["bars"][0]["unexpected"] = True
            if kind == "future_cap": row["peers"]["ALFA"]["capitalization"] = {"security:x": {"market_cap": 100, "available_at": "2099-01-01T00:00:00.000Z"}}
            if kind == "future_headline": row["headlines"][0]["created_at"] = "2099-01-01T00:00:00.000Z"
            if kind == "linked": row["headlines"][0]["linked_tickers"] = [{"ticker": "ALFA", "relevance_score": 0.6, "unexpected": 1}]
            with self.subTest(kind=kind), self.assertRaises(ValueError): parse_manifest(row)

    def test_bars_cannot_be_read_before_new_york_close(self):
        row = deepcopy(self.raw)
        row["decision_time"] = row["context_provenance"]["retrieval_spec"]["decision_time"] = row["context_provenance"]["retrieval_spec"]["as_of_session"] + "T12:00:00.000Z"
        with self.assertRaises(ValueError): dataset_context(row)

    def test_dst_closes(self):
        self.assertEqual(new_york_close("2026-01-12").hour, 21)
        self.assertEqual(new_york_close("2026-07-13").hour, 20)
        self.assertEqual(new_york_close("2026-03-06").hour, 21)
        self.assertEqual(new_york_close("2026-03-09").hour, 20)

    def test_full_member_aggregate_and_pit_cap_weights(self):
        row = deepcopy(self.raw)
        peer = row["peers"]["ALFA"]
        peer.pop("aggregate")
        peer["capitalization"] = {member["vs_security_id"]: {"market_cap": 100 * (index + 1), "available_at": row["decision_time"]} for index, member in enumerate(peer["group"]["members"])}
        spec, packet = dataset_context(row)
        aggregate = packet["peer_aggregates"][0]
        self.assertEqual(aggregate["observed_peer_count_10d"], len(peer["group"]["members"]))
        weighting = aggregate["weighting"]
        self.assertAlmostEqual(weighting["largest_member_weight"], 6 / 21)
        self.assertAlmostEqual(weighting["effective_member_count"], 441 / 91)
        self.assertIn("PEER_AGGREGATES_CLIENT_DERIVED_MAD", compute_context(spec, packet)["risk_codes"])

    def test_representatives_cannot_stand_in_for_full_universe(self):
        row = deepcopy(self.raw)
        peer = row["peers"]["ALFA"]
        peer.pop("aggregate")
        peer["group"]["eligible_member_count"] += 10
        with self.assertRaisesRegex(ValueError, "every eligible member"): dataset_context(row)

    def test_malformed_packet_reports_validation_error_not_type_traceback(self):
        spec, packet = dataset_context(self.raw)
        packet["market_series"] = [False]
        with self.assertRaises(ValueError): compute_context(spec, packet)

    def fake(self, fail_benchmark=None):
        outer = self
        class Provider:
            def _get_pages(self, path, query, **kwargs):
                name = query["ticker"]
                if path.endswith("history"):
                    outer.assertNotIn("from", query)
                    outer.assertEqual(kwargs["max_rows"], 254)
                if name == fail_benchmark: raise ApiResponseError(403, "not entitled")
                if path == "/v1/news": return {"as_of": outer.raw["decision_time"], "rows": []}
                series = outer.raw["bars"]["ALFA"] if name == "AAPL" else next(item for item in outer.raw["market"]["series"] if item["ticker"] == name)
                return {"as_of": outer.raw["decision_time"], "rows": [{"date": bar["session"], **{key: bar[key] for key in ("open", "high", "low", "close", "volume")}, "split_coefficient": 1} for bar in series["bars"]]}
        return Provider()

    def test_live_partial_card_never_invents_peers(self):
        from visualsectors_toolkit.context_card import render_context_card
        spec, packet = live_context(self.fake(), "AAPL")
        result = compute_context(spec, packet)
        card = render_context_card(result, "AAPL")
        self.assertIn("not supplied", card)
        self.assertIn("LIVE_API_NON_POINT_IN_TIME", card)
        self.assertEqual(packet["peer_groups"], [])
        self.assertEqual(packet["market_breadth"]["eligible_count_10d"], 0)

    def test_missing_optional_benchmark_downgrades_instead_of_fabricating(self):
        spec, packet = live_context(self.fake("QQQ"), "AAPL")
        result = compute_context(spec, packet)
        self.assertIn("BENCHMARK_QQQ_NOT_SUPPLIED", result["risk_codes"])
        self.assertFalse(next(item for item in packet["market_series"] if item["ticker"] == "QQQ")["bars"])

    def test_live_candidate_failure_is_not_an_all_clear(self):
        with self.assertRaises(ApiResponseError): live_context(self.fake("AAPL"), "AAPL")

    def test_offline_cli_is_python_only(self):
        with patch("visualsectors_toolkit.context.shutil.which", return_value=None), redirect_stdout(StringIO()) as output:
            self.assertEqual(main(("context", "--offline", "--format", "markdown")), 0)
        for lane in ("Price", "Peers", "Market"): self.assertIn(lane, output.getvalue())
        self.assertIn("Synthetic demonstration", output.getvalue())
