from __future__ import annotations

from pathlib import Path

from digital_asset_directory.learning import recommended_review_lanes

ROOT = Path(__file__).resolve().parents[1]


def test_cross_vendor_review_lane_is_listed_for_material_work() -> None:
    lanes = recommended_review_lanes("material architecture and schema change")
    by_id = {lane["lane_id"]: lane for lane in lanes}
    assert "review-lane:cross-vendor-review" in by_id
    lane = by_id["review-lane:cross-vendor-review"]
    assert lane["mode"] == "checklist_if_useful"
    assert "yes|no|why" in lane["purpose"]
    assert "docs/CROSS_VENDOR_REVIEW_POLICY.md" in lane["required_for"]
    assert "bot-install" in lane["capture"]


def test_cross_vendor_policy_and_pr_template_exist() -> None:
    policy = (ROOT / "docs/CROSS_VENDOR_REVIEW_POLICY.md").read_text(encoding="utf-8")
    template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    assert "cross-vendor review: yes | no | why" in policy
    assert "Human-owned settings" in policy
    assert "Codex GitHub connector" in policy
    assert "cross-vendor review: yes | no | why" in template
    assert "docs/CROSS_VENDOR_REVIEW_POLICY.md" in template
