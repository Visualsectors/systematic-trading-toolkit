import ast
import tempfile
import unittest
from pathlib import Path

from visualsectors_toolkit.cli import main


class CliTests(unittest.TestCase):
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
