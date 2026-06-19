import re
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = SKILL_ROOT / "SKILL.md"
REFERENCE_DIR = SKILL_ROOT / "reference"
REFERENCE_README = REFERENCE_DIR / "README.md"
ENVIRONMENT_REFERENCE = REFERENCE_DIR / "environment.md"
NATURAL_LANGUAGE_REFERENCE = REFERENCE_DIR / "natural-language-input-protocol.md"
CPN_CONTROLS_REFERENCE = REFERENCE_DIR / "cpn-refinement-and-promotion-controls.md"

EXPECTED_REFERENCE_FILES = {
    "README.md",
    "agent-routing.md",
    "cpn-pair-model-schema.md",
    "cpn-refinement-and-promotion-controls.md",
    "cpn-workflow-readiness-checklist.md",
    "environment.md",
    "fallback-rules.md",
    "input-schema.md",
    "lattice-structure-and-term-attachment.md",
    "natural-language-input-protocol.md",
}

EXPECTED_SKILL_REFERENCES = {
    "reference/agent-routing.md",
    "reference/environment.md",
    "reference/fallback-rules.md",
    "reference/input-schema.md",
    "reference/natural-language-input-protocol.md",
}


class SkillReferenceDocsTests(unittest.TestCase):
    def test_reference_directory_contains_only_the_supported_reference_docs(self):
        actual = {path.name for path in REFERENCE_DIR.glob("*.md")}

        self.assertEqual(actual, EXPECTED_REFERENCE_FILES)

    def test_skill_only_references_the_retained_reference_docs(self):
        content = SKILL_FILE.read_text(encoding="utf-8")
        referenced = set(re.findall(r"reference/[A-Za-z0-9._-]+\.md", content))

        self.assertEqual(referenced, EXPECTED_SKILL_REFERENCES)

    def test_reference_readme_lists_only_the_supported_reference_docs(self):
        content = REFERENCE_README.read_text(encoding="utf-8")
        listed = set(re.findall(r"`([A-Za-z0-9._-]+\.md)`", content))

        self.assertEqual(listed, EXPECTED_REFERENCE_FILES - {"README.md"})

    def test_primary_reference_contract_centers_lattice_structure_and_legacy_bond_label(self):
        input_schema = (REFERENCE_DIR / "input-schema.md").read_text(encoding="utf-8")
        term_attachment = (
            REFERENCE_DIR / "lattice-structure-and-term-attachment.md"
        ).read_text(encoding="utf-8")
        routing = (REFERENCE_DIR / "agent-routing.md").read_text(encoding="utf-8")
        natural_language = NATURAL_LANGUAGE_REFERENCE.read_text(encoding="utf-8")

        self.assertIn("`lattice_structure`", input_schema)
        self.assertIn("structure-first", input_schema)
        self.assertIn("site_ref", input_schema)
        self.assertIn("bond_ref", input_schema)
        self.assertIn("orbit_ref", input_schema)
        self.assertIn("explicit_edge_ref", input_schema)
        self.assertIn("support_ref", input_schema)
        self.assertIn("site terms", term_attachment)
        self.assertIn("bond terms", term_attachment)
        self.assertIn("higher-body terms", term_attachment)
        self.assertIn("primary conceptual object", input_schema)
        self.assertIn("legacy compatibility", input_schema)
        self.assertIn("legacy compatibility", routing)
        self.assertIn("legacy compatibility", natural_language)

    def test_environment_reference_tracks_sunny_version_line(self):
        content = ENVIRONMENT_REFERENCE.read_text(encoding="utf-8")

        self.assertIn("`Sunny.jl 0.9.x`", content)
        self.assertNotIn("`Sunny.jl 0.7.x`", content)

    def test_stable_reference_docs_do_not_depend_on_develop_only_example_paths(self):
        for reference_file in (
            NATURAL_LANGUAGE_REFERENCE,
            CPN_CONTROLS_REFERENCE,
        ):
            content = reference_file.read_text(encoding="utf-8")

            self.assertNotIn("tmp/", content)
            self.assertNotIn("tests/data/", content)
            self.assertNotIn("tests/fixtures/", content)

    def test_cpn_controls_reference_covers_glt_solver_mode_routing(self):
        content = CPN_CONTROLS_REFERENCE.read_text(encoding="utf-8")

        for needle in (
            "`--glt-solver-mode`",
            "`fast`",
            "`certified`",
            "`--glt-certification-mode auto`",
            "`--glt-certification-mode required`",
            "`solver_role == \"final\"`",
            "`solver_role` remains `diagnostic-only`",
            "directly runs the certified GLT path",
        ):
            self.assertIn(needle, content)


if __name__ == "__main__":
    unittest.main()
