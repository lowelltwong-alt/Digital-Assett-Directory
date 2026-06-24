from pathlib import Path
import json
import yaml

from digital_asset_directory.catalog import run_scan
from digital_asset_directory.config import load_config


def test_local_catalog_pipeline_writes_outputs(tmp_path: Path):
    hub = tmp_path / "hub"
    hub.mkdir()
    for rel in [
        "config",
        "processed/catalog",
        "processed/graph",
        "processed/alerts",
        "processed/reports",
        "state",
    ]:
        (hub / rel).mkdir(parents=True, exist_ok=True)
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    (source / "README.md").write_text(
        "# Asset\nknowledge graph learning loop evaluation", encoding="utf-8"
    )
    (hub / "config" / "scoring.yaml").write_text(
        "weights:\n  reuse_potential: 1.0\n", encoding="utf-8"
    )
    cfg = {
        "project": {"database": "state/catalog.sqlite3"},
        "sources": {
            "local": [
                {
                    "id": "local",
                    "path": str(source),
                    "path_alias": "source",
                    "exclude": ["**/.git/**"],
                }
            ],
            "github": [],
        },
        "settings": {"read_only": True},
    }
    (hub / "config" / "sources.local.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    app_cfg = load_config(repo_root=hub)
    summary = run_scan(app_cfg, local=True, github=False)
    assert summary["asset_count"] >= 2
    assert summary["raw_observation_files"]
    raw_path = hub / summary["raw_observation_files"][0]
    assert raw_path.exists()
    raw_record = json.loads(raw_path.read_text(encoding="utf-8").splitlines()[0])
    assert raw_record["scan_id"] == summary["scan_id"]
    assert raw_record["observation_type"] == "normalized_asset_candidate"
    assert raw_record["authority_note"]
    assert (hub / "processed" / "catalog" / "assets.jsonl").exists()
    assert (hub / "processed" / "graph" / "graph.json").exists()
    audit_events = "\n".join(
        path.read_text(encoding="utf-8") for path in (hub / "audit" / "events").glob("*.jsonl")
    )
    assert "scan_started" in audit_events
    assert "scan_completed" in audit_events
    assert summary["source_files_mutated"] is False
