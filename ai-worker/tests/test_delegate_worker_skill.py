"""Contract tests for the delegate-worker model-executed function."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "delegate-worker"
SKILL_PATH = SKILL_DIR / "SKILL.md"
OPENAI_YAML_PATH = SKILL_DIR / "agents" / "openai.yaml"


def parse_frontmatter(document: str) -> tuple[dict[str, str], str]:
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", document, re.DOTALL)
    if match is None:
        raise AssertionError("SKILL.md must contain one YAML frontmatter block")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise AssertionError(f"invalid frontmatter line: {line!r}")
        fields[key.strip()] = value.strip()
    return fields, match.group(2)


class DelegateWorkerSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = SKILL_PATH.read_text(encoding="utf-8")
        cls.frontmatter, cls.body = parse_frontmatter(cls.document)
        cls.metadata = OPENAI_YAML_PATH.read_text(encoding="utf-8")

    def test_skill_has_only_supported_frontmatter_fields(self) -> None:
        self.assertEqual(set(self.frontmatter), {"name", "description"})
        self.assertEqual(self.frontmatter["name"], "delegate-worker")

    def test_description_exposes_positive_and_negative_routing(self) -> None:
        description = self.frontmatter["description"].lower()
        for trigger in ("repository discovery", "context compression", "visual analysis", "image generation"):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, description)
        for exclusion in ("architecture", "security", "concurrency", "production", "destructive", "implementation"):
            with self.subTest(exclusion=exclusion):
                self.assertIn(exclusion, description)

    def test_context_risk_heuristic_is_explicit(self) -> None:
        self.assertIn("context volume is high", self.body)
        self.assertIn("reasoning complexity is low or medium", self.body)
        self.assertIn("risk is low", self.body)
        self.assertIn("risk is medium/high", self.body)

    def test_abstraction_boundary_forbids_direct_backend_calls(self) -> None:
        self.assertIn("Invoke only `ai-worker`; never invoke `agy` directly.", self.body)
        shell_blocks = re.findall(r"```bash\n(.*?)```", self.body, re.DOTALL)
        self.assertEqual(len(shell_blocks), 3)
        for block in shell_blocks:
            with self.subTest(block=block):
                self.assertIn("ai-worker", block)
                self.assertNotRegex(block, r"(^|\s)agy(?:\s|$)")

    def test_analyze_contract_has_cwd_task_and_both_callers(self) -> None:
        self.assertRegex(self.body, r"ai-worker analyze --cwd \"\$PWD\" --task")
        self.assertIn("AI_WORKER_CALLER=codex", self.body)
        self.assertIn("AI_WORKER_CALLER=claude", self.body)
        self.assertIn("positional task or stdin", self.body)

    def test_vision_contract_supports_multiple_images_and_known_formats(self) -> None:
        self.assertRegex(self.body, r"ai-worker vision --image .* --task")
        self.assertIn("Repeat `--image` for multiple images", self.body)
        for image_format in ("PNG", "JPEG", "WebP"):
            with self.subTest(image_format=image_format):
                self.assertIn(image_format, self.body)

    def test_image_contract_marks_output_non_authoritative_and_jpeg(self) -> None:
        self.assertRegex(self.body, r"ai-worker image --prompt .* --output .*\.jpg")
        self.assertIn("reliably emits JPEG", self.body)
        self.assertIn("Do not claim generated images are factual evidence", self.body)

    def test_primary_agent_retains_every_high_value_responsibility(self) -> None:
        for responsibility in (
            "final reasoning",
            "code modifications",
            "architecture",
            "security",
            "concurrency correctness",
            "production/destructive operations",
            "verification",
            "final review",
        ):
            with self.subTest(responsibility=responsibility):
                self.assertIn(responsibility, self.body)

    def test_sensitive_data_and_recursive_delegation_are_forbidden(self) -> None:
        for forbidden in (
            "credentials",
            "private keys",
            "tokens",
            "cookies",
            "production secrets",
            "`.env` secret values",
            "Never recursively invoke `ai-worker`",
            "another agent, MCP, or autonomous tool",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, self.body)

    def test_mutating_and_production_actions_are_forbidden(self) -> None:
        for action in ("edit", "commit", "push", "deploy", "delete", "operate production systems"):
            with self.subTest(action=action):
                self.assertIn(action, self.body)

    def test_verification_policy_covers_critical_evidence(self) -> None:
        self.assertIn("Independently open the most important cited files", self.body)
        for evidence in ("financial figures", "security settings", "production state", "exact configuration", "safety-critical"):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, self.body)

    def test_examples_cover_positive_and_primary_only_cases(self) -> None:
        self.assertIn("Good delegation:", self.body)
        self.assertIn("Keep primary:", self.body)
        for case in ("cluster 200 logs", "compare two screenshots", "memory-order correctness", "review cryptography"):
            with self.subTest(case=case):
                self.assertIn(case, self.body)

    def test_openai_metadata_matches_skill(self) -> None:
        self.assertIn('display_name: "Delegate AI Worker"', self.metadata)
        short_match = re.search(r'short_description: "([^"]+)"', self.metadata)
        self.assertIsNotNone(short_match)
        self.assertGreaterEqual(len(short_match.group(1)), 25)
        self.assertLessEqual(len(short_match.group(1)), 64)
        self.assertRegex(self.metadata, r'default_prompt: ".*\$delegate-worker.*"')

    def test_skill_remains_small_and_contains_no_auxiliary_docs(self) -> None:
        self.assertLess(len(self.body.splitlines()), 500)
        files = {
            path.relative_to(SKILL_DIR).as_posix()
            for path in SKILL_DIR.rglob("*")
            if path.is_file()
        }
        self.assertEqual(files, {"SKILL.md", "agents/openai.yaml"})


if __name__ == "__main__":
    unittest.main()
