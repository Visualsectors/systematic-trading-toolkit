import ast
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from visualsectors_toolkit.cli import _build_parser, main
from visualsectors_toolkit.providers import ApiResponseError, MissingApiKeyError, VisualSectorsProviderError


class CliTests(unittest.TestCase):
    def test_every_subcommand_help_exits_cleanly(self):
        parser = _build_parser()
        subcommands = next(action for action in parser._actions if hasattr(action, "choices") and isinstance(action.choices, dict))
        for command in (None, *subcommands.choices):
            with self.subTest(command=command), redirect_stdout(StringIO()) as output:
                with self.assertRaises(SystemExit) as caught:
                    main((command, "--help") if command else ("--help",))
                self.assertEqual(caught.exception.code, 0)
                self.assertIn("usage: vstoolkit", output.getvalue())
                if command in ("plan", "size-stop"):
                    self.assertIn("10%", output.getvalue())
                    self.assertNotIn("10%%", output.getvalue())

    def test_demo_writes_all_six_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.md"
            self.assertEqual(main(("demo", "--output", str(output))), 0)
            text = output.read_text(encoding="utf-8")
            for heading in (
                "## 1. Screener", "## 2. Position sizing", "## 3. Research agent",
                "## 4. Risk management", "## 5. Monitoring", "## 6. Entry and exit planning",
            ):
                self.assertIn(heading, text)
            self.assertIn("Synthetic data only", text)

    def test_missing_live_key_prints_exact_signup_line_and_exits_two(self):
        error = StringIO()
        with patch(
            "visualsectors_toolkit.cli.VisualSectorsProvider", side_effect=MissingApiKeyError()
        ), redirect_stderr(error):
            self.assertEqual(main(("plan", "AAPL")), 2)
        self.assertEqual(
            error.getvalue().strip(),
            "AAPL needs live data. Get a free key (no card) at "
            "https://api.visualsectors.com/signup, then run: vstoolkit login",
        )

    def test_login_keeps_key_out_of_output_and_command_line(self):
        secret = "recorded-secret-test"
        output = StringIO()
        error = StringIO()
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                with patch("visualsectors_toolkit.cli.getpass.getpass", return_value=secret), patch(
                    "visualsectors_toolkit.cli.VisualSectorsProvider"
                ) as provider, redirect_stdout(output), redirect_stderr(error):
                    provider.return_value.verify.return_value = ("Recorded data gap",)
                    self.assertEqual(main(("login", "--no-open")), 0)
                provider.assert_called_once_with(api_key=secret)
                provider.return_value.verify.assert_called_once_with()
                self.assertNotIn(secret, output.getvalue())
                self.assertNotIn(secret, error.getvalue())
                self.assertIn("Recorded data gap", error.getvalue())
                self.assertIn("VISUALSECTORS_API_KEY=", Path(".env").read_text(encoding="utf-8"))
                self.assertIn(".env", Path(".gitignore").read_text(encoding="utf-8"))
            finally:
                os.chdir(original)

    def test_empty_login_does_not_fall_back_to_an_existing_key(self):
        with patch("visualsectors_toolkit.cli.getpass.getpass", return_value=""), patch(
            "visualsectors_toolkit.cli.VisualSectorsProvider"
        ) as provider, redirect_stderr(StringIO()):
            self.assertEqual(main(("login", "--no-open")), 2)
            provider.assert_not_called()

    def test_failed_login_never_replaces_existing_key(self):
        original = Path.cwd()
        error = StringIO()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                Path(".env").write_text("VISUALSECTORS_API_KEY=previous-test-key\n", encoding="utf-8")
                with patch("visualsectors_toolkit.cli.getpass.getpass", return_value="invalid-test-key"), patch(
                    "visualsectors_toolkit.cli.VisualSectorsProvider"
                ) as provider, redirect_stderr(error):
                    provider.return_value.verify.side_effect = ApiResponseError(401, "invalid")
                    self.assertEqual(main(("login", "--no-open")), 2)
                self.assertEqual(Path(".env").read_text(encoding="utf-8"), "VISUALSECTORS_API_KEY=previous-test-key\n")
                self.assertTrue(error.getvalue().strip().endswith("run: vstoolkit login"))
                self.assertNotIn("invalid-test-key", error.getvalue())
            finally:
                os.chdir(original)

    def test_monitor_persists_first_provider_failure_with_real_ticker(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            with patch(
                "visualsectors_toolkit.cli._provider",
                side_effect=VisualSectorsProviderError("recorded outage"),
            ), redirect_stdout(StringIO()):
                self.assertEqual(main(("monitor", "--ticker", "AAPL", "--state", str(state))), 2)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["ticker"], "AAPL")
            self.assertEqual(saved["failure"], "recorded outage")

    def test_plan_supports_short_direction_offline(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(("plan", "BRVO", "--direction", "short", "--offline")), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["plan"]["direction"], "short")

    def test_risk_command_exposes_real_register_with_evidence_and_triggers(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(("risk", "--ticker", "ALFA", "--offline")), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["ticker"], "ALFA")
        self.assertTrue(result["flags"])
        for flag in result["flags"]:
            self.assertIn(flag["kind"], ("headwind", "tailwind", "uncertainty"))
            self.assertTrue(flag["trigger"])
            self.assertTrue(flag["reassessment_action"])


class PurityTests(unittest.TestCase):
    def test_calculation_modules_do_not_import_io_or_nondeterminism(self):
        root = Path(__file__).parents[1] / "src" / "visualsectors_toolkit"
        pure = ("levels.py", "models.py", "monitoring.py", "research.py", "risk.py", "screening.py", "sizing.py")
        forbidden = {"requests", "httpx", "urllib", "socket", "random", "secrets", "os", "pathlib"}
        for name in pure:
            with self.subTest(module=name):
                tree = ast.parse((root / name).read_text(encoding="utf-8"))
                imports = {
                    alias.name.split(".")[0]
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Import)
                    for alias in node.names
                }
                imports.update(
                    node.module.split(".")[0]
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                )
                self.assertFalse(imports & forbidden, f"{name} imports {imports & forbidden}")
                calls = [
                    node.func.attr
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                ]
                self.assertNotIn("now", calls)
                self.assertNotIn("utcnow", calls)


if __name__ == "__main__":
    unittest.main()
