#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from digital_asset_directory.validation import validate_repo  # noqa: E402

result = validate_repo(ROOT)
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["valid"] else 1)
