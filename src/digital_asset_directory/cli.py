from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .catalog import catalog_status, run_scan
from .config import load_config
from .context_pack import build_context_pack, write_context_pack
from .database import CatalogDB
from .governance import enforce_postflight, install_governance
from .learning import add_lesson, postflight, preflight
from .orphan_adapter import run_orphan_radar
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
