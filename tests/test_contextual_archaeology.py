from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from digital_asset_directory.archaeology import (
    append_repo_learning_event,
    build_root_cause_lessons,
    build_worktree_attempts,
    infer_context_tags,
    install_repo_learning_loop,
    run_archaeology,
    write_archaeology_outputs,
    write_root_cause_lesson_outputs,
)
from digital_asset_directory.config import LocalSource
from digital_asset_directory.models import AssetRecord, ContextTagRecord, CounterfactualLessonRecord

pytestmark = pytest.mark.integration


ROOT = Path(__file__).resolve().parents[1]


def make_asset(
    asset_id: str,
    *,
    title: str,
    logical_path: str,
    asset_type: str = "document",
    text: str = "",
    parent_asset_id: str | None = "dad:asset:repo",
) -> AssetRecord:
    return AssetRecord(
        asset_id=asset_id,
        revision_id=f"dad:revision:{asset_id}",
        source_id="local",
        parent_asset_id=parent_asset_id,
        source_kind="local",
        asset_type=asset_type,
        title=title,
        description=text[:200],
        logical_path=logical_path,
        content_hash=asset_id,
        metadata_fingerprint=f"metadata:{asset_id}",
        first_seen_at="2026-01-01T00:00:00+00:00",
        last_seen_at="2026-01-01T00:00:00+00:00",
        tags=[],
        capabilities=[],
        needs=[],
        outcomes=[],
        lifecycle_state="active",
        freshness_status="current",
        sensitivity="internal",
        trust_zone="source_owned",
        value_score=50,
        value_components={},
        metadata={
            "excerpt": text,
            "chunk_text": text,
            "text_tokens": sorted(text.lower().split()),
        },
    )


def run_git(repo: Path, *args: str) -> None:
    try:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        pytest.skip("git is not available")


def test_context_tag_registry_has_unique_valid_ids():
    payload = json.loads((ROOT / "registry" / "context-tag-registry.json").read_text())
    ids = [tag["context_tag_id"] for tag in payload["tags"]]

    assert len(ids) == len(set(ids))
    assert {
        "late_stabilizer",
        "repeated_failure",
        "counterfactual_sequence",
        "score_methodology",
        "calibration",
    }.issubset(ids)
    for tag in payload["tags"]:
        ContextTagRecord.model_validate(tag)


def test_context_bound_lesson_requires_context_and_danger_warning():
    with pytest.raises(ValidationError):
        CounterfactualLessonRecord(
            lesson_candidate_id="dad:lesson-candidate:test",
            lesson_candidate="Add validation before promotion.",
            applies_when=["Schema-sensitive work"],
            counterfactual_better_order=["Schema first", "Implementation second"],
            evidence_asset_ids=["dad:asset:a"],
            source_events=["dad:event:a"],
            context_tags=["schema_contract"],
            authority_boundary="Generated candidate only.",
            generated_at="2026-01-01T00:00:00+00:00",
            scan_id="dad:scan:test",
        )


def test_worktree_and_temp_attempts_are_detected_as_noisy_candidates():
    assets = [
        make_asset(
            "dad:asset:worktree",
            title="Worktree Test",
            logical_path="local/_codex_worktrees/feature-t123/tests/test_route.py",
            text="failure before validator",
        ),
        make_asset(
            "dad:asset:temp",
            title="Temp Fixture",
            logical_path="local/.pytest-tmp-root/pytest-0/popen-gw0/repo/test_app.py",
            text="synthetic fixture failure",
        ),
    ]

    attempts = build_worktree_attempts(assets, scan_id="dad:scan:test")
    by_kind = {attempt.attempt_kind: attempt for attempt in attempts}

    assert {"worktree", "temp"} == set(by_kind)
    assert by_kind["worktree"].review_status == "generated_candidate"
    assert "temp_fixture_noise" in by_kind["temp"].context_tags


def test_repeated_failure_and_late_stabilizer_produce_context_bound_lesson(tmp_path: Path):
    assets = [
        make_asset(
            "dad:asset:repo",
            title="Synthetic Repo",
            logical_path="local/repo",
            asset_type="repository",
            text="repository",
            parent_asset_id=None,
        ),
        make_asset(
            "dad:asset:failure",
            title="Failure Notes",
            logical_path="local/repo/docs/failure.md",
            text="TODO repeated failure regression missing gate before validation",
        ),
        make_asset(
            "dad:asset:validator",
            title="Schema Validator Test Gate",
            logical_path="local/repo/tests/test_validator.py",
            asset_type="test",
            text="validator schema review gate stabilizer",
        ),
    ]

    result = run_archaeology(
        assets,
        [LocalSource(id="local", path=tmp_path, path_alias="local")],
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    root_result = build_root_cause_lessons(
        result,
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert any(pattern.pattern_type == "late_stabilizer" for pattern in result.change_patterns)
    assert len(root_result.counterfactual_lessons) == 1
    lesson = root_result.counterfactual_lessons[0]
    assert lesson.review_status == "generated_candidate"
    assert lesson.applies_when
    assert lesson.does_not_apply_when
    assert lesson.danger_if_misapplied
    assert "late_stabilizer" in lesson.context_tags


def test_repo_learning_loop_install_and_event_are_files_only(tmp_path: Path):
    changed = install_repo_learning_loop(tmp_path, mode="files-only")
    record = append_repo_learning_event(
        tmp_path,
        stage="after_work",
        task="Use a generated asset safely",
        agent="test-agent",
        context_tags=["schema_contract"],
        assets_used=["dad:asset:a"],
        expected_value="Expected schema reuse.",
        actual_value="$(malicious-looking text is stored as data only)",
        evidence=["unit test"],
        created_at="2026-01-01T00:00:00+00:00",
    )

    created = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*") if path.is_file()}
    assert created == {
        ".digital-asset-directory/learning/README.md",
        ".digital-asset-directory/learning/context-tags.yaml",
        ".digital-asset-directory/learning/events.jsonl",
    }
    assert all(".git/hooks" not in str(path) for path in changed)
    assert record.review_status == "generated_candidate"
    readme_text = (tmp_path / ".digital-asset-directory" / "learning" / "README.md").read_text()
    assert "methodology version" in readme_text
    assert "load-bearing decisions" in readme_text
    assert "observable decision traces" in readme_text
    event_text = (tmp_path / ".digital-asset-directory" / "learning" / "events.jsonl").read_text()
    assert "malicious-looking text is stored as data only" in event_text


def test_git_history_produces_timeline_events_without_network(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init")
    run_git(repo, "config", "user.email", "test@example.invalid")
    run_git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("failure missing gate\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "add failure note before validator")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate.py").write_text("def test_gate(): assert True\n", encoding="utf-8")
    run_git(repo, "add", "tests/test_gate.py")
    run_git(repo, "commit", "-m", "add schema validator gate")

    assets = [
        make_asset(
            "dad:asset:repo",
            title="Synthetic Repo",
            logical_path="local/repo",
            asset_type="repository",
            parent_asset_id=None,
        )
    ]
    result = run_archaeology(
        assets,
        [LocalSource(id="local", path=tmp_path, path_alias="local")],
        scan_id="dad:scan:test",
        max_repos=1,
        max_commits=10,
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert len(result.timeline_events) == 2
    assert any("validator" in event.summary for event in result.timeline_events)
    assert all(event.review_status == "generated_candidate" for event in result.timeline_events)


def test_archaeology_writers_create_generated_outputs(tmp_path: Path):
    assets = [
        make_asset(
            "dad:asset:failure",
            title="Failure Notes",
            logical_path="local/docs/failure.md",
            text="TODO repeated failure regression",
        ),
        make_asset(
            "dad:asset:validator",
            title="Schema Validator",
            logical_path="local/tests/test_validator.py",
            asset_type="test",
            text="schema validator test gate",
        ),
    ]
    local_sources = [LocalSource(id="local", path=tmp_path, path_alias="local")]

    archaeology = write_archaeology_outputs(
        tmp_path,
        assets,
        local_sources,
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    root_causes = write_root_cause_lesson_outputs(
        tmp_path,
        assets,
        local_sources,
        scan_id="dad:scan:test",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert Path(archaeology["outputs"]["report"]).exists()
    assert Path(root_causes["outputs"]["counterfactual_lessons"]).exists()
    assert Path(root_causes["outputs"]["context_tag_coverage"]).exists()


def test_infer_context_tags_stays_domain_general():
    tags = infer_context_tags("legal contract route chunk schema validator review gate")

    assert {"route_isolation", "chunking", "schema_contract", "human_gate"}.issubset(tags)
