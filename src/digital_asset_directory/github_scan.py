from __future__ import annotations

import base64
import fnmatch
import os
from typing import Any, Iterator
from urllib.parse import quote

import requests

from .config import GitHubSource, Settings
from .extractors import classify_asset, extract_bytes, freshness_status
from .ids import asset_id, revision_id
from .models import AssetRecord
from .scoring import score_asset
from .utils import sha256_bytes, utc_now

API = "https://api.github.com"


class GitHubReadOnlyClient:
    def __init__(self, token: str | None = None, timeout: int = 30) -> None:
        self.session = requests.Session()
        self.timeout = timeout
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "digital-asset-directory/0.1",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(f"{API}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[Any]:
        page = 1
        while True:
            payload = self.get(path, {**(params or {}), "per_page": 100, "page": page})
            if not payload:
                return
            yield from payload
            if len(payload) < 100:
                return
            page += 1


def _priority_match(path: str, patterns: list[str]) -> bool:
    lowered = path.lower()
    for pattern in patterns:
        p = pattern.lower()
        if fnmatch.fnmatch(lowered, p) or fnmatch.fnmatch(lowered, p.replace("**/", "*")):
            return True
        if p.endswith("/**") and lowered.startswith(p[:-3]):
            return True
    return False


def scan_github_source(
    source: GitHubSource, settings: Settings, scoring: dict, max_files: int | None = None
) -> list[AssetRecord]:
    token = os.environ.get(source.token_env)
    client = GitHubReadOnlyClient(token)
    if token:
        repos = list(
            client.paginate(
                "/user/repos",
                {"affiliation": "owner,collaborator,organization_member", "sort": "updated"},
            )
        )
        repos = [
            repo
            for repo in repos
            if repo.get("owner", {}).get("login", "").casefold() == source.owner.casefold()
        ]
    else:
        repos = list(client.paginate(f"/users/{quote(source.owner)}/repos", {"sort": "updated"}))
    now = utc_now()
    assets: list[AssetRecord] = []
    file_count = 0
    for repo in repos:
        if repo.get("archived") and not source.include_archived:
            continue
        if repo.get("private") and not source.include_private:
            continue
        full_name = repo["full_name"]
        logical_repo = f"github/{full_name}"
        identifier = asset_id(source.id, f"repository:{full_name}")
        repo_hash = str(repo.get("pushed_at") or repo.get("updated_at") or repo.get("id"))
        modified = repo.get("pushed_at") or repo.get("updated_at")
        record = AssetRecord(
            asset_id=identifier,
            revision_id=revision_id(identifier, sha256_bytes(repo_hash.encode())),
            source_id=source.id,
            source_kind="github",
            asset_type="repository",
            title=repo["name"],
            description=repo.get("description") or "GitHub repository",
            logical_path=logical_repo,
            uri=repo.get("html_url", ""),
            content_hash=sha256_bytes(repo_hash.encode()),
            size_bytes=int(repo.get("size", 0)) * 1024,
            modified_at=modified,
            first_seen_at=now,
            last_seen_at=now,
            tags=sorted(set(["repository", *(repo.get("topics") or [])])),
            capabilities=["catalog_assets"],
            needs=[],
            outcomes=["faster_builds", "higher_discovery"],
            entrypoints=[],
            lifecycle_state="archived" if repo.get("archived") else "active",
            freshness_status=freshness_status(
                modified, settings.stale_days_by_type.get("repository", settings.stale_days_default)
            ),
            sensitivity="internal" if repo.get("private") else "public",
            trust_zone="source_owned",
            confidence="high",
            metadata={
                "default_branch": repo.get("default_branch", "main"),
                "private": bool(repo.get("private")),
                "archived": bool(repo.get("archived")),
                "fork": bool(repo.get("fork")),
                "license": (repo.get("license") or {}).get("spdx_id"),
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "open_issues": repo.get("open_issues_count", 0),
            },
        )
        assets.append(score_asset(record, scoring))
        branch = repo.get("default_branch")
        if not branch or source.content_mode == "metadata":
            continue
        try:
            tree = client.get(
                f"/repos/{quote(full_name, safe='/')}/git/trees/{quote(branch)}", {"recursive": "1"}
            )
        except requests.HTTPError:
            continue
        for item in tree.get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item["path"]
            if source.content_mode == "priority" and not _priority_match(
                path, source.priority_patterns
            ):
                continue
            if int(item.get("size") or 0) > source.max_file_bytes:
                continue
            if max_files is not None and file_count >= max_files:
                return assets
            try:
                blob = client.get(f"/repos/{quote(full_name, safe='/')}/git/blobs/{item['sha']}")
                data = (
                    base64.b64decode(blob.get("content", ""))
                    if blob.get("encoding") == "base64"
                    else b""
                )
            except (requests.HTTPError, ValueError):
                continue
            logical = f"{logical_repo}/{path}"
            extracted = extract_bytes(logical, data, 5000, settings.redact_sensitive_excerpts)
            file_id = asset_id(source.id, logical)
            asset_type = classify_asset(logical)
            file_record = AssetRecord(
                asset_id=file_id,
                revision_id=revision_id(file_id, item["sha"]),
                source_id=source.id,
                parent_asset_id=identifier,
                source_kind="github",
                asset_type=asset_type,
                title=extracted["title"],
                description=extracted["description"],
                logical_path=logical,
                uri=f"https://github.com/{full_name}/blob/{branch}/{path}",
                content_hash=item["sha"],
                size_bytes=int(item.get("size") or len(data)),
                modified_at=modified,
                first_seen_at=now,
                last_seen_at=now,
                tags=extracted["tags"],
                capabilities=extracted["capabilities"],
                needs=extracted["needs"],
                outcomes=extracted["outcomes"],
                entrypoints=[path]
                if path in {"README.md", "AI_FRONT_DOOR.md", "AGENTS.md", "CLAUDE.md"}
                else [],
                lifecycle_state="discovered",
                freshness_status=freshness_status(
                    modified,
                    settings.stale_days_by_type.get(asset_type, settings.stale_days_default),
                ),
                sensitivity="internal" if repo.get("private") else "public",
                trust_zone="source_owned",
                confidence="high",
                metadata={
                    "repository": full_name,
                    "branch": branch,
                    "git_blob_sha": item["sha"],
                    "excerpt": extracted["excerpt"],
                    "text_tokens": extracted["text_tokens"],
                    "redaction_count": extracted["redaction_count"],
                },
            )
            assets.append(score_asset(file_record, scoring))
            file_count += 1
    return assets
