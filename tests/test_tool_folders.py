"""The GitHub folder list is a tested, runnable front door to the toolkit."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
FOLDERS = ("screener", "position-sizer", "research", "risk-management", "monitoring", "support-resistance")


class ToolFolderTests(unittest.TestCase):
    def run_launcher(self, relative, arguments, cwd):
        result = subprocess.run(
            [sys.executable, str(ROOT / relative), *arguments],
            cwd=cwd,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_every_tool_has_structured_readme_api_link_and_launcher(self):
        for folder in FOLDERS:
            with self.subTest(folder=folder):
                self.assertTrue((ROOT / folder / "run.py").is_file())
                text = (ROOT / folder / "README.md").read_text(encoding="utf-8")
                for heading in ("## Quickstart", "## Inputs", "## What you get", "## How it works", "## Important boundaries"):
                    self.assertIn(heading, text)
                self.assertIn("https://api.visualsectors.com/signup", text)
                self.assertIn("--help", text)
                self.assertNotIn("api.vsdata.biz", text)

    def test_every_launcher_help_works_outside_the_checkout(self):
        paths = [f"{folder}/run.py" for folder in FOLDERS] + ["position-sizer/portfolio_slots.py"]
        with tempfile.TemporaryDirectory() as directory:
            for path in paths:
                with self.subTest(path=path):
                    text = self.run_launcher(path, ("--help",), directory)
                    self.assertIn("usage: vstoolkit", text)

    def test_every_launcher_executes_a_keyless_example(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = (
                ("screener/run.py", ("--offline", "--limit", "5")),
                ("position-sizer/run.py", ("--capital", "100000", "--risk-fraction", "0.005", "--entry", "100", "--stop", "95", "--max-allocation", "0.10")),
                ("position-sizer/portfolio_slots.py", ("--offline", "--tickers", "ALFA,BRVO", "--portfolio", "100000", "--intended-holdings", "10")),
                ("research/run.py", ("--offline", "--ticker", "ALFA", "--thesis", "Price holds structural support")),
                ("risk-management/run.py", ("--offline", "--ticker", "ALFA")),
                ("monitoring/run.py", ("--offline", "--ticker", "ALFA", "--state", str(Path(directory) / "monitor.json"))),
                ("support-resistance/run.py", ("ALFA", "--offline", "--capital", "25000")),
            )
            for path, arguments in cases:
                with self.subTest(path=path):
                    output = json.loads(self.run_launcher(path, arguments, directory))
                    self.assertIsInstance(output, dict)
                    self.assertTrue(output)
            self.assertEqual(json.loads((Path(directory) / "monitor.json").read_text(encoding="utf-8"))["ticker"], "ALFA")

    def test_local_readme_links_resolve_and_root_lists_all_six_tools(self):
        readmes = [ROOT / "README.md", *(ROOT / folder / "README.md" for folder in FOLDERS)]
        for readme in readmes:
            text = readme.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                if target.startswith(("https://", "http://", "#")):
                    continue
                with self.subTest(readme=readme, link=target):
                    self.assertTrue((readme.parent / target.split("#", 1)[0]).exists(), target)
        root_text = readmes[0].read_text(encoding="utf-8")
        self.assertLess(root_text.index("## Choose a tool"), root_text.index("## Run it on AAPL"))
        for folder in FOLDERS:
            self.assertIn(f"[{folder}/]({folder}/)", root_text)

    def test_support_resistance_replaces_the_old_launcher_path(self):
        self.assertFalse((ROOT / "entry-exit/run.py").exists())
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("support-resistance", workflow)
        self.assertNotIn("entry-exit", workflow)

    def test_monitoring_readme_has_one_fixed_timestamp_first_run_example(self):
        text = (ROOT / "monitoring/README.md").read_text(encoding="utf-8")
        command = r"python .\monitoring\run.py --offline --ticker ALFA --direction long --state .\monitoring\offline-state.local.json"
        self.assertEqual(text.count(command), 1)
        self.assertIn("fixed observation timestamp", text)
        self.assertIn("preserving the state file", text)

    def test_release_readme_matches_free_friendly_cli_default(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("The default limit is 5.", text)
        self.assertNotIn("The default limit is 25", text)

    def test_release_readme_does_not_describe_the_retired_production_contract(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("API **2.2.0 is live**", text)
        self.assertIn("| Free | 6 months | 60 | 1,000 | 5,000 |", text)
        self.assertIn("| LinkedIn-approved Free | 3 years | 500 | 10,000 | 100,000 |", text)
        for stale in ("2.1.0-dev", "older contract", "not yet production entitlements", "30-day levels-history window"):
            self.assertNotIn(stale, text)
        self.assertIn("A successful run on an account with a custom grant does not prove ordinary Free entitlements.", text)

    def test_level_docs_distinguish_frequencies_from_magnitudes_and_selection(self):
        for relative in ("README.md", "support-resistance/README.md", "docs/METHODOLOGY.md"):
            with self.subTest(document=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                for term in ("p_hold_7d_pct", "exp_bounce_pct", "hard_break_pct", "magnitudes in percentage points", "hindsight", "only_best=true"):
                    self.assertIn(term, text)
                self.assertNotIn("break rates", text)

    def test_release_qa_preserves_the_scope_of_unverified_checks(self):
        text = (ROOT / "docs/LIVE_QA.md").read_text(encoding="utf-8")
        self.assertIn("final ordinary-Free entitlement behavior and full chat-plugin installation remain unverified", text)
        self.assertIn("Do not claim the full checklist passed", text)
        self.assertIn("latest client guard is covered by synthetic regressions", text)


if __name__ == "__main__":
    unittest.main()
