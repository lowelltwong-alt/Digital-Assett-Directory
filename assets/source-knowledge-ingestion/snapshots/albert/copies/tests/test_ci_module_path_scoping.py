import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


class CiModulePathScopingTests(unittest.TestCase):
    def test_simulator_workflow_is_not_repository_wide(self) -> None:
        text = read_workflow("simulation-red-team.yml")
        self.assertGreaterEqual(text.count("paths:"), 2)
        self.assertGreaterEqual(text.count('"simulation/**"'), 2)
        self.assertNotIn("codex/**", text)
        self.assertNotIn("agent/**", text)
        self.assertNotRegex(text, re.compile(r'paths:[\s\S]*?"\*\*/\*ocr\*"', re.IGNORECASE))
        self.assertNotIn('"apps/albert-trial-sim-ui/**"', text)

    def test_browser_workflow_is_ui_and_fixture_scoped(self) -> None:
        text = read_workflow("ui-browser.yml")
        self.assertGreaterEqual(text.count("paths:"), 2)
        self.assertGreaterEqual(text.count('"apps/albert-trial-sim-ui/**"'), 2)
        self.assertNotIn("codex/**", text)
        self.assertNotIn("agent/**", text)
        self.assertNotIn('"simulation/**"', text)
        self.assertNotRegex(text, re.compile(r'"\*\*/\*ocr\*"', re.IGNORECASE))

    def test_ocr_workflow_is_ocr_scoped_and_runs_ocr_contracts(self) -> None:
        text = read_workflow("ocr-quality.yml")
        self.assertGreaterEqual(text.count("paths:"), 2)
        self.assertIn('"**/*ocr*"', text)
        self.assertIn("tests/test_tesseract_synthetic_finetune_contract.py", text)
        self.assertIn("tests/test_ocr_model_training_history.py", text)
        self.assertNotIn("simulation/run_simulation_red_team_suite.py", text)
        self.assertNotIn("npx playwright test", text)

    def test_workflow_changes_have_a_lightweight_contract_gate(self) -> None:
        text = read_workflow("ci-contracts.yml")
        self.assertIn('".github/workflows/**"', text)
        self.assertIn("simulation/validate_simulation_red_team_ci.py", text)
        self.assertIn("tests.test_ci_module_path_scoping", text)
        self.assertNotIn("simulation/run_simulation_red_team_suite.py", text)


if __name__ == "__main__":
    unittest.main()
