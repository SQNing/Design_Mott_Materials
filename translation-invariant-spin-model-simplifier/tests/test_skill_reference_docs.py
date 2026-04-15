import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = SKILL_ROOT / "SKILL.md"
REFERENCE_DIR = SKILL_ROOT / "reference"
REFERENCE_README = REFERENCE_DIR / "README.md"

EXPECTED_REFERENCE_FILES = {
    "README.md",
    "environment.md",
    "fallback-rules.md",
    "input-schema.md",
}

EXPECTED_SKILL_REFERENCES = {
    "reference/environment.md",
    "reference/fallback-rules.md",
    "reference/input-schema.md",
}


class SkillReferenceDocsTests(unittest.TestCase):
    def test_reference_directory_only_contains_skill_facing_docs(self):
        actual = {path.name for path in REFERENCE_DIR.glob("*.md")}

        self.assertEqual(actual, EXPECTED_REFERENCE_FILES)

    def test_skill_only_references_the_retained_reference_docs(self):
        content = SKILL_FILE.read_text(encoding="utf-8")
        referenced = set(re.findall(r"reference/[A-Za-z0-9._-]+\.md", content))

        self.assertEqual(referenced, EXPECTED_SKILL_REFERENCES)

    def test_reference_readme_lists_only_the_retained_reference_docs(self):
        content = REFERENCE_README.read_text(encoding="utf-8")
        listed = set(re.findall(r"`([A-Za-z0-9._-]+\.md)`", content))

        self.assertEqual(listed, EXPECTED_REFERENCE_FILES - {"README.md"})


if __name__ == "__main__":
    unittest.main()
