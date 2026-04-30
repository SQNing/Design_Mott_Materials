import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = SKILL_ROOT / "SKILL.md"
ROUTING_FILE = SKILL_ROOT / "reference" / "agent-routing.md"
REFERENCE_README = SKILL_ROOT / "reference" / "README.md"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class SkillSurfaceDocsTests(unittest.TestCase):
    def test_top_level_skill_keeps_core_guarantees_and_delegates_routing(self):
        content = _read_text(SKILL_FILE)

        self.assertIn("interaction.status = needs_input", content)
        self.assertIn("H_main + H_low_weight + H_residual", content)
        self.assertIn("reference/agent-routing.md", content)
        self.assertNotIn("normalize_document_with_agent.py", content)
        self.assertNotIn("run_document_reader_pipeline.py", content)
        self.assertNotIn("solve_cpn_payload_pipeline.py", content)

    def test_agent_routing_reference_covers_current_supported_routes(self):
        content = _read_text(ROUTING_FILE)

        for needle in (
            "Input Classes",
            "Routing By Input Class",
            "Agent-Assisted Landing",
            "Classical Family Resolution",
            "Backend And Solver Routing",
            "Current Semantic Conventions",
            "Recommended Entrypoints",
            "many_body_hr",
            "spin-only",
            "cpn",
            "agent_normalization_request",
            "agent_normalized_document",
            "sunny-cpn-minimize",
            "cpn-generalized-lt",
        ):
            self.assertIn(needle, content)

    def test_reference_readme_lists_agent_routing_reference(self):
        content = _read_text(REFERENCE_README)

        self.assertIn("agent-routing.md", content)


if __name__ == "__main__":
    unittest.main()
