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


if __name__ == "__main__":
    unittest.main()
