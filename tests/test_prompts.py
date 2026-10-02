from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    "narrative-cluster-v1.md": "60f33ccd7743579554092e66e1f7ab7622e3e54b703b89d5a4b11313452afbb7",
    "news-sentiment-explainer-v1.md": "f25ed284e38a87eda78bb9706009810858d2be8f7b4ba3db1791c29426d5db16",
    "options-reference-v1.md": "a1bc126e2284638b24dcfa220c0e913f94be9c7e8ce82ed253db78a794b00273",
    "support-resistance-explainer-v1.md": "e2f78a37c5ff7b80c06405051ee6fef97619b80bd0d9a20eca87265c245fd317",
}


# unittest classes, because CI runs `python -m unittest discover -s tests`, which skips bare pytest functions.
class PromptTests(unittest.TestCase):
    def test_public_prompt_files_are_present_and_pinned(self) -> None:
        for filename, expected in PROMPTS.items():
            with self.subTest(prompt=filename):
                text = (ROOT / "prompts" / filename).read_text(encoding="utf-8").replace("\r\n", "\n").rstrip()
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), expected)

    def test_prompts_keep_the_connector_only_boundary(self) -> None:
        for filename in PROMPTS:
            with self.subTest(prompt=filename):
                text = (ROOT / "prompts" / filename).read_text(encoding="utf-8").lower()
                self.assertTrue(
                    "do not browse" in text
                    or "no browsing" in text
                    or "use only the closed projection" in text
                )

    def test_readmes_call_the_prompts_an_unsynced_snapshot(self) -> None:
        self.assertIn("are not kept in sync", (ROOT / "prompts/README.md").read_text(encoding="utf-8"))
        self.assertIn("This is a one-time snapshot", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
