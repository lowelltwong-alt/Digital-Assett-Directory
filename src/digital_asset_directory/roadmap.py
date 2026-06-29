from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import yaml

from .utils import utc_now, write_json

AGENT_REVIEWERS = {
    "agent",
    "ai",
    "automation",
    "bot",
    "claude",
    "claude-code",
    "codex",
    "system",
}

HUMAN_REVIEWERS = {
    "human",
    "human reviewer",
    "lowell",
    "user",
}


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _load_gate_evidence(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "roadmap" / "gate-evidence.json"
    if not path.exists():
        return {"human_gates": {}, "commands": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def record_human_gate_evidence(
    repo_root: Path,
    *,
    phase_id: str,
    gate_id: str,
    reviewer: str,
    summary: str,
    evidence: list[str],
    status: str = "verified",
) -> dict[str, Any]:
    gate_evidence = _load_gate_evidence(repo_root)
    gate_evidence.setdefault("schema_version", "0.1.0")
    gate_evidence.setdefault("human_gates", {})
    gate_evidence.setdefault("commands", {})
    gate_evidence["human_gates"][gate_id] = {
        "phase_id": phase_id,
        "status": status,
        "reviewed_at": utc_now(),
        "reviewer": reviewer,
        "summary": summary,
        "evidence": evidence,
    }
    write_json(repo_root / "roadmap" / "gate-evidence.json", gate_evidence)
    return gate_evidence


def _normalize_human_gate(phase_id: str, gate: Any) -> dict[str, str]:
    if isinstance(gate, dict):
        description = str(gate.get("description") or gate.get("id") or "")
        gate_id = str(gate.get("id") or f"{phase_id}-{_slug(description)}")
        return {"id": gate_id, "description": description}
    description = str(gate)
    return {"id": f"{phase_id}-{_slug(description)}", "description": description}


def _verified_human_gate(
    gate: dict[str, str], phase_id: str, gate_evidence: dict[str, Any]
) -> dict[str, Any] | None:
    record = gate_evidence.get("human_gates", {}).get(gate["id"])
    if not isinstance(record, dict):
        return None
    if record.get("phase_id") != phase_id:
        return None
    if record.get("status") != "verified":
        return None
    if not _has_human_reviewer(record):
        return None
    return record


def _has_human_reviewer(record: dict[str, Any]) -> bool:
    reviewer = str(record.get("reviewer") or "").strip().lower()
    if reviewer in HUMAN_REVIEWERS:
        return True
    if reviewer in AGENT_REVIEWERS:
        return False
    if reviewer.startswith(("codex", "claude", "agent", "automation", "bot", "system")):
        return False
    return bool(record.get("human_verified") is True)


def _human_gate_rejection_reason(record: dict[str, Any] | None, phase_id: str) -> str:
    if not isinstance(record, dict):
        return "missing_gate_evidence"
    if record.get("phase_id") != phase_id:
        return "phase_mismatch"
    if record.get("status") != "verified":
        return "not_verified"
    if not _has_human_reviewer(record):
        return "missing_human_reviewer"
    return "unknown"


def _command_has_evidence(command: str, phase_id: str, gate_evidence: dict[str, Any]) -> bool:
    record = gate_evidence.get("commands", {}).get(phase_id, {}).get(command)
    return isinstance(record, dict) and record.get("status") == "passed"


def check_roadmap(repo_root: Path, update: bool = True) -> dict[str, Any]:
    roadmap_path = repo_root / "roadmap" / "roadmap.yaml"
    roadmap = yaml.safe_load(roadmap_path.read_text(encoding="utf-8"))
    gate_evidence = _load_gate_evidence(repo_root)
    result = {
        "roadmap_version": roadmap["roadmap_version"],
        "last_checked_at": utc_now(),
        "phases": {},
    }
    computed_by_phase: dict[str, str] = {}
    for phase in roadmap.get("phases", []):
        acceptance = phase.get("acceptance", {})
        dependencies = list(acceptance.get("depends_on", []))
        blocked_dependencies = [
            phase_id
            for phase_id in dependencies
            if computed_by_phase.get(str(phase_id)) != "complete"
        ]
        required = acceptance.get("required_files", []) + acceptance.get("required_outputs", [])
        present = [path for path in required if (repo_root / path).exists()]
        missing = [path for path in required if not (repo_root / path).exists()]
        human_gates = [
            _normalize_human_gate(phase["id"], gate) for gate in acceptance.get("human_gates", [])
        ]
        verified_gates: list[dict[str, str]] = []
        unverified_gates: list[dict[str, str]] = []
        for gate in human_gates:
            if _verified_human_gate(gate, phase["id"], gate_evidence):
                verified_gates.append(gate)
            else:
                unverified_gates.append(gate)
        unverified_gate_details = []
        for gate in unverified_gates:
            record = gate_evidence.get("human_gates", {}).get(gate["id"])
            unverified_gate_details.append(
                {
                    "gate_id": gate["id"],
                    "description": gate["description"],
                    "reviewer": record.get("reviewer") if isinstance(record, dict) else None,
                    "reason": _human_gate_rejection_reason(record, phase["id"]),
                }
            )
        commands = acceptance.get("commands", [])
        commands_missing_evidence = [
            command
            for command in commands
            if not _command_has_evidence(command, phase["id"], gate_evidence)
        ]
        if blocked_dependencies:
            computed = "blocked"
        elif missing:
            computed = "planned" if phase.get("status") == "planned" else "blocked"
        elif unverified_gates:
            computed = "awaiting_human_gate"
        elif commands_missing_evidence:
            computed = "awaiting_validation_evidence"
        elif phase.get("status") == "boundary_deferred":
            computed = "boundary_deferred"
        else:
            computed = "complete"
        status_warnings = []
        if phase.get("status", "planned") != computed:
            status_warnings.append(
                f"declared_status {phase.get('status', 'planned')} differs from computed_status {computed}"
            )
        result["phases"][phase["id"]] = {
            "declared_status": phase.get("status", "planned"),
            "computed_status": computed,
            "evidence": present,
            "missing": missing,
            "human_gates_verified": [gate["description"] for gate in verified_gates],
            "human_gates_unverified": [gate["description"] for gate in unverified_gates],
            "human_gate_ids_verified": [gate["id"] for gate in verified_gates],
            "human_gate_ids_unverified": [gate["id"] for gate in unverified_gates],
            "human_gate_unverified_details": unverified_gate_details,
            "commands_declared_not_executed_by_check": commands_missing_evidence,
            "blocked_dependencies": blocked_dependencies,
            "status_warnings": status_warnings,
        }
        computed_by_phase[phase["id"]] = computed
    if update:
        write_json(repo_root / "roadmap" / "state.json", result)
    return result
