from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, cast

import typer
from rich.console import Console

from .catalog import catalog_status, run_scan
from .config import load_config
from .context_pack import build_context_pack, write_context_pack
from .database import CatalogDB
from .governance import enforce_postflight, install_governance
from .learning import add_lesson, postflight, preflight
from .orphan_adapter import run_orphan_radar
from .proposals import (
    ProposalEngineOption,
    load_proposal_reviews,
    run_proposal_engines,
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


@recommend_app.command("proposal-calibration-evidence")
def recommend_proposal_calibration_evidence(
    hub: Optional[Path] = typer.Option(None),
    review_file: Optional[Path] = typer.Option(None, "--review-file"),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    """Write tracked-ready roadmap evidence only after proposal calibration review is complete."""
    cfg = _cfg(hub=hub)
    path = review_file or cfg.repo_root / "processed" / "proposals" / "proposal_review_template.jsonl"
    if not path.is_absolute():
        path = cfg.repo_root / path
    reviews = load_proposal_reviews(path)
    try:
        summary, evidence_path = write_proposal_calibration_evidence(
            cfg.repo_root, reviews, path, output
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
