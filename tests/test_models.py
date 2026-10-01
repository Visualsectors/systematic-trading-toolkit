import copy
import unittest

from visualsectors_toolkit.models import parse_manifest, to_dict
from visualsectors_toolkit.providers import SyntheticFixtureProvider


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.raw = to_dict(SyntheticFixtureProvider().manifest)

    def test_fixture_round_trips(self):
        parsed = parse_manifest(self.raw)
        self.assertTrue(parsed.synthetic)
        self.assertEqual(len(parsed.snapshots), 5)

    def test_unknown_fields_fail_closed(self):
        raw = copy.deepcopy(self.raw)
        raw["snapshots"][0]["mystery"] = 1
        with self.assertRaisesRegex(ValueError, "unknown fields: mystery"):
            parse_manifest(raw)

    def test_boolean_and_fractional_earnings_days_are_rejected(self):
        for invalid in (True, 1.5):
            with self.subTest(invalid=invalid):
                raw = copy.deepcopy(self.raw)
                raw["snapshots"][0]["days_to_earnings"] = invalid
                with self.assertRaisesRegex(ValueError, "must be an integer"):
                    parse_manifest(raw)

    def test_timezone_is_required(self):
        raw = copy.deepcopy(self.raw)
        raw["decision_time"] = "2026-01-15T21:00:00"
        with self.assertRaisesRegex(ValueError, "must include a timezone"):
            parse_manifest(raw)

    def test_decision_time_rejects_future_snapshot_evidence_and_level(self):
        mutations = (
            ("as_of", "2026-01-16T00:00:00Z"),
            ("evidence_as_of", "2026-01-16T00:00:00Z"),
            ("level_date", "2026-01-16"),
        )
        for kind, value in mutations:
            with self.subTest(kind=kind):
                raw = copy.deepcopy(self.raw)
                if kind == "as_of":
                    raw["snapshots"][0]["as_of"] = value
                elif kind == "evidence_as_of":
                    raw["snapshots"][0]["evidence"][0]["as_of"] = value
                else:
                    raw["snapshots"][0]["levels"][0]["level_date"] = value
                with self.assertRaisesRegex(ValueError, "after manifest.decision_time"):
                    parse_manifest(raw)

    def test_evidence_stance_is_required_and_ids_are_unique(self):
        missing = copy.deepcopy(self.raw)
        del missing["snapshots"][0]["evidence"][0]["stance"]
        with self.assertRaisesRegex(ValueError, "missing required fields: stance"):
            parse_manifest(missing)
        duplicate = copy.deepcopy(self.raw)
        duplicate["snapshots"][0]["evidence"][1]["id"] = duplicate["snapshots"][0]["evidence"][0]["id"]
        with self.assertRaisesRegex(ValueError, "evidence IDs must be unique"):
            parse_manifest(duplicate)

    def test_punctuation_only_ticker_is_rejected(self):
        raw = copy.deepcopy(self.raw)
        raw["snapshots"][0]["ticker"] = "..."
        with self.assertRaisesRegex(ValueError, "invalid ticker"):
            parse_manifest(raw)

    def test_file_backed_implausible_levels_keep_a_named_warning_without_duplication(self):
        raw = copy.deepcopy(self.raw)
        source = raw["snapshots"][0]["levels"][0]
        source.update(exp_bounce_pct=4420, reward_risk=1e12, approach="risk_reward")
        parsed = parse_manifest(raw)
        row = parsed.snapshots[0]
        warnings = [warning for warning in row.warnings if "exp_bounce_pct=4420" in warning]
        self.assertEqual(len(warnings), 1)
        self.assertIn(f"{row.ticker} {source['side']} {source['level_type']}", warnings[0])
        self.assertIn("excluded from scoring and zones", warnings[0])
        self.assertEqual(parse_manifest(to_dict(parsed)).snapshots[0].warnings, row.warnings)


if __name__ == "__main__":
    unittest.main()
