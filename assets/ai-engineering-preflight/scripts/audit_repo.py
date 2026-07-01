#!/usr/bin/env python3
"""Audit a repo for AI preflight readiness.

This script reads only. It does not modify files.
"""
from __future__ import annotations

import argparse
from pathlib import Path

AGENT_FILES = [
    'AGENTS.md',
    'CLAUDE.md',
    'GEMINI.md',
    '.github/copilot-instructions.md',
    '.cursor/rules/ai-engineering-preflight.mdc',
    'docs/ai-preflight/PYTHON_PREFLIGHT.md',
    'docs/ai-preflight/RUST_PREFLIGHT.md',
]


def detect(repo: Path) -> str:
    has_rust = (repo / 'Cargo.toml').exists() or any(repo.rglob('*.rs'))
    has_python = (
        (repo / 'pyproject.toml').exists()
        or (repo / 'setup.py').exists()
        or (repo / 'requirements.txt').exists()
        or any(repo.rglob('*.py'))
    )
    if has_python and has_rust:
        return 'mixed'
    if has_rust:
        return 'rust'
    if has_python:
        return 'python'
    return 'common'


def count_files(repo: Path, pattern: str) -> int:
    return sum(1 for _ in repo.rglob(pattern))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not repo.exists():
        raise SystemExit(f'Repo path does not exist: {repo}')

    profile = detect(repo)
    print(f'# AI Preflight Audit: {repo.name}\n')
    print(f'- repo: `{repo}`')
    print(f'- recommended profile: `{profile}`')
    print(f'- Python files: {count_files(repo, "*.py")}')
    print(f'- Rust files: {count_files(repo, "*.rs")}')
    print('\n## Existing agent/preflight files')
    for rel in AGENT_FILES:
        path = repo / rel
        print(f'- [{"x" if path.exists() else " "}] `{rel}`')

    print('\n## Potential long files')
    candidates = []
    for pattern in ('*.py', '*.rs'):
        for path in repo.rglob(pattern):
            try:
                line_count = len(path.read_text(encoding='utf-8', errors='ignore').splitlines())
            except OSError:
                continue
            if line_count >= 400:
                candidates.append((line_count, path.relative_to(repo)))
    for line_count, rel in sorted(candidates, reverse=True)[:20]:
        print(f'- `{rel}` — {line_count} lines')
    if not candidates:
        print('- none found at >=400 lines')

    print('\n## Suggested deployment command')
    print('```bash')
    print('python /path/to/assets/ai-engineering-preflight/scripts/deploy_to_repo.py \\')
    print(f'  --repo {repo} \\')
    print(f'  --profile {profile} \\')
    print('  --apply')
    print('```')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
