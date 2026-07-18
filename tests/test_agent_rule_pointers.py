from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
POINTERS = [
    ROOT / ".cursor" / "rules" / "dad.mdc",
    ROOT / ".github" / "copilot-instructions.md",
    ROOT / "GEMINI.md",
    ROOT / ".windsurfrules",
    ROOT / ".aider.conf.yml",
    ROOT / ".clinerules",
    ROOT / ".continue" / "config.json",
]


def test_agent_rule_pointers_exist_and_route_to_agents_contract() -> None:
    for pointer in POINTERS:
        assert pointer.is_file(), pointer
        text = pointer.read_text(encoding="utf-8")
        assert "AGENTS.md" in text
        assert "preflight" in text
        assert "postflight" in text
        assert "DAD-Session" in text
        assert "protected" in text.lower()


def test_continue_pointer_is_valid_json() -> None:
    config = json.loads((ROOT / ".continue" / "config.json").read_text(encoding="utf-8"))
    rule = config["rules"][0]
    assert rule["name"] == "DAD agent contract"
    assert "AGENTS.md" in rule["description"]
    assert "preflight" in rule["description"]
    assert "postflight" in rule["description"]
    assert "DAD-Session" in rule["description"]


@pytest.mark.parametrize(
    "path",
    [
        ".aider.conf.yml",
        ".cursor/rules/dad.mdc",
        ".github/copilot-instructions.md",
        ".windsurfrules",
        "GEMINI.md",
        ".clinerules",
    ],
)

def test_non_continue_pointers_are_thin(path: str) -> None:
    assert len((ROOT / path).read_text(encoding="utf-8").splitlines()) <= 12
