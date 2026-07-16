"""Deterministic portability policy, evidence, and release-gate projections.

This module never calls a model, probes a provider, changes a route, approves an
exception, or executes an artifact.  It makes objective DAD-local portability
contracts enforceable at lifecycle and protected-transition boundaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

from jsonschema.validators import validator_for


REGISTRY_PATH = Path("registry/portable-capability-registry.json")
POLICY_PATH = Path("registry/portability-policy-registry.json")
QUALIFICATION_REGISTRY_PATH = Path("registry/portable-runtime-qualification-registry.json")
CARD_SCHEMA_PATH = Path("schemas/portable-capability-card.schema.json")
REGISTRY_SCHEMA_PATH = Path("schemas/portable-capability-registry.schema.json")
POLICY_SCHEMA_PATH = Path("schemas/portability-policy.schema.json")
ASSESSMENT_SCHEMA_PATH = Path("schemas/portability-assessment.schema.json")
RECEIPT_SCHEMA_PATH = Path("schemas/model-attempt-receipt-v2.schema.json")
QUALIFICATION_SCHEMA_PATH = Path("schemas/portable-runtime-qualification.schema.json")
HEALTH_SCHEMA_PATH = Path("schemas/portability-health-snapshot.schema.json")

AUTHORITY_BOUNDARY = (
    "Portability findings are deterministic DAD-local lifecycle evidence. They cannot approve "
    "exceptions, provider access, model execution, policy activation, downstream adoption, "
    "release, external effects, or a producer checking its own material output."
)

_REUSABLE_TASK = re.compile(
    r"\b(?:reusable|skill|subagent|agent family|workflow|routine|trigger|harness|prompt|"
    r"library|knowledge base|knowledge graph|template|capability pack|runtime adapter|"
    r"model retirement|portable|model[- ]agnostic|provider[- ]neutral)\b",
    re.I,
)
_CREATE_OR_REVISE = re.compile(
    r"\b(?:build|create|implement|add|revise|update|export|activate|promote|replace|retire|migrate)\b",
    re.I,
)
_NORMATIVE_REQUEST = re.compile(
    r"\b(?:always|only|permanent(?:ly)?|locked|tied|fixed|must\s+use|requires?|default\s+to)\b",
    re.I,
)
_NORMATIVE_SOURCE = re.compile(
    r"(?:always|only|permanent(?:ly)?|locked|fixed|must\s+use|requires?|default\s+to)"
    r".{0,80}(?:gpt(?:[-_.]?[0-9])?|openai|anthropic|claude|gemini|cursor|bedrock|vertex|mistral|llama|groq)"
    r"|(?:gpt(?:[-_.]?[0-9])?|openai|anthropic|claude|gemini|cursor|bedrock|vertex|mistral|llama|groq)"
    r".{0,80}(?:only|permanent(?:ly)?|locked|fixed|required|default)",
    re.I | re.S,
)
_GOVERNED_PREFIXES = (
    "assets/agent-skills/",
    "schemas/",
    "registry/",
    "config/global-personal-skills.json",
    ".githooks/",
    ".github/",
    "src/",
)
_SELF_DESCRIBING_GOVERNED_FILES = {REGISTRY_PATH.as_posix()}
_MAX_PORTABLE_SOURCE_BYTES = 1_048_576
_NORMATIVE_RUNTIME_TERMS = re.compile(
    r"(?:^|[^a-z0-9])(?:gpt(?:[-_.]?[0-9])?|openai|anthropic|claude|gemini|cursor|"
    r"bedrock|vertex|mistral|llama|groq)(?:$|[^a-z0-9])",
    re.I,
)
_ABSOLUTE_PATH = re.compile(r"(?:[a-zA-Z]:[\\/](?:Users|Documents|Desktop)|/Users/|/home/)")
_CONFIRMED_SECRET = re.compile(
    r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-[A-Za-z0-9]{20,}\b|"
    r"\bghp_[A-Za-z0-9]{20,}\b|\bAKIA[A-Z0-9]{16}\b)"
)
_SUSPECTED_SECRET = re.compile(r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\b", re.I)

_SOURCE_SPECS = (
    ("dad_skill_registry", "registry/agent-skill-library.json", "skills", "skill_id"),
    ("personal_skill_allowlist", "config/global-personal-skills.json", "skills", "skill_id"),
    ("agent_families", "registry/agent-family-portfolio-registry.json", "families", "family_id"),
    ("product_workflows", "registry/technical-product-company-os-registry.json", "workflows", "workflow_id"),
    ("knowledge_workflows", "registry/knowledge-engineering-family-registry.json", "workflow_cards", "workflow_id"),
    ("knowledge_techniques", "registry/knowledge-engineering-technique-registry.json", "techniques", "technique_id"),
    ("ml_workflows", "registry/ml-agent-family-registry.json", "workflow_cards", "workflow_id"),
    ("ml_techniques", "registry/ml-technique-registry.json", "techniques", "technique_id"),
)


def _has_governed_prefix(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in _GOVERNED_PREFIXES)


def _line_has_normative_runtime_binding(line: str) -> bool:
    lowered = line.lower()
    if "optional adapter" in lowered or "optional runtime adapter" in lowered:
        return False
    return bool(_NORMATIVE_SOURCE.search(line))


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def _validate(payload: dict[str, Any], schema_path: Path) -> None:
    schema = _load(schema_path)
    cls = validator_for(schema)
    cls.check_schema(schema)
    errors = sorted(cls(schema, format_checker=cls.FORMAT_CHECKER).iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        error = errors[0]
        where = ".".join(str(part) for part in error.path) or "<root>"
        raise ValueError(f"Invalid {schema_path.name} at {where}: {error.message}")


def load_registry(repo_root: Path) -> dict[str, Any]:
    registry = _load(repo_root / REGISTRY_PATH)
    _validate(registry, repo_root / REGISTRY_SCHEMA_PATH)
    return registry


def load_policy(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = _load(repo_root / POLICY_PATH)
    _validate(registry, repo_root / POLICY_SCHEMA_PATH)
    active_id = registry["active_policy_revision_id"]
    matches = [row for row in registry["policy_revisions"] if row["revision_id"] == active_id]
    decisions = [row for row in registry["activation_decisions"] if row["policy_revision_id"] == active_id]
    if len(matches) != 1 or not decisions:
        raise ValueError("Active portability policy lacks one revision and an activation decision")
    digest_material = {key: value for key, value in matches[0].items() if key != "content_digest"}
    if matches[0]["content_digest"] != canonical_digest(digest_material):
        raise ValueError("Active portability policy content digest does not match its revision")
    return registry, matches[0]


def classify_eligibility(task: str = "", paths: Iterable[str] = ()) -> dict[str, Any]:
    normalized = sorted(
        {
            str(path).replace("\\", "/")[2:]
            if str(path).replace("\\", "/").startswith("./")
            else str(path).replace("\\", "/")
            for path in paths
            if str(path)
        }
    )
    governed = [path for path in normalized if _has_governed_prefix(path)]
    explicit = bool(_REUSABLE_TASK.search(task) and _CREATE_OR_REVISE.search(task))
    runtime_binding_requested = bool(
        explicit and _NORMATIVE_REQUEST.search(task) and _NORMATIVE_RUNTIME_TERMS.search(task)
    )
    if not explicit and not governed:
        applicability = "not_applicable"
        reasons = ["no_reusable_creation_or_governed_path"]
    elif explicit or governed:
        applicability = "portable_required"
        reasons = (["explicit_reusable_creation_or_revision"] if explicit else []) + (
            ["governed_path_changed"] if governed else []
        )
    else:
        applicability = "ambiguous_candidate"
        reasons = ["semantic_disposition_required"]
    return {
        "applicability": applicability,
        "reason_codes": reasons,
        "governed_paths": governed,
        "runtime_binding_requested": runtime_binding_requested,
        "model_calls": 0,
    }


def _json_at_commit(repo_root: Path, commit: str, relative: str) -> dict[str, Any] | None:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        return None
    value = json.loads(completed.stdout)
    return value if isinstance(value, dict) else None


def _identities_from_payload(payload: dict[str, Any] | None, collection: str, key: str) -> set[str]:
    if not payload:
        return set()
    rows = payload.get(collection, [])
    return {
        str(row.get(key))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get(key), str) and row.get(key)
    }


def _identity_rows(
    payload: dict[str, Any] | None, collection: str, key: str
) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    return {
        str(row[key]): row
        for row in payload.get(collection, [])
        if isinstance(row, dict) and isinstance(row.get(key), str) and row.get(key)
    }


@lru_cache(maxsize=8)
def _baseline_snapshot(repo_root_value: str, baseline_commit: str) -> dict[str, tuple[Any, ...]]:
    """Cache immutable Git-object evidence, never mutable working-tree state."""

    repo_root = Path(repo_root_value)
    snapshot: dict[str, tuple[Any, ...]] = {}
    for name, relative, collection, key in _SOURCE_SPECS:
        rows = _identity_rows(
            _json_at_commit(repo_root, baseline_commit, relative), collection, key
        )
        snapshot[name] = tuple(sorted(rows))
        snapshot[name + ":row_digests"] = tuple(
            sorted((identity, canonical_digest(row)) for identity, row in rows.items())
        )
    baseline_tree = subprocess.run(
        ["git", "ls-tree", "-r", baseline_commit, "assets/agent-skills"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    skill_blobs: list[tuple[str, str]] = []
    for line in baseline_tree.stdout.splitlines():
        metadata, separator, relative = line.partition("\t")
        if not separator or not relative.endswith("/SKILL.md"):
            continue
        fields = metadata.split()
        if len(fields) >= 3:
            skill_blobs.append(("skill:" + Path(relative).parent.name, fields[2]))
    snapshot["dad_skill_directories"] = tuple(sorted(identity for identity, _ in skill_blobs))
    snapshot["dad_skill_directories:row_digests"] = tuple(sorted(skill_blobs))
    return snapshot


def inventory(repo_root: Path) -> dict[str, Any]:
    registry = load_registry(repo_root)
    baseline_commit = registry["baseline"]["git_commit"]
    baseline_snapshot = _baseline_snapshot(str(repo_root.resolve()), baseline_commit)
    surfaces: dict[str, dict[str, Any]] = {}
    current_all: set[str] = set()
    baseline_all: set[str] = set()
    changed_all: set[str] = set()
    current_observations: dict[str, list[dict[str, str]]] = {}
    for name, relative, collection, key in _SOURCE_SPECS:
        current_payload = _load(repo_root / relative)
        current_rows = _identity_rows(current_payload, collection, key)
        current = set(current_rows)
        baseline = set(baseline_snapshot[name])
        baseline_digests = dict(baseline_snapshot[name + ":row_digests"])
        changed = {
            identity
            for identity in current & baseline
            if canonical_digest(current_rows[identity]) != baseline_digests.get(identity)
        }
        current_all |= current
        baseline_all |= baseline
        changed_all |= changed
        for identity, row in current_rows.items():
            current_observations.setdefault(identity, []).append(
                {"surface": name, "digest": canonical_digest(row)}
            )
        surfaces[name] = {
            "current_count": len(current),
            "baseline_count": len(baseline),
            "new_identity_ids": sorted(current - baseline),
            "changed_identity_ids": sorted(changed),
        }
    current_dirs = {
        "skill:" + path.parent.name
        for path in (repo_root / "assets" / "agent-skills").glob("*/SKILL.md")
    }
    baseline_dirs = set(baseline_snapshot["dad_skill_directories"])
    baseline_skill_digests = dict(
        baseline_snapshot["dad_skill_directories:row_digests"]
    )
    current_skill_digests: dict[str, str] = {}
    for path in (repo_root / "assets" / "agent-skills").glob("*/SKILL.md"):
        data = path.read_bytes().replace(b"\r\n", b"\n")
        current_skill_digests["skill:" + path.parent.name] = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        ).hexdigest()
    changed_dirs = {
        identity
        for identity in current_dirs & baseline_dirs
        if current_skill_digests.get(identity) != baseline_skill_digests.get(identity)
    }
    surfaces["dad_skill_directories"] = {
        "current_count": len(current_dirs),
        "baseline_count": len(baseline_dirs),
        "new_identity_ids": sorted(current_dirs - baseline_dirs),
        "changed_identity_ids": sorted(changed_dirs),
    }
    current_all |= current_dirs
    baseline_all |= baseline_dirs
    changed_all |= changed_dirs
    for identity, digest in current_skill_digests.items():
        current_observations.setdefault(identity, []).append(
            {"surface": "dad_skill_directories", "digest": "git-blob-sha1:" + digest}
        )
    baseline_material = {
        "git_commit": baseline_commit,
        "source_surfaces": {
            name: list(baseline_snapshot[name])
            for name, relative, collection, key in _SOURCE_SPECS
        }
        | {"dad_skill_directories": sorted(baseline_dirs)},
    }
    observed_baseline_digest = canonical_digest(baseline_material)
    material = {"baseline_commit": baseline_commit, "surfaces": surfaces}
    requiring_disposition = (current_all - baseline_all) | changed_all
    return {
        **material,
        "current_identity_count": len(current_all),
        "baseline_identity_count": len(baseline_all),
        "new_identity_ids": sorted(current_all - baseline_all),
        "changed_identity_ids": sorted(changed_all),
        "requiring_disposition_ids": sorted(requiring_disposition),
        "observation_digests": {
            identity: canonical_digest(
                sorted(rows, key=lambda row: (row["surface"], row["digest"]))
            )
            for identity, rows in sorted(current_observations.items())
            if identity in requiring_disposition
        },
        "baseline_content_digest": observed_baseline_digest,
        "baseline_integrity": (
            "verified"
            if observed_baseline_digest == registry["baseline"]["content_digest"]
            else "failed"
        ),
        "inventory_digest": canonical_digest(material),
        "model_calls": 0,
    }


def _finding(code: str, artifact_id: str, *, severity: str = "error") -> dict[str, str]:
    return {"code": code, "artifact_id": artifact_id, "severity": severity}


def _resolved_portable_files(
    repo_root: Path, card: dict[str, Any]
) -> list[tuple[str, Path]] | None:
    personal_manifest: dict[str, Any] | None = None
    resolved: list[tuple[str, Path]] = []
    for raw in card.get("portable_files", []):
        label = str(raw)
        if label.startswith("personal-skill-source:"):
            if personal_manifest is None:
                personal_manifest = _load(repo_root / "config/global-personal-skills.json")
            suffix = label.split(":", 1)[1]
            skill_name, separator, relative = suffix.partition("/")
            row = next(
                (
                    item
                    for item in personal_manifest.get("skills", [])
                    if item.get("source_path") == skill_name
                    and item.get("skill_id") == card.get("artifact_id")
                ),
                None,
            )
            if not separator or not row:
                return None
            codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            path = codex_home / personal_manifest["source_root_relative"] / skill_name / relative
        else:
            relative_path = Path(label)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                return None
            path = repo_root / relative_path
        if not path.is_file():
            return None
        resolved.append((label.replace("\\", "/"), path))
    return resolved


def _portable_files_digest(repo_root: Path, card: dict[str, Any]) -> str | None:
    resolved = _resolved_portable_files(repo_root, card)
    if resolved is None:
        return None
    rows: list[dict[str, str]] = []
    for label, path in resolved:
        rows.append(
            {
                "path": label,
                "sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return canonical_digest(rows)


def _portable_source_text(repo_root: Path, card: dict[str, Any]) -> str:
    resolved = _resolved_portable_files(repo_root, card)
    if resolved is None:
        return ""
    chunks: list[str] = []
    for _, path in resolved:
        if path.stat().st_size > _MAX_PORTABLE_SOURCE_BYTES:
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks)


def changed_governed_files(repo_root: Path, baseline_commit: str) -> list[str]:
    """Return every governed path changed from the immutable baseline.

    The Git diff supplies tracked changes while porcelain v1 with
    ``--untracked-files=all`` prevents an untracked directory from collapsing
    into a single path and hiding nested reusable assets.
    """

    paths: set[str] = set()
    tracked = subprocess.run(
        ["git", "diff", "--name-only", baseline_commit, "--"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode == 0:
        paths.update(tracked.stdout.splitlines())
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            raw = line[3:]
            if " -> " in raw:
                raw = raw.split(" -> ", 1)[1]
            paths.add(raw.strip('"'))
    normalized = {path.replace("\\", "/") for path in paths if path}
    return sorted(
        path
        for path in normalized
        if path not in _SELF_DESCRIBING_GOVERNED_FILES
        and _has_governed_prefix(path)
    )


def _instruction_binding_digest(card: dict[str, Any]) -> str | None:
    binding = card.get("instruction_binding")
    if not isinstance(binding, dict):
        return None
    if binding.get("source_ref") != "personal-codex-source:AGENTS.md":
        return "unavailable"
    path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "AGENTS.md"
    if not path.is_file():
        return "unavailable"
    text = path.read_text(encoding="utf-8")
    begin = str(binding.get("begin_marker", ""))
    end = str(binding.get("end_marker", ""))
    start = text.find(begin)
    finish = text.find(end, start + len(begin)) if start >= 0 else -1
    if start < 0 or finish < 0:
        return "unavailable"
    return canonical_digest(text[start + len(begin) : finish].strip())


def _live_source_path(card: dict[str, Any]) -> Path | None:
    binding = card.get("live_source_binding")
    if not isinstance(binding, dict):
        return None
    source_ref = str(binding.get("source_ref", ""))
    if not source_ref.startswith("personal-skill-source:"):
        return None
    relative = Path(source_ref.split(":", 1)[1])
    if relative.is_absolute() or ".." in relative.parts:
        return None
    path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / relative
    return path if path.is_file() else None


def validate_portability(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    registry = load_registry(repo_root)
    _, policy = load_policy(repo_root)
    cards = registry["cards"]
    findings: list[dict[str, str]] = []
    quarantine: list[dict[str, str]] = []
    card_ids: set[str] = set()
    revision_ids: set[str] = set()
    artifact_cards: dict[str, dict[str, Any]] = {}
    revision_cards: dict[str, dict[str, Any]] = {}
    for card in cards:
        artifact = str(card.get("artifact_id", "unknown"))
        try:
            _validate(card, repo_root / CARD_SCHEMA_PATH)
        except ValueError:
            findings.append(_finding("invalid_portability_card", artifact))
            continue
        if card["card_id"] in card_ids or card["revision_id"] in revision_ids or artifact in artifact_cards:
            findings.append(_finding("duplicate_portability_identity", artifact))
        card_ids.add(card["card_id"])
        revision_ids.add(card["revision_id"])
        artifact_cards[artifact] = card
        revision_cards[card["revision_id"]] = card
        normative = [artifact, *card.get("capability_ids", []), *card.get("dependencies", [])]
        if card["binding_class"] == "portable_core" and any(_NORMATIVE_RUNTIME_TERMS.search(value) for value in normative):
            findings.append(_finding("normative_runtime_binding_in_core", artifact))
        serialized = json.dumps(card, sort_keys=True)
        if _CONFIRMED_SECRET.search(serialized):
            findings.append(_finding("confirmed_secret", artifact))
        elif _SUSPECTED_SECRET.search(serialized):
            quarantine.append(_finding("suspected_secret", artifact, severity="quarantine"))
        for value in [card.get("source_authority", ""), *card.get("portable_files", [])]:
            if _ABSOLUTE_PATH.search(str(value)):
                findings.append(_finding("sensitive_absolute_path", artifact))
        observed_content = _portable_files_digest(repo_root, card)
        if observed_content is None:
            findings.append(_finding("portable_source_unavailable", artifact))
        elif observed_content != card.get("content_digest"):
            findings.append(_finding("content_digest_mismatch", artifact))
        source_text = _portable_source_text(repo_root, card)
        resolved_sources = _resolved_portable_files(repo_root, card)
        if resolved_sources and any(
            path.stat().st_size > _MAX_PORTABLE_SOURCE_BYTES for _, path in resolved_sources
        ):
            findings.append(_finding("oversized_portable_source_unscanned", artifact))
        live_source = _live_source_path(card)
        if card.get("live_source_binding"):
            if live_source is None:
                findings.append(_finding("external_source_unavailable", artifact, severity="warning"))
            else:
                observed_live = "sha256:" + hashlib.sha256(live_source.read_bytes()).hexdigest()
                if observed_live != card["live_source_binding"]["content_digest"]:
                    findings.append(_finding("content_digest_mismatch", artifact))
                try:
                    source_text += "\n" + live_source.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    findings.append(_finding("portable_source_unavailable", artifact))
        if _CONFIRMED_SECRET.search(source_text):
            findings.append(_finding("confirmed_secret", artifact))
        elif _SUSPECTED_SECRET.search(source_text):
            quarantine.append(_finding("suspected_secret", artifact, severity="quarantine"))
        if card["binding_class"] == "portable_core" and any(
            _line_has_normative_runtime_binding(line) for line in source_text.splitlines()
        ):
            findings.append(_finding("normative_runtime_binding_in_source", artifact))
        if card.get("instruction_binding"):
            observed_instruction = _instruction_binding_digest(card)
            if observed_instruction == "unavailable":
                findings.append(_finding("external_source_unavailable", artifact, severity="warning"))
            elif observed_instruction != card["instruction_binding"]["content_digest"]:
                findings.append(_finding("content_digest_mismatch", artifact))
        fresh = card.get("fresh_until") or card.get("exception_expires_at")
        if fresh:
            parsed = datetime.fromisoformat(str(fresh).replace("Z", "+00:00"))
            if parsed.astimezone(timezone.utc) <= observed:
                findings.append(_finding("expired_exception" if card["binding_class"] == "environment_bound_exception" else "stale_evidence", artifact))
    for artifact, card in artifact_cards.items():
        if card.get("binding_class") == "runtime_adapter":
            core = revision_cards.get(str(card.get("core_revision_id", "")))
            if not core or core.get("binding_class") != "portable_core":
                findings.append(_finding("missing_core_parent", artifact))
            elif card.get("preserved_contract_digests") != core.get("contract_digests"):
                findings.append(_finding("adapter_redefines_core_contract", artifact))
        if card.get("binding_class") == "provider_probe":
            adapter = revision_cards.get(str(card.get("adapter_revision_id", "")))
            if not adapter or adapter.get("binding_class") != "runtime_adapter":
                findings.append(_finding("missing_adapter_parent", artifact))
        if card.get("binding_class") == "environment_bound_exception":
            findings.append(_finding("exception_decision_unverified", artifact))
    graph = {artifact: [dep for dep in card.get("dependencies", []) if dep in artifact_cards] for artifact, card in artifact_cards.items()}
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(child) for child in graph.get(node, [])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False
    if any(visit(node) for node in graph):
        findings.append(_finding("dependency_cycle", "portable-capability-registry"))
    inv = inventory(repo_root)
    if inv.get("baseline_integrity") == "failed":
        findings.append(_finding("baseline_integrity_failure", registry["baseline"]["baseline_id"]))
    for artifact in inv["requiring_disposition_ids"]:
        if artifact not in artifact_cards:
            findings.append(_finding("missing_portability_disposition", artifact))
        elif artifact_cards[artifact].get("source_observation_digest") != inv["observation_digests"].get(artifact):
            findings.append(_finding("stale_portability_disposition", artifact))
    covered_files = {
        str(path).replace("\\", "/")
        for card in artifact_cards.values()
        for path in card.get("portable_files", [])
        if not str(path).startswith("personal-skill-source:")
    }
    for relative in changed_governed_files(repo_root, registry["baseline"]["git_commit"]):
        if relative not in covered_files:
            findings.append(_finding("undispositioned_governed_file", relative))
    findings = sorted({(row["code"], row["artifact_id"], row["severity"]): row for row in findings}.values(), key=lambda row: (row["code"], row["artifact_id"]))
    hard_codes = set(policy["objective_gate_codes"])
    hard = [row for row in findings if row["code"] in hard_codes or row["code"] in {"duplicate_portability_identity", "adapter_redefines_core_contract", "missing_adapter_parent"}]
    return {
        "valid": not hard,
        "policy_revision_id": policy["revision_id"],
        "rollout_mode": policy["rollout_mode"],
        "baseline_id": registry["baseline"]["baseline_id"],
        "card_count": len(cards),
        "inventory": inv,
        "findings": findings,
        "quarantine": quarantine,
        "hard_finding_count": len(hard),
        "model_calls": 0,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def assess_lifecycle(
    repo_root: Path,
    *,
    stage: str,
    task: str = "",
    paths: Iterable[str] = (),
    artifact_ids: Iterable[str] = (),
    protected_transition: bool = False,
) -> dict[str, Any]:
    eligibility = classify_eligibility(task, paths)
    validation = validate_portability(repo_root)
    applicable = eligibility["applicability"]
    finding_codes = sorted({row["code"] for row in validation["findings"]}) if applicable != "not_applicable" or protected_transition else []
    if eligibility.get("runtime_binding_requested"):
        finding_codes = sorted(set(finding_codes) | {"normative_runtime_binding_in_request"})
    exact_artifacts = sorted({str(value) for value in artifact_ids if str(value)})
    exact_binding_stages = {
        "implementation_lease",
        "activation",
        "registry_promotion",
        "reviewed_portable",
        "cross_repo_delivery",
    }
    governed_scope = sorted({str(path).replace("\\", "/") for path in eligibility["governed_paths"]})
    if (
        protected_transition
        and stage in exact_binding_stages
        and applicable == "portable_required"
        and (not exact_artifacts or not governed_scope)
    ):
        finding_codes = sorted(set(finding_codes) | {"missing_exact_portability_binding"})
    if exact_artifacts:
        known_cards = {
            str(card.get("artifact_id", "")): card for card in load_registry(repo_root)["cards"]
        }
        if any(artifact not in known_cards for artifact in exact_artifacts):
            finding_codes = sorted(set(finding_codes) | {"missing_exact_portability_binding"})
        else:
            covered_scope = {
                str(path).replace("\\", "/")
                for artifact in exact_artifacts
                for path in known_cards[artifact].get("portable_files", [])
                if not str(path).startswith("personal-skill-source:")
            }
            if any(path not in covered_scope for path in governed_scope):
                finding_codes = sorted(
                    set(finding_codes) | {"missing_exact_portability_binding"}
                )
    quarantine_codes = sorted({row["code"] for row in validation["quarantine"]})
    if applicable == "not_applicable" and not protected_transition:
        outcome = "not_applicable"
    elif (
        validation["hard_finding_count"]
        or eligibility.get("runtime_binding_requested")
        or "missing_exact_portability_binding" in finding_codes
        or (protected_transition and quarantine_codes)
    ) and (protected_transition or validation["rollout_mode"] in {"enforce_new_or_worsened", "reviewed_active"}):
        outcome = "block"
    elif stage == "postflight" and applicable != "not_applicable" and finding_codes:
        outcome = "eligible_unverified"
    elif stage == "preflight" and "explicit_reusable_creation_or_revision" in eligibility["reason_codes"]:
        outcome = "eligible_unverified"
    elif finding_codes:
        outcome = "warn"
    else:
        outcome = "pass"
    affected = validation["inventory"]["new_identity_ids"] if applicable != "not_applicable" or protected_transition else []
    requested_scope_digest = canonical_digest({"paths": governed_scope})
    material = {
        "stage": stage,
        "applicability": applicable,
        "policy_revision_id": validation["policy_revision_id"],
        "baseline_id": validation["baseline_id"],
        "affected_artifact_ids": affected,
        "bound_artifact_ids": exact_artifacts,
        "requested_scope_digest": requested_scope_digest,
        "finding_codes": finding_codes,
        "quarantine_codes": quarantine_codes,
        "gate_outcome": outcome,
        "model_calls": 0,
    }
    assessment = {
        "schema_version": "dad.portability_assessment.v1",
        "assessment_id": "portability-assessment:" + canonical_digest(material).split(":", 1)[1],
        **material,
        "assessment_digest": canonical_digest(material),
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _validate(assessment, repo_root / ASSESSMENT_SCHEMA_PATH)
    return assessment


def verify_attempt_receipt(
    repo_root: Path,
    receipt: dict[str, Any],
    *,
    prior_receipts: Iterable[dict[str, Any]] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    _validate(receipt, repo_root / RECEIPT_SCHEMA_PATH)
    registry = _load(repo_root / QUALIFICATION_REGISTRY_PATH)
    issuer = next((row for row in registry["receipt_issuers"] if row["issuer_id"] == receipt["issuer_id"]), None)
    reasons: list[str] = []
    if not issuer:
        reasons.append("unregistered_receipt_issuer")
    else:
        if issuer["verification_method"] != receipt["verification_method"]:
            reasons.append("verification_method_mismatch")
        if receipt["adapter_revision_id"] not in issuer["adapter_revision_ids"]:
            reasons.append("adapter_revision_mismatch")
        if issuer.get("live_claims_allowed"):
            reasons.append("durable_replay_ledger_unavailable")
    if receipt["verification_method"] != "synthetic_fixture":
        if not str(receipt.get("attestation_ref", "")).strip():
            reasons.append("attestation_missing")
        reasons.append("attestation_verifier_unavailable")
    for prior in prior_receipts:
        if prior.get("nonce") == receipt["nonce"] or prior.get("evidence_digest") == receipt["evidence_digest"]:
            reasons.append("receipt_replay_detected")
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires = datetime.fromisoformat(receipt["expires_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
    if expires <= observed:
        reasons.append("receipt_expired")
    if receipt["verification_state"] in {"expired", "revoked", "disputed", "unknown"}:
        reasons.append("receipt_not_verified")
    if receipt["verification_state"] == "verified" and not all(
        str(receipt.get(key, "")).strip()
        for key in ("provider_id", "model_family", "model_release")
    ):
        reasons.append("model_identity_incomplete")
    verified = not reasons and receipt["verification_state"] == "verified"
    return {
        "receipt_id": receipt["receipt_id"],
        "verified": verified,
        "verification_state": "verified" if verified else "unknown",
        "reason_codes": sorted(set(reasons)),
        "live_claim_allowed": bool(verified and issuer and issuer.get("live_claims_allowed")),
        "execution_authorized": False,
    }


def qualify_runtime(repo_root: Path, qualification: dict[str, Any], receipts: list[dict[str, Any]]) -> dict[str, Any]:
    _validate(qualification, repo_root / QUALIFICATION_SCHEMA_PATH)
    receipt_map = {row["receipt_id"]: row for row in receipts}
    selected = [receipt_map.get(item) for item in qualification["receipt_ids"]]
    if any(item is None for item in selected):
        return {"result": "no_winner", "reason_codes": ["missing_receipt"], "execution_authorized": False}
    verified = [
        verify_attempt_receipt(repo_root, item, prior_receipts=selected[:index])
        for index, item in enumerate(selected)
        if item
    ]
    bindings = {(item["core_revision_id"], item["adapter_revision_id"], item["harness_revision_id"], item["corpus_revision_id"], item["role_id"]) for item in selected if item}
    identities = {(item["provider_id"], item["model_family"], item["model_release"]) for item in selected if item}
    reasons: list[str] = []
    if not all(row["verified"] for row in verified):
        reasons.append("receipt_unverified")
    if len(bindings) != 1:
        reasons.append("incomparable_bindings")
    expected_binding = (
        qualification["core_revision_id"],
        qualification["adapter_revision_id"],
        qualification["harness_revision_id"],
        qualification["corpus_revision_id"],
        qualification["role_id"],
    )
    if bindings != {expected_binding}:
        reasons.append("qualification_binding_mismatch")
    if len(identities) < 2:
        reasons.append("same_model_arms")
    if qualification["evaluator_integrity"] != "verified":
        reasons.append("evaluator_integrity_failed")
    if qualification["hard_gate_failures"]:
        reasons.append("hard_gate_failure")
    if qualification["matched_attempts"] != len(selected):
        reasons.append("matched_attempt_count_mismatch")
    if not all(row["live_claim_allowed"] for row in verified):
        reasons.append("live_diversity_not_authorized")
    result = "no_winner" if reasons else qualification["result"]
    return {"result": result, "reason_codes": sorted(set(reasons)), "human_promotion_required": True, "execution_authorized": False}


def build_graph(repo_root: Path) -> dict[str, Any]:
    cards = load_registry(repo_root)["cards"]
    nodes = [{"id": row["artifact_id"], "revision_id": row["revision_id"], "binding_class": row["binding_class"], "status": row["status"]} for row in cards]
    edges: list[dict[str, str]] = []
    for row in cards:
        for dep in row.get("dependencies", []):
            edges.append({"source": row["artifact_id"], "target": dep, "edge_type": "depends_on", "review_status": "candidate"})
        if row.get("core_revision_id"):
            edges.append({"source": row["revision_id"], "target": row["core_revision_id"], "edge_type": "adapts_for", "review_status": "candidate"})
    return {"schema_version": "dad.portability_graph.v1", "nodes": nodes, "edges": edges, "candidate_only": True, "execution_authorized": False}


def affected(repo_root: Path, artifact_id: str) -> dict[str, Any]:
    registry = load_registry(repo_root)
    reverse: dict[str, set[str]] = {}
    for row in registry["cards"]:
        for dep in row.get("dependencies", []):
            reverse.setdefault(dep, set()).add(row["artifact_id"])
        for consumer in row.get("reverse_consumers", []):
            reverse.setdefault(row["artifact_id"], set()).add(consumer)
    seen: set[str] = set()
    frontier = [artifact_id]
    while frontier:
        current = frontier.pop(0)
        for item in sorted(reverse.get(current, set())):
            if item not in seen:
                seen.add(item)
                frontier.append(item)
    return {"artifact_id": artifact_id, "affected_consumers": sorted(seen), "candidate_only": True, "execution_authorized": False}


def health_snapshot(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    validation = validate_portability(repo_root, now=now)
    findings = validation["findings"]
    grouped: dict[str, int] = {}
    for row in findings:
        grouped[row["code"]] = grouped.get(row["code"], 0) + 1
    priorities = {"confirmed_secret": 0, "missing_portability_disposition": 1, "stale_evidence": 2, "expired_exception": 2}
    decision_rows = sorted(findings, key=lambda row: (priorities.get(row["code"], 9), row["code"], row["artifact_id"]))
    decisions = [{"title": row["code"], "artifact_id": row["artifact_id"], "recommended_action": "inspect"} for row in decision_rows[:3]]
    observed = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    material = {"validation": validation["inventory"]["inventory_digest"], "findings": grouped, "decisions": decisions}
    snapshot = {
        "schema_version": "dad.portability_health_snapshot.v1",
        "snapshot_id": "portability-health:" + canonical_digest(material).split(":", 1)[1],
        "generated_at": observed,
        "policy_revision_id": validation["policy_revision_id"],
        "baseline_id": validation["baseline_id"],
        "coverage": {"card_count": validation["card_count"], "new_identity_count": len(validation["inventory"]["new_identity_ids"]), "missing_disposition_count": grouped.get("missing_portability_disposition", 0)},
        "finding_counts": grouped,
        "decisions": decisions,
        "backlog_count": max(0, len(decision_rows) - len(decisions)),
        "model_calls": 0,
        "candidate_only": True,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    _validate(snapshot, repo_root / HEALTH_SCHEMA_PATH)
    return snapshot


def exception_candidate(artifact_id: str, reason: str) -> dict[str, Any]:
    material = {"artifact_id": artifact_id, "reason": reason}
    return {
        "schema_version": "dad.portability_exception_candidate.v1",
        "candidate_id": "portability-exception-candidate:" + canonical_digest(material).split(":", 1)[1],
        **material,
        "status": "candidate_requires_human_decision",
        "reviewed_exception_created": False,
        "execution_authorized": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def retirement_exposure(repo_root: Path, runtime_id: str, signal_digest: str) -> dict[str, Any]:
    graph = build_graph(repo_root)
    affected_ids = sorted({edge["source"] for edge in graph["edges"] if edge["target"] == runtime_id})
    material = {"runtime_id": runtime_id, "signal_digest": signal_digest, "affected": affected_ids}
    return {
        "exposure_id": "portability-retirement-exposure:" + canonical_digest(material).split(":", 1)[1],
        **material,
        "route_changed": False,
        "human_decision_required": True,
        "execution_authorized": False,
    }


def rollback_eligible(route: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if route.get("health") != "available": reasons.append("runtime_unavailable")
    if route.get("retirement_state") in {"retired", "revoked"}: reasons.append("runtime_ineligible")
    if route.get("privacy_eligible") is not True: reasons.append("privacy_ineligible")
    if route.get("authority_eligible") is not True: reasons.append("authority_ineligible")
    if route.get("qualification_current") is not True: reasons.append("qualification_ineligible")
    return {"eligible": not reasons, "reason_codes": reasons, "action": "move_active_policy_pointer" if not reasons else "resumable_checkpoint", "execution_authorized": False}


__all__ = [
    "affected", "assess_lifecycle", "build_graph", "canonical_digest",
    "classify_eligibility", "exception_candidate", "health_snapshot", "inventory",
    "load_policy", "load_registry", "qualify_runtime", "retirement_exposure",
    "rollback_eligible", "validate_portability", "verify_attempt_receipt",
]
