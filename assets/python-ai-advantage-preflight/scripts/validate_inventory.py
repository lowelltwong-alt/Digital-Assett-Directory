from __future__ import annotations

import json
from pathlib import Path

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    inventory = root / "data" / "python_language_ai_advantage_inventory.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))

    required = [
        "schema_version",
        "keywords",
        "soft_keywords",
        "operators_and_delimiters",
        "builtins",
        "special_methods_and_reserved_names",
        "underused_high_leverage_patterns",
    ]
    missing = [key for key in required if key not in payload]
    if missing:
        raise SystemExit(f"Missing required keys: {missing}")

    if "def" not in payload["keywords"]:
        raise SystemExit("Keyword inventory missing 'def'")
    if not payload["underused_high_leverage_patterns"]:
        raise SystemExit("No underused patterns present")

    print("inventory valid")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
