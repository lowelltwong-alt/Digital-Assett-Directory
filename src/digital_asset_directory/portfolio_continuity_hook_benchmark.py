"""Instrumented, revision-bound performance evidence for the Codex shadow hook."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from .portability_control import canonical_digest, runtime_adapter_interface_digest
from .portfolio_continuity_codex_hook import (
    CODEX_HOOK_ADAPTER_ID,
    CODEX_HOOK_ADAPTER_REVISION_ID,
    build_codex_hook_receipt,
)
from .portfolio_continuity_events import (
    ContinuityIntegrityError,
    _append_observation_to_ledger,
    _expected_event_id,
    _load_ledger_index,
    _refresh_continuity_ledger_path_index,
    read_observation_events,
    validate_continuity_ledger_full,
)
from .transport import init_data_root
from .utils import atomic_write_text, json_dumps


SCHEMA_VERSION = "dad.intent_continuity_hook_performance_evidence.v1"
METHODOLOGY_ID = "methodology:nearest-rank-p95-cold-process-v1"
RUNTIME_ADAPTER_ARTIFACT_ID = "adapter:intent-continuity-codex-host"
MINIMUM_QUALIFYING_SAMPLES = 5
AUTHORITY_BOUNDARY = (
    "Hook performance evidence is synthetic, revision-bound candidate evidence only. "
    "It cannot trust or activate hooks, approve a trial, mutate source work, notify, "
    "schedule, archive, or authorize execution."
)


class HookPerformanceEvidenceError(ValueError):
    """Instrumented evidence is malformed, stale, or not bound to current code."""


def _schema_path(repo_root: Path) -> Path:
    return repo_root / "schemas/intent-continuity-hook-performance-evidence.schema.json"


def _validate_schema(repo_root: Path, evidence: Mapping[str, Any]) -> None:
    schema = json.loads(_schema_path(repo_root).read_text(encoding="utf-8"))
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(dict(evidence)), key=lambda error: list(error.path))
    if errors:
        rendered = "; ".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise HookPerformanceEvidenceError(rendered)


def _validate_scale_schema(repo_root: Path, evidence: Mapping[str, Any]) -> None:
    schema = json.loads(
        (repo_root / "schemas/intent-continuity-hook-scale-evidence.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(dict(evidence)), key=lambda error: list(error.path))
    if errors:
        rendered = "; ".join(f"{list(error.path)}: {error.message}" for error in errors)
        raise HookPerformanceEvidenceError(rendered)


def nearest_rank_p95(samples: list[float]) -> float:
    """Return nearest-rank p95 (ceil(0.95*n), one-based) rounded to 3 decimals."""

    if not samples:
        raise HookPerformanceEvidenceError("At least one latency sample is required")
    ordered = sorted(float(sample) for sample in samples)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return round(ordered[index], 3)


def _hook_command(repo_root: Path) -> tuple[str, str, list[str] | str, bool, int]:
    hooks = json.loads((repo_root / ".codex/hooks.json").read_text(encoding="utf-8"))[
        "hooks"
    ]
    handler = hooks["Stop"][0]["hooks"][0]
    timeout_ms = int(float(handler["timeout"]) * 1000)
    if os.name == "nt":
        command_kind = "commandWindows"
        command = str(handler[command_kind])
        expected = 'python "$(git rev-parse --show-toplevel)/.codex/hooks/intent_continuity_shadow.py"'
        if command != expected:
            raise HookPerformanceEvidenceError("commandWindows is not the reviewed command")
        args = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ]
        return command_kind, command, args, False, timeout_ms
    command_kind = "command"
    command = str(handler[command_kind])
    return command_kind, command, command, True, timeout_ms


def _copy_minimal_hub(repo_root: Path, hub_root: Path) -> None:
    required = (
        "AI_FRONT_DOOR.md",
        "MACHINE_NAVIGATION_MANIFEST.json",
        "registry/source-of-truth.json",
        "pyproject.toml",
        "src/digital_asset_directory/cli.py",
    )
    for relative in required:
        target = hub_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / relative, target)


def _status(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return completed.stdout


def run_hook_performance_benchmark(
    repo_root: Path,
    *,
    sample_count: int = MINIMUM_QUALIFYING_SAMPLES,
    latency_budget_ms: float = 1500.0,
) -> dict[str, Any]:
    """Measure exact cold hook processes against a temporary initialized DAD root."""

    repo_root = repo_root.resolve()
    if not MINIMUM_QUALIFYING_SAMPLES <= sample_count <= 100:
        raise HookPerformanceEvidenceError(
            f"sample_count must be between {MINIMUM_QUALIFYING_SAMPLES} and 100"
        )
    if latency_budget_ms <= 0:
        raise HookPerformanceEvidenceError("latency_budget_ms must be positive")
    command_kind, command, invocation, use_shell, timeout_ms = _hook_command(repo_root)
    interface_digest = runtime_adapter_interface_digest(
        repo_root, RUNTIME_ADAPTER_ARTIFACT_ID
    )
    status_before = _status(repo_root)
    samples: list[float] = []
    silent_success_count = 0
    persistence_success_count = 0
    forbidden_values: list[str] = []
    with tempfile.TemporaryDirectory(prefix="dad-hook-performance-") as raw_temp:
        base = Path(raw_temp)
        hub_root = base / "hub"
        _copy_minimal_hub(repo_root, hub_root)
        data_root = base / "data"
        init_data_root(data_root, hub_root=hub_root)
        env = os.environ.copy()
        env["DAD_HUB"] = str(hub_root)
        env["DAD_DATA_ROOT"] = str(data_root)
        ledger = data_root / "raw/portfolio/continuity-events.jsonl"
        for index in range(sample_count):
            session = f"synthetic-performance-session-{index}"
            turn = f"synthetic-performance-turn-{index}"
            forbidden_values.extend([session, turn])
            payload = json.dumps(
                {
                    "session_id": session,
                    "turn_id": turn,
                    "hook_event_name": "Stop",
                    "cwd": r"C:\synthetic-private-path",
                    "transcript_path": r"C:\synthetic-private-transcript.jsonl",
                    "model": "synthetic-private-model",
                    "permission_mode": "synthetic-private-permission",
                }
            )
            started = time.perf_counter()
            completed = subprocess.run(
                invocation,
                cwd=repo_root,
                input=payload,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000,
                check=False,
                env=env,
                shell=use_shell,
            )
            samples.append(round((time.perf_counter() - started) * 1000, 3))
            if completed.returncode == 0 and not completed.stdout and not completed.stderr:
                silent_success_count += 1
            events = read_observation_events(ledger)
            if len(events) == index + 1:
                persistence_success_count += 1
        rendered_events = json.dumps(
            read_observation_events(ledger),
            sort_keys=True,
        )
        privacy_check_passed = all(value not in rendered_events for value in forbidden_values)
        privacy_check_passed = privacy_check_passed and all(
            value not in rendered_events
            for value in (
                "synthetic-private-path",
                "synthetic-private-transcript",
                "synthetic-private-model",
                "synthetic-private-permission",
            )
        )
    status_after = _status(repo_root)
    material = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "measurement_origin": "instrumented_harness",
        "adapter_id": CODEX_HOOK_ADAPTER_ID,
        "adapter_revision_id": CODEX_HOOK_ADAPTER_REVISION_ID,
        "adapter_interface_digest": interface_digest,
        "command_kind": command_kind,
        "command_digest": canonical_digest(
            {"command_kind": command_kind, "command": command}
        ),
        "methodology_id": METHODOLOGY_ID,
        "sample_count": sample_count,
        "latency_ms_samples": samples,
        "latency_ms_p95": nearest_rank_p95(samples),
        "latency_budget_ms": float(latency_budget_ms),
        "timeout_ms": timeout_ms,
        "silent_success_count": silent_success_count,
        "persistence_success_count": persistence_success_count,
        "privacy_check_passed": privacy_check_passed,
        "source_worktree_unchanged": status_before == status_after,
        "evidence_integrity": "self_consistent_not_origin_authenticated",
        "origin_authenticated": False,
        "supervisor_attestation_required": True,
        "synthetic_payload": True,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "measurement_id": "dad:hook-performance:"
        + canonical_digest(material).split(":", 1)[1],
        **material,
    }
    validate_hook_performance_evidence(repo_root, evidence)
    return evidence


def validate_hook_performance_evidence(
    repo_root: Path, evidence: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate measurement math, outcomes, identity, and current source binding."""

    repo_root = repo_root.resolve()
    value = dict(evidence)
    _validate_schema(repo_root, value)
    material = {key: item for key, item in value.items() if key not in {"schema_version", "measurement_id"}}
    expected_id = "dad:hook-performance:" + canonical_digest(material).split(":", 1)[1]
    if value["measurement_id"] != expected_id:
        raise HookPerformanceEvidenceError("measurement_id does not match evidence")
    if value["adapter_revision_id"] != CODEX_HOOK_ADAPTER_REVISION_ID:
        raise HookPerformanceEvidenceError("adapter revision does not match current hook")
    expected_interface = runtime_adapter_interface_digest(
        repo_root, RUNTIME_ADAPTER_ARTIFACT_ID
    )
    if value["adapter_interface_digest"] != expected_interface:
        raise HookPerformanceEvidenceError("adapter interface digest is stale")
    command_kind, command, _invocation, _shell, timeout_ms = _hook_command(repo_root)
    expected_command = canonical_digest({"command_kind": command_kind, "command": command})
    if value["command_kind"] != command_kind or value["command_digest"] != expected_command:
        raise HookPerformanceEvidenceError("hook command binding is stale")
    samples = [float(sample) for sample in value["latency_ms_samples"]]
    if value["sample_count"] != len(samples):
        raise HookPerformanceEvidenceError("sample_count does not match latency samples")
    if float(value["latency_ms_p95"]) != nearest_rank_p95(samples):
        raise HookPerformanceEvidenceError("p95 does not match nearest-rank methodology")
    if int(value["timeout_ms"]) != timeout_ms:
        raise HookPerformanceEvidenceError("timeout does not match current hook")
    for field in ("silent_success_count", "persistence_success_count"):
        if int(value[field]) != int(value["sample_count"]):
            raise HookPerformanceEvidenceError(f"{field} does not cover every sample")
    if value["privacy_check_passed"] is not True:
        raise HookPerformanceEvidenceError("privacy check did not pass")
    if value["source_worktree_unchanged"] is not True:
        raise HookPerformanceEvidenceError("source worktree changed during measurement")
    return value


def write_hook_performance_evidence(path: Path, evidence: Mapping[str, Any]) -> None:
    atomic_write_text(path, json_dumps(dict(evidence), pretty=True) + "\n")


def _synthetic_scale_rows(base: Path, count: int) -> list[str]:
    seed_ledger = base / "seed-events.jsonl"
    receipt = build_codex_hook_receipt(
        {"session_id": "scale-seed", "turn_id": "scale-seed", "hook_event_name": "Stop"},
        observed_at="2026-07-17T00:00:00+00:00",
        repository_id="dad",
    )
    _append_observation_to_ledger(
        seed_ledger,
        receipt,
        recorded_at="2026-07-17T00:00:00+00:00",
        retry_clock_tolerant=True,
    )
    seed = read_observation_events(seed_ledger)[0]
    rows: list[str] = []
    previous = ""
    for index in range(count):
        suffix = f"{index + 1:064x}"
        event = deepcopy(seed)
        event["command_id"] = "dad:continuity-command:" + suffix
        event["stream_id"] = "dad:continuity-stream:" + suffix
        event["source_id"] = "codex-session:" + suffix
        event["source_revision"] = "codex-hook:" + suffix
        event["payload"]["session_id"] = "codex-session:" + suffix
        event["payload"]["source_digest"] = "sha256:" + suffix
        event["payload_digest"] = canonical_digest(event["payload"])
        event["prev_event_id"] = previous
        event.pop("event_id", None)
        event["event_id"] = _expected_event_id(event)
        previous = event["event_id"]
        rows.append(json.dumps(event, sort_keys=True, separators=(",", ":")))
    return rows


def _collect_scale_sample(
    *,
    repo_root: Path,
    ledger: Path,
    data_root: Path,
    rows: list[str],
    count: int,
    index_state: str,
    invocation: list[str] | str,
    use_shell: bool,
    timeout_ms: int,
    env: Mapping[str, str],
) -> dict[str, Any]:
    ledger.write_text(
        ("\n".join(rows[:count]) + "\n") if count else "",
        encoding="utf-8",
    )
    index_path = ledger.with_suffix(ledger.suffix + ".index.json")
    index_path.unlink(missing_ok=True)
    failure_path = data_root / "raw/portfolio/continuity-hook-failures.jsonl"
    failure_path.unlink(missing_ok=True)
    if index_state == "warm":
        _refresh_continuity_ledger_path_index(ledger)
    payload = json.dumps(
        {
            "session_id": f"scale-session-{count}-{index_state}",
            "turn_id": f"scale-turn-{count}-{index_state}",
            "hook_event_name": "Stop",
        }
    )
    started = time.perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            invocation,
            cwd=repo_root,
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000,
            check=False,
            env=dict(env),
            shell=use_shell,
        )
        exit_code = completed.returncode
        silent = not completed.stdout and not completed.stderr
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = -1
        silent = False
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    ledger_bytes = ledger.read_bytes() if ledger.exists() else b""
    ledger_line_count = ledger_bytes.count(b"\n")
    try:
        raw_index = json.loads(index_path.read_text(encoding="utf-8"))
        if not isinstance(raw_index, dict):
            raw_index = {}
    except (OSError, json.JSONDecodeError):
        raw_index = {}
    try:
        index = _load_ledger_index(ledger)
    except (OSError, ValueError, ContinuityIntegrityError):
        index = None
    try:
        full_events = validate_continuity_ledger_full(ledger)
        full_oracle_valid = len(full_events) == count + 1
    except (OSError, ValueError, ContinuityIntegrityError):
        full_oracle_valid = False
    failure_marker_count = (
        failure_path.read_bytes().count(b"\n") if failure_path.exists() else 0
    )
    return {
        "latency_ms": elapsed_ms,
        "exit_code": exit_code,
        "silent": silent,
        "ledger_event_count": ledger_line_count,
        "index_event_count": int(raw_index.get("event_count", -1)),
        "index_valid": index is not None,
        "index_size_matches": int(raw_index.get("ledger_size", -1))
        == len(ledger_bytes),
        "index_digest_matches": raw_index.get("ledger_sha256")
        == "sha256:" + hashlib.sha256(ledger_bytes).hexdigest(),
        "index_command_count": len(raw_index.get("commands", {})),
        "failure_marker_count": failure_marker_count,
        "persistence_confirmed": index is not None
        and int(index["event_count"]) == count + 1
        and ledger_line_count == count + 1,
        "full_oracle_valid": full_oracle_valid,
        "timed_out": timed_out,
    }


def collect_hook_scale_evidence(
    repo_root: Path,
    *,
    warm_sample_count: int = MINIMUM_QUALIFYING_SAMPLES,
    cold_sample_count: int = 1,
) -> dict[str, Any]:
    """Collect all scale outcomes without discarding a failed qualification."""

    repo_root = repo_root.resolve()
    if not MINIMUM_QUALIFYING_SAMPLES <= warm_sample_count <= 100:
        raise HookPerformanceEvidenceError(
            f"warm_sample_count must be between {MINIMUM_QUALIFYING_SAMPLES} and 100"
        )
    if not 1 <= cold_sample_count <= 100:
        raise HookPerformanceEvidenceError("cold_sample_count must be between 1 and 100")
    _kind, _command, invocation, use_shell, timeout_ms = _hook_command(repo_root)
    status_before = _status(repo_root)
    with tempfile.TemporaryDirectory(prefix="dad-hook-scale-") as raw_temp:
        base = Path(raw_temp)
        hub_root = base / "hub"
        _copy_minimal_hub(repo_root, hub_root)
        data_root = base / "data"
        init_data_root(data_root, hub_root=hub_root)
        ledger = data_root / "raw/portfolio/continuity-events.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        rows = _synthetic_scale_rows(base, 10_000)
        env = os.environ.copy()
        env["DAD_HUB"] = str(hub_root)
        env["DAD_DATA_ROOT"] = str(data_root)
        results: list[dict[str, Any]] = []
        cases = ((0, "warm"), (1_000, "warm"), (10_000, "cold"), (10_000, "warm"))
        for count, index_state in cases:
            target = warm_sample_count if index_state == "warm" else cold_sample_count
            samples = [
                _collect_scale_sample(
                    repo_root=repo_root,
                    ledger=ledger,
                    data_root=data_root,
                    rows=rows,
                    count=count,
                    index_state=index_state,
                    invocation=invocation,
                    use_shell=use_shell,
                    timeout_ms=timeout_ms,
                    env=env,
                )
                for _sample_index in range(target)
            ]
            latency_samples = [float(sample["latency_ms"]) for sample in samples]
            p95 = nearest_rank_p95(latency_samples)
            last = samples[-1]
            results.append(
                {
                    "preexisting_event_count": count,
                    "index_state": index_state,
                    "sample_count": len(samples),
                    "latency_ms_samples": latency_samples,
                    "latency_ms_p95": p95,
                    "samples": samples,
                    "latency_ms": p95,
                    "exit_code": 0 if all(sample["exit_code"] == 0 for sample in samples) else -1,
                    "silent": all(sample["silent"] is True for sample in samples),
                    "ledger_event_count": last["ledger_event_count"],
                    "index_event_count": last["index_event_count"],
                    "index_valid": all(sample["index_valid"] is True for sample in samples),
                    "index_size_matches": all(
                        sample["index_size_matches"] is True for sample in samples
                    ),
                    "index_digest_matches": all(
                        sample["index_digest_matches"] is True for sample in samples
                    ),
                    "index_command_count": last["index_command_count"],
                    "failure_marker_count": sum(
                        int(sample["failure_marker_count"]) for sample in samples
                    ),
                    "persistence_confirmed": all(
                        sample["persistence_confirmed"] is True for sample in samples
                    ),
                    "full_oracle_valid": all(
                        sample["full_oracle_valid"] is True for sample in samples
                    ),
                    "timed_out_count": sum(
                        int(sample["timed_out"] is True) for sample in samples
                    ),
                }
            )
    material = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "methodology_id": "methodology:exact-content-index-scale-v1",
        "adapter_revision_id": CODEX_HOOK_ADAPTER_REVISION_ID,
        "adapter_interface_digest": runtime_adapter_interface_digest(
            repo_root, RUNTIME_ADAPTER_ARTIFACT_ID
        ),
        "warm_latency_budget_ms": 1500.0,
        "cold_hard_timeout_ms": timeout_ms,
        "results": results,
        "source_worktree_unchanged": status_before == _status(repo_root),
        "evidence_integrity": "self_consistent_not_origin_authenticated",
        "origin_authenticated": False,
        "supervisor_attestation_required": True,
        "synthetic_payload": True,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    evidence = {
        "schema_version": "dad.intent_continuity_hook_scale_evidence.v1",
        "measurement_id": "dad:hook-scale:" + canonical_digest(material).split(":", 1)[1],
        **material,
    }
    validate_hook_scale_collection(repo_root, evidence)
    return evidence


def validate_hook_scale_collection(
    repo_root: Path, evidence: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate identity and measurement math, but not pass/fail qualification."""

    repo_root = repo_root.resolve()
    value = dict(evidence)
    _validate_scale_schema(repo_root, value)
    material = {
        key: item for key, item in value.items() if key not in {"schema_version", "measurement_id"}
    }
    expected_id = "dad:hook-scale:" + canonical_digest(material).split(":", 1)[1]
    if value["measurement_id"] != expected_id:
        raise HookPerformanceEvidenceError("scale measurement_id does not match evidence")
    if value["adapter_revision_id"] != CODEX_HOOK_ADAPTER_REVISION_ID:
        raise HookPerformanceEvidenceError("scale adapter revision is stale")
    expected_interface = runtime_adapter_interface_digest(
        repo_root, RUNTIME_ADAPTER_ARTIFACT_ID
    )
    if value["adapter_interface_digest"] != expected_interface:
        raise HookPerformanceEvidenceError("scale adapter interface digest is stale")
    expected_cases = [(0, "warm"), (1_000, "warm"), (10_000, "cold"), (10_000, "warm")]
    observed_cases = [
        (int(row["preexisting_event_count"]), str(row["index_state"]))
        for row in value["results"]
    ]
    if observed_cases != expected_cases:
        raise HookPerformanceEvidenceError("scale cases are incomplete or unordered")
    for row in value["results"]:
        required_new_fields = {
            "sample_count",
            "latency_ms_samples",
            "latency_ms_p95",
            "samples",
            "full_oracle_valid",
            "timed_out_count",
        }
        if not required_new_fields.issubset(row):
            raise HookPerformanceEvidenceError("scale evidence lacks repeated-sample fields")
        samples = list(row["samples"])
        latencies = [float(sample["latency_ms"]) for sample in samples]
        minimum = MINIMUM_QUALIFYING_SAMPLES if row["index_state"] == "warm" else 1
        if int(row["sample_count"]) != len(samples) or len(samples) < minimum:
            raise HookPerformanceEvidenceError("scale sample count is insufficient")
        if [float(item) for item in row["latency_ms_samples"]] != latencies:
            raise HookPerformanceEvidenceError("scale latency samples do not match outcomes")
        p95 = nearest_rank_p95(latencies)
        if float(row["latency_ms_p95"]) != p95 or float(row["latency_ms"]) != p95:
            raise HookPerformanceEvidenceError("scale p95 does not match nearest-rank methodology")
        if int(row["timed_out_count"]) != sum(
            int(sample["timed_out"] is True) for sample in samples
        ):
            raise HookPerformanceEvidenceError("scale timeout count does not match samples")
    if value["source_worktree_unchanged"] is not True:
        raise HookPerformanceEvidenceError("source worktree changed during scale harness")
    return value


def qualify_hook_scale_evidence(
    repo_root: Path, evidence: Mapping[str, Any]
) -> dict[str, Any]:
    """Fail closed on any safety, oracle, timeout, or latency result."""

    value = validate_hook_scale_collection(repo_root, evidence)
    for row in value["results"]:
        expected_event_count = int(row["preexisting_event_count"]) + 1
        for sample in row["samples"]:
            if (
                int(sample["exit_code"]) != 0
                or sample["silent"] is not True
                or sample["timed_out"] is not False
                or sample["persistence_confirmed"] is not True
                or sample["full_oracle_valid"] is not True
                or sample["index_valid"] is not True
                or sample["index_size_matches"] is not True
                or sample["index_digest_matches"] is not True
                or int(sample["ledger_event_count"]) != expected_event_count
                or int(sample["index_event_count"]) != expected_event_count
                or int(sample["index_command_count"]) != expected_event_count
                or int(sample["failure_marker_count"]) != 0
            ):
                raise HookPerformanceEvidenceError("scale case did not complete safely")
        budget = (
            float(value["warm_latency_budget_ms"])
            if row["index_state"] == "warm"
            else float(value["cold_hard_timeout_ms"])
        )
        if float(row["latency_ms_p95"]) > budget:
            raise HookPerformanceEvidenceError(
                "scale case exceeded its latency boundary: "
                f"{row['preexisting_event_count']}/{row['index_state']} "
                f"{row['latency_ms_p95']}ms > {budget}ms"
            )
    return value


def validate_hook_scale_evidence(
    repo_root: Path, evidence: Mapping[str, Any]
) -> dict[str, Any]:
    """Compatibility name for the fail-closed qualification step."""

    return qualify_hook_scale_evidence(repo_root, evidence)


def run_hook_scale_harness(repo_root: Path) -> dict[str, Any]:
    """Collect and qualify repeated cold/warm 0, 1K, and 10K evidence."""

    evidence = collect_hook_scale_evidence(repo_root)
    return qualify_hook_scale_evidence(repo_root, evidence)


def write_hook_scale_evidence(path: Path, evidence: Mapping[str, Any]) -> None:
    atomic_write_text(path, json_dumps(dict(evidence), pretty=True) + "\n")


__all__ = [
    "HookPerformanceEvidenceError",
    "MINIMUM_QUALIFYING_SAMPLES",
    "METHODOLOGY_ID",
    "collect_hook_scale_evidence",
    "nearest_rank_p95",
    "qualify_hook_scale_evidence",
    "run_hook_performance_benchmark",
    "run_hook_scale_harness",
    "validate_hook_performance_evidence",
    "validate_hook_scale_collection",
    "validate_hook_scale_evidence",
    "write_hook_performance_evidence",
    "write_hook_scale_evidence",
]
