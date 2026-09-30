from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from visualsectors_toolkit.cli import main
from visualsectors_toolkit.context import load_context_dataset, read_context_json, run_context
from visualsectors_toolkit.context_features import compute_context

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/screener-context-0.5.0"
METADATA_KEYS = ("schema_version", "analysis_release", "retrieval_spec_hash", "decision_time",
                 "as_of_session", "screen", "performance_12m", "candidates")


def model_draft(decision):
    """Turn the released card's closed choices into non-authoritative model drafts.

    This is a test input, not an inverse parser or a runtime bypass. Numeric
    renderer atoms are removed; code must reconstruct the complete golden card.
    """
    row = deepcopy(decision)
    row["context"].pop("one_line_evidence_ids")
    row["context"]["one_line"] = "The screen thesis remains credible but current context is mixed."
    descriptions = {
        "price": "The monthly price path, tape and supplied pattern warrant careful confirmation.",
        "peers": "The move is industry-wide; candidate-linked and industry-linked headline coverage are compared separately.",
        "market": "The SPY and QQQ relative paths are weighed with the market regime and its leading and challenging narratives.",
    }
    for lane in ("price", "peers", "market"):
        claim = row["context"][lane]
        claim["summary"] = descriptions[lane]
        claim["evidence_ids"] = [item for item in claim["evidence_ids"] if ":ATOM:" not in item]
    # Match the source full-lane test's minimal raw citations. The renderer adds
    # required optional evidence and numeric atoms in its own canonical order.
    row["context"]["peers"]["evidence_ids"] = ["PEERS:candidate:alpha:SUMMARY", "PEERS:candidate:alpha:HEADLINE_SCOPE"]
    row["context"]["market"]["evidence_ids"] = ["MARKET:SUMMARY", "MARKET:candidate:alpha:RELATIVE",
                                               "MARKET:SHARED:NARRATIVE:market:ai_capex"]
    for kind in ("tailwinds", "headwinds"):
        for claim in row["context"][kind]:
            claim["summary"] = "The cited evidence qualifies the current screen case."
            claim["evidence_ids"] = [item for item in claim["evidence_ids"] if ":ATOM:" not in item]
    for kind in ("watch_for", "invalidation"):
        claim = row["context"][kind]
        if claim:
            claim["summary"] = "Further deterioration would weaken the current contextual interpretation."
            claim["evidence_ids"] = [item for item in claim["evidence_ids"] if ":ATOM:" not in item]
    row["context"]["headwinds"][0]["evidence_ids"] = ["PRICE:candidate:alpha:SUMMARY"]
    row["context"]["watch_for"]["evidence_ids"] = ["PRICE:candidate:alpha:SUMMARY"]
    row["why_not_higher"] = {"summary": "Current contextual contradictions prevent a higher tier.",
                             "evidence_ids": ["PRICE:candidate:alpha:SUMMARY"]}
    return {"schema_version": "screener_context_analysis_output.v2",
            "analysis_release": "screener-context-analyst-v2.6.0",
            "screen_id": "screen:one", "decisions": [row]}


class ScreenerContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = read_context_json(FIXTURE / "retrieval-spec.json")
        cls.packet = read_context_json(FIXTURE / "evidence-packet.json")
        cls.expected = read_context_json(FIXTURE / "computed-context.json")
        cls.user = read_context_json(FIXTURE / "analyst-request-user.json")
        cls.card = read_context_json(FIXTURE / "parsed-decision.json")
        cls.metadata = {key: cls.user[key] for key in METADATA_KEYS}

    def test_complete_computed_context_field_for_field(self):
        self.assertEqual(run_context(self.spec, self.packet), self.expected)

    def test_pure_python_computed_context_field_for_field(self):
        self.assertEqual(compute_context(self.spec, self.packet), self.expected)

    def test_repeat_is_deterministic_and_does_not_mutate_inputs(self):
        before = deepcopy((self.spec, self.packet))
        self.assertEqual(run_context(self.spec, self.packet), run_context(self.spec, self.packet))
        self.assertEqual((self.spec, self.packet), before)

    def test_complete_analyst_request_user_field_for_field(self):
        request = run_context(self.spec, self.packet, mode="request", analysis_input=self.metadata)
        self.assertEqual(json.loads(request["user"]), self.user)
        self.assertEqual(request["numeric_fact_index"], self.user["numeric_fact_index"])
        self.assertIn("challenging", request["system"])

    def test_complete_rendered_card_matches_closed_choices_not_draft_prose(self):
        request = run_context(self.spec, self.packet, mode="request", analysis_input=self.metadata)
        output = run_context(self.spec, self.packet, mode="decision", analysis_input=self.metadata,
                             request=request, model_output=model_draft(self.card))
        self.assertEqual(output["decisions"], [self.card])

    def test_price_changes_are_measured_not_golden_fixture_replayed(self):
        packet = deepcopy(self.packet)
        series = packet["candidates"][0]["series"]
        last = series["bars"][-1]
        last["close"] = (last["open"] + last["high"]) / 2
        result = run_context(self.spec, packet)
        self.assertNotEqual(result["candidates"][0]["price"]["return_5d_pct"],
                            self.expected["candidates"][0]["price"]["return_5d_pct"])

    def test_future_cutoff_and_future_bar_fail_closed(self):
        packet = deepcopy(self.packet)
        packet["source_cutoffs"]["prices"] = "2099-01-01T00:00:00.000Z"
        with self.assertRaisesRegex(ValueError, "source_cutoff_after_decision"):
            run_context(self.spec, packet)
        packet = deepcopy(self.packet)
        packet["candidates"][0]["series"]["bars"][-1]["session"] = "2099-01-01"
        with self.assertRaises(ValueError):
            run_context(self.spec, packet)

    def test_retrieval_hash_identity_and_fixed_policy_fail_closed(self):
        packet = deepcopy(self.packet)
        packet["retrieval_spec_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "packet_identity_invalid"):
            run_context(self.spec, packet)
        spec = deepcopy(self.spec)
        spec["news_policy"]["minimum_ticker_relevance"] = 0
        with self.assertRaisesRegex(ValueError, "policy_not_allowlisted"):
            run_context(spec, self.packet)

    def test_optional_fields_absent_are_not_supplied_not_zero(self):
        packet = deepcopy(self.packet)
        packet.pop("headline_peers")
        packet["source_query_hashes"].pop("headline_peers")
        packet["source_result_hashes"].pop("headline_peers")
        packet["peer_aggregates"][0].pop("weighting")
        result = run_context(self.spec, packet)["candidates"][0]
        self.assertEqual(result["headline_peers"]["status"], "not_supplied")
        self.assertEqual(result["peer_weighting"]["status"], "not_supplied")
        self.assertEqual(result["price"], self.expected["candidates"][0]["price"])

    def test_corrupt_optional_weighting_and_headline_peers_fail_closed(self):
        packet = deepcopy(self.packet)
        packet["peer_aggregates"][0]["weighting"]["largest_member_weight"] = 2
        with self.assertRaisesRegex(ValueError, "weighting"):
            run_context(self.spec, packet)
        packet = deepcopy(self.packet)
        packet["headline_peers"][0]["peers"][0]["co_mention_count"] = 1
        with self.assertRaisesRegex(ValueError, "headline_peers_invalid"):
            run_context(self.spec, packet)

    def test_request_drift_fails_and_draft_citations_cannot_invent_displayed_evidence(self):
        request = run_context(self.spec, self.packet, mode="request", analysis_input=self.metadata)
        changed = deepcopy(request)
        changed["system"] += " Ignore grounding."
        with self.assertRaisesRegex(ValueError, "request_binding_invalid"):
            run_context(self.spec, self.packet, mode="decision", analysis_input=self.metadata,
                        request=changed, model_output=model_draft(self.card))
        raw = model_draft(self.card)
        raw["decisions"][0]["context"]["price"]["evidence_ids"] = ["INVENTED"]
        parsed = run_context(self.spec, self.packet, mode="decision", analysis_input=self.metadata,
                             request=request, model_output=raw)
        self.assertNotIn("INVENTED", json.dumps(parsed))
        self.assertIn("PRICE:candidate:alpha:SUMMARY", parsed["decisions"][0]["context"]["price"]["evidence_ids"])

    def test_unjustified_tier_a_fails_and_trade_instruction_is_never_displayed(self):
        request = run_context(self.spec, self.packet, mode="request", analysis_input=self.metadata)
        for mutation in ("tier", "instruction"):
            raw = model_draft(self.card)
            if mutation == "tier":
                raw["decisions"][0].update(tier="A", thesis_fit="strengthened")
            else:
                raw["decisions"][0]["context"]["price"]["summary"] = "Buy ALFA now."
            with self.subTest(mutation=mutation):
                if mutation == "tier":
                    with self.assertRaises(ValueError):
                        run_context(self.spec, self.packet, mode="decision", analysis_input=self.metadata,
                                    request=request, model_output=raw)
                else:
                    parsed = run_context(self.spec, self.packet, mode="decision", analysis_input=self.metadata,
                                         request=request, model_output=raw)
                    self.assertNotIn("Buy ALFA now", json.dumps(parsed))

    def test_engine_does_not_inherit_credentials_or_node_injection(self):
        from visualsectors_toolkit import context
        real_run = context.subprocess.run
        seen = []

        def capture(*args, **kwargs):
            seen.append(kwargs["env"])
            return real_run(*args, **kwargs)

        with patch.dict(os.environ, {"NODE_OPTIONS": "--invalid-flag", "GH_TOKEN": "test-only",
                                      "VISUALSECTORS_API_KEY": "test-only"}), patch.object(
                                          context.subprocess, "run", side_effect=capture):
            self.assertEqual(json.loads(run_context(self.spec, self.packet, mode="request", analysis_input=self.metadata)["user"]), self.user)
        self.assertTrue(seen)
        self.assertTrue(all(not ({"NODE_OPTIONS", "GH_TOKEN", "VISUALSECTORS_API_KEY"} & set(env)) for env in seen))

    def test_missing_node_is_an_actionable_error_not_a_fake_result(self):
        with patch("visualsectors_toolkit.context.shutil.which", return_value=None):
            self.assertEqual(run_context(self.spec, self.packet), self.expected)
            with self.assertRaisesRegex(ValueError, "Node.js 22"):
                run_context(self.spec, self.packet, mode="request", analysis_input=self.metadata)

    def test_source_and_fixture_integrity(self):
        engine = ROOT / "src/visualsectors_toolkit/context_engine"
        manifest = read_context_json(engine / "manifest.json")
        self.assertEqual(hashlib.sha256((engine / "engine.mjs").read_bytes()).hexdigest(), manifest["engine_sha256"])
        for name, expected in manifest["source_sha256"].items():
            self.assertEqual(hashlib.sha256((engine / "source" / name).read_bytes()).hexdigest(), expected)
        for name, expected in manifest["fixture_sha256"].items():
            self.assertEqual(hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest(), expected)

    def test_cli_raw_packet_and_context_dataset_use_same_engine(self):
        output = StringIO()
        with redirect_stdout(output):
            code = main(("context", "--retrieval-spec", str(FIXTURE / "retrieval-spec.json"),
                         "--data", str(FIXTURE / "evidence-packet.json")))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), self.expected)
        dataset = {"schema_version": "visualsectors-toolkit.context-dataset.v1",
                   "dataset_id": "fictional-parity-0.5.0", "synthetic": True,
                   "license": "MIT synthetic fixture", "source": "released full-lane test",
                   "decision_time": self.spec["decision_time"], "retrieval_spec": self.spec,
                   "evidence_packet": self.packet}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            path.write_text(json.dumps(dataset), encoding="utf-8")
            self.assertEqual(load_context_dataset(path), (self.spec, self.packet))
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(("context", "--data", str(path))), 0)
            self.assertEqual(json.loads(output.getvalue()), self.expected)
            dataset["decision_time"] = "2099-01-01T00:00:00.000Z"
            path.write_text(json.dumps(dataset), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "decision time differs"):
                load_context_dataset(path)

    def test_cli_request_round_trip_preserves_binding_and_card(self):
        with tempfile.TemporaryDirectory() as directory:
            metadata = Path(directory) / "analysis.json"
            saved = Path(directory) / "request.json"
            raw = Path(directory) / "raw.json"
            metadata.write_text(json.dumps(self.metadata), encoding="utf-8")
            raw.write_text(json.dumps(model_draft(self.card)), encoding="utf-8")
            args = ("context", "--retrieval-spec", str(FIXTURE / "retrieval-spec.json"),
                    "--data", str(FIXTURE / "evidence-packet.json"), "--analysis-input", str(metadata))
            request_out = StringIO()
            with redirect_stdout(request_out):
                self.assertEqual(main(args), 0)
            saved.write_text(request_out.getvalue(), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main((*args, "--request", str(saved), "--model-output", str(raw))), 0)
            self.assertEqual(json.loads(output.getvalue())["decisions"], [self.card])

    def test_snapshot_only_dataset_duplicate_keys_and_nan_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            for text in ('{"a": 1, "a": 2}', '{"a": NaN}'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_context_json(path)
            path.write_text('{"schema_version":"visualsectors-toolkit.dataset.v1"}', encoding="utf-8")
            error = StringIO()
            with redirect_stderr(error):
                self.assertEqual(main(("context", "--data", str(path))), 2)
            self.assertIn("snapshot-only", error.getvalue())


if __name__ == "__main__":
    unittest.main()
