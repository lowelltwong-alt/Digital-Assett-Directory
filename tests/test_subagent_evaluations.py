from __future__ import annotations

import copy
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from jsonschema.validators import validator_for

from digital_asset_directory.subagent_evaluations import (
    build_graph,
    content_hash,
    ingest_packet,
    load_packet,
    validate_records,
)
from digital_asset_directory.graph_surfaces import (
    graph_surface_freshness,
    resolve_graph_surface_path,
)


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "examples/subagent-evaluations/logos-t475-and-dad-graph-v1"


def _hub(tmp_path: Path) -> Path:
    hub = tmp_path / "hub"
    for rel in (
        "registry/schema-registry.json",
        "registry/subagent-evaluation-methodology.json",
        "registry/subagent-evaluation-methodologies/0.1.0.json",
        "registry/subagent-capability-registry.json",
        "registry/graph-edge-registry.json",
        "registry/edge-type-registry.json",
        "schemas/subagent-role-profile-revision.schema.json",
        "schemas/subagent-execution-attempt.schema.json",
        "schemas/subagent-attempt-evaluation.schema.json",
        "schemas/subagent-capability-graph.schema.json",
        "schemas/subagent-action-recommendation.schema.json",
        "schemas/subagent-evaluation-methodology.schema.json",
        "schemas/subagent-unrated-inventory.schema.json",
    ):
        target = hub / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    evidence_source = ROOT / "examples/subagent-evaluations/logos-t475-and-dad-graph-v1/evidence"
    evidence_target = hub / "examples/subagent-evaluations/logos-t475-and-dad-graph-v1/evidence"
    evidence_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(evidence_source, evidence_target)
    return hub


def _copy_packet(tmp_path: Path) -> Path:
    target = tmp_path / "packet"
    shutil.copytree(PACKET, target)
    return target


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_seed_packet_validates_and_scores_are_replayed(tmp_path: Path):
    hub = _hub(tmp_path)
    packet = load_packet(PACKET)

    result = validate_records(
        hub, packet["role_profiles"], packet["attempts"], packet["evaluations"]
    )

    assert len(result["attempts"]) == 16
    assert len(result["evaluations"]) == 16
    terra = result["evaluations"]["dad:subagent-evaluation:logos-t475-chandrasekhar"]
    assert terra["aggregate_result"] == {
        "status": "parent_observational_rating",
        "score": 70.45,
        "gate_failed": True,
        "confidence": 0.78,
    }
    assert terra["outcome"] == "mixed"
    assert terra["failures"]


def test_evidence_hashes_survive_crlf_to_lf_checkout(tmp_path: Path):
    hub = _hub(tmp_path)
    evidence_dir = hub / "examples/subagent-evaluations/logos-t475-and-dad-graph-v1/evidence"
    for path in evidence_dir.glob("*.json"):
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    packet = load_packet(PACKET)

    result = validate_records(
        hub, packet["role_profiles"], packet["attempts"], packet["evaluations"]
    )
    assert len(result["evaluations"]) == 16


def test_ingest_is_idempotent_and_conflicting_id_fails(tmp_path: Path):
    hub = _hub(tmp_path)
    packet = _copy_packet(tmp_path)

    first = ingest_packet(hub, packet)
    second = ingest_packet(hub, packet)

    assert first["results"]["attempts"] == {"appended": 16, "unchanged": 0}
    assert second["results"]["attempts"] == {"appended": 0, "unchanged": 16}

    attempts_path = packet / "execution-attempts.jsonl"
    rows = [json.loads(line) for line in attempts_path.read_text().splitlines()]
    rows[0]["display_label"] = "same-id-different-bytes"
    _write_jsonl(attempts_path, rows)
    evaluations_path = packet / "attempt-evaluations.jsonl"
    evaluations = [json.loads(line) for line in evaluations_path.read_text().splitlines()]
    evaluations[0]["attempt_snapshot_sha256"] = content_hash(rows[0])
    _write_jsonl(evaluations_path, evaluations)
    profiles_path = packet / "role-profile-revisions.jsonl"
    profiles = [json.loads(line) for line in profiles_path.read_text().splitlines()]
    extra_profile = copy.deepcopy(profiles[0])
    extra_profile["role_profile_id"] = "dad:role-profile:conflict-probe"
    extra_profile["revision_id"] = "dad:role-profile-revision:conflict-probe:v1"
    extra_profile["revision_sha256"] = content_hash(
        {key: value for key, value in extra_profile.items() if key != "revision_sha256"}
    )
    _write_jsonl(profiles_path, [*profiles, extra_profile])
    with pytest.raises(ValueError, match="Conflicting immutable record"):
        ingest_packet(hub, packet)
    raw_profiles = hub / "raw/agent-evaluations/role-profile-revisions.jsonl"
    assert len(raw_profiles.read_text(encoding="utf-8").splitlines()) == 3


def test_concurrent_identical_ingest_does_not_duplicate_rows(tmp_path: Path):
    hub = _hub(tmp_path)
    packet = _copy_packet(tmp_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: ingest_packet(hub, packet), range(2)))

    assert sorted(result["results"]["attempts"]["appended"] for result in results) == [0, 16]
    raw_attempts = hub / "raw/agent-evaluations/execution-attempts.jsonl"
    assert len(raw_attempts.read_text(encoding="utf-8").splitlines()) == 16


def test_missing_evidence_is_not_replayed_as_zero(tmp_path: Path):
    hub = _hub(tmp_path)
    packet = load_packet(PACKET)
    evaluations = copy.deepcopy(packet["evaluations"])
    evaluation = evaluations[0]
    evaluation["dimension_results"] = {
        dimension: {
            "status": "insufficient_evidence",
            "score": None,
            "evidence_refs": [],
            "rationale": "No evidence.",
        }
        for dimension in evaluation["dimension_results"]
    }
    evaluation["capability_results"] = [
        {
            **capability,
            "status": "insufficient_evidence",
            "rating": None,
            "confidence": 0.0,
            "evidence_refs": [],
            "counterevidence_refs": [],
        }
        for capability in evaluation["capability_results"]
    ]
    evaluation["aggregate_result"] = {
        "status": "insufficient_evidence",
        "score": None,
        "gate_failed": False,
        "confidence": 0.4,
    }
    evaluation["evidence_grade"] = "execution_failure_log"
    evaluation["evidence_bundle_sha256"] = content_hash(
        {
            key: evaluation[key]
            for key in (
                "dimension_results", "capability_results", "strengths", "failures",
                "improvement_recommendations", "limitations", "evidence_grade",
                "evaluator_identity",
            )
        }
    )

    result = validate_records(hub, packet["role_profiles"], packet["attempts"], evaluations)
    assert result["evaluations"][evaluation["evaluation_id"]]["aggregate_result"]["score"] is None


def test_graph_preserves_attempt_identity_and_blocks_profile_ranking(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)

    result = build_graph(hub)
    graph = json.loads(Path(result["graph_path"]).read_text(encoding="utf-8"))

    assert result["counts"] == {
        "node_count": graph["node_count"],
        "edge_count": graph["edge_count"],
        "evaluation_count": 16,
        "attempt_count": 16,
        "role_revision_count": 3,
        "unrated_inventory_count": 1,
    }
    dalton_attempts = [
        row
        for row in graph["nodes"]
        if row["node_type"] == "execution_attempt" and row["label"] == "Dalton"
    ]
    assert len(dalton_attempts) == 2
    assert len({row["attempt_id"] for row in dalton_attempts}) == 2
    assert all(row["profile_score"] is None for row in graph["profile_summaries"])
    terra = next(
        row
        for row in graph["profile_summaries"]
        if row["role_profile_id"] == "dad:role-profile:terra-integration-specialist"
    )
    assert terra["rated_attempt_count"] == 0
    assert terra["observational_attempt_count"] == 3
    assert terra["gate_failed_attempt_count"] == 1
    assert all(
        row["action"] == "insufficient_evidence"
        for row in graph["consolidation_review_queue"]
    )
    assert graph["unrated_inventory"][0]["record_count"] == 378
    assert graph["unrated_inventory"][0]["agent_execution_identity_usable"] is False
    claude_evaluation = "evaluation:dad:subagent-evaluation:dad-graph-claude-opus-timeout"
    assert not any(edge["source"] == claude_evaluation for edge in graph["edges"] if edge["edge_type"] == "evaluation_assesses_capability")


def test_repeated_reviews_of_one_attempt_do_not_inflate_profile_eligibility(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    evaluations_path = hub / "raw/agent-evaluations/attempt-evaluations.jsonl"
    evaluations = [json.loads(line) for line in evaluations_path.read_text().splitlines()]
    seed = next(
        row
        for row in evaluations
        if row["evaluation_id"] == "dad:subagent-evaluation:dad-graph-lorentz"
    )
    duplicates = []
    for index in range(5):
        row = copy.deepcopy(seed)
        row["evaluation_id"] = f"dad:subagent-evaluation:repeat-review-{index}"
        row["evaluator"] = "same-independent-reviewer"
        row["evaluator_independence"] = "independent"
        row["aggregate_result"]["status"] = "rated_attempt"
        row["evidence_grade"] = "independent_hashed_review"
        row["evaluator_attempt_id"] = "dad:subagent-attempt:dad-graph-hypatia"
        row["evaluator_identity"] = {
            "actor_id": f"invented-reviewer-{index}",
            "actor_type": "subagent",
            "verification_status": "runtime_verified",
            "relationship_to_attempt": "independent",
            "evidence_ref": "source://examples/subagent-evaluations/logos-t475-and-dad-graph-v1/evidence/dad-graph-hypatia.json",
        }
        row["evidence_bundle_sha256"] = content_hash(
            {
                key: row[key]
                for key in (
                    "dimension_results", "capability_results", "strengths", "failures",
                    "improvement_recommendations", "limitations", "evidence_grade",
                    "evaluator_identity",
                )
            }
        )
        duplicates.append(row)
    _write_jsonl(evaluations_path, [*evaluations, *duplicates])

    with pytest.raises(ValueError, match="unverified independence"):
        build_graph(hub)


def test_graph_is_deterministic_except_generation_time(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    first = json.loads(Path(build_graph(hub)["graph_path"]).read_text(encoding="utf-8"))
    second = json.loads(Path(build_graph(hub)["graph_path"]).read_text(encoding="utf-8"))

    for payload in (first, second):
        payload.pop("generated_at")
    assert first == second


def test_graph_schema_and_edge_registries_cover_emitted_edges(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    result = build_graph(hub)
    graph = json.loads(Path(result["graph_path"]).read_text(encoding="utf-8"))
    schema = json.loads(
        (ROOT / "schemas/subagent-capability-graph.schema.json").read_text(encoding="utf-8")
    )
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    validator_cls(schema).validate(graph)

    graph_registry = json.loads(
        (ROOT / "registry/graph-edge-registry.json").read_text(encoding="utf-8")
    )
    general_registry = json.loads(
        (ROOT / "registry/edge-type-registry.json").read_text(encoding="utf-8")
    )
    emitted = set(graph["edges_by_type"])
    assert emitted <= {row["edge_type"] for row in graph_registry["edge_types"]}
    assert emitted <= {row["id"] for row in general_registry["edge_types"]}
    schema_edge_types = set(
        schema["properties"]["edges"]["items"]["properties"]["edge_type"]["enum"]
    )
    assert schema_edge_types == emitted


def test_graph_contains_no_authorizing_edge_or_action(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    graph = json.loads(Path(build_graph(hub)["graph_path"]).read_text(encoding="utf-8"))

    forbidden_edges = {
        "better_than", "recommended", "approved_by", "trusted", "authorized_by", "supersedes"
    }
    assert not (set(graph["edges_by_type"]) & forbidden_edges)
    assert all(row["auto_apply"] is False for row in graph["consolidation_review_queue"])
    assert all(row["human_gate_required"] is True for row in graph["consolidation_review_queue"])


def test_missing_inputs_fail_instead_of_empty_green(tmp_path: Path):
    hub = _hub(tmp_path)
    with pytest.raises(ValueError, match="inputs are incomplete"):
        build_graph(hub)


def test_historical_evaluation_replays_against_versioned_snapshot(tmp_path: Path):
    hub = _hub(tmp_path)
    current_path = hub / "registry/subagent-evaluation-methodology.json"
    current = json.loads(current_path.read_text(encoding="utf-8"))
    current["methodology_version"] = "0.2.0"
    updated = json.dumps(current, indent=2) + "\n"
    current_path.write_text(updated, encoding="utf-8")
    snapshot = hub / "registry/subagent-evaluation-methodologies/0.2.0.json"
    snapshot.write_text(updated, encoding="utf-8")
    packet = load_packet(PACKET)

    result = validate_records(
        hub, packet["role_profiles"], packet["attempts"], packet["evaluations"]
    )
    assert result["evaluations"]["dad:subagent-evaluation:logos-t475-banach"][
        "rubric_version"
    ] == "0.1.0"


def test_unrated_inventory_rejects_private_or_unstructured_payload(tmp_path: Path):
    hub = _hub(tmp_path)
    packet = _copy_packet(tmp_path)
    unrated_path = packet / "unrated-inventory.jsonl"
    row = json.loads(unrated_path.read_text(encoding="utf-8"))
    row["source"] = "C:/Users/example/private/attempts.jsonl"
    _write_jsonl(unrated_path, [row])

    with pytest.raises(ValueError):
        ingest_packet(hub, packet)


@pytest.mark.parametrize(
    "private_value",
    [
        "synthetic credential sk-abcdefghijklmnopqrstuvwxyz123456",
        "review artifact at C:/private/report.json",
        "review artifact at /workspace/private/report.json",
    ],
)
def test_attempt_payload_rejects_secret_values_and_absolute_paths(
    tmp_path: Path, private_value: str
):
    hub = _hub(tmp_path)
    packet = _copy_packet(tmp_path)
    attempts_path = packet / "execution-attempts.jsonl"
    attempts = [json.loads(line) for line in attempts_path.read_text().splitlines()]
    attempts[0]["task_summary"] = private_value
    _write_jsonl(attempts_path, attempts)

    with pytest.raises(ValueError):
        ingest_packet(hub, packet)


def test_agents_graph_prefix_and_methodology_freshness(tmp_path: Path):
    hub = _hub(tmp_path)
    ingest_packet(hub, PACKET)
    build_graph(hub)
    assert resolve_graph_surface_path(hub, "agents/subagent-capability-graph.json") == (
        hub / "processed/agents/subagent-capability-graph.json"
    )
    surface = {
        "builder": {"module": "digital_asset_directory.subagent_evaluations.build_graph"},
        "outputs": {
            "manifest_logical_path": "agents/subagent-capability-graph-manifest.json",
            "body_logical_path": "agents/subagent-capability-graph.json",
        },
    }
    assert graph_surface_freshness(hub, surface)["state"] == "fresh"
    capability_path = hub / "registry/subagent-capability-registry.json"
    capability_path.write_text(capability_path.read_text() + " ", encoding="utf-8")
    freshness = graph_surface_freshness(hub, surface)
    assert freshness["state"] == "stale"
    assert any(reason.startswith("methodology_hash_changed:") for reason in freshness["reasons"])
