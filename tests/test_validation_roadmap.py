from pathlib import Path

from digital_asset_directory.roadmap import check_roadmap
from digital_asset_directory.validation import validate_repo

ROOT = Path(__file__).resolve().parents[1]


def test_repo_contracts_validate():
    result = validate_repo(ROOT)
    assert result["valid"], result["errors"]


def test_seed_roadmap_file_gate_is_complete():
    result = check_roadmap(ROOT, update=False)
    assert result["phases"]["phase-0-seed"]["computed_status"] == "complete"
