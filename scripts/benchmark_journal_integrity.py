#!/usr/bin/env python3
"""Benchmark journal integrity workers without exposing file contents or paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

from digital_asset_directory.journal import _checkpoint_file_index_integrity


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _normalized_digest(result: dict[str, Any]) -> str:
    normalized = {
        key: value
        for key, value in result.items()
        if key not in {"verification_backend", "verification_worker_count"}
    }
    payload = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal-repo", type=Path, required=True)
    parser.add_argument("--workers", default="1,2,4")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    workers = [int(value) for value in args.workers.split(",")]
    if not workers or any(value < 1 for value in workers):
        parser.error("--workers must contain positive integers")

    repo = args.journal_repo.resolve()
    if _git(repo, "status", "--porcelain"):
        raise SystemExit("journal worktree must be clean")
    head_before = _git(repo, "rev-parse", "HEAD")
    manifest = json.loads(
        (repo / "journal_checkpoint_manifest.json").read_text(encoding="utf-8")
    )
    runs: list[dict[str, Any]] = []
    digests: set[str] = set()
    for worker_count in workers:
        timings: list[float] = []
        result: dict[str, Any] = {}
        for _ in range(args.repeats):
            started = time.perf_counter()
            result = _checkpoint_file_index_integrity(
                repo, manifest, max_workers=worker_count
            )
            timings.append(time.perf_counter() - started)
        digest = _normalized_digest(result)
        digests.add(digest)
        runs.append(
            {
                "workers": worker_count,
                "repeat_count": len(timings),
                "median_seconds": round(statistics.median(timings), 3),
                "min_seconds": round(min(timings), 3),
                "max_seconds": round(max(timings), 3),
                "indexed_file_count": result.get("indexed_file_count"),
                "error_count": len(result.get("errors", [])),
                "result_digest": digest,
            }
        )
    head_after = _git(repo, "rev-parse", "HEAD")
    clean_after = not bool(_git(repo, "status", "--porcelain"))
    parity = len(digests) == 1
    report = {
        "schema_version": "dad.journal.integrity_benchmark.v1",
        "parity": parity,
        "head_unchanged": head_before == head_after,
        "worktree_clean_after": clean_after,
        "runs": runs,
        "privacy": "counts, durations, and normalized result digests only",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if parity and head_before == head_after and clean_after else 1


if __name__ == "__main__":
    raise SystemExit(main())
