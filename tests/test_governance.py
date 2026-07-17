from pathlib import Path
import shutil
import subprocess

import pytest

from digital_asset_directory.governance import (
    BEGIN,
    enforce_postflight,
    install_governance,
    scaffold_new_repo,
)
from digital_asset_directory.learning import preflight, postflight

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[1]


def test_downstream_install_is_idempotent_and_enforces_open_session(tmp_path: Path):
    hub = tmp_path / "hub"
    (hub / "scripts").mkdir(parents=True)
    (hub / "state" / "agent_sessions").mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    install_governance(target, hub)
    install_governance(target, hub)
    agents_text = (target / "AGENTS.md").read_text()
    assert agents_text.count(BEGIN) == 1
    assert "load-bearing decisions" in agents_text
    assert "fresh-eyes review" in agents_text
    assert "branch/PR status" in agents_text
    assert "escalation date" in agents_text
    assert "~/.dad/bin/asset-dir" in agents_text
    assert "~/.dad/bin/asset-dir.ps1" in agents_text
    assert "PYTHONPATH=src python -m digital_asset_directory.cli" in agents_text
    assert "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli" in agents_text
    assert (
        'PYTHONPATH=src python -m digital_asset_directory.cli agent preflight --repo . '
        '--agent <agent-id> --task "<task>"'
    ) in agents_text
    assert (
        "$env:PYTHONPATH='src'; python -m digital_asset_directory.cli agent preflight "
        '--repo . --agent <agent-id> --task "<task>"'
    ) in agents_text
    assert agents_text.index("~/.dad/bin/asset-dir") < agents_text.index(
        "PYTHONPATH=src python -m digital_asset_directory.cli"
    )
    assert "A missing CLI does not relax local fail-closed boundaries." in agents_text
    assert "optional adapters" in agents_text
    assert "must not become the sole authority" in agents_text
    session = preflight(hub, target, hub / "state" / "catalog.sqlite3", "codex", "change")
    ok, _ = enforce_postflight(hub, target)
    assert not ok
    postflight(hub, hub / "state" / "catalog.sqlite3", session["session_id"], "done", lessons=["x"])
    ok, _ = enforce_postflight(hub, target)
    assert ok


def test_scaffold_new_repo_wires_starter_files_and_governance(tmp_path: Path):
    hub = tmp_path / "hub"
    (hub / "scripts").mkdir(parents=True)
    template = hub / "templates" / "ci-module-boundary" / "monorepo"
    template.mkdir(parents=True)
    shutil.copy(
        ROOT / "templates" / "ci-module-boundary" / "monorepo" / "module-boundaries.yaml",
        template / "module-boundaries.yaml",
    )
    shutil.copy(ROOT / "templates" / "ci-module-boundary" / "ADOPTION.md", template.parent / "ADOPTION.md")
    (hub / "schemas").mkdir()
    shutil.copy(
        ROOT / "schemas" / "ci-module-boundary.schema.json",
        hub / "schemas" / "ci-module-boundary.schema.json",
    )
    target = tmp_path / "fresh"
    changed = scaffold_new_repo(target, hub, name="Fresh Project")
    assert (target / "README.md").exists()
    assert (target / ".gitignore").exists()
    assert BEGIN in (target / "AGENTS.md").read_text(encoding="utf-8")
    config_text = (target / ".digital-asset-directory.yml").read_text(encoding="utf-8")
    assert "hub_path" in config_text
    assert "load_bearing_decision_review" in config_text
    assert "mailbox_path" in config_text
    assert (target / ".digital-asset" / "mail" / "README.md").exists()
    assert (target / ".digital-asset" / "mail" / ".gitignore").exists()
    assert (target / ".digital-asset" / "mail" / "inbox.jsonl").exists()
    assert (target / ".githooks" / "pre-push").exists()
    manifest = target / ".ci" / "module-boundaries.candidate.yaml"
    assert manifest.exists()
    assert "repository_id: fresh-project" in manifest.read_text(encoding="utf-8")
    assert not (target / ".ci" / "module-boundaries.yaml").exists()
    assert (target / ".ci" / "ADOPTION.md").exists()
    assert (target / "schemas" / "ci-module-boundary.schema.json").exists()
    assert any("README.md" in str(path) for path in changed)


def test_downstream_governed_change_requires_local_portability_adoption(tmp_path: Path):
    target = tmp_path / "downstream"
    governed = target / "assets/agent-skills/new-skill/SKILL.md"
    governed.parent.mkdir(parents=True)
    governed.write_text("# Candidate", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
    ok, message = enforce_postflight(ROOT, target)
    assert ok is False
    assert "reviewed local portability disposition" in message


def test_enrolled_downstream_code_change_fails_closed_without_local_path_policy(
    tmp_path: Path,
):
    target = tmp_path / "downstream"
    marker = target / ".digital-asset/dad-integration.json"
    source = target / "src/reusable/library.py"
    marker.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")
    source.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
    ok, message = enforce_postflight(ROOT, target)
    assert ok is False
    assert "reviewed local portability registry/path policy" in message
