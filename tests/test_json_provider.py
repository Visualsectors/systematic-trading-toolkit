import json
import tempfile
import unittest
from pathlib import Path

from visualsectors_toolkit.models import to_dict
from visualsectors_toolkit.providers import JsonFileProvider, SyntheticFixtureProvider


class JsonProviderTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.dumps(to_dict(SyntheticFixtureProvider().manifest), ensure_ascii=False)

    def test_utf8_bom_and_utf16_power_shell_files_are_accepted(self):
        for encoding in ("utf-8-sig", "utf-16"):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "dataset.json"
                path.write_bytes(self.payload.encode(encoding))
                self.assertEqual(len(JsonFileProvider(path).universe()), 5)

    def test_unsupported_encoding_includes_power_shell_hint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.json"
            path.write_bytes(b"\x80\x81")
            with self.assertRaisesRegex(ValueError, "Set-Content -Encoding utf8"):
                JsonFileProvider(path)


if __name__ == "__main__":
    unittest.main()
