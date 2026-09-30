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
FOLDERS = ("screener", "position-sizer", "research", "risk-management", "monitoring", "entry-exit")


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
                ("entry-exit/run.py", ("ALFA", "--offline", "--capital", "25000")),
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


if __name__ == "__main__":
    unittest.main()
