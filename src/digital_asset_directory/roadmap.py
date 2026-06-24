from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

from .utils import utc_now, write_json


def check_roadmap(repo_root: Path, update: bool = True) -> dict[str, Any]:
    roadmap_path = repo_root / "roadmap" / "roadmap.yaml"
    roadmap = yaml.safe_load(roadmap_path.read_text(encoding="utf-8"))
    result = {
        "roadmap_version": roadmap["roadmap_version"],
        "last_checked_at": utc_now(),
        "phases": {},
    }
    for phase in roadmap.get("phases", []):
        acceptance = phase.get("acceptance", {})
        required = acceptance.get("required_files", []) + acceptance.get("required_outputs", [])
        present = [path for path in required if (repo_root / path).exists()]
        missing = [path for path in required if not (repo_root / path).exists()]
        manual = acceptance.get("human_gates", [])
        if missing:
            computed = "planned" if phase.get("status") == "planned" else "blocked"
        elif manual:
            computed = "awaiting_human_gate"
        else:
            computed = "complete"
        result["phases"][phase["id"]] = {
            "declared_status": phase.get("status", "planned"),
            "computed_status": computed,
            "evidence": present,
            "missing": missing,
            "human_gates_unverified": manual,
            "commands_declared_not_executed_by_check": acceptance.get("commands", []),
        }
    if update:
        write_json(repo_root / "roadmap" / "state.json", result)
    return result
