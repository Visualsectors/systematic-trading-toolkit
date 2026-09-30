import re
import json
import unittest
from pathlib import Path


class SkillTests(unittest.TestCase):
    def test_four_skills_share_wording_and_have_portable_metadata(self):
        root = Path(__file__).parents[1]
        canonical = (root / "docs/SKILL_WORDING.md").read_text(encoding="utf-8")
        names = {"compose-screen", "analyze-screener-context", "build-research-thesis", "reassess-position"}
        self.assertEqual({item.name for item in (root / "skills").iterdir() if item.is_dir()}, names)
        for name in names:
            directory = root / "skills" / name
            self.assertEqual((directory / "references/wording.md").read_text(encoding="utf-8"), canonical)
            metadata = (directory / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${name}", metadata)
            self.assertIn("allow_implicit_invocation: true", metadata)
            self.assertTrue((directory / "references").is_dir())

    def test_derived_vocabulary_is_identical_in_skill_and_package(self):
        root = Path(__file__).parents[1]
        a = json.loads((root / "skills/compose-screen/references/trader-jargon.json").read_text(encoding="utf-8"))
        b = json.loads((root / "src/visualsectors_toolkit/fixtures/trader_jargon.json").read_text(encoding="utf-8"))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 190)

    def test_plugin_manifests_reference_the_four_skills(self):
        root = Path(__file__).parents[1]
        plugin = json.loads((root / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["name"], "systematic-trading-toolkit")
        self.assertEqual(marketplace["name"], "visualsectors")
        self.assertEqual(marketplace["plugins"][0]["source"], "./")

    def test_skill_frontmatter_and_names(self):
        root = Path(__file__).parents[1] / "skills"
        for skill in sorted(root.iterdir()):
            with self.subTest(skill=skill.name):
                text = (skill / "SKILL.md").read_text(encoding="utf-8")
                match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
                self.assertIsNotNone(match, "missing YAML frontmatter")
                fields = {}
                for line in match.group(1).splitlines():
                    key, separator, value = line.partition(":")
                    self.assertEqual(separator, ":")
                    fields[key] = value.strip()
                self.assertEqual(set(fields), {"name", "description"})
                self.assertEqual(fields["name"], skill.name)
                self.assertRegex(skill.name, r"^[a-z0-9-]+$")
                self.assertTrue(fields["description"])


if __name__ == "__main__":
    unittest.main()
