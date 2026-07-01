from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def route_score(route: dict[str, Any], *, task: str, language: str, risk: str) -> int:
    text = " ".join(
        [
            route["task_context"],
            " ".join(route["match"]["task_types"]),
            " ".join(route["match"]["repo_types"]),
            " ".join(route["match"]["risk_tags"]),
        ]
    ).lower()
    task_terms = [part for part in task.lower().replace("-", " ").split() if len(part) > 2]
    score = sum(1 for term in task_terms if term in text)
    if language and language in route["match"]["languages"]:
        score += 4
    if risk and risk in route["match"]["risk_tags"]:
        score += 3
    return score


def main() -> int:
    parser = argparse.ArgumentParser(description="Suggest DAD coding tactics for a task.")
    parser.add_argument("--task", required=True, help="Short task description.")
    parser.add_argument("--language", default="unknown", help="python, rust, mixed, or agent-instruction.")
    parser.add_argument("--risk", default="default", help="Optional risk or context tag.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum tactics to show.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of readable text.")
    args = parser.parse_args()

    router = load_json("registry/preflight-profile-router.json")
    tactics = {item["tactic_id"]: item for item in load_json("registry/coding-tactics-radar.json")["tactics"]}
    routes = sorted(
        router["routes"],
        key=lambda route: route_score(
            route,
            task=args.task,
            language=args.language,
            risk=args.risk,
        ),
        reverse=True,
    )
    selected_routes = [route for route in routes if route_score(
        route,
        task=args.task,
        language=args.language,
        risk=args.risk,
    ) > 0][:3]
    if not selected_routes:
        selected_routes = [route for route in routes if route["route_id"] == router["default_route"]]

    seen: set[str] = set()
    selected_tactics: list[dict[str, Any]] = []
    for route in selected_routes:
        for tactic_id in route["recommended_tactic_ids"]:
            tactic = tactics[tactic_id]
            language_ok = tactic["language"] in {args.language, "agent-instruction"}
            if args.language in {"mixed", "unknown"}:
                language_ok = True
            if tactic_id not in seen and language_ok:
                selected_tactics.append(tactic)
                seen.add(tactic_id)
            if len(selected_tactics) >= args.limit:
                break

    result = {
        "task": args.task,
        "language": args.language,
        "risk": args.risk,
        "routes": [
            {
                "route_id": route["route_id"],
                "task_context": route["task_context"],
                "required_preflight_profiles": route["required_preflight_profiles"],
                "validation_expectations": route["validation_expectations"],
                "stop_conditions": route["stop_conditions"],
            }
            for route in selected_routes
        ],
        "tactics": [
            {
                "tactic_id": tactic["tactic_id"],
                "name": tactic["name"],
                "why_it_applies": tactic["applies_when"],
                "why_it_may_not_apply": tactic["does_not_apply_when"],
                "risk_if_misapplied": tactic["danger_if_misapplied"],
                "minimal_example": tactic["minimal_code_example_path"],
                "verification": tactic["verification_commands"],
                "review_status": tactic["review_status"],
            }
            for tactic in selected_tactics
        ],
    }

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"Task: {args.task}")
    print(f"Language: {args.language}")
    print("")
    print("Routes:")
    for route in result["routes"]:
        print(f"- {route['route_id']}: {route['task_context']}")
        print(f"  Required profiles: {', '.join(route['required_preflight_profiles'])}")
        print(f"  Validation: {'; '.join(route['validation_expectations'])}")
    print("")
    print("Tactics:")
    for tactic in result["tactics"]:
        print(f"- {tactic['tactic_id']}: {tactic['name']}")
        print(f"  Applies: {'; '.join(tactic['why_it_applies'])}")
        print(f"  May not apply: {'; '.join(tactic['why_it_may_not_apply'])}")
        print(f"  Risk: {tactic['risk_if_misapplied']}")
        print(f"  Example: {tactic['minimal_example']}")
        print(f"  Verify: {'; '.join(tactic['verification'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
