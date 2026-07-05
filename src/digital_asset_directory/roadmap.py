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


def _load_roadmap(repo_root: Path) -> dict[str, Any]:
    roadmap_path = repo_root / "roadmap" / "roadmap.yaml"
    return yaml.safe_load(roadmap_path.read_text(encoding="utf-8"))


def _find_phase(repo_root: Path, phase_id: str) -> dict[str, Any]:
    roadmap = _load_roadmap(repo_root)
    for phase in roadmap.get("phases", []):
        if phase.get("id") == phase_id:
            return phase
    raise ValueError(f"Unknown roadmap phase: {phase_id}")


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


def build_human_gate_review_packet(repo_root: Path, phase_id: str) -> dict[str, Any]:
    phase = _find_phase(repo_root, phase_id)
    gate_evidence = _load_gate_evidence(repo_root)
    roadmap_state = check_roadmap(repo_root, update=False)["phases"][phase_id]
    acceptance = phase.get("acceptance", {})
    required_files = list(acceptance.get("required_files", [])) + list(
        acceptance.get("required_outputs", [])
    )
    command_evidence = gate_evidence.get("commands", {}).get(phase_id, {})
    gates = [_normalize_human_gate(phase_id, gate) for gate in acceptance.get("human_gates", [])]
    unverified_by_id = {
        item["gate_id"]: item for item in roadmap_state.get("human_gate_unverified_details", [])
    }
    gate_rows = []
    for gate in gates:
        record = gate_evidence.get("human_gates", {}).get(gate["id"])
        if gate["id"] in roadmap_state.get("human_gate_ids_verified", []):
            status = "verified"
            reason = ""
        elif gate["id"] in roadmap_state.get("human_gate_ids_boundary_deferred", []):
            status = "boundary_deferred"
            reason = "boundary_deferred"
        else:
            status = "unverified"
            reason = unverified_by_id.get(gate["id"], {}).get("reason", "missing_gate_evidence")
        gate_rows.append(
            {
                "gate_id": gate["id"],
                "description": gate["description"],
                "current_status": status,
                "reason": reason,
                "existing_record": _review_packet_gate_record(record),
                "human_review_required": True,
                "agent_review_satisfies_gate": False,
                "review_questions": [
                    "Does the cited evidence prove this exact gate in the current local environment?",
                    "Is the evidence fresh enough for a human to trust today?",
                    "Does approving this gate avoid broad enrollment, repo mutation, mail delivery, public release, or protected-repo writes?",
                    "If any evidence is missing, stale, ambiguous, or agent-only, should this gate remain unverified?",
                ],
                "acceptable_decisions": ["verified", "leave_unverified"],
                "recording_note": (
                    "Only a human reviewer record in roadmap/gate-evidence.json can satisfy "
                    "this gate. This packet is review input, not approval evidence."
                ),
            }
        )
    return {
        "schema_version": "dad.roadmap.human-gate-review-packet.v1",
        "generated_at": utc_now(),
        "phase_id": phase_id,
        "phase_title": str(phase.get("title", "")),
        "declared_status": roadmap_state.get("declared_status"),
        "computed_status": roadmap_state.get("computed_status"),
        "packet_status": "review_input_only",
        "no_roadmap_state_mutation": True,
        "human_gate_satisfied": False,
        "agent_review_satisfies_gate": False,
        "required_files": [
            {"path": path, "exists": (repo_root / path).exists()} for path in required_files
        ],
        "commands": [
            {
                "command": command,
                "gate_evidence_status": command_evidence.get(command, {}).get("status", "missing"),
                "recorded_at": command_evidence.get(command, {}).get("recorded_at", ""),
                "evidence": command_evidence.get(command, {}).get("evidence", []),
            }
            for command in acceptance.get("commands", [])
        ],
        "command_evidence_files": [
            path
            for path in required_files
            if path.endswith(".commands.json") and (repo_root / path).exists()
        ],
        "human_gates": gate_rows,
        "next_actions": [
            "Human reviews each gate against the cited evidence.",
            "Leave a gate unverified when proof is missing, stale, ambiguous, or agent-only.",
            "Record verified gate evidence separately in roadmap/gate-evidence.json only after human review.",
            "Run roadmap check after any human gate evidence is recorded.",
        ],
        "authority_boundary": (
            "This packet compiles candidate review evidence only. It does not record a "
            "human gate, complete a roadmap phase, approve public release, authorize "
            "enrollment, or permit cross-repo writes."
        ),
    }


def write_human_gate_review_packet(
    repo_root: Path,
    phase_id: str,
    output: Path | None = None,
) -> dict[str, Any]:
    packet = build_human_gate_review_packet(repo_root, phase_id)
    target = output or repo_root / "roadmap" / "evidence" / f"{phase_id}.human-review-packet.json"
    if not target.is_absolute():
        target = repo_root / target
    write_json(target, packet)
    packet["path"] = str(target)
    return packet


def _review_packet_gate_record(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    return {
        "phase_id": record.get("phase_id", ""),
        "status": record.get("status", ""),
        "reviewed_at": record.get("reviewed_at", ""),
        "reviewer": record.get("reviewer", ""),
        "human_reviewer_accepted": _has_human_reviewer(record),
        "evidence": record.get("evidence", []),
        "summary": record.get("summary", ""),
    }


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


def _boundary_deferred_human_gate(
    gate: dict[str, str], phase_id: str, gate_evidence: dict[str, Any]
) -> dict[str, Any] | None:
    record = gate_evidence.get("human_gates", {}).get(gate["id"])
    if not isinstance(record, dict):
        return None
    if record.get("phase_id") != phase_id:
        return None
    if record.get("status") != "boundary_deferred":
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
    if record.get("status") not in {"verified", "boundary_deferred"}:
        return "not_verified"
    if not _has_human_reviewer(record):
        return "missing_human_reviewer"
    if record.get("status") == "boundary_deferred":
        return "boundary_deferred"
    return "unknown"


def _command_has_evidence(command: str, phase_id: str, gate_evidence: dict[str, Any]) -> bool:
    record = gate_evidence.get("commands", {}).get(phase_id, {}).get(command)
    return isinstance(record, dict) and record.get("status") == "passed"


def check_roadmap(repo_root: Path, update: bool = True) -> dict[str, Any]:
    roadmap = _load_roadmap(repo_root)
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
        deferred_gates: list[dict[str, str]] = []
        unverified_gates: list[dict[str, str]] = []
        for gate in human_gates:
            if _verified_human_gate(gate, phase["id"], gate_evidence):
                verified_gates.append(gate)
            elif phase.get("status") == "boundary_deferred" and _boundary_deferred_human_gate(
                gate, phase["id"], gate_evidence
            ):
                deferred_gates.append(gate)
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
            "human_gates_boundary_deferred": [
                gate["description"] for gate in deferred_gates
            ],
            "human_gates_unverified": [gate["description"] for gate in unverified_gates],
            "human_gate_ids_verified": [gate["id"] for gate in verified_gates],
            "human_gate_ids_boundary_deferred": [gate["id"] for gate in deferred_gates],
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
