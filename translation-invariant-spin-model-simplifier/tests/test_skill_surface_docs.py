import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = SKILL_ROOT / "SKILL.md"
ROUTING_FILE = SKILL_ROOT / "reference" / "agent-routing.md"
REFERENCE_README = SKILL_ROOT / "reference" / "README.md"
ENVIRONMENT_FILE = SKILL_ROOT / "reference" / "environment.md"
TOP_LEVEL_README = SKILL_ROOT / "README.md"


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

    def test_routing_docs_capture_recent_auditability_improvements(self):
        routing = _read_text(ROUTING_FILE)
        environment = _read_text(ENVIRONMENT_FILE)

        for needle in (
            "Broad-Text Escalation Checklist",
            "Agent-Assisted Landing Audit",
            "Evidence that usually supports staying `spin-only`",
            "Evidence that should trigger escalation",
            "missing detail alone is not evidence that retained-local-multiplet handling is required",
            "What agent assistance may transform",
            "What agent assistance must preserve",
            "What still forces `needs_input`",
        ):
            self.assertIn(needle, routing)

        for needle in (
            "Example blocked Sunny-backed message",
            "Example opt-in alternative-backend message",
            "requested Sunny-backed execution could not proceed",
        ):
            self.assertIn(needle, environment)

    def test_reference_readme_lists_agent_routing_reference(self):
        content = _read_text(REFERENCE_README)

        self.assertIn("agent-routing.md", content)

    def test_top_level_readme_describes_the_stable_surface(self):
        content = _read_text(TOP_LEVEL_README)

        for needle in (
            "stable expert-facing surface",
            "`SKILL.md`",
            "`reference/`",
            "`scripts/`",
            "`tests/`",
            "contract guardrails",
        ):
            self.assertIn(needle, content)


if __name__ == "__main__":
    unittest.main()
