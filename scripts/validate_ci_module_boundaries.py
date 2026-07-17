from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import jsonschema

from digital_asset_directory.ci_module_boundaries import (
    build_metadata_only_adoption_audit,
    evaluate_changes,
    load_manifest,
    parse_changes,
    validate_manifest,
)
from digital_asset_directory.ci_module_boundary_github import validate_github_workflows


def _print(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _validate_schema(repo: Path, manifest: dict) -> None:
    schema_path = repo / "schemas" / "ci-module-boundary.schema.json"
    if not schema_path.exists():
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "ci-module-boundary.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)


def _repo_path(repo: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repo / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and evaluate declared CI module boundaries.")
    parser.add_argument("--repo", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate")
    validate.add_argument("--manifest", type=Path, default=Path(".ci/module-boundaries.yaml"))
    validate.add_argument("--base-manifest", type=Path)
    validate.add_argument("--provider", choices=["github-actions"])
    validate.add_argument(
        "--observed-dependency",
        action="append",
        default=[],
        metavar="UPSTREAM:DOWNSTREAM",
    )

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--manifest", type=Path, default=Path(".ci/module-boundaries.yaml"))
    evaluate.add_argument("--event", default="pull_request")
    evaluate.add_argument("--changed", action="append", default=[])
    evaluate.add_argument("--changes-file", type=Path)

    audit = sub.add_parser("audit-enrolled")
    audit.add_argument("--output", type=Path)

    fixtures = sub.add_parser("fixtures")
    fixtures.add_argument(
        "--cases",
        type=Path,
        default=Path("assets/coding-harnesses/ci-module-boundary-governance/tests-or-evals/scenarios.yaml"),
    )
    return _run(parser.parse_args())


def _run(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    try:
        if args.command == "validate":
            manifest_path = _repo_path(repo, args.manifest)
            manifest = load_manifest(manifest_path)
            _validate_schema(repo, manifest)
            base = load_manifest(_repo_path(repo, args.base_manifest)) if args.base_manifest else None
            observed = []
            for value in args.observed_dependency:
                upstream, separator, downstream = value.partition(":")
                if not separator:
                    raise ValueError(f"Observed dependency must be UPSTREAM:DOWNSTREAM: {value}")
                observed.append((upstream, downstream))
            result = validate_manifest(
                manifest,
                base_manifest=base,
                observed_dependencies=observed if args.observed_dependency else None,
            )
            workflow_diagnostics = (
                validate_github_workflows(repo, manifest)
                if args.provider == "github-actions"
                else []
            )
            if workflow_diagnostics:
                result["diagnostics"].extend(workflow_diagnostics)
                result["summary"]["errors"] += sum(
                    item["severity"] == "error" for item in workflow_diagnostics
                )
                result["summary"]["warnings"] += sum(
                    item["severity"] == "warning" for item in workflow_diagnostics
                )
                if any(item["severity"] == "error" for item in workflow_diagnostics):
                    result["status"] = "invalid"
        elif args.command == "evaluate":
            manifest = load_manifest(_repo_path(repo, args.manifest))
            lines = list(args.changed)
            if args.changes_file:
                lines.extend(_repo_path(repo, args.changes_file).read_text(encoding="utf-8").splitlines())
            result = evaluate_changes(manifest, parse_changes(lines), event=args.event)
        elif args.command == "audit-enrolled":
            result = build_metadata_only_adoption_audit(repo)
            if args.output:
                raise ValueError("Audit output files are review artifacts; redirect stdout or add them by reviewed patch.")
        else:
            cases_path = _repo_path(repo, args.cases)
            cases = load_manifest(cases_path)
            failures = []
            results = []
            for case in cases["cases"]:
                manifest = load_manifest((cases_path.parent / case.get("manifest", "../examples/module-boundaries.yaml")).resolve())
                if case["operation"] == "evaluate":
                    actual = evaluate_changes(
                        manifest,
                        parse_changes(case.get("changes", [])),
                        event=case.get("event", "pull_request"),
                    )
                    expected = case["expect"]
                    passed = all(actual.get(key) == value for key, value in expected.items())
                else:
                    base = load_manifest((cases_path.parent / case["base_manifest"]).resolve()) if case.get("base_manifest") else None
                    observed = [tuple(item) for item in case.get("observed_dependencies", [])]
                    actual = validate_manifest(
                        manifest,
                        base_manifest=base,
                        observed_dependencies=observed if "observed_dependencies" in case else None,
                    )
                    expected_codes = set(case.get("expect_codes", []))
                    actual_codes = {item["code"] for item in actual["diagnostics"] if item["severity"] == "error"}
                    passed = actual["status"] == case["expect_status"] and expected_codes.issubset(actual_codes)
                results.append({"case_id": case["case_id"], "passed": passed})
                if not passed:
                    failures.append({"case_id": case["case_id"], "actual": actual})
            result = {
                "status": "passed" if not failures else "failed",
                "case_count": len(results),
                "passed_count": sum(item["passed"] for item in results),
                "results": results,
                "failures": failures,
            }
        _print(result)
        return 0 if result.get("status") in {"valid", "ok", "passed"} else 1
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        _print({"status": "invalid", "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
