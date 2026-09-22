import re
import unittest
from pathlib import Path


class SkillTests(unittest.TestCase):
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
