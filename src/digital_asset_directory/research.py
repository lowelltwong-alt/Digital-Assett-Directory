from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from .database import CatalogDB
from .radars import missing_need_counts
from .utils import utc_now, write_json, atomic_write_text


def research_missing_parts(
    repo_root: Path,
    database_path: Path,
    limit: int = 20,
    token_env: str = "GITHUB_TOKEN",
    *,
    enable_external: bool = False,
) -> dict[str, Any]:
    if not enable_external:
        return {
            "schema_version": "0.1.0",
            "created_at": utc_now(),
            "status": "blocked_external_research_not_enabled",
            "findings": [],
            "rules": [
                "Live GitHub research requires --enable-external.",
                "External research must record source terms, rate-limit posture, license, provenance, freshness, security, and compatibility review.",
                "Do not copy code automatically.",
            ],
        }
    with CatalogDB(database_path) as db:
        assets = db.assets()
    missing = missing_need_counts(assets)[:10]
    token = os.environ.get(token_env)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "digital-asset-directory/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    findings: list[dict[str, Any]] = []
    for need, count in missing:
        query = need.replace("_", " ")
        params: dict[str, str | int] = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(limit, 30),
        }
        response = requests.get(
            "https://api.github.com/search/repositories",
            params=params,
            headers=headers,
            timeout=30,
        )
        if response.status_code == 403:
            findings.append(
                {"need": need, "asset_count": count, "error": "GitHub rate limit or access denied"}
            )
            continue
        response.raise_for_status()
        candidates: list[dict[str, Any]] = []
        for item in response.json().get("items", []):
            candidates.append(
                {
                    "full_name": item["full_name"],
                    "url": item["html_url"],
                    "description": item.get("description"),
                    "stars": item.get("stargazers_count", 0),
                    "license": (item.get("license") or {}).get("spdx_id"),
                    "archived": item.get("archived", False),
                    "review_required": [
                        "license",
                        "security",
                        "maintenance",
                        "compatibility",
                        "authority boundary",
                    ],
                }
            )
        findings.append({"need": need, "asset_count": count, "candidates": candidates})
    report: dict[str, Any] = {
        "schema_version": "0.1.0",
        "created_at": utc_now(),
        "status": "candidate_research_only",
        "findings": findings,
        "rules": [
            "External repositories are suggestions, not approved dependencies.",
            "Review license, security, provenance, maintenance, and compatibility before reuse.",
            "Do not copy code automatically.",
        ],
    }
    stamp = report["created_at"].replace(":", "-")
    json_path = repo_root / "raw" / "research" / f"missing-parts-{stamp}.json"
    write_json(json_path, report)
    lines = [
        "# Missing-Part GitHub Research",
        "",
        f"Generated: {report['created_at']}",
        "",
        "> Candidate research only; no repository is approved or imported by this report.",
        "",
    ]
    for finding in findings:
        lines.append(f"## {finding['need']} ({finding['asset_count']} asset signals)")
        if finding.get("error"):
            lines.append(f"- Error: {finding['error']}")
        for item in finding.get("candidates", []):
            lines.append(
                f"- `{item['full_name']}` — stars: {item['stars']}; license: {item['license'] or 'unknown'}; {item['description'] or ''}"
            )
        lines.append("")
    md_path = repo_root / "processed" / "reports" / "missing_part_research.md"
    atomic_write_text(md_path, "\n".join(lines))
    return report
