from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from jsonschema.validators import validator_for
import pytest
import yaml

from digital_asset_directory.agent_families import agent_family_health, build_portfolio_cockpit_v2
import digital_asset_directory.technical_product_os as product_os


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate(schema_relative: str, payload: dict) -> None:
    schema = load_json(schema_relative)
    cls = validator_for(schema)
    cls.check_schema(schema)
    cls(schema, format_checker=cls.FORMAT_CHECKER).validate(payload)


@pytest.fixture
def isolated_ledgers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    route = tmp_path / "routing.jsonl"
    run = tmp_path / "runs.jsonl"
    monkeypatch.setattr(product_os, "_route_ledger", lambda _: route)
    monkeypatch.setattr(product_os, "_run_ledger", lambda _: run)
    return route, run


def test_registry_schemas_and_exact_top_ten_are_valid() -> None:
    schemas = load_json("registry/schema-registry.json")["schemas"]
    expected = {
        "technical_product_company_os_registry": "schemas/technical-product-company-os-registry.schema.json",
        "project_position_diagnosis": "schemas/project-position-diagnosis.schema.json",
        "capability_routing_receipt": "schemas/capability-routing-receipt.schema.json",
        "workflow_run_event": "schemas/workflow-run-event.schema.json",
        "capability_portfolio_snapshot": "schemas/capability-portfolio-snapshot.schema.json",
    }
    assert all(schemas[key] == value for key, value in expected.items())
    registry = load_json("registry/technical-product-company-os-registry.json")
    validate(expected["technical_product_company_os_registry"], registry)
    assert [row["coverage_rank"] for row in registry["capabilities"]] == list(range(1, 11))
    assert registry["ai_agnostic"] is True


def test_platform_is_family_and_three_adjacent_domains_are_packs() -> None:
    portfolio = load_json("registry/agent-family-portfolio-registry.json")
    family_ids = {row["family_id"] for row in portfolio["families"]}
    assert "family:platform-cloud-sre" in family_ids
    assert "pack:observability-incident-resilience" not in family_ids
    assert "pack:developer-platform-devex" not in family_ids
    assert "pack:product-intelligence-experimentation" not in family_ids
    assert len(portfolio["families"]) == 12


def test_all_new_skill_packs_validate_and_stay_model_neutral() -> None:
    names = [
        "technical-product-company-os",
        "platform-cloud-sre-agent-family",
        "observability-resilience-specialist-pack",
        "developer-platform-devex-specialist-pack",
        "product-intelligence-experimentation-pack",
        "mcp-integration-specialist-pack",
        "ui-ux-specialist-pack",
    ]
    skill_ids = {row["skill_id"] for row in load_json("registry/agent-skill-library.json")["skills"]}
    for name in names:
        base = ROOT / "assets" / "agent-skills" / name
        pack = yaml.safe_load((base / "subagents.yaml").read_text(encoding="utf-8"))
        validate("schemas/subagent-pack.schema.json", pack)
        assert pack["ai_agnostic"] is True
        assert f"skill:{name}" in skill_ids
        lowered = json.dumps(pack).lower()
        assert all(term not in lowered for term in ("gpt-", "claude-", "gemini-"))


def test_project_position_diagnosis_is_candidate_only_and_right_sized() -> None:
    diagnosis = {
        "schema_version": "dad.project_position_diagnosis.v1",
        "diagnosis_id": "diagnosis:fixture",
        "as_of": "2026-07-15T12:00:00Z",
        "candidate_only": True,
        "coverage": {
            "source_refs": ["repo:fixture"],
            "input_fingerprint": f"sha256:{'a' * 64}",
            "unavailable_sources": [],
            "gaps": [],
        },
        "project_identity": {"project_id": "project:fixture", "authority_ref": "owner:human", "owner": "human-owner"},
        "current_state": "active",
        "observed_position": {
            "evidence_stage": "implementation-underway",
            "working_surfaces": ["bounded core"],
            "broken_surfaces": [],
            "incomplete_surfaces": ["named integration"],
            "evidence_refs": ["test:fixture"],
        },
        "issue_codes": ["integration-contract-missing"],
        "destination": {
            "confirmation_status": "human_confirmed",
            "human_decision_ref": "decision:fixture-destination-v1",
            "confirmation_recorded_at": "2026-07-15T11:55:00Z",
            "purpose": "Connect the bounded core to the named target.",
            "end_state_class": "integration",
            "completion_depth": "integrate-with-target",
            "integration_targets": ["system:target"],
            "acceptance_evidence": ["contract and failure tests"],
            "non_goals": ["full product release"],
            "sufficient_stop": "The named target passes contract and rollback checks.",
        },
        "routing": {
            "selected_capabilities": ["capability:integration-api-mcp-automation"],
            "prerequisites": [],
            "validators": ["family:quality-verification-release"],
            "suppressed_capabilities": ["capability:product-ux-accessibility"],
            "mcp_first_assessment": {
                "applicable": True,
                "reason": "A cross-runtime integration is required.",
                "preferred_interface": "resource",
                "direct_api_fallback_status": "not-needed",
            },
        },
        "human_decisions": [],
        "smallest_reversible_next_action": "Draft the read-only resource contract.",
        "producer_ref": "role:technical-product-project-position-diagnostician",
        "independent_validation_ref": "evaluation:fixture-position-v1",
        "execution_handoff_status": "candidate-ready-for-human-approval",
        "execution_authorized": False,
        "authority_boundary": "Diagnosis and route are candidates; existing execution gates still apply.",
    }
    validate("schemas/project-position-diagnosis.schema.json", diagnosis)
    assert len(diagnosis["routing"]["selected_capabilities"]) <= 3
    assert diagnosis["execution_authorized"] is False


def test_project_position_workflow_does_not_expand_to_full_delivery() -> None:
    route = product_os.route_capabilities(ROOT, "where is this project and what remains")
    assert route["selected_capabilities"] == []
    matches = {row["workflow_id"] for row in route["workflow_matches"]}
    assert "workflow:project-position-to-right-sized-completion" in matches
    assert "workflow:software-product-delivery" not in matches
    registry = load_json("registry/technical-product-company-os-registry.json")
    workflow = next(row for row in registry["workflows"] if row["workflow_id"] == "workflow:project-position-to-right-sized-completion")
    assert workflow["capability_sequence"] == ["capability:technical-product-architecture"]
    assert len(workflow["required_human_gates"]) == 3


def test_project_position_role_and_specialist_packs_are_bounded() -> None:
    product_pack = yaml.safe_load((ROOT / "assets/agent-skills/technical-product-company-os/subagents.yaml").read_text(encoding="utf-8"))
    assert "technical-product-project-position-diagnostician" in {row["role_id"] for row in product_pack["roles"]}
    for name, parent in (
        ("mcp-integration-specialist-pack", "family:integration-mcp-automation"),
        ("ui-ux-specialist-pack", "family:product-ux-accessibility"),
    ):
        pack = yaml.safe_load((ROOT / f"assets/agent-skills/{name}/subagents.yaml").read_text(encoding="utf-8"))
        assert pack["routing_policy"]["parent_family"] == parent
        assert pack["routing_policy"]["maximum_primary_roles"] == 3
        assert pack["routing_policy"]["whole_pack_activation"] == "prohibited"


def test_specialist_role_selector_requires_evidence_and_enforces_smallest_set() -> None:
    blocked = product_os.select_specialist_roles(
        ROOT,
        "pack:mcp-integration-specialist-pack",
        "repository uses MCP dependencies",
    )
    assert blocked["selected_role_ids"] == []
    assert blocked["rejection_reason_codes"] == ["activation_evidence_required"]
    selected = product_os.select_specialist_roles(
        ROOT,
        "pack:mcp-integration-specialist-pack",
        "choose MCP or API and design a read only MCP resource for the named target",
        activation_evidence=["target:approved-read-context", "gap:cross-runtime-context"],
    )
    assert 1 <= len(selected["selected_role_ids"]) <= 3
    assert "mcp-fit-boundary-diagnostician" in selected["selected_role_ids"]
    assert "mcp-resource-context-specialist" in selected["selected_role_ids"]
    assert selected["whole_pack_activation"] is False
    assert len(selected["selected_role_ids"]) < len(selected["considered"])


def test_incidental_mcp_context_does_not_activate_integration_capability() -> None:
    for query in ("repository uses MCP dependencies", "fix one test in an MCP server"):
        route = product_os.route_capabilities(ROOT, query)
        assert "capability:integration-api-mcp-automation" not in route["selected_capabilities"]
        integration = next(
            row for row in route["considered"]
            if row["capability_id"] == "capability:integration-api-mcp-automation"
        )
        assert "incidental_context_suppressed" in integration["reason_codes"]


def test_human_confirmed_handoff_requires_attestation_and_checker() -> None:
    schema = load_json("schemas/project-position-diagnosis.schema.json")
    cls = validator_for(schema)
    invalid = {
        "schema_version": "dad.project_position_diagnosis.v1",
        "diagnosis_id": "diagnosis:invalid",
        "as_of": "2026-07-15T12:00:00Z",
        "candidate_only": True,
        "coverage": {"source_refs": ["repo:x"], "input_fingerprint": f"sha256:{'b' * 64}", "unavailable_sources": [], "gaps": []},
        "project_identity": {"project_id": "project:x", "authority_ref": "owner:x", "owner": "human"},
        "current_state": "active",
        "observed_position": {"evidence_stage": "implementation-underway", "working_surfaces": [], "broken_surfaces": [], "incomplete_surfaces": [], "evidence_refs": []},
        "issue_codes": ["none-observed"],
        "destination": {"confirmation_status": "human_confirmed", "human_decision_ref": "", "confirmation_recorded_at": "", "purpose": "ship", "end_state_class": "major-product", "completion_depth": "productionize-approved-scope", "integration_targets": [], "acceptance_evidence": [], "non_goals": [], "sufficient_stop": "done"},
        "routing": {"selected_capabilities": [], "prerequisites": [], "validators": [], "suppressed_capabilities": [], "mcp_first_assessment": {"applicable": False, "reason": "none", "preferred_interface": "not-applicable", "direct_api_fallback_status": "not-needed"}},
        "human_decisions": [],
        "smallest_reversible_next_action": "wait",
        "producer_ref": "role:producer",
        "independent_validation_ref": "",
        "execution_handoff_status": "candidate-ready-for-human-approval",
        "execution_authorized": False,
        "authority_boundary": "candidate only",
    }
    errors = list(cls(schema, format_checker=cls.FORMAT_CHECKER).iter_errors(invalid))
    assert errors
    assert {tuple(error.path) for error in errors} >= {
        ("destination", "human_decision_ref"),
        ("destination", "acceptance_evidence"),
        ("destination", "non_goals"),
        ("independent_validation_ref",),
    }


def test_catalog_is_fingerprinted_and_graph_refs_resolve() -> None:
    first = product_os.build_capability_index(ROOT)
    second = product_os.build_capability_index(ROOT)
    assert first["catalog_fingerprint"] == second["catalog_fingerprint"]
    node_ids = {row["node_id"] for row in first["nodes"]}
    for edge in first["edges"]:
        assert edge["source"] in node_ids
        assert edge["target"] in node_ids


def test_router_returns_smallest_bounded_set_and_required_support() -> None:
    platform = product_os.route_capabilities(ROOT, "cloud platform SRE disaster recovery")
    assert platform["selected_capabilities"][0] == "capability:platform-cloud-sre"
    assert len(platform["selected_capabilities"]) <= 3
    assert "family:quality-verification-release" in platform["required_validators"]
    experiment = product_os.route_capabilities(ROOT, "run experiment hypothesis metric")
    assert "capability:product-intelligence-experimentation" in experiment["selected_capabilities"]
    assert experiment["workflow_matches"][0]["workflow_id"] == "workflow:product-experiment"


def test_governance_blocks_self_granted_execution_unknown_privacy_and_c4() -> None:
    route = product_os.route_capabilities(ROOT, "deploy production", requested_right="execute", consequence_tier="C3")
    assert route["status"] == "blocked_candidate"
    assert route["execution_authorized"] is False
    unknown = product_os.evaluate_decision_right(
        ROOT, requested_right="draft", consequence_tier="C1", privacy_class="unknown"
    )
    assert unknown["allowed"] is False
    prohibited = product_os.evaluate_decision_right(
        ROOT,
        requested_right="execute",
        consequence_tier="C4",
        privacy_class="public",
        human_gate_verified=True,
        checker_gate_verified=True,
        domain_gate_verified=True,
        lease_verified=True,
        final_confirmation_verified=True,
        rollback_present=True,
    )
    assert prohibited["allowed"] is False
    assert "prohibited_action" in prohibited["reason_codes"]


def _receipt(query: str = "production ready platform cloud") -> dict:
    route = product_os.route_capabilities(ROOT, query)
    return product_os.build_routing_receipt(
        route,
        opaque_task_id="task-1",
        request_class="technical_product",
        request_tags=["platform"],
        repository_id="repo:synthetic",
    )


def test_privacy_guard_rejects_raw_prompts_paths_and_secrets(isolated_ledgers: tuple[Path, Path]) -> None:
    receipt = _receipt()
    receipt["raw_prompt"] = "secret"
    with pytest.raises(ValueError, match="Privacy-unsafe telemetry field"):
        product_os.append_routing_receipt(ROOT, receipt)


def test_route_retries_are_deduplicated_and_do_not_inflate_usage(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    first = _receipt()
    second = _receipt()
    assert product_os.append_routing_receipt(ROOT, first)["appended"] is True
    duplicate = product_os.append_routing_receipt(ROOT, second)
    assert duplicate == {**duplicate, "appended": False, "reason": "duplicate_semantic_route_retry"}
    snapshot = product_os.build_capability_portfolio_snapshot(ROOT)
    platform = next(row for row in snapshot["capabilities"] if row["entity_id"] == "capability:platform-cloud-sre")
    assert platform["selected_count"] == 1
    assert platform["executed_count"] == 0


def _run_event(
    state: str,
    *,
    run_id: str,
    route_id: str,
    synthetic: bool = False,
    when: datetime | None = None,
) -> dict:
    return product_os.build_workflow_run_event(
        workflow_id="workflow:production-readiness",
        workflow_revision_id="workflow-revision:production-readiness:v1",
        run_id=run_id,
        route_event_id=route_id,
        event_state=state,
        capability_ids=["capability:platform-cloud-sre"],
        input_fingerprint=f"sha256:{'1' * 64}",
        output_fingerprint=f"sha256:{'2' * 64}" if state != "started" else "",
        execution_mode="deterministic",
        producer_ref="producer:workflow-worker",
        synthetic_or_fixture=synthetic,
        independent_checker_ref="checker:independent" if state == "independently_validated" else "",
        independent_evaluation_ref="evaluation:1" if state == "independently_validated" else "",
        validation_outcome="supported_success" if state == "independently_validated" else "",
        now=when,
    )


def test_execution_completion_and_independent_validation_are_distinct(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    receipt = _receipt()
    product_os.append_routing_receipt(ROOT, receipt)
    start = datetime(2026, 7, 14, tzinfo=timezone.utc)
    for offset, state in enumerate(("started", "completed", "independently_validated")):
        event = _run_event(state, run_id="run-1", route_id=receipt["id"], when=start + timedelta(seconds=offset))
        assert product_os.append_workflow_run_event(ROOT, event)["appended"] is True
    snapshot = product_os.build_capability_portfolio_snapshot(ROOT)
    usage = next(row for row in snapshot["capabilities"] if row["entity_id"] == "capability:platform-cloud-sre")
    assert (usage["selected_count"], usage["executed_count"], usage["completed_count"], usage["independently_validated_count"]) == (1, 1, 1, 1)
    assert usage["supported_success_count"] == 1


def test_validation_event_requires_independent_evidence(isolated_ledgers: tuple[Path, Path]) -> None:
    receipt = _receipt()
    product_os.append_routing_receipt(ROOT, receipt)
    product_os.append_workflow_run_event(ROOT, _run_event("started", run_id="run-bad", route_id=receipt["id"]))
    product_os.append_workflow_run_event(ROOT, _run_event("completed", run_id="run-bad", route_id=receipt["id"]))
    event = _run_event("independently_validated", run_id="run-bad", route_id=receipt["id"])
    event.pop("independent_evaluation_ref")
    with pytest.raises(ValueError, match="checker and evaluation"):
        product_os.append_workflow_run_event(ROOT, event)


def test_material_workflow_run_requires_complete_control_plane_bindings() -> None:
    common = {
        "workflow_id": "workflow:production-readiness",
        "workflow_revision_id": "workflow-revision:production-readiness:v1",
        "run_id": "material-run",
        "route_event_id": "route-event:material",
        "event_state": "started",
        "capability_ids": ["capability:platform-cloud-sre"],
        "input_fingerprint": f"sha256:{'3' * 64}",
        "execution_mode": "deterministic",
        "producer_ref": "producer:workflow-worker",
        "material_execution": True,
    }
    with pytest.raises(ValueError, match="control-plane bindings"):
        product_os.build_workflow_run_event(**common)

    event = product_os.build_workflow_run_event(
        **common,
        plan_id="plan:production-readiness",
        plan_revision_id="plan-revision:production-readiness:v1",
        entity_id="entity:production-readiness",
        entity_revision_id="entity-revision:production-readiness:v1",
        family_id="family:quality-verification-release",
        role_id="role:independent-checker",
        attempt_id="attempt:material-run:1",
        runtime_route_decision_id="runtime-route:material-run:1",
        harness_revision_id="harness-revision:release-gate:v1",
        lease_id="lease:material-run:1",
        effect_class="a2_bounded_reversible",
        tool_time_ms=12,
        evidence_refs=["evidence:material-run"],
        validation_refs=["validation:pending"],
        dependency_refs=["dependency:release-gate"],
    )
    assert event["plan_revision_id"] == "plan-revision:production-readiness:v1"
    assert event["harness_revision_id"] == "harness-revision:release-gate:v1"
    assert event["material_execution"] is True


def test_synthetic_runs_are_excluded_and_unknown_cost_is_not_zero(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    receipt = product_os.build_routing_receipt(
        product_os.route_capabilities(ROOT, "production ready platform cloud"),
        opaque_task_id="fixture-task",
        request_class="technical_product",
        request_tags=["fixture"],
        repository_id="repo:synthetic",
        synthetic_or_fixture=True,
    )
    product_os.append_routing_receipt(ROOT, receipt)
    event = _run_event("started", run_id="fixture", route_id=receipt["id"], synthetic=True)
    product_os.append_workflow_run_event(ROOT, event)
    snapshot = product_os.build_capability_portfolio_snapshot(ROOT)
    assert snapshot["summary"]["operational_run_count"] == 0
    assert snapshot["efficiency"]["unknown_token_event_count"] == 0
    assert snapshot["efficiency"]["known_cost_total"] == 0.0


def test_never_used_means_unobserved_and_quiet_mode_has_no_now_decisions(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    snapshot = product_os.build_capability_portfolio_snapshot(ROOT, quiet_mode=True)
    assert all(row["observation_status"] == "unobserved" for row in snapshot["capabilities"])
    assert snapshot["operator"]["now"] == []
    assert snapshot["operator"]["immediate_decision_count"] == 0


def test_cursor_offload_is_denied_until_adapter_is_authorized() -> None:
    result = product_os.classify_offload(
        ROOT,
        task_class="mechanical_refactor",
        mechanical_task=True,
        closed_allowed_paths=True,
        stable_authority_and_interfaces=True,
        deterministic_validation=True,
        isolated_worktree=True,
        reversible_diff=True,
        explicit_lease=True,
        independent_checker=True,
        sanitized_minimal_packet=True,
    )
    assert result["eligible"] is False
    assert "adapter_not_authorized" in result["reason_codes"]
    prohibited = product_os.classify_offload(
        ROOT,
        task_class="secrets",
        mechanical_task=True,
        closed_allowed_paths=True,
        stable_authority_and_interfaces=True,
        deterministic_validation=True,
        isolated_worktree=True,
        reversible_diff=True,
        explicit_lease=True,
        independent_checker=True,
        sanitized_minimal_packet=True,
        prohibited_classes=["secrets"],
    )
    assert prohibited["eligible"] is False
    assert any(reason.startswith("prohibited_") for reason in prohibited["reason_codes"])


def test_capability_digest_feeds_existing_cockpit_and_remains_bounded(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    snapshot = product_os.build_capability_portfolio_snapshot(ROOT)
    cockpit = build_portfolio_cockpit_v2(agent_family_health(ROOT), None, snapshot)
    validate("schemas/portfolio-cockpit-v2.schema.json", cockpit)
    assert "capability_os" in cockpit["sources"]
    assert len(cockpit["now"]) <= 3


def test_negative_intent_environment_tools_and_lifecycle_suppress_routes() -> None:
    negative = product_os.route_capabilities(ROOT, "do not use cloud or platform")
    assert "capability:platform-cloud-sre" not in negative["selected_capabilities"]
    platform_row = next(
        row for row in negative["considered"] if row["capability_id"] == "capability:platform-cloud-sre"
    )
    assert "negative_intent_suppressed" in platform_row["reason_codes"]

    lifecycle = product_os.route_capabilities(
        ROOT,
        "cloud platform",
        lifecycle_states={"capability:platform-cloud-sre": "superseded"},
    )
    assert lifecycle["selected_capabilities"] == []
    constrained = product_os.route_capabilities(
        ROOT,
        "cloud platform",
        environment_eligible_capability_ids=["capability:technical-product-architecture"],
        tool_eligible_capability_ids=["capability:platform-cloud-sre"],
    )
    assert constrained["selected_capabilities"] == []


def test_negative_workflow_intent_is_reported_but_not_activated() -> None:
    route = product_os.route_capabilities(ROOT, "do not run experiment")
    assert route["workflow_matches"] == []
    assert route["suppressed_workflow_matches"][0]["workflow_id"] == "workflow:product-experiment"
    assert "negative_workflow_intent_suppressed" in route["suppressed_workflow_matches"][0]["reason_codes"]
    assert product_os.route_capabilities(ROOT, "production incident")["workflow_matches"] == []


def test_decision_rights_require_actor_tier_named_gates_and_trusted_executor() -> None:
    execute_c0 = product_os.evaluate_decision_right(
        ROOT,
        requested_right="execute",
        consequence_tier="C0",
        privacy_class="public",
        actor_class="leased_executor",
        actor_id="executor:one",
    )
    assert execute_c0["allowed"] is False
    assert "decision_right_tier_mismatch" in execute_c0["reason_codes"]

    validate_self = product_os.evaluate_decision_right(
        ROOT,
        requested_right="validate",
        consequence_tier="C1",
        privacy_class="internal_metadata",
        actor_class="checker",
        actor_id="agent:same",
        producer_id="agent:same",
        checker_id="agent:same",
        verified_gates=["producer_checker_separation", "raw_evidence"],
        human_gate_verified=True,
        checker_gate_verified=True,
        lease_verified=True,
        rollback_present=True,
    )
    assert validate_self["allowed"] is False
    assert "producer_checker_separation_failed" in validate_self["reason_codes"]

    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    execute_declared = product_os.evaluate_decision_right(
        ROOT,
        requested_right="execute",
        consequence_tier="C3",
        privacy_class="public",
        actor_class="leased_executor",
        actor_id="executor:one",
        action_digest=f"sha256:{'a' * 64}",
        lease_ref="lease:one",
        lease_expires_at=future,
        human_approval_ref="approval:one",
        checker_evaluation_ref="evaluation:one",
        verified_gates=["action_digest", "scope_match"],
        human_gate_verified=True,
        checker_gate_verified=True,
        domain_gate_verified=True,
        lease_verified=True,
        final_confirmation_verified=True,
        rollback_present=True,
    )
    assert execute_declared["policy_eligible"] is True
    assert execute_declared["allowed"] is False
    assert execute_declared["execution_authorized"] is False
    assert execute_declared["reason_codes"] == ["trusted_execution_verifier_unavailable"]


def test_receipt_is_revision_aware_and_secret_looking_values_are_rejected(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    receipt = _receipt()
    assert receipt["catalog_fingerprint"].startswith("sha256:")
    assert receipt["capability_descriptor_revision"] == "0.2.0"
    assert receipt["selected_workflow_revisions"] == ["workflow-revision:production-readiness:v1"]
    receipt["request_tags"] = ["sk-proj-abcdef123456789"]
    with pytest.raises(ValueError, match="Secret-looking telemetry"):
        product_os.append_routing_receipt(ROOT, receipt)


def test_orphan_run_and_self_validation_are_rejected(isolated_ledgers: tuple[Path, Path]) -> None:
    orphan = _run_event("started", run_id="orphan", route_id="route-event:missing")
    with pytest.raises(ValueError, match="existing routing receipt"):
        product_os.append_workflow_run_event(ROOT, orphan)

    receipt = _receipt()
    product_os.append_routing_receipt(ROOT, receipt)
    product_os.append_workflow_run_event(ROOT, _run_event("started", run_id="self-check", route_id=receipt["id"]))
    product_os.append_workflow_run_event(ROOT, _run_event("completed", run_id="self-check", route_id=receipt["id"]))
    event = _run_event("independently_validated", run_id="self-check", route_id=receipt["id"])
    event["independent_checker_ref"] = event["producer_ref"]
    with pytest.raises(ValueError, match="distinct from the producer"):
        product_os.append_workflow_run_event(ROOT, event)


def test_corrections_require_existing_effective_same_scope_targets(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    start = datetime(2026, 7, 14, tzinfo=timezone.utc)
    route = product_os.route_capabilities(ROOT, "production ready platform cloud")
    original = product_os.build_routing_receipt(
        route,
        opaque_task_id="task:correction",
        request_class="platform-readiness",
        request_tags=["platform"],
        repository_id="repo:pilot",
        now=start,
    )
    product_os.append_routing_receipt(ROOT, original)
    missing = product_os.build_routing_receipt(
        route,
        opaque_task_id="task:correction",
        request_class="platform-readiness",
        request_tags=["platform"],
        repository_id="repo:pilot",
        event_type="dad.capability.route.corrected.v1",
        corrects_event_id="route-event:does-not-exist",
        override_reason_codes=["incorrect_selection"],
        now=start + timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="exist and remain effective"):
        product_os.append_routing_receipt(ROOT, missing)

    correction = product_os.build_routing_receipt(
        route,
        opaque_task_id="task:correction",
        request_class="platform-readiness",
        request_tags=["platform"],
        repository_id="repo:pilot",
        event_type="dad.capability.route.corrected.v1",
        corrects_event_id=original["id"],
        override_reason_codes=["incorrect_selection"],
        now=start + timedelta(seconds=2),
    )
    assert product_os.append_routing_receipt(ROOT, correction)["appended"] is True
    with pytest.raises(ValueError, match="exist and remain effective"):
        product_os.append_routing_receipt(
            ROOT,
            {
                **missing,
                "id": "route-event:second-correction",
                "corrects_event_id": original["id"],
                "time": (start + timedelta(seconds=3)).isoformat(),
            },
        )

    run = _run_event("corrected", run_id="correction-run", route_id=correction["id"])
    run["corrects_event_id"] = "run-event:does-not-exist"
    with pytest.raises(ValueError, match="exist and remain effective"):
        product_os.append_workflow_run_event(ROOT, run)


def test_workflow_revision_usage_last_used_unknown_and_operational_graph(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    receipt = _receipt()
    product_os.append_routing_receipt(ROOT, receipt)
    start = datetime(2026, 7, 14, tzinfo=timezone.utc)
    for offset, state in enumerate(("started", "completed", "independently_validated")):
        event = _run_event(state, run_id="run-graph", route_id=receipt["id"], when=start + timedelta(seconds=offset))
        if state == "independently_validated":
            event["validation_outcome"] = "unknown"
        product_os.append_workflow_run_event(ROOT, event)
    snapshot = product_os.build_capability_portfolio_snapshot(ROOT)
    workflow = next(
        row
        for row in snapshot["workflows"]
        if row["entity_id"] == "workflow-revision:production-readiness:v1"
    )
    assert workflow["selected_count"] == 1
    assert workflow["executed_count"] == 1
    assert workflow["supported_unknown_count"] == 1
    assert workflow["last_used_at"] == start.isoformat()
    graph = product_os.build_operational_capability_graph(ROOT, snapshot=snapshot, now=start)
    validate("schemas/capability-operational-graph.schema.json", graph)
    node_types = {row["node_type"] for row in graph["nodes"]}
    assert {"route_trace", "workflow_run", "project", "repository", "evidence", "validator", "policy"} <= node_types
    node_ids = {row["node_id"] for row in graph["nodes"]}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])


def test_routines_are_dormant_delta_only_zero_model_and_human_gated(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    dormant = product_os.evaluate_routines(ROOT)
    assert len(dormant) == 4
    assert {row["evaluation_status"] for row in dormant} == {"dormant"}
    assert all(row["model_tokens"] == 0 and row["model_call_count"] == 0 for row in dormant)
    previous = {row["routine_id"]: row["input_fingerprint"] for row in dormant}
    unchanged = product_os.evaluate_routines(
        ROOT,
        activated_routine_ids=previous,
        previous_fingerprints=previous,
    )
    assert {row["evaluation_status"] for row in unchanged} == {"unchanged_heartbeat"}
    changed_previous = dict(previous)
    changed_previous["capability-catalog-delta"] = f"sha256:{'0' * 64}"
    changed = product_os.evaluate_routines(
        ROOT,
        activated_routine_ids=["capability-catalog-delta"],
        previous_fingerprints=changed_previous,
    )
    due = next(row for row in changed if row["routine_id"] == "capability-catalog-delta")
    assert due["evaluation_status"] == "candidate_due"
    assert due["human_decision_required"] is True
    assert due["notification_authorized"] is False
    assert due["external_mutation_authorized"] is False


def test_catalog_enumeration_does_not_manufacture_gap_candidates(
    isolated_ledgers: tuple[Path, Path],
) -> None:
    for offset in range(3):
        route = product_os.route_capabilities(ROOT, "production ready platform cloud")
        receipt = product_os.build_routing_receipt(
            route,
            opaque_task_id=f"task:narrow-{offset}",
            request_class="platform-readiness",
            request_tags=["platform"],
            repository_id="repo:pilot",
            now=datetime(2026, 7, 14, tzinfo=timezone.utc) + timedelta(seconds=offset),
        )
        product_os.append_routing_receipt(ROOT, receipt)

    snapshot = product_os.build_capability_portfolio_snapshot(ROOT)
    usage = {row["entity_id"]: row for row in snapshot["capabilities"]}
    matched = {
        row["capability_id"]
        for row in product_os.route_capabilities(
            ROOT, "production ready platform cloud"
        )["considered"]
        if "query_match" in row["reason_codes"] and row["eligible"]
    }
    assert matched
    assert all(
        usage[capability_id]["eligible_considered_count"] == 3
        for capability_id in matched
    )
    assert all(
        row["observation_status"] == "unobserved"
        and row["eligible_considered_count"] == 0
        for capability_id, row in usage.items()
        if capability_id not in matched
    )
    assert not {
        gap["affected_ids"][0]
        for gap in snapshot["gap_candidates"]
        if gap["gap_type"] == "repeated_eligible_not_selected"
    } - matched
