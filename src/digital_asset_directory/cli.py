from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, cast

import typer
from rich.console import Console

from .calibration import (
    import_asset_calibration_review_csv,
    load_asset_calibration_reviews,
    update_asset_calibration_review_file,
    write_asset_calibration_summary,
    write_asset_calibration_review_csv,
    write_phase2_calibration_reports,
)
from .catalog import catalog_status, run_scan
from .config import load_config
from .context_pack import build_context_pack, write_context_pack
from .database import CatalogDB
from .governance import enforce_postflight, install_governance
from .learning import add_lesson, postflight, preflight
from .orphan_adapter import run_orphan_radar
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
from .recommendations import recommend_skills_and_agents, recommend_swarm
from .research import research_missing_parts
from .roadmap import check_roadmap
from .validation import validate_repo

app = typer.Typer(no_args_is_help=True, help="Digital Asset Directory portfolio intelligence CLI.")
lesson_app = typer.Typer(no_args_is_help=True)
app.add_typer(lesson_app, name="lesson")
agent_app = typer.Typer(no_args_is_help=True)
app.add_typer(agent_app, name="agent")
roadmap_app = typer.Typer(no_args_is_help=True)
app.add_typer(roadmap_app, name="roadmap")
research_app = typer.Typer(no_args_is_help=True)
app.add_typer(research_app, name="research")
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


@agent_app.command("install")
def agent_install(
    repository: Path = typer.Option(..., "--repo"),
    hub: Optional[Path] = typer.Option(None),
    force: bool = False,
) -> None:
    cfg = _cfg(hub=hub)
    changed = install_governance(repository, cfg.repo_root, force)
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
    limit: int = typer.Option(20, min=1, max=30), hub: Optional[Path] = typer.Option(None)
) -> None:
    cfg = _cfg(hub=hub)
    report = research_missing_parts(cfg.repo_root, cfg.database_path, limit)
    console.print_json(data=report)


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
    console.print_json(
        data={
            "scan_id": scan_id,
            "engine": normalized_engine,
            "bottom_up_count": len(bottom_up),
            "top_down_count": len(top_down),
            "comparison": comparison,
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
    path = review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
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
    path = review_file or cfg.repo_root / "processed" / "calibration" / "asset_rating_template.jsonl"
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
        write_asset_calibration_summary(
            cfg.repo_root, load_asset_calibration_reviews(path), path
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


@recommend_app.command("proposal-review-summary")
def recommend_proposal_review_summary(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
) -> None:
    """Summarize filled proposal review JSONL labels without changing roadmap state."""
    cfg = _cfg(hub=hub)
    path = review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
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
    path = review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
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
    top_path = top_down_file or cfg.repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
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
    top_path = top_down_file or cfg.repo_root / "processed" / "proposals" / "top_down_proposals.jsonl"
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
    path = review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
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
    console.print_json(
        data={"review_file": str(path), "output": evidence_path, "summary": summary}
    )


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
