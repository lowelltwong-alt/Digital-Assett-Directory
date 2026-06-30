from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, cast

import typer
from rich.console import Console

from .archaeology import (
    append_repo_learning_event,
    install_repo_learning_loop,
    write_archaeology_outputs,
    write_root_cause_lesson_outputs,
)
from .asset_families import (
    write_asset_family_reports,
    write_learning_loop_outputs,
    write_workflow_sweep_reports,
)
from .background_connections import write_background_connection_outputs
from .calibration import (
    build_asset_calibration_review_queue,
    import_asset_calibration_review_csv,
    load_asset_calibration_reviews,
    load_catalog_assets,
    update_asset_calibration_review_file,
    write_asset_calibration_evidence,
    write_asset_calibration_summary,
    write_asset_calibration_review_csv,
    write_phase2_calibration_reports,
    write_phase25_score_delta_validation,
)
from .catalog import catalog_status, run_scan
from .ci_release_scope import write_ci_release_artifact_scope_outputs
from .config import load_config
from .context_pack import build_context_pack, write_context_pack
from .database import CatalogDB
from .governance import enforce_postflight, install_governance, scaffold_new_repo
from .governance_map_scope import write_governance_map_adoption_scope_outputs
from .learning import (
    add_asset_use_feedback,
    add_lesson,
    midflight,
    postflight,
    preflight,
    rebuild_lesson_routes,
)
from .lesson_automation_coverage import write_lesson_automation_coverage_outputs
from .manual_tasks import write_manual_task_queue
from .orphan_adapter import run_orphan_radar
from .operational import write_operational_readiness_report
from .priority_content_lessons import (
    build_priority_content_lesson_review_queue,
    load_priority_content_lesson_candidates,
    load_priority_content_lesson_reviews,
    summarize_priority_content_lesson_reviews,
    update_priority_content_lesson_review_file,
    write_learning_rule_promotion_candidate_outputs,
    write_priority_content_lesson_outputs,
    write_priority_content_lesson_review_template_outputs,
)
from .priority_content_scope import (
    write_priority_content_extract_outputs,
    write_priority_content_extract_scope_outputs,
)
from .proposals import (
    ProposalEngineOption,
    build_proposal_review_queue,
    import_proposal_review_csv,
    load_roadmap_relevance_context,
    load_generated_proposals,
    load_proposal_reviews,
    run_proposal_engines,
    update_proposal_review_file,
    write_proposal_review_csv,
    write_proposal_review_unblind_map,
    write_proposal_calibration_evidence,
    write_proposal_outputs,
    write_proposal_review_results_summary,
)
from .public_safe_sweep import write_public_safe_source_sweep
from .recommendations import recommend_skills_and_agents, recommend_swarm
from .readiness import write_downstream_pilot_candidates, write_phase45_readiness_reports
from .research import research_missing_parts
from .repo_buildout import load_default_repo_buildout_artifacts, write_repo_buildout_outputs
from .repo_learning_scope import write_repo_learning_loop_install_scope_outputs
from .roadmap import check_roadmap
from .semantic_evolution import write_semantic_evolution_outputs
from .template_library import validate_template_registry, write_template_library_report
from .validation import validate_repo
from .workflow_parts import (
    build_workflow_part_review_queue,
    load_workflow_part_reviews,
    load_workflow_parts,
    update_workflow_part_review_file,
    write_workflow_part_calibration_evidence,
    write_workflow_part_outputs,
    write_workflow_part_review_results_summary,
    write_workflow_part_review_template_outputs,
    write_workflow_part_usage_guidance,
)

app = typer.Typer(no_args_is_help=True, help="Digital Asset Directory portfolio intelligence CLI.")
lesson_app = typer.Typer(no_args_is_help=True)
app.add_typer(lesson_app, name="lesson")
agent_app = typer.Typer(no_args_is_help=True)
app.add_typer(agent_app, name="agent")
roadmap_app = typer.Typer(no_args_is_help=True)
app.add_typer(roadmap_app, name="roadmap")
research_app = typer.Typer(no_args_is_help=True)
app.add_typer(research_app, name="research")
template_app = typer.Typer(no_args_is_help=True)
app.add_typer(template_app, name="templates")
orphan_app = typer.Typer(no_args_is_help=True)
app.add_typer(orphan_app, name="orphan-radar")
recommend_app = typer.Typer(no_args_is_help=True)
app.add_typer(recommend_app, name="recommend")
console = Console()


def _cfg(config: Optional[Path] = None, hub: Optional[Path] = None):
    return load_config(config, repo_root=hub)


@app.command()
def scan(
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    local_only: bool = False,
    github_only: bool = False,
    max_files: Optional[int] = typer.Option(None, min=1),
) -> None:
    """Run a read-only inventory and regenerate catalog, graph, radar, and alert outputs."""
    cfg = _cfg(config, hub)
    summary = run_scan(cfg, local=not github_only, github=not local_only, max_files=max_files)
    console.print_json(data=summary)


@app.command()
def status(
    config: Optional[Path] = typer.Option(None), hub: Optional[Path] = typer.Option(None)
) -> None:
    console.print_json(data=catalog_status(_cfg(config, hub)))


@app.command()
def doctor(config: Optional[Path] = typer.Option(None), hub: Optional[Path] = typer.Option(None)) -> None:
    """Check whether the local DAD hub is operational without rescanning or mutating sources."""
    result = write_operational_readiness_report(_cfg(config, hub))
    console.print_json(data=result)
    if not result["ready"]:
        raise typer.Exit(2)


@template_app.command("check")
def templates_check(hub: Optional[Path] = typer.Option(None)) -> None:
    """Validate the tracked template registry and write the generated dependency report."""
    cfg = _cfg(hub=hub)
    result = write_template_library_report(cfg.repo_root)
    console.print_json(data=result)
    if not result["valid"]:
        raise typer.Exit(2)


@template_app.command("validate")
def templates_validate(hub: Optional[Path] = typer.Option(None)) -> None:
    """Validate template records without writing reports."""
    cfg = _cfg(hub=hub)
    result = validate_template_registry(cfg.repo_root)
    console.print_json(data=result)
    if not result["valid"]:
        raise typer.Exit(2)


@app.command()
def context(
    query: str,
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(20, min=1, max=100),
) -> None:
    cfg = _cfg(config, hub)
    with CatalogDB(cfg.database_path) as db:
        pack = build_context_pack(query, db.assets(), db.edges(), db.alerts(open_only=True), limit)
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:80] or "context"
    paths = write_context_pack(cfg.repo_root, pack, slug)
    console.print(f"Wrote {paths[0]} and {paths[1]}")


@app.command()
def idea(
    query: str,
    config: Optional[Path] = typer.Option(None),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(20, min=1, max=100),
) -> None:
    """Create an AI-ready context pack for an idea or build problem."""
    context(query, config, hub, limit)


@app.command(name="validate")
def validate_command(hub: Optional[Path] = typer.Option(None)) -> None:
    cfg = _cfg(hub=hub)
    result = validate_repo(cfg.repo_root)
    console.print_json(data=result)
    if not result["valid"]:
        raise typer.Exit(1)


@roadmap_app.command("check")
def roadmap_check(hub: Optional[Path] = typer.Option(None), no_update: bool = False) -> None:
    cfg = _cfg(hub=hub)
    result = check_roadmap(cfg.repo_root, update=not no_update)
    console.print_json(data=result)


@lesson_app.command("add")
def lesson_add(
    repository: Path = typer.Option(Path("."), "--repo"),
    summary: str = typer.Option(...),
    task: str = "",
    agent: str = "human",
    model: Optional[str] = None,
    lesson: list[str] = typer.Option([], "--lesson"),
    files_changed: list[str] = typer.Option([], "--file"),
    tests_run: list[str] = typer.Option([], "--test"),
    tests_not_run: list[str] = typer.Option([], "--test-not-run"),
    discovery: list[str] = typer.Option([], "--discovery"),
    failure: list[str] = typer.Option([], "--failure"),
    reusable_pattern: list[str] = typer.Option([], "--reusable-pattern"),
    missing_capability: list[str] = typer.Option([], "--missing-capability"),
    evidence: list[str] = typer.Option([], "--evidence"),
    confidence: str = "medium",
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    record = add_lesson(
        cfg.repo_root,
        cfg.database_path,
        repository=str(repository.resolve()),
        task=task,
        agent=agent,
        model=model,
        summary=summary,
        lessons=lesson,
        files_changed=files_changed,
        tests_run=tests_run,
        tests_not_run=tests_not_run,
        discoveries=discovery,
        failures=failure,
        reusable_patterns=reusable_pattern,
        missing_capabilities=missing_capability,
        evidence=evidence,
        confidence=confidence,
    )
    console.print(record.lesson_id)


@lesson_app.command("reindex")
def lesson_reindex(hub: Optional[Path] = typer.Option(None)) -> None:
    """Rebuild by-repo and by-capability lesson indexes from canonical lesson files."""
    cfg = _cfg(hub=hub)
    result = rebuild_lesson_routes(cfg.repo_root)
    console.print_json(data=result)


@lesson_app.command("asset-use")
def lesson_asset_use(
    asset_id: str = typer.Option(..., "--asset-id"),
    repository: Path = typer.Option(Path("."), "--repo"),
    task: str = typer.Option(..., "--task"),
    agent: str = typer.Option(..., "--agent"),
    used_for: str = typer.Option(..., "--used-for"),
    interaction_stage: str = typer.Option("after_use", "--stage"),
    expected_usefulness: str = typer.Option("unknown", "--expected-usefulness"),
    expected_futurefulness: str = typer.Option("unknown", "--expected-futurefulness"),
    expected_value_reason: str = typer.Option("", "--expected-value-reason"),
    planned_use: str = typer.Option("", "--planned-use"),
    found_by: str = typer.Option("", "--found-by"),
    found_query: str = typer.Option("", "--found-query"),
    issue_addressed: str = typer.Option("", "--issue-addressed"),
    part_used: list[str] = typer.Option([], "--part-used"),
    part_not_used: list[str] = typer.Option([], "--part-not-used"),
    not_used_reason: str = typer.Option("", "--not-used-reason"),
    upgrade_made: list[str] = typer.Option([], "--upgrade-made"),
    difficulty: list[str] = typer.Option([], "--difficulty"),
    thing_learned: list[str] = typer.Option([], "--thing-learned"),
    reuse_when: list[str] = typer.Option([], "--reuse-when"),
    avoid_when: list[str] = typer.Option([], "--avoid-when"),
    pay_forward: str = typer.Option("", "--pay-forward"),
    next_agent_action: list[str] = typer.Option([], "--next-agent-action"),
    use_outcome: str = typer.Option(..., "--use-outcome"),
    observed_usefulness: str = typer.Option(..., "--observed-usefulness"),
    observed_futurefulness: str = typer.Option(..., "--observed-futurefulness"),
    missing_part: list[str] = typer.Option([], "--missing-part"),
    score_feedback: str = typer.Option("", "--score-feedback"),
    ceiling_feedback: str = typer.Option("", "--ceiling-feedback"),
    evidence: list[str] = typer.Option([], "--evidence"),
    model: Optional[str] = None,
    confidence: str = "medium",
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Record deterministic candidate feedback after materially using an asset."""
    cfg = _cfg(hub=hub)
    try:
        record = add_asset_use_feedback(
            cfg.repo_root,
            cfg.database_path,
            asset_id=asset_id,
            repository=str(repository.resolve()),
            task=task,
            agent=agent,
            used_for=used_for,
            interaction_stage=interaction_stage,
            expected_usefulness=expected_usefulness,
            expected_futurefulness=expected_futurefulness,
            expected_value_reason=expected_value_reason,
            planned_use=planned_use,
            found_by=found_by,
            found_query=found_query,
            issue_addressed=issue_addressed,
            parts_used=part_used,
            parts_not_used=part_not_used,
            not_used_reason=not_used_reason,
            upgrades_made=upgrade_made,
            difficulties=difficulty,
            things_learned=thing_learned,
            reuse_when=reuse_when,
            avoid_when=avoid_when,
            pay_forward_guidance=pay_forward,
            next_agent_actions=next_agent_action,
            use_outcome=use_outcome,
            observed_usefulness=observed_usefulness,
            observed_futurefulness=observed_futurefulness,
            missing_parts_seen=missing_part,
            score_feedback=score_feedback,
            ceiling_feedback=ceiling_feedback,
            evidence=evidence,
            model=model,
            confidence=confidence,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print(record.lesson_id)


@lesson_app.command("repo-event")
def lesson_repo_event(
    repository: Path = typer.Option(Path("."), "--repo"),
    stage: str = typer.Option(..., "--stage"),
    task: str = typer.Option(..., "--task"),
    agent: str = typer.Option("human", "--agent"),
    context_tag: list[str] = typer.Option([], "--context-tag"),
    asset_used: list[str] = typer.Option([], "--asset-used"),
    expected_value: str = typer.Option("", "--expected-value"),
    actual_value: str = typer.Option("", "--actual-value"),
    failure_class: str = typer.Option("", "--failure-class"),
    dependency_order_notes: str = typer.Option("", "--dependency-order-notes"),
    evidence: list[str] = typer.Option([], "--evidence"),
) -> None:
    """Append a repo-local candidate learning event as data, never executable instructions."""
    stage_value = stage.lower()
    if stage_value not in {"before_work", "during_failure", "after_work", "review"}:
        console.print("Stage must be one of: before_work, during_failure, after_work, review")
        raise typer.Exit(2)
    try:
        record = append_repo_learning_event(
            repository,
            stage=stage_value,
            task=task,
            agent=agent,
            context_tags=context_tag,
            assets_used=asset_used,
            expected_value=expected_value,
            actual_value=actual_value,
            failure_class=failure_class,
            dependency_order_notes=dependency_order_notes,
            evidence=evidence,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=record.model_dump(mode="json"))


@agent_app.command("preflight")
def agent_preflight(
    repository: Path = typer.Option(Path("."), "--repo"),
    agent: str = typer.Option(...),
    task: str = typer.Option(...),
    model: Optional[str] = None,
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    payload = preflight(cfg.repo_root, repository, cfg.database_path, agent, task, model)
    console.print_json(data=payload)


@agent_app.command("postflight")
def agent_postflight(
    session: str = typer.Option(...),
    repository: Path = typer.Option(Path("."), "--repo"),
    summary: str = typer.Option(...),
    hub: Optional[Path] = typer.Option(None),
    file: list[str] = typer.Option([], "--file"),
    command: list[str] = typer.Option([], "--command"),
    test: list[str] = typer.Option([], "--test"),
    test_not_run: list[str] = typer.Option([], "--test-not-run"),
    confirmed: list[str] = typer.Option([], "--confirmed"),
    inferred: list[str] = typer.Option([], "--inferred"),
    assumption: list[str] = typer.Option([], "--assumption"),
    unknown: list[str] = typer.Option([], "--unknown"),
    lesson: list[str] = typer.Option([], "--lesson"),
    risk: list[str] = typer.Option([], "--risk"),
    next_action: list[str] = typer.Option([], "--next-action"),
    discovery: list[str] = typer.Option([], "--discovery"),
    failure: list[str] = typer.Option([], "--failure"),
    reusable_pattern: list[str] = typer.Option([], "--reusable-pattern"),
    missing_capability: list[str] = typer.Option([], "--missing-capability"),
    evidence: list[str] = typer.Option([], "--evidence"),
) -> None:
    cfg = _cfg(hub=hub)
    handoff, lesson_record = postflight(
        cfg.repo_root,
        cfg.database_path,
        session,
        summary,
        files_changed=file,
        commands_run=command,
        tests_run=test,
        tests_not_run=test_not_run,
        confirmed=confirmed,
        inferred=inferred,
        assumptions=assumption,
        unknowns=unknown,
        lessons=lesson,
        risks=risk,
        next_actions=next_action,
        discoveries=discovery,
        failures=failure,
        reusable_patterns=reusable_pattern,
        missing_capabilities=missing_capability,
        evidence=evidence,
    )
    console.print_json(
        data={"handoff_id": handoff.handoff_id, "lesson_id": lesson_record.lesson_id}
    )


@agent_app.command("midflight")
def agent_midflight(
    session: str = typer.Option(...),
    hub: Optional[Path] = typer.Option(None),
    context: list[str] = typer.Option([], "--context"),
    path: list[str] = typer.Option([], "--path"),
    ack_rule: list[str] = typer.Option([], "--ack-rule"),
) -> None:
    """Check and acknowledge deterministic learning rules during material work."""
    cfg = _cfg(hub=hub)
    try:
        result = midflight(
            cfg.repo_root,
            session,
            context=context,
            paths=path,
            ack_rules=ack_rule,
        )
    except FileNotFoundError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)
    if result["missing_learning_rule_acknowledgements"]:
        raise typer.Exit(2)


@agent_app.command("install")
def agent_install(
    repository: Path = typer.Option(..., "--repo"),
    hub: Optional[Path] = typer.Option(None),
    force: bool = False,
) -> None:
    cfg = _cfg(hub=hub)
    changed = install_governance(repository, cfg.repo_root, force)
    console.print("\n".join(str(path) for path in changed))


@agent_app.command("install-learning-loop")
def agent_install_learning_loop(
    repository: Path = typer.Option(..., "--repo"),
    mode: str = typer.Option("files-only", "--mode"),
    force: bool = False,
) -> None:
    """Install files-only repo learning-loop templates; no hooks are created."""
    try:
        changed = install_repo_learning_loop(repository, mode=mode, force=force)
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={"repo": str(repository.resolve()), "changed": [str(path) for path in changed]}
    )


@agent_app.command("new")
def agent_new(
    repository: Path = typer.Option(..., "--repo"),
    name: Optional[str] = typer.Option(None, "--name"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Scaffold a new repository already wired to this hub (starter files + governance)."""
    cfg = _cfg(hub=hub)
    changed = scaffold_new_repo(repository, cfg.repo_root, name)
    console.print("\n".join(str(path) for path in changed))


@agent_app.command("enforce")
def agent_enforce(
    repository: Path = typer.Option(Path("."), "--repo"), hub: Optional[Path] = typer.Option(None)
) -> None:
    cfg = _cfg(hub=hub)
    ok, message = enforce_postflight(cfg.repo_root, repository)
    console.print(message)
    if not ok:
        raise typer.Exit(2)


@research_app.command("missing")
def research_missing(
    limit: int = typer.Option(20, min=1, max=30),
    enable_external: bool = typer.Option(
        False,
        "--enable-external",
        help="Allow live external GitHub API calls for missing-part research.",
    ),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    report = research_missing_parts(
        cfg.repo_root, cfg.database_path, limit, enable_external=enable_external
    )
    console.print_json(data=report)
    if report["status"] == "blocked_external_research_not_enabled":
        raise typer.Exit(2)


@recommend_app.command("skills")
def recommend_skills(
    hub: Optional[Path] = typer.Option(None),
    threshold: int = typer.Option(3, min=2, max=100),
) -> None:
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        records = recommend_skills_and_agents(db.assets(), threshold)
    console.print_json(data=[record.model_dump(mode="json") for record in records])


@recommend_app.command("swarm")
def recommend_swarm_command(
    goal: str,
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(12, min=1, max=50),
) -> None:
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        record = recommend_swarm(goal, db.assets(), limit)
    console.print_json(data=record.model_dump(mode="json"))


@recommend_app.command("asset-families")
def recommend_asset_families(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated candidate reports for high-leverage asset-family patterns."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_asset_family_reports(
            cfg.repo_root,
            db.assets(),
            source_id=source_id,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("learning-loops")
def recommend_learning_loops(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(25, "--review-sample", min=1, max=200),
) -> None:
    """Write generated candidate learning-loop records from the current catalog."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_learning_loop_outputs(
            cfg.repo_root,
            db.assets(),
            scan_id=scan_id,
            source_id=source_id,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("workflow-sweeps")
def recommend_workflow_sweeps(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
    include_noise: bool = typer.Option(False, "--include-noise/--exclude-noise"),
    usefulness_per_sweep_limit: int = typer.Option(
        25, "--usefulness-per-sweep-limit", min=1, max=100
    ),
    usefulness_global_limit: int = typer.Option(75, "--usefulness-global-limit", min=1, max=300),
) -> None:
    """Write generated candidate workflow-family sweeps, governance first."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_workflow_sweep_reports(
            cfg.repo_root,
            db.assets(),
            source_id=source_id,
            review_sample=review_sample,
            include_noise=include_noise,
            usefulness_per_sweep_limit=usefulness_per_sweep_limit,
            usefulness_global_limit=usefulness_global_limit,
        )
    console.print_json(data=result)


@recommend_app.command("workflow-parts")
def recommend_workflow_parts(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated candidate workflow-part records from the current catalog."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_workflow_part_outputs(
            cfg.repo_root,
            db.assets(),
            db.edges(),
            scan_id=scan_id,
            source_id=source_id,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("workflow-part-review-template")
def recommend_workflow_part_review_template(
    hub: Optional[Path] = typer.Option(None),
    workflow_parts_file: Optional[Path] = typer.Option(None, "--workflow-parts-file"),
    sample_size: int = typer.Option(50, "--sample-size", min=1, max=200),
) -> None:
    """Write a stratified generated review template for workflow-part calibration."""
    cfg = _cfg(hub=hub)
    path = workflow_parts_file or cfg.repo_root / "processed" / "learning" / "workflow_parts.jsonl"
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        result = write_workflow_part_review_template_outputs(
            cfg.repo_root, load_workflow_parts(path), sample_size=sample_size
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"workflow_parts_file": str(path), **result})


@recommend_app.command("workflow-part-review-summary")
def recommend_workflow_part_review_summary(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
) -> None:
    """Summarize filled workflow-part review JSONL labels without changing roadmap state."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        reviews = load_workflow_part_reviews(path)
        summary, output = write_workflow_part_review_results_summary(
            cfg.repo_root, reviews, path
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": output, "summary": summary})


@recommend_app.command("workflow-part-review-queue")
def recommend_workflow_part_review_queue(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    workflow_parts_file: Optional[Path] = typer.Option(None, "--workflow-parts-file"),
    status: str = typer.Option("pending", "--status"),
    part_type: str = typer.Option("all", "--part-type"),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    """List workflow-part review queue items joined with candidate context."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    parts_path = workflow_parts_file or cfg.repo_root / "processed" / "learning" / "workflow_parts.jsonl"
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not parts_path.is_absolute():
        parts_path = cfg.repo_root / parts_path
    status_value = status.lower()
    if status_value not in {"pending", "reviewed", "all"}:
        console.print("Status must be one of: pending, reviewed, all")
        raise typer.Exit(2)
    try:
        queue = build_workflow_part_review_queue(
            load_workflow_part_reviews(review_path),
            load_workflow_parts(parts_path),
            status=status_value,  # type: ignore[arg-type]
            part_type=part_type,
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(review_path),
            "workflow_parts_file": str(parts_path),
            **queue,
        }
    )


@recommend_app.command("workflow-part-review-label")
def recommend_workflow_part_review_label(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    part_id: Optional[str] = typer.Option(None, "--part-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    usefulness: Optional[str] = typer.Option(None, "--usefulness"),
    safety: Optional[str] = typer.Option(None, "--safety"),
    specificity: Optional[str] = typer.Option(None, "--specificity"),
    dataflow_completeness: Optional[str] = typer.Option(None, "--dataflow-completeness"),
    decision: Optional[str] = typer.Option(None, "--decision"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    false_negative_note: Optional[str] = typer.Option(None, "--false-negative-note"),
    useful_example_note: Optional[str] = typer.Option(None, "--useful-example-note"),
    missing_dataflow_note: Optional[str] = typer.Option(None, "--missing-dataflow-note"),
) -> None:
    """Update one workflow-part review JSONL record with human calibration labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_workflow_part_review_file(
            path,
            sample_id=sample_id,
            part_id=part_id,
            reviewer=reviewer,
            usefulness=usefulness,
            safety=safety,
            specificity=specificity,
            dataflow_completeness=dataflow_completeness,
            decision=decision,
            notes=notes,
            false_positive_reason=false_positive_reason,
            false_negative_note=false_negative_note,
            useful_example_note=useful_example_note,
            missing_dataflow_note=missing_dataflow_note,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "updated": updated.model_dump(mode="json"),
            "summary": summary,
        }
    )


@recommend_app.command("workflow-part-calibration-evidence")
def recommend_workflow_part_calibration_evidence(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Write tracked-ready evidence only after workflow-part calibration review is complete."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        summary, evidence_path = write_workflow_part_calibration_evidence(
            cfg.repo_root, load_workflow_part_reviews(path), path, output
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": evidence_path, "summary": summary})


@recommend_app.command("workflow-part-guidance")
def recommend_workflow_part_guidance(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    limit: int = typer.Option(30, "--limit", min=1, max=100),
) -> None:
    """Write manual workflow-part usage guidance from completed human review labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        guidance, report, payload = write_workflow_part_usage_guidance(
            cfg.repo_root, load_workflow_part_reviews(path), path, limit=limit
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "report": report,
            "payload": payload,
            "summary": guidance["summary"],
            "authority_boundary": guidance["authority_boundary"],
        }
    )


@recommend_app.command("manual-tasks")
def recommend_manual_tasks(
    hub: Optional[Path] = typer.Option(None),
    workflow_guidance_file: Optional[Path] = typer.Option(None, "--workflow-guidance-file"),
    limit: int = typer.Option(25, "--limit", min=1, max=100),
    family_limit: int = typer.Option(12, "--family-limit", min=1, max=50),
) -> None:
    """Write a generated manual task queue from current alerts and workflow-part guidance."""
    cfg = _cfg(hub=hub)
    guidance_path = (
        workflow_guidance_file
        or cfg.repo_root / "processed" / "workflow_parts" / "workflow_part_usage_guidance.json"
    )
    if not guidance_path.is_absolute():
        guidance_path = cfg.repo_root / guidance_path
    try:
        workflow_guidance = json.loads(guidance_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else None
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        result = write_manual_task_queue(
            cfg.repo_root,
            db.alerts(open_only=True),
            db.assets(),
            workflow_guidance,
            latest_scan_id=latest_scan_id,
            scan_changed_count=int(scan_summary.get("changed_during_scan_count") or 0),
            limit=limit,
            family_limit=family_limit,
        )
    console.print_json(data={"workflow_guidance_file": str(guidance_path), **result})


@recommend_app.command("repo-buildout")
def recommend_repo_buildout(
    repo: str = typer.Option(..., "--repo"),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(10, "--limit", min=1, max=50),
) -> None:
    """Write generated repo-specific buildout recommendations from current catalog data."""
    cfg = _cfg(hub=hub)
    artifacts = load_default_repo_buildout_artifacts(cfg.repo_root)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        try:
            result = write_repo_buildout_outputs(
                cfg.repo_root,
                repo,
                db.assets(),
                db.edges(),
                db.alerts(open_only=True),
                local_sources=cfg.local_sources,
                artifacts=artifacts,
                scan_id=latest_scan_id,
                scan_changed_count=int(scan_summary.get("changed_during_scan_count") or 0),
                limit=limit,
            )
        except ValueError as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("lesson-automation-coverage")
def recommend_lesson_automation_coverage(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
) -> None:
    """Write a no-rescan coverage report and scan-cycle log for future learning automation."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        result = write_lesson_automation_coverage_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            cfg.github_sources,
            scan_id=latest_scan_id,
            scan_summary=scan_summary,
            limit=limit,
        )
    console.print_json(data=result)


@recommend_app.command("priority-content-scope")
def recommend_priority_content_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(200, "--limit", min=1, max=1000),
    per_repo_limit: int = typer.Option(12, "--per-repo-limit", min=1, max=50),
) -> None:
    """Write a metadata-only approval scope for a future bounded content extract pass."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_priority_content_extract_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
            per_repo_limit=per_repo_limit,
        )
    console.print_json(data=result)


@recommend_app.command("ci-release-scope")
def recommend_ci_release_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(200, "--limit", min=1, max=1000),
    per_repo_limit: int = typer.Option(12, "--per-repo-limit", min=1, max=50),
) -> None:
    """Write a metadata-only approval scope for CI, release, changelog, QA, and log artifacts."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_ci_release_artifact_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
            per_repo_limit=per_repo_limit,
        )
    console.print_json(data=result)


@recommend_app.command("repo-learning-loop-scope")
def recommend_repo_learning_loop_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
) -> None:
    """Write a generated approval scope for files-only repo learning-loop installation."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_repo_learning_loop_install_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
        )
    console.print_json(data=result)


@recommend_app.command("governance-map-scope")
def recommend_governance_map_scope(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
) -> None:
    """Write a generated approval scope for governance maps and child mirrors."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_governance_map_adoption_scope_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=latest_scan_id,
            limit=limit,
        )
    console.print_json(data=result)


@recommend_app.command("priority-content-extract")
def recommend_priority_content_extract(
    approval_id: str = typer.Option(..., "--approval-id"),
    repo_key: list[str] = typer.Option([], "--repo-key"),
    category: list[str] = typer.Option([], "--category"),
    scope_file: Optional[Path] = typer.Option(None, "--scope-file"),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    max_bytes_per_file: int = typer.Option(20_000, "--max-bytes-per-file", min=1, max=200_000),
    max_excerpt_chars: int = typer.Option(4_000, "--max-excerpt-chars", min=200, max=20_000),
) -> None:
    """Read only approved scoped paths with byte caps and write generated observations."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        try:
            result = write_priority_content_extract_outputs(
                cfg.repo_root,
                cfg.local_sources,
                scope_file=scope_file,
                approval_id=approval_id,
                repo_keys=repo_key,
                category_ids=category,
                scan_id=latest_scan_id,
                max_bytes_per_file=max_bytes_per_file,
                max_excerpt_chars=max_excerpt_chars,
                limit=limit,
            )
        except ValueError as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("priority-content-lessons")
def recommend_priority_content_lessons(
    observations_file: Optional[Path] = typer.Option(None, "--observations-file"),
    hub: Optional[Path] = typer.Option(None),
    min_observations: int = typer.Option(1, "--min-observations", min=1, max=20),
    limit: int = typer.Option(100, "--limit", min=1, max=500),
) -> None:
    """Synthesize generated lesson candidates from bounded priority-content observations."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        try:
            result = write_priority_content_lesson_outputs(
                cfg.repo_root,
                observations_file=observations_file,
                scan_id=latest_scan_id,
                min_observations=min_observations,
                limit=limit,
            )
        except ValueError as exc:
            console.print(str(exc))
            raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("priority-content-lesson-review-template")
def recommend_priority_content_lesson_review_template(
    candidates_file: Optional[Path] = typer.Option(None, "--candidates-file"),
    hub: Optional[Path] = typer.Option(None),
    sample_size: int = typer.Option(100, "--sample-size", min=1, max=500),
) -> None:
    """Write a generated human-review template for priority-content lesson candidates."""
    cfg = _cfg(hub=hub)
    path = candidates_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_candidates.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        result = write_priority_content_lesson_review_template_outputs(
            cfg.repo_root,
            load_priority_content_lesson_candidates(path),
            sample_size=sample_size,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"candidates_file": str(path), **result})


@recommend_app.command("priority-content-lesson-review-summary")
def recommend_priority_content_lesson_review_summary(
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Summarize priority-content lesson review labels without promoting lessons."""
    cfg = _cfg(hub=hub)
    path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        summary = summarize_priority_content_lesson_reviews(
            load_priority_content_lesson_reviews(path)
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "summary": summary})


@recommend_app.command("priority-content-lesson-promotion-candidates")
def recommend_priority_content_lesson_promotion_candidates(
    candidates_file: Optional[Path] = typer.Option(None, "--candidates-file"),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(100, "--limit", min=1, max=500),
) -> None:
    """Package reviewed priority-content lessons as generated learning-rule promotion candidates."""
    cfg = _cfg(hub=hub)
    candidates_path = candidates_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_candidates.jsonl"
    )
    reviews_path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not candidates_path.is_absolute():
        candidates_path = cfg.repo_root / candidates_path
    if not reviews_path.is_absolute():
        reviews_path = cfg.repo_root / reviews_path
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        latest_scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
    try:
        result = write_learning_rule_promotion_candidate_outputs(
            cfg.repo_root,
            load_priority_content_lesson_candidates(candidates_path),
            load_priority_content_lesson_reviews(reviews_path),
            scan_id=latest_scan_id,
            limit=limit,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "candidates_file": str(candidates_path),
            "review_file": str(reviews_path),
            **result,
        }
    )


@recommend_app.command("priority-content-lesson-review-queue")
def recommend_priority_content_lesson_review_queue(
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    hub: Optional[Path] = typer.Option(None),
    status: str = typer.Option("pending", "--status"),
    limit: int = typer.Option(10, "--limit", min=1, max=100),
) -> None:
    """List priority-content lesson review queue items for human labeling."""
    cfg = _cfg(hub=hub)
    path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        result = build_priority_content_lesson_review_queue(
            load_priority_content_lesson_reviews(path),
            status=status,
            limit=limit,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), **result})


@recommend_app.command("priority-content-lesson-review-label")
def recommend_priority_content_lesson_review_label(
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    lesson_candidate_id: Optional[str] = typer.Option(None, "--lesson-candidate-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    applicability: Optional[str] = typer.Option(None, "--applicability"),
    usefulness: Optional[str] = typer.Option(None, "--usefulness"),
    safety: Optional[str] = typer.Option(None, "--safety"),
    actionability: Optional[str] = typer.Option(None, "--actionability"),
    decision: Optional[str] = typer.Option(None, "--decision"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    missing_context_note: Optional[str] = typer.Option(None, "--missing-context-note"),
    useful_example_note: Optional[str] = typer.Option(None, "--useful-example-note"),
    promotion_blocker_note: Optional[str] = typer.Option(None, "--promotion-blocker-note"),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Apply one human-approved priority-content lesson review label."""
    cfg = _cfg(hub=hub)
    path = review_file or (
        cfg.repo_root / "processed" / "learning" / "priority_content_lesson_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_priority_content_lesson_review_file(
            path,
            sample_id=sample_id,
            lesson_candidate_id=lesson_candidate_id,
            reviewer=reviewer,
            applicability=applicability,
            usefulness=usefulness,
            safety=safety,
            actionability=actionability,
            decision=decision,
            notes=notes,
            false_positive_reason=false_positive_reason,
            missing_context_note=missing_context_note,
            useful_example_note=useful_example_note,
            promotion_blocker_note=promotion_blocker_note,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={"review_file": str(path), "updated": updated.model_dump(mode="json"), "summary": summary}
    )


@recommend_app.command("public-safe-source-sweep")
def recommend_public_safe_source_sweep(
    source_path: Path = typer.Option(..., "--source-path"),
    source_id: str = typer.Option(..., "--source-id"),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=300),
    max_files: Optional[int] = typer.Option(None, "--max-files", min=1),
    hub: Optional[Path] = typer.Option(None),
) -> None:
    """Metadata-only sweep for private sources whose workflow is reusable but rows are not."""
    cfg = _cfg(hub=hub)
    result = write_public_safe_source_sweep(
        cfg.repo_root,
        source_path,
        source_id=source_id,
        review_sample=review_sample,
        max_files=max_files,
    )
    console.print_json(data=result)


@recommend_app.command("archaeology")
def recommend_archaeology(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    include_worktrees: bool = typer.Option(True, "--include-worktrees/--exclude-worktrees"),
    include_temp: bool = typer.Option(True, "--include-temp/--exclude-temp"),
    max_repos: int = typer.Option(25, "--max-repos", min=1, max=100),
    max_commits: int = typer.Option(200, "--max-commits", min=1, max=1000),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated worktree, git-history, failure, and change-pattern archaeology reports."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_archaeology_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=scan_id,
            source_id=source_id,
            include_worktrees=include_worktrees,
            include_temp=include_temp,
            max_repos=max_repos,
            max_commits=max_commits,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("root-cause-lessons")
def recommend_root_cause_lessons(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    include_worktrees: bool = typer.Option(True, "--include-worktrees/--exclude-worktrees"),
    include_temp: bool = typer.Option(True, "--include-temp/--exclude-temp"),
    max_repos: int = typer.Option(25, "--max-repos", min=1, max=100),
    max_commits: int = typer.Option(200, "--max-commits", min=1, max=1000),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
) -> None:
    """Write generated context-bound root-cause and counterfactual lesson candidates."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_root_cause_lesson_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=scan_id,
            source_id=source_id,
            include_worktrees=include_worktrees,
            include_temp=include_temp,
            max_repos=max_repos,
            max_commits=max_commits,
            review_sample=review_sample,
        )
    console.print_json(data=result)


@recommend_app.command("semantic-evolution")
def recommend_semantic_evolution(
    hub: Optional[Path] = typer.Option(None),
    source_id: str = typer.Option("all", "--source-id"),
    basename: Optional[str] = typer.Option(None, "--basename"),
    asset_type: str = typer.Option("schema", "--asset-type"),
    max_families: int = typer.Option(100, "--max-families", min=1, max=500),
    review_sample: int = typer.Option(50, "--review-sample", min=1, max=200),
    max_read_bytes: int = typer.Option(1_000_000, "--max-read-bytes", min=0),
) -> None:
    """Grade structured semantic evolution versus copy/fixture noise from the current catalog."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_semantic_evolution_outputs(
            cfg.repo_root,
            db.assets(),
            cfg.local_sources,
            scan_id=scan_id,
            source_id=source_id,
            basename=basename,
            asset_type=asset_type,
            max_families=max_families,
            review_sample=review_sample,
            max_read_bytes=max_read_bytes,
        )
    console.print_json(data=result)


@recommend_app.command("background-connections")
def recommend_background_connections(
    hub: Optional[Path] = typer.Option(None),
    attention: str = typer.Option("recent", "--attention"),
    cold: str = typer.Option("older", "--cold"),
    limit: int = typer.Option(50, "--limit", min=1, max=200),
    escalation_budget: int = typer.Option(5, "--escalation-budget", min=1, max=20),
    tau: float = typer.Option(0.70, "--tau", min=0.0, max=1.0),
    max_hops: int = typer.Option(2, "--max-hops", min=0, max=2),
    reserve_cold: int = typer.Option(2, "--reserve-cold", min=0, max=20),
) -> None:
    """Generate manual, local-only background connection candidates from existing catalog data."""
    normalized_attention = attention.lower()
    normalized_cold = cold.lower()
    if normalized_attention != "recent":
        console.print("Attention mode must be: recent")
        raise typer.Exit(2)
    if normalized_cold != "older":
        console.print("Cold mode must be: older")
        raise typer.Exit(2)
    if reserve_cold > escalation_budget:
        console.print("reserve-cold cannot exceed escalation-budget")
        raise typer.Exit(2)
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        result = write_background_connection_outputs(
            cfg.repo_root,
            db.assets(),
            db.edges(),
            scan_id=scan_id,
            attention=normalized_attention,
            cold=normalized_cold,
            limit=limit,
            escalation_budget=escalation_budget,
            tau=tau,
            max_hops=max_hops,
            reserve_cold=reserve_cold,
        )
    console.print_json(data=result)


@recommend_app.command("proposals")
def recommend_proposals(
    hub: Optional[Path] = typer.Option(None),
    engine: str = typer.Option("both", "--engine"),
    per_asset_limit: int = typer.Option(3, min=1, max=20),
    portfolio_limit: int = typer.Option(20, min=1, max=200),
    review_sample: int = typer.Option(25, min=1, max=200),
) -> None:
    """Generate bottom-up and/or top-down candidate proposals from the current catalog."""
    normalized_engine = engine.lower()
    if normalized_engine not in {"bottom-up", "top-down", "both"}:
        console.print("Engine must be one of: bottom-up, top-down, both")
        raise typer.Exit(2)
    selected_engine = cast(ProposalEngineOption, normalized_engine)
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_id = latest_scan["scan_id"] if latest_scan else "catalog-without-scan"
        bottom_up, top_down, comparison = run_proposal_engines(
            assets=db.assets(),
            edges=db.edges(),
            alerts=db.alerts(open_only=True),
            scan_id=scan_id,
            engine=selected_engine,
            per_asset_limit=per_asset_limit,
            portfolio_limit=portfolio_limit,
            review_sample=review_sample,
            roadmap_context=load_roadmap_relevance_context(cfg.repo_root),
        )
    paths = write_proposal_outputs(cfg.repo_root, bottom_up, top_down, comparison)
    comparison_summary = {key: value for key, value in comparison.items() if key != "review_sample"}
    console.print_json(
        data={
            "scan_id": scan_id,
            "engine": normalized_engine,
            "bottom_up_count": len(bottom_up),
            "top_down_count": len(top_down),
            "comparison": comparison_summary,
            "outputs": paths,
        }
    )


@recommend_app.command("calibration-reports")
def recommend_calibration_reports(
    hub: Optional[Path] = typer.Option(None),
    sample_size: int = typer.Option(25, "--sample-size", min=1, max=100),
) -> None:
    """Write generated phase-2 scoring, orphan, and synergy calibration review reports."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_phase2_calibration_reports(
            cfg.repo_root,
            db.assets(),
            db.alerts(open_only=True),
            db.synergies(),
            sample_size=sample_size,
        )
    console.print_json(data=result)


@recommend_app.command("calibration-review-summary")
def recommend_calibration_review_summary(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
) -> None:
    """Summarize phase-2 asset scoring calibration review progress."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    records = load_asset_calibration_reviews(path)
    summary, output = write_asset_calibration_summary(cfg.repo_root, records, path)
    console.print_json(data={"review_file": str(path), "output": output, "summary": summary})


@recommend_app.command("calibration-review-label")
def recommend_calibration_review_label(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    asset_id: Optional[str] = typer.Option(None, "--asset-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    score_rating: Optional[str] = typer.Option(None, "--score-rating"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    false_negative_note: Optional[str] = typer.Option(None, "--false-negative-note"),
    weight_change_note: Optional[str] = typer.Option(None, "--weight-change-note"),
    notes: Optional[str] = typer.Option(None, "--notes"),
) -> None:
    """Update one phase-2 asset calibration review record with human labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_asset_calibration_review_file(
            path,
            sample_id=sample_id,
            asset_id=asset_id,
            reviewer=reviewer,
            score_rating=score_rating,
            false_positive_reason=false_positive_reason,
            false_negative_note=false_negative_note,
            weight_change_note=weight_change_note,
            notes=notes,
        )
        write_asset_calibration_summary(cfg.repo_root, load_asset_calibration_reviews(path), path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "updated": updated.model_dump(mode="json"),
            "summary": summary,
        }
    )


@recommend_app.command("calibration-review-queue")
def recommend_calibration_review_queue(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    status: str = typer.Option("pending", "--status"),
    band: str = typer.Option("all", "--band"),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    """List asset calibration review queue items with generated score context."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path

    status_value = status.lower()
    band_value = band.lower()
    if status_value not in {"pending", "reviewed", "all"}:
        console.print("Status must be one of: pending, reviewed, all")
        raise typer.Exit(2)
    if band_value not in {"low", "medium", "high", "all"}:
        console.print("Band must be one of: low, medium, high, all")
        raise typer.Exit(2)
    try:
        queue = build_asset_calibration_review_queue(
            load_asset_calibration_reviews(path),
            status=status_value,  # type: ignore[arg-type]
            band=band_value,  # type: ignore[arg-type]
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), **queue})


@recommend_app.command("calibration-review-export-csv")
def recommend_calibration_review_export_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Export phase-2 asset calibration reviews to a human-editable CSV."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    output_path = output or cfg.repo_root / "processed" / "calibration" / "asset_rating_batch.csv"
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not output_path.is_absolute():
        output_path = cfg.repo_root / output_path
    records = load_asset_calibration_reviews(review_path)
    written = write_asset_calibration_review_csv(output_path, records)
    console.print_json(
        data={"review_file": str(review_path), "output": written, "row_count": len(records)}
    )


@recommend_app.command("calibration-review-import-csv")
def recommend_calibration_review_import_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    csv_file: Optional[Path] = typer.Option(None, "--csv-file"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
) -> None:
    """Import human-edited phase-2 asset calibration review CSV labels."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    csv_path = csv_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_batch.csv"
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not csv_path.is_absolute():
        csv_path = cfg.repo_root / csv_path
    try:
        result = import_asset_calibration_review_csv(
            review_path, csv_path, default_reviewer=reviewer
        )
        write_asset_calibration_summary(
            cfg.repo_root, load_asset_calibration_reviews(review_path), review_path
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("calibration-evidence")
def recommend_calibration_evidence(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Write tracked roadmap evidence only after asset calibration review is complete."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    records = load_asset_calibration_reviews(path)
    try:
        summary, evidence_path = write_asset_calibration_evidence(
            cfg.repo_root, records, path, output
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": evidence_path, "summary": summary})


@recommend_app.command("phase25-score-delta")
def recommend_phase25_score_delta(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
    json_output: Optional[Path] = typer.Option(None, "--json-output"),
) -> None:
    """Compare reviewed Phase 2 labels against current Phase 2.5 v0.3 scores."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    with CatalogDB(cfg.database_path) as db:
        latest_scan = db.latest_scan()
        scan_summary = json.loads(latest_scan.get("summary_json") or "{}") if latest_scan else {}
        result = write_phase25_score_delta_validation(
            cfg.repo_root,
            load_asset_calibration_reviews(path),
            load_catalog_assets(cfg.repo_root / "processed" / "catalog" / "assets.jsonl"),
            scan_summary=scan_summary,
            output=output,
            json_output=json_output,
        )
    console.print_json(data={"review_file": str(path), **result})


@recommend_app.command("downstream-pilots")
def recommend_downstream_pilots(
    hub: Optional[Path] = typer.Option(None),
    limit: int = typer.Option(10, min=1, max=50),
) -> None:
    """Write a generated candidate pack for selecting a downstream governance pilot."""
    cfg = _cfg(hub=hub)
    with CatalogDB(cfg.database_path) as db:
        result = write_downstream_pilot_candidates(cfg.repo_root, db.assets(), limit=limit)
    console.print_json(data=result)


@recommend_app.command("roadmap-readiness")
def recommend_roadmap_readiness(hub: Optional[Path] = typer.Option(None)) -> None:
    """Write planning-only readiness templates for later roadmap phases."""
    cfg = _cfg(hub=hub)
    console.print_json(data=write_phase45_readiness_reports(cfg.repo_root))


@recommend_app.command("proposal-review-summary")
def recommend_proposal_review_summary(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
) -> None:
    """Summarize filled proposal review JSONL labels without changing roadmap state."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    reviews = load_proposal_reviews(path)
    summary, output = write_proposal_review_results_summary(cfg.repo_root, reviews, path)
    console.print_json(data={"review_file": str(path), "output": output, "summary": summary})


@recommend_app.command("proposal-review-label")
def recommend_proposal_review_label(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    sample_id: Optional[str] = typer.Option(None, "--sample-id"),
    proposal_id: Optional[str] = typer.Option(None, "--proposal-id"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
    usefulness: Optional[str] = typer.Option(None, "--usefulness"),
    safety: Optional[str] = typer.Option(None, "--safety"),
    novelty: Optional[str] = typer.Option(None, "--novelty"),
    actionability: Optional[str] = typer.Option(None, "--actionability"),
    decision: Optional[str] = typer.Option(None, "--decision"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    false_positive_reason: Optional[str] = typer.Option(None, "--false-positive-reason"),
    false_negative_note: Optional[str] = typer.Option(None, "--false-negative-note"),
    useful_example_note: Optional[str] = typer.Option(None, "--useful-example-note"),
) -> None:
    """Update one proposal review JSONL record with human calibration labels."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    try:
        updated, summary = update_proposal_review_file(
            path,
            sample_id=sample_id,
            proposal_id=proposal_id,
            reviewer=reviewer,
            usefulness=usefulness,
            safety=safety,
            novelty=novelty,
            actionability=actionability,
            decision=decision,
            notes=notes,
            false_positive_reason=false_positive_reason,
            false_negative_note=false_negative_note,
            useful_example_note=useful_example_note,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(path),
            "updated": updated.model_dump(mode="json"),
            "summary": summary,
        }
    )


@recommend_app.command("proposal-review-queue")
def recommend_proposal_review_queue(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    bottom_up_file: Optional[Path] = typer.Option(None, "--bottom-up-file"),
    top_down_file: Optional[Path] = typer.Option(None, "--top-down-file"),
    status: str = typer.Option("pending", "--status"),
    engine: str = typer.Option("all", "--engine"),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    """List proposal review queue items joined with proposal context."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    bottom_path = (
        bottom_up_file or cfg.repo_root / "processed" / "proposals" / "bottom_up_proposals.jsonl"
    )
    top_path = (
        top_down_file or cfg.repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
    )
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not bottom_path.is_absolute():
        bottom_path = cfg.repo_root / bottom_path
    if not top_path.is_absolute():
        top_path = cfg.repo_root / top_path

    status_value = status.lower()
    engine_value = engine.lower()
    engine_map = {
        "all": "all",
        "bottom-up": "bottom_up_self_proposal",
        "bottom_up_self_proposal": "bottom_up_self_proposal",
        "top-down": "top_down_orchestration",
        "top_down_orchestration": "top_down_orchestration",
    }
    if status_value not in {"pending", "reviewed", "all"}:
        console.print("Status must be one of: pending, reviewed, all")
        raise typer.Exit(2)
    if engine_value not in engine_map:
        console.print("Engine must be one of: all, bottom-up, top-down")
        raise typer.Exit(2)
    try:
        queue = build_proposal_review_queue(
            load_proposal_reviews(review_path),
            load_generated_proposals(bottom_path, top_path),
            status=status_value,  # type: ignore[arg-type]
            engine=engine_map[engine_value],  # type: ignore[arg-type]
            limit=limit,
        )
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(
        data={
            "review_file": str(review_path),
            "bottom_up_file": str(bottom_path),
            "top_down_file": str(top_path),
            **queue,
        }
    )


@recommend_app.command("proposal-review-export-csv")
def recommend_proposal_review_export_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    bottom_up_file: Optional[Path] = typer.Option(None, "--bottom-up-file"),
    top_down_file: Optional[Path] = typer.Option(None, "--top-down-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
    unblind_output: Optional[Path] = typer.Option(None, "--unblind-output"),
    blind: bool = typer.Option(True, "--blind/--include-engine"),
) -> None:
    """Export proposal review records and proposal context to a human-editable CSV."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    bottom_path = (
        bottom_up_file or cfg.repo_root / "processed" / "proposals" / "bottom_up_proposals.jsonl"
    )
    top_path = (
        top_down_file or cfg.repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
    )
    output_path = output or cfg.repo_root / "processed" / "proposals" / "proposal_review_batch.csv"
    unblind_path = (
        unblind_output
        or cfg.repo_root / "processed" / "proposals" / "proposal_review_unblind_map.csv"
    )
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not bottom_path.is_absolute():
        bottom_path = cfg.repo_root / bottom_path
    if not top_path.is_absolute():
        top_path = cfg.repo_root / top_path
    if not output_path.is_absolute():
        output_path = cfg.repo_root / output_path
    if not unblind_path.is_absolute():
        unblind_path = cfg.repo_root / unblind_path
    reviews = load_proposal_reviews(review_path)
    proposals = load_generated_proposals(bottom_path, top_path)
    written = write_proposal_review_csv(output_path, reviews, proposals, blind=blind)
    unblind_written = write_proposal_review_unblind_map(unblind_path, reviews) if blind else None
    console.print_json(
        data={
            "review_file": str(review_path),
            "bottom_up_file": str(bottom_path),
            "top_down_file": str(top_path),
            "output": written,
            "blind": blind,
            "unblind_output": unblind_written,
            "row_count": len(reviews),
        }
    )


@recommend_app.command("proposal-review-import-csv")
def recommend_proposal_review_import_csv(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    csv_file: Optional[Path] = typer.Option(None, "--csv-file"),
    reviewer: Optional[str] = typer.Option(None, "--reviewer"),
) -> None:
    """Import validated human labels from proposal review CSV back into review JSONL."""
    cfg = _cfg(hub=hub)
    review_path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    csv_path = csv_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_batch.csv"
    if not review_path.is_absolute():
        review_path = cfg.repo_root / review_path
    if not csv_path.is_absolute():
        csv_path = cfg.repo_root / csv_path
    try:
        result = import_proposal_review_csv(review_path, csv_path, default_reviewer=reviewer)
    except (FileNotFoundError, ValueError) as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data=result)


@recommend_app.command("proposal-calibration-evidence")
def recommend_proposal_calibration_evidence(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
    default_path: Optional[str] = typer.Option(None, "--default-path"),
    default_rationale: Optional[str] = typer.Option(None, "--default-rationale"),
) -> None:
    """Write tracked-ready roadmap evidence only after proposal calibration review is complete."""
    cfg = _cfg(hub=hub)
    path = (
        review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    )
    if not path.is_absolute():
        path = cfg.repo_root / path
    reviews = load_proposal_reviews(path)
    try:
        summary, evidence_path = write_proposal_calibration_evidence(
            cfg.repo_root,
            reviews,
            path,
            output,
            default_path=default_path,
            default_rationale=default_rationale,
        )
    except ValueError as exc:
        console.print(str(exc))
        raise typer.Exit(2) from exc
    console.print_json(data={"review_file": str(path), "output": evidence_path, "summary": summary})


@orphan_app.command("run")
def orphan_run(
    source: Path = typer.Option(..., "--src"),
    executable: str = "orphan-radar",
    hub: Optional[Path] = typer.Option(None),
) -> None:
    cfg = _cfg(hub=hub)
    console.print_json(data=run_orphan_radar(cfg.repo_root, source, executable))


if __name__ == "__main__":
    app()
