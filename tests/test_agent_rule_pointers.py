from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POINTER = ROOT / ".github" / "copilot-instructions.md"


def test_copilot_pointer_exists_and_routes_to_agents_contract() -> None:
    assert POINTER.is_file()
    text = POINTER.read_text(encoding="utf-8")
    assert "AGENTS.md" in text
    assert "preflight" in text
    assert "postflight" in text
    assert "DAD-Session" in text
    assert "protected" in text.lower()
    assert len(text.splitlines()) <= 12