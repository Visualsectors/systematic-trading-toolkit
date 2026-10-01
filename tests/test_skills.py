import re
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
TOPICS = ("screener", "research", "risk-management", "monitoring", "support-resistance")
EXISTING_SKILLS = {
    "compose-screen": "screener",
    "analyze-screener-context": "screener",
    "build-research-thesis": "research",
    "review-risk": "risk-management",
    "reassess-position": "monitoring",
    "read-levels": "support-resistance",
}


def topical_skills():
    return sorted(path.parent for topic in TOPICS for path in (ROOT / topic / "skills").glob("*/SKILL.md"))


class SkillTests(unittest.TestCase):
    def test_skills_live_with_their_tools_and_share_portable_wording(self):
        canonical = (ROOT / "docs/SKILL_WORDING.md").read_bytes()
        directories = topical_skills()
        names = [directory.name for directory in directories]
        self.assertEqual(len(names), len(set(names)), "duplicate skill names")
        for name, topic in EXISTING_SKILLS.items():
            self.assertIn(ROOT / topic / "skills" / name, directories)
        self.assertFalse(list((ROOT / "skills").glob("*/SKILL.md")), "skills must not live in a separate root folder")
        self.assertFalse(list((ROOT / "position-sizer").rglob("SKILL.md")), "position sizing intentionally has no skill")
        for directory in directories:
            self.assertEqual((directory / "references/wording.md").read_bytes(), canonical)
            metadata = (directory / "agents/openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${directory.name}", metadata)
            self.assertIn("allow_implicit_invocation: true", metadata)
            self.assertTrue((directory / "references").is_dir())

    def test_derived_vocabulary_is_identical_in_skill_and_package(self):
        a = json.loads((ROOT / "screener/skills/compose-screen/references/trader-jargon.json").read_text(encoding="utf-8"))
        b = json.loads((ROOT / "src/visualsectors_toolkit/fixtures/trader_jargon.json").read_text(encoding="utf-8"))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 190)

    def test_plugin_manifest_discovers_every_topical_skill_exactly_once(self):
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["name"], "systematic-trading-toolkit")
        self.assertEqual(marketplace["name"], "visualsectors")
        self.assertEqual(marketplace["plugins"][0]["source"], "./")
        discovered = []
        for relative in plugin["skills"]:
            self.assertTrue(relative.startswith("./"))
            self.assertNotIn("..", Path(relative).parts)
            directory = ROOT / relative
            self.assertTrue(directory.is_dir(), f"missing manifest path: {relative}")
            self.assertIn(directory.parent.name, TOPICS)
            self.assertEqual(directory.name, "skills")
            discovered.extend(path.parent for path in directory.glob("*/SKILL.md"))
        self.assertEqual(len(discovered), len(set(discovered)), "manifest loads duplicate skills")
        self.assertEqual(set(discovered), set(topical_skills()))

    def test_skill_frontmatter_and_names(self):
        for skill in topical_skills():
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

    def test_moved_skills_keep_their_local_references(self):
        for skill in topical_skills():
            for document in [skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]:
                text = document.read_text(encoding="utf-8")
                for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                    if target.startswith(("https://", "http://", "#")):
                        continue
                    with self.subTest(document=document, link=target):
                        self.assertTrue((document.parent / target.split("#", 1)[0]).exists(), target)


if __name__ == "__main__":
    unittest.main()
