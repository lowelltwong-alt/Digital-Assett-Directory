from __future__ import annotations

import json
import shlex
import subprocess
import time
import uuid
from json import JSONDecodeError
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .utils import utc_now

CommandSpec = str | Sequence[str]

PASS_OUTCOMES = {"pass", "passed", "success", "ok"}
FAIL_OUTCOMES = {"fail", "failed", "failure", "error", "errored"}
SKIP_OUTCOMES = {"skip", "skipped"}
KNOWN_OUTCOMES = PASS_OUTCOMES | FAIL_OUTCOMES | SKIP_OUTCOMES | {"xfail", "xfailed", "xpass", "xpassed"}


def _command_args(command: CommandSpec) -> list[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return [str(part) for part in command]


def _command_text(command: CommandSpec) -> str:
    if isinstance(command, str):
        return command
    return " ".join(shlex.quote(str(part)) for part in command)


def _tail(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def _repo_path(repo_root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else repo_root / path


def _file_fingerprint(path: Path | None) -> tuple[int, int] | None:
    if path is None or not path.exists():
        return None
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def run_command(command: CommandSpec, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            _command_args(command),
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    elapsed = time.monotonic() - started
    return {
        "command": _command_text(command),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": round(elapsed, 3),
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }


def _normalize_outcome(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in PASS_OUTCOMES:
        return "passed"
    if raw in FAIL_OUTCOMES:
        return "failed"
    if raw in SKIP_OUTCOMES:
        return "skipped"
    if raw in {"xfail", "xfailed"}:
        return "xfailed"
    if raw in {"xpass", "xpassed"}:
        return "xpassed"
    return raw or "unknown"


def _duration_seconds(record: dict[str, Any]) -> float | None:
    for key in ("duration_seconds", "duration", "elapsed_seconds", "time"):
        if key not in record:
            continue
        try:
            value = float(record[key])
        except (TypeError, ValueError):
            continue
        if value >= 0:
            return value
    return None


def _records_from_json_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("tests", "records", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "test_id" in payload or "nodeid" in payload:
            return [payload]
    return []


def load_structured_observations(path: Path) -> dict[str, dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    records: list[dict[str, Any]]
    if text[0] in "[{":
        try:
            records = _records_from_json_payload(json.loads(text))
        except JSONDecodeError:
            records = []
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    payload = json.loads(stripped)
                    if isinstance(payload, dict):
                        records.append(payload)
    else:
        records = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                payload = json.loads(stripped)
                if isinstance(payload, dict):
                    records.append(payload)
    observations: dict[str, dict[str, Any]] = {}
    for record in records:
        test_id = record.get("test_id") or record.get("nodeid") or record.get("name")
        outcome = record.get("outcome") or record.get("status") or record.get("result")
        if not test_id:
            continue
        observation: dict[str, Any] = {"outcome": _normalize_outcome(outcome)}
        duration = _duration_seconds(record)
        if duration is not None:
            observation["duration_seconds"] = duration
        observations[str(test_id)] = observation
    return observations


def load_structured_report(path: Path) -> dict[str, str]:
    return {
        test_id: str(observation["outcome"])
        for test_id, observation in load_structured_observations(path).items()
    }


def _outcome_map(observations: dict[str, Any]) -> dict[str, str]:
    output: dict[str, str] = {}
    for test_id, value in observations.items():
        if isinstance(value, dict):
            output[test_id] = str(value.get("outcome", "unknown"))
        else:
            output[test_id] = str(value)
    return output


def _duration_map(observations: dict[str, Any]) -> dict[str, float]:
    output: dict[str, float] = {}
    for test_id, value in observations.items():
        if not isinstance(value, dict) or "duration_seconds" not in value:
            continue
        try:
            output[test_id] = float(value["duration_seconds"])
        except (TypeError, ValueError):
            continue
    return output


def _percent_savings(native_seconds: float, shadow_seconds: float) -> float | None:
    if native_seconds <= 0:
        return None
    return round(((native_seconds - shadow_seconds) / native_seconds) * 100, 2)


def build_timing_analysis(
    native_result: dict[str, Any],
    shadow_result: dict[str, Any],
    *,
    replacement_comparable: bool = False,
) -> dict[str, Any]:
    native_seconds = float(native_result.get("duration_seconds") or 0)
    shadow_seconds = float(shadow_result.get("duration_seconds") or 0)
    sequential_burn_in = native_seconds + shadow_seconds
    parallel_shadow = max(native_seconds, shadow_seconds)
    replacement_fields: dict[str, Any]
    if replacement_comparable:
        replacement_fields = {
            "replacement_estimate_status": "compared",
            "estimated_replacement_seconds": round(shadow_seconds, 3),
            "estimated_replacement_savings_seconds": round(
                native_seconds - shadow_seconds, 3
            ),
            "estimated_replacement_savings_percent": _percent_savings(
                native_seconds, shadow_seconds
            ),
            "replacement_would_be_faster": shadow_seconds < native_seconds,
        }
    else:
        replacement_fields = {
            "replacement_estimate_status": "not_comparable_without_verified_parity",
            "estimated_replacement_seconds": None,
            "estimated_replacement_savings_seconds": None,
            "estimated_replacement_savings_percent": None,
            "replacement_would_be_faster": None,
        }
    return {
        "measurement_mode": "sequential",
        "native_seconds": round(native_seconds, 3),
        "shadow_seconds": round(shadow_seconds, 3),
        "sequential_burn_in_seconds": round(sequential_burn_in, 3),
        "sequential_burn_in_overhead_seconds": round(shadow_seconds, 3),
        "estimated_parallel_shadow_seconds": round(parallel_shadow, 3),
        "estimated_parallel_shadow_overhead_seconds": round(
            max(0.0, parallel_shadow - native_seconds), 3
        ),
        **replacement_fields,
        "measurement_note": (
            "Sequential burn-in measures potential replacement savings without CPU/IO contention. "
            "Replacement estimates are comparable only after structured parity is verified. "
            "Parallel shadow runs improve confidence but usually do not save wall-clock time until "
            "a reviewed shadow path replaces a native slice."
        ),
    }


def build_structured_duration_comparison(
    native: dict[str, Any] | None,
    shadow: dict[str, Any] | None,
) -> dict[str, Any]:
    if native is None or shadow is None:
        return {"used": False, "status": "not_available"}
    native_durations = _duration_map(native)
    shadow_durations = _duration_map(shadow)
    shared = sorted(set(native_durations) & set(shadow_durations))
    if not shared:
        return {"used": False, "status": "no_shared_durations"}
    native_total = sum(native_durations[test_id] for test_id in shared)
    shadow_total = sum(shadow_durations[test_id] for test_id in shared)
    deltas = [
        {
            "test_id": test_id,
            "native_seconds": round(native_durations[test_id], 6),
            "shadow_seconds": round(shadow_durations[test_id], 6),
            "savings_seconds": round(native_durations[test_id] - shadow_durations[test_id], 6),
            "savings_percent": _percent_savings(
                native_durations[test_id], shadow_durations[test_id]
            ),
        }
        for test_id in shared
    ]
    deltas.sort(key=lambda item: item["savings_seconds"], reverse=True)
    return {
        "used": True,
        "status": "compared",
        "shared_duration_count": len(shared),
        "native_total_seconds": round(native_total, 6),
        "shadow_total_seconds": round(shadow_total, 6),
        "estimated_replacement_savings_seconds": round(native_total - shadow_total, 6),
        "estimated_replacement_savings_percent": _percent_savings(native_total, shadow_total),
        "largest_savings": deltas[:10],
        "largest_regressions": list(reversed(deltas[-10:])),
    }


def compare_structured_reports(
    native: dict[str, Any] | None, shadow: dict[str, Any] | None
) -> dict[str, Any]:
    if native is None and shadow is None:
        return {
            "used": False,
            "status": "not_provided",
            "native_only": [],
            "shadow_only": [],
            "outcome_mismatches": [],
            "duration_comparison": {"used": False, "status": "not_available"},
        }
    if native is None or shadow is None:
        return {
            "used": True,
            "status": "missing_one_report",
            "native_only": sorted((native or {}).keys()),
            "shadow_only": sorted((shadow or {}).keys()),
            "outcome_mismatches": [],
            "duration_comparison": {"used": False, "status": "not_available"},
        }
    if not native and not shadow:
        return {
            "used": True,
            "status": "empty_reports",
            "native_only": [],
            "shadow_only": [],
            "outcome_mismatches": [],
            "duration_comparison": {"used": False, "status": "not_available"},
        }

    native_outcomes = _outcome_map(native)
    shadow_outcomes = _outcome_map(shadow)
    native_ids = set(native_outcomes)
    shadow_ids = set(shadow_outcomes)
    shared = sorted(native_ids & shadow_ids)
    mismatches = [
        {
            "test_id": test_id,
            "native_outcome": native_outcomes[test_id],
            "shadow_outcome": shadow_outcomes[test_id],
        }
        for test_id in shared
        if native_outcomes[test_id] != shadow_outcomes[test_id]
    ]
    native_only = sorted(native_ids - shadow_ids)
    shadow_only = sorted(shadow_ids - native_ids)
    status = "matched" if not native_only and not shadow_only and not mismatches else "mismatch"
    return {
        "used": True,
        "status": status,
        "native_only": native_only,
        "shadow_only": shadow_only,
        "outcome_mismatches": mismatches,
        "duration_comparison": build_structured_duration_comparison(native, shadow),
    }


def _passed(result: dict[str, Any]) -> bool:
    return result["exit_code"] == 0 and not result["timed_out"]


def _parity_status(
    native_result: dict[str, Any],
    shadow_result: dict[str, Any],
    structured: dict[str, Any],
) -> str:
    native_passed = _passed(native_result)
    shadow_passed = _passed(shadow_result)
    if structured["status"] in {
        "mismatch",
        "missing_one_report",
        "empty_reports",
        "report_integrity_failed",
    }:
        return "structured_mismatch"
    if native_passed and shadow_passed:
        if structured["status"] == "matched":
            return "matched_pass"
        return "exit_code_match_only"
    if native_passed and not shadow_passed:
        return "shadow_failed_native_passed"
    if not native_passed and shadow_passed:
        return "shadow_passed_native_failed"
    return "both_failed"


def build_parity_result(
    *,
    repo_root: Path,
    native_result: dict[str, Any],
    shadow_result: dict[str, Any],
    native_report: Path | None = None,
    shadow_report: Path | None = None,
    report_integrity_errors: list[str] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    if report_integrity_errors:
        structured = {
            "used": True,
            "status": "report_integrity_failed",
            "integrity_errors": report_integrity_errors,
            "native_only": [],
            "shadow_only": [],
            "outcome_mismatches": [],
            "duration_comparison": {"used": False, "status": "not_available"},
        }
    else:
        native_observations = load_structured_observations(native_report) if native_report else None
        shadow_observations = load_structured_observations(shadow_report) if shadow_report else None
        structured = compare_structured_reports(native_observations, shadow_observations)
    status = _parity_status(native_result, shadow_result, structured)
    exit_code = 0 if status == "matched_pass" else 1
    return {
        "schema_version": "test_parity_run.v1",
        "run_id": f"dad:test-parity:{uuid.uuid4()}",
        "created_at": utc_now(),
        "repo_root": str(repo_root),
        "session_id": session_id,
        "native_authority": "pytest",
        "shadow_authority": "candidate_only",
        "candidate_only": True,
        "parity_status": status,
        "exit_code": exit_code,
        "native": native_result,
        "shadow": shadow_result,
        "timing_analysis": build_timing_analysis(
            native_result,
            shadow_result,
            replacement_comparable=status == "matched_pass",
        ),
        "structured_comparison": structured,
        "native_report": str(native_report) if native_report else None,
        "shadow_report": str(shadow_report) if shadow_report else None,
        "promotion_boundary": (
            "Rust shadow results are audit evidence only. Native pytest remains authoritative "
            "until reviewed parity evidence promotes a narrower gate."
        ),
    }


def _audit_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("<omitted from audit>" if key in {"stdout_tail", "stderr_tail"} else _audit_payload(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_audit_payload(item) for item in value]
    return value


def append_parity_audit(
    repo_root: Path, result: dict[str, Any], audit_path: Path | None = None
) -> Path:
    path = audit_path or repo_root / "audit" / "events" / "test_parity.jsonl"
    if not path.is_absolute():
        path = repo_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": "audit_event.v1",
        "event_type": "test_parity_run",
        "created_at": utc_now(),
        "run_id": result["run_id"],
        "candidate_only": True,
        "payload": _audit_payload(result),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return path


def run_test_parity(
    repo_root: Path,
    *,
    native_command: CommandSpec,
    shadow_command: CommandSpec,
    timeout_seconds: int = 120,
    native_report: Path | None = None,
    shadow_report: Path | None = None,
    audit: bool = True,
    audit_path: Path | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    native_report_path = _repo_path(repo_root, native_report)
    shadow_report_path = _repo_path(repo_root, shadow_report)
    report_before = {
        "native": _file_fingerprint(native_report_path),
        "shadow": _file_fingerprint(shadow_report_path),
    }
    native_result = run_command(native_command, repo_root, timeout_seconds)
    shadow_result = run_command(shadow_command, repo_root, timeout_seconds)
    report_integrity_errors: list[str] = []
    if (
        native_report_path is not None
        and shadow_report_path is not None
        and native_report_path.resolve() == shadow_report_path.resolve()
    ):
        report_integrity_errors.append("native_report and shadow_report resolve to the same path")
    for label, path in (("native", native_report_path), ("shadow", shadow_report_path)):
        if path is None:
            continue
        after = _file_fingerprint(path)
        if after is None:
            report_integrity_errors.append(f"{label}_report was not produced: {path}")
        elif report_before[label] == after:
            report_integrity_errors.append(f"{label}_report appears stale or unchanged: {path}")
    result = build_parity_result(
        repo_root=repo_root,
        native_result=native_result,
        shadow_result=shadow_result,
        native_report=native_report_path,
        shadow_report=shadow_report_path,
        report_integrity_errors=report_integrity_errors,
        session_id=session_id,
    )
    if audit:
        result["audit_path"] = str(append_parity_audit(repo_root, result, audit_path))
    return result
