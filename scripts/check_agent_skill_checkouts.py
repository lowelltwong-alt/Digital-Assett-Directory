from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema.validators import validator_for

from render_agent_skill_checkout import load_registry


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKOUT_LOG = Path("processed/skills/checkouts.jsonl")
CHECKOUT_SCHEMA_REL = "schemas/agent-skill-checkout-record.schema.json"


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def validator_for_schema(rel: str):
    schema = load_json(rel)
    validator_cls = validator_for(schema)
    validator_cls.check_schema(schema)
    return validator_cls(schema)


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    if not path.exists():
        return records, malformed
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            malformed.append({"line": line_number, "error": str(exc)})
            continue
        records.append(item)
    return records, malformed


def assess_checkout(record: dict[str, Any], skills_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    skill_id = record["skill_id"]
    skill = skills_by_id.get(skill_id)
    if not skill:
        return {
            "checkout_id": record["checkout_id"],
            "repo_id": record["repo_id"],
            "skill_id": skill_id,
            "status": "unknown_skill",
            "recommended_notice": "manual_review",
        }
    if skill["status"] in {"deprecated", "retired", "replaced"}:
        return {
            "checkout_id": record["checkout_id"],
            "repo_id": record["repo_id"],
            "skill_id": skill_id,
            "checked_out_version": record["checked_out_version"],
            "current_version": skill["version"],
            "status": f"skill_{skill['status']}",
            "recommended_notice": "retirement",
            "replacement_skill_id": skill["lifecycle"].get("replacement_skill_id", ""),
        }
    if record["checked_out_version"] != skill["version"]:
        return {
            "checkout_id": record["checkout_id"],
            "repo_id": record["repo_id"],
            "skill_id": skill_id,
            "checked_out_version": record["checked_out_version"],
            "current_version": skill["version"],
            "status": "update_available",
            "recommended_notice": "update",
        }
    return {
        "checkout_id": record["checkout_id"],
        "repo_id": record["repo_id"],
        "skill_id": skill_id,
        "checked_out_version": record["checked_out_version"],
        "current_version": skill["version"],
        "status": "current",
        "recommended_notice": "",
    }


def build_report(checkout_log: Path, repo: str | None = None) -> dict[str, Any]:
    registry = load_registry()
    skills_by_id = {skill["skill_id"]: skill for skill in registry.get("skills", [])}
    validator = validator_for_schema(CHECKOUT_SCHEMA_REL)
    records, malformed = iter_jsonl(checkout_log)
    try:
        checkout_log_ref = str(checkout_log.resolve().relative_to(ROOT))
    except ValueError:
        checkout_log_ref = "<external-checkout-log>"

    valid_records: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        try:
            validator.validate(record)
        except Exception as exc:
            validation_errors.append({"record": index, "error": str(exc)})
            continue
        if repo and repo not in {record["repo_id"], record["repo_alias"]}:
            continue
        if record["review_status"] == "archived":
            continue
        valid_records.append(record)

    assessments = [assess_checkout(record, skills_by_id) for record in valid_records]
    notices = [row for row in assessments if row["recommended_notice"]]
    return {
        "schema_version": "0.1.0",
        "checkout_log": checkout_log_ref,
        "registry": "registry/agent-skill-library.json",
        "repo_filter": repo or "",
        "records_checked": len(valid_records),
        "malformed_rows": malformed,
        "validation_errors": validation_errors,
        "notice_candidates": notices,
        "assessments": assessments,
        "authority_boundary": (
            "This report identifies candidate skill update, retirement, or manual-review notices. "
            "It does not deliver mail or mutate target repos."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DAD agent skill checkout freshness.")
    parser.add_argument("--checkout-log", type=Path, default=ROOT / DEFAULT_CHECKOUT_LOG)
    parser.add_argument("--repo", default="", help="Optional repo_id or repo_alias filter")
    parser.add_argument("--output", type=Path, help="Optional JSON report output")
    args = parser.parse_args()

    report = build_report(args.checkout_log, repo=args.repo or None)
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)
    return 1 if report["malformed_rows"] or report["validation_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
